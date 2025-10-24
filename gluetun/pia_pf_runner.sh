#!/bin/sh
set -Eeuo pipefail

log(){ printf '%s %s\n' "$(date +'%F %T')" "$*"; }

GLUETUN_DIR=${GLUETUN_DIR:-/gluetun}
STATUS_FILE=${VPN_PORT_FORWARDING_STATUS_FILE:-/tmp/gluetun/forwarded_port}
QB_SCRIPT=${QB_SCRIPT:-$GLUETUN_DIR/update-qb.sh}
QB_PORT=${QBIT_WEBUI_PORT:-8090}
CERT=${CERT:-$GLUETUN_DIR/ca.rsa.4096.crt}
CFG=${CFG:-$GLUETUN_DIR/wireguard/wg0.conf}
SLEEP_KEEPALIVE=${SLEEP_KEEPALIVE:-900}
RETRY_MAX=${RETRY_MAX:-30}

mkdir -p "$(dirname "$STATUS_FILE")"

# 0) Đợi DNS/mạng sẵn sàng
i=0
until getent hosts serverlist.piaservers.net >/dev/null 2>&1; do
  i=$((i+1)); [ $i -gt 60 ] && break
  sleep 2
done

# 1) Lấy Endpoint từ wg0.conf
EP="$(awk -F'=' '/^Endpoint/ {gsub(/ /,""); print $2}' "$CFG" | head -n1)"
[ -n "$EP" ] || { log "ERROR: No Endpoint in $CFG"; sleep 10; exec "$0"; }
EP_HOST=${EP%:*}; EP_PORT=${EP##*:}

PF_HOSTNAME=${PF_HOSTNAME:-}
PF_GATEWAY=${PF_GATEWAY:-}

# 2) Tải CA nếu chưa có
if [ ! -s "$CERT" ]; then
  log "Downloading PIA CA..."
  wget -qO "$CERT" https://raw.githubusercontent.com/pia-foss/manual-connections/master/ca.rsa.4096.crt
fi

# 3) Hàm lấy token
get_token(){
  [ -n "${PIA_TOKEN:-}" ] && return 0
  [ -n "${PIA_USER:-}" ] && [ -n "${PIA_PASS:-}" ] || { log "Need PIA_USER/PIA_PASS or PIA_TOKEN"; sleep 30; exec "$0"; }
  PIA_TOKEN="$(curl -fsS --location --request POST \
    'https://www.privateinternetaccess.com/api/client/v2/token' \
    --form "username=$PIA_USER" --form "password=$PIA_PASS" | jq -r '.token')"
  [ -n "$PIA_TOKEN" ] || { log "ERROR: get token failed"; sleep 30; exec "$0"; }
}

# 4) Hàm xin chữ ký; echo: payload|signature|port|expires_at
request_signature(){
  host="$1"; gw="$2"
  curl -fsS -m 10 \
    --connect-to "$host::$gw:" \
    --cacert "$CERT" \
    -G --data-urlencode "token=$PIA_TOKEN" \
    "https://$host:19999/getSignature"
}

# 5) Tìm PF_HOSTNAME
pick_hostname(){
  # Nếu đã có PF_HOSTNAME -> thử luôn
  if [ -n "$PF_HOSTNAME" ]; then
    resp="$(request_signature "$PF_HOSTNAME" "$PF_GATEWAY" || true)"
    [ "$(echo "$resp" | jq -r '.status // empty')" = "OK" ] && { printf '%s|%s\n' "$PF_HOSTNAME" "$resp"; return 0; }
    log "Given PF_HOSTNAME=$PF_HOSTNAME not accepted; will auto-detect."
  fi

  # Chuẩn hóa PF_GATEWAY
  if [ -z "$PF_GATEWAY" ]; then
    case "$EP_HOST" in
      *[a-zA-Z]*) PF_GATEWAY="$(getent hosts "$EP_HOST" | awk '{print $1}' | head -n1 || true)";;
      *) PF_GATEWAY="$EP_HOST";;
    esac
  fi
  [ -n "$PF_GATEWAY" ] || { log "ERROR: cannot resolve gateway"; return 1; }

  # Tải serverlist (thử nhiều lần)
  sl=""
  for t in 1 2 3 5 8; do
    sl="$(curl -fsS https://serverlist.piaservers.net/vpninfo/servers/v6 | head -n1 || true)"
    [ -n "$sl" ] && break
    sleep "$t"
  done
  [ -n "$sl" ] || { log "WARN: cannot fetch serverlist; will brute-force later."; }

  # a) Map trực tiếp IP -> wg.cn
  if [ -n "$sl" ]; then
    host="$(printf '%s' "$sl" | jq -r --arg ip "$EP_HOST" \
      '.regions[] | .servers.wg[]? | select(.ip==$ip) | .cn' | head -n1)"
    if [ -n "$host" ]; then
      resp="$(request_signature "$host" "$PF_GATEWAY" || true)"
      [ "$(echo "$resp" | jq -r '.status // empty')" = "OK" ] && { printf '%s|%s\n' "$host" "$resp"; return 0; }
    fi
  fi

  # b) Brute-force: thử toàn bộ CN (wg + meta) với IP gateway
  if [ -n "$sl" ]; then
    printf '%s' "$sl" | jq -r '
      [.regions[].servers.wg[]?.cn, .regions[].servers.meta[]?.cn]
      | map(select(.!=null)) | unique[]' \
      | while IFS= read -r h; do
          resp="$(request_signature "$h" "$PF_GATEWAY" || true)"
          if [ "$(echo "$resp" | jq -r '.status // empty')" = "OK" ]; then
            printf '%s|%s\n' "$h" "$resp"
            exit 0
          fi
        done
  fi

  return 1
}

# 6) Vòng đời chính
get_token

# Lặp đến khi tìm được hostname hợp lệ
while :; do
  pick="$(pick_hostname || true)"
  if [ -n "$pick" ]; then
    PF_HOSTNAME="${pick%%|*}"; SIGJSON="${pick#*|}"
    break
  fi
  log "Auto-detect hostname failed; retrying in 30s..."
  sleep 30
done

payload="$(echo "$SIGJSON" | jq -r '.payload')"
signature="$(echo "$SIGJSON" | jq -r '.signature')"
port="$(echo "$payload" | base64 -d | jq -r '.port')"
expires_at="$(echo "$payload" | base64 -d | jq -r '.expires_at')"

echo "$port" > "$STATUS_FILE"
log "Forwarded port: $port via $PF_HOSTNAME ($PF_GATEWAY), expires at $expires_at"

PORT_FILE="$STATUS_FILE" QBIT_HOST=127.0.0.1 QBIT_WEBUI_PORT="$QB_PORT" \
  QBIT_USER="${QBIT_USER:-}" QBIT_PASS="${QBIT_PASS:-}" sh "$QB_SCRIPT" || true

# Keepalive + tự phục hồi
n=0
while :; do
  resp="$(curl -fsS -m 10 -G \
    --connect-to "$PF_HOSTNAME::$PF_GATEWAY:" \
    --cacert "$CERT" \
    --data-urlencode "payload=$payload" \
    --data-urlencode "signature=$signature" \
    "https://$PF_HOSTNAME:19999/bindPort" || true)"

  if [ "$(echo "$resp" | jq -r '.status // empty')" != "OK" ]; then
    log "bindPort failed; re-signing..."
    # xin chữ ký mới (ưu tiên cùng hostname)
    for j in 1 2 3 5 8; do
      new="$(request_signature "$PF_HOSTNAME" "$PF_GATEWAY" || true)"
      if [ "$(echo "$new" | jq -r '.status // empty')" = "OK" ]; then
        payload="$(echo "$new" | jq -r '.payload')"
        signature="$(echo "$new" | jq -r '.signature')"
        port="$(echo "$payload" | base64 -d | jq -r '.port')"
        echo "$port" > "$STATUS_FILE"
        log "Re-signed. Port: $port"
        PORT_FILE="$STATUS_FILE" QBIT_HOST=127.0.0.1 QBIT_WEBUI_PORT="$QB_PORT" \
          QBIT_USER="${QBIT_USER:-}" QBIT_PASS="${QBIT_PASS:-}" sh "$QB_SCRIPT" || true
        break
      fi
      sleep "$j"
    done
  else
    # refresh qB mỗi ~1 giờ
    if [ $((n % (3600 / SLEEP_KEEPALIVE) )) -eq 0 ]; then
      PORT_FILE="$STATUS_FILE" QBIT_HOST=127.0.0.1 QBIT_WEBUI_PORT="$QB_PORT" \
        QBIT_USER="${QBIT_USER:-}" QBIT_PASS="${QBIT_PASS:-}" sh "$QB_SCRIPT" || true
    fi
    n=$((n+1))
  fi

  sleep "$SLEEP_KEEPALIVE"
done
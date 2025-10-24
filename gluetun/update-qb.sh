#!/bin/sh
set -eu

PORT_FILE="${PORT_FILE:-/tmp/gluetun/forwarded_port}"
QB_HOST="${QBIT_HOST:-127.0.0.1}"
QB_PORT="${QBIT_WEBUI_PORT:-8080}"
QB_USER="${QBIT_USER:-}"
QB_PASS="${QBIT_PASS:-}"
LOG_FILE="${LOG_FILE:-/tmp/gluetun/update-qb.log}"
TRIES="${TRIES:-120}"
SLEEP="${SLEEP:-2}"
BASE="http://${QB_HOST}:${QB_PORT}"
COOK="/tmp/gluetun/qb-cookies.txt"

log(){ printf '%s %s\n' "$(date +'%F %T')" "$*" >>"$LOG_FILE"; }
enc(){ printf %s "$1" | sed -e 's/%/%25/g;s/&/%26/g;s/+/%2B/g;s/ /%20/g;s/"/%22/g;s/'"'"'/%27/g'; }

H1="--header=Referer: ${BASE}/"
H2="--header=Origin: ${BASE}"

qb_login(){
  [ -n "$QB_USER" ] || return 0
  rm -f "$COOK"
  data="username=$(enc "$QB_USER")&password=$(enc "$QB_PASS")"
  wget -q -O - $H1 $H2 --save-cookies "$COOK" --keep-session-cookies \
    --header "Content-Type: application/x-www-form-urlencoded" \
    --post-data "$data" "${BASE}/api/v2/auth/login" >/dev/null 2>&1 || true
}

set_port(){ # with/without cookie
  p="$1"
  json=$(printf '{"random_port":false,"listen_port":%s}' "$p")
  if [ -f "$COOK" ]; then
    wget -q -O - $H1 $H2 --load-cookies "$COOK" \
      --header "Content-Type: application/x-www-form-urlencoded" \
      --post-data "json=$(enc "$json")" "${BASE}/api/v2/app/setPreferences" \
      >/dev/null 2>&1 || true
  else
    wget -q -O - $H1 $H2 \
      --header "Content-Type: application/x-www-form-urlencoded" \
      --post-data "json=$(enc "$json")" "${BASE}/api/v2/app/setPreferences" \
      >/dev/null 2>&1 || true
  fi
}

read_port(){
  if [ -f "$COOK" ]; then
    wget -q -O - $H1 $H2 --load-cookies "$COOK" "${BASE}/api/v2/app/preferences" 2>/dev/null \
      | tr -d '\n' | sed -n 's/.*"listen_port":\([0-9][0-9]*\).*/\1/p'
  else
    wget -q -O - $H1 $H2 "${BASE}/api/v2/app/preferences" 2>/dev/null \
      | tr -d '\n' | sed -n 's/.*"listen_port":\([0-9][0-9]*\).*/\1/p'
  fi
}

# --- main ---
[ -r "$PORT_FILE" ] || { log "ERROR: $PORT_FILE not found"; exit 1; }
P="$(tr -d '\r\n' <"$PORT_FILE")"
case "$P" in ''|*[!0-9]*) log "ERROR: bad port '$P'"; exit 1;; esac
log "PIA forwarded port: $P"

# Thử login (nếu có user/pass)
qb_login

i=0
while [ $i -lt "$TRIES" ]; do
  set_port "$P"
  curr="$(read_port || true)"
  if [ "$curr" = "$P" ]; then
    log "listen_port updated -> $P"
    exit 0
  fi
  i=$((i+1)); sleep "$SLEEP"
done

log "WARN: tried $P, qB reports '${curr:-?}'"
exit 1
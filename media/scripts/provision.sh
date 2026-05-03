#!/usr/bin/env bash
# media/scripts/provision.sh — One-shot wiring of media stack inter-service connections.
#
# Idempotent: safe to re-run after first deploy or container wipe.
# Prereq: ./scripts/up.sh media (all containers healthy).
#
# Reads:  media/data/<service>/config.{xml,yaml} for arr API keys
# Writes: cross-service connections via REST APIs
#         (Prowlarr↔Sonarr/Radarr, Sonarr/Radarr→qBT, Bazarr↔Sonarr/Radarr, root folders)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MEDIA_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$MEDIA_DIR/.." && pwd)"

# Reuse shared logging helpers
# shellcheck source=../../scripts/_lib.sh
source "$ROOT_DIR/scripts/_lib.sh"

ENV_FILE="$MEDIA_DIR/.env"
DATA_DIR="$MEDIA_DIR/data"
[[ -f "$ENV_FILE" ]] || { log_error "$ENV_FILE not found — copy from .env.example first"; exit 1; }
set -a; source "$ENV_FILE"; set +a

: "${QBIT_USER:=admin}"
: "${QBIT_PASS:?Set QBIT_PASS in $ENV_FILE before running provision.sh}"

# Endpoints (provision.sh runs from host → uses host-published ports)
PROWLARR=http://localhost:9696
SONARR=http://localhost:8989
RADARR=http://localhost:7878
BAZARR=http://localhost:6767
QBT=http://localhost:8080

# Internal URLs (what arr services write into their own configs — container DNS on home-net)
QBT_INTERNAL_HOST=gluetun
QBT_INTERNAL_PORT=8080

RESP=/tmp/.provision-resp.$$
trap 'rm -f "$RESP"' EXIT

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

# Read API key from arr config.xml (handles container-owned files via podman unshare)
extract_arr_key() {
  local svc="$1"
  local cfg="$DATA_DIR/$svc/config.xml"
  local key
  key=$(grep -oP '(?<=<ApiKey>)[^<]+' "$cfg" 2>/dev/null \
        || podman unshare grep -oP '(?<=<ApiKey>)[^<]+' "$cfg" 2>/dev/null)
  [[ -n "$key" ]] || { log_error "$svc: ApiKey not found in $cfg"; return 1; }
  printf '%s' "$key"
}

# Bazarr stores key in config.yaml under auth.apikey
extract_bazarr_key() {
  local cfg="$DATA_DIR/bazarr/config/config.yaml"
  podman unshare grep -A1 "^auth:" "$cfg" 2>/dev/null \
    | grep "apikey:" | awk '{print $2}'
}

wait_healthy() {
  local container="$1" timeout="${2:-60}" elapsed=0
  while (( elapsed < timeout )); do
    if podman inspect "$container" --format '{{.State.Health.Status}}' 2>/dev/null \
       | grep -q "^healthy$"; then return 0; fi
    sleep 2; elapsed=$((elapsed+2))
  done
  log_error "$container did not become healthy within ${timeout}s"
  return 1
}

# POST JSON via curl, capturing status code and body to $RESP
post_json() {
  local url="$1" key_header="$2" payload="$3"
  curl -s -o "$RESP" -w '%{http_code}' \
    -X POST -H "$key_header" -H "Content-Type: application/json" \
    -d "$payload" "$url"
}

# ---------------------------------------------------------------------------
# Phase 1 — health check
# ---------------------------------------------------------------------------
log_info "Phase 1: waiting for all services healthy..."
for c in prowlarr sonarr radarr bazarr gluetun qbittorrent flaresolverr jellyfin; do
  wait_healthy "$c" 60 || exit 1
  log_success "$c healthy"
done

# ---------------------------------------------------------------------------
# Phase 2 — extract keys
# ---------------------------------------------------------------------------
log_info "Phase 2: extracting API keys..."
SONARR_KEY=$(extract_arr_key sonarr)
RADARR_KEY=$(extract_arr_key radarr)
PROWLARR_KEY=$(extract_arr_key prowlarr)
BAZARR_KEY=$(extract_bazarr_key)
[[ -n "$BAZARR_KEY" ]] || { log_error "Bazarr API key not found"; exit 1; }
log_success "all keys extracted"

# ---------------------------------------------------------------------------
# Phase 3 — qBittorrent permanent password
# ---------------------------------------------------------------------------
log_info "Phase 3: qBittorrent permanent password..."

qbt_login() {
  local user="$1" pass="$2"
  curl -si --data-urlencode "username=$user" --data-urlencode "password=$pass" \
    "$QBT/api/v2/auth/login" 2>/dev/null | sed -n 's/.*SID=\([^;]*\);.*/\1/p'
}

QBT_COOKIE=$(qbt_login "$QBIT_USER" "$QBIT_PASS" || true)

if [[ -z "$QBT_COOKIE" ]]; then
  QBT_TEMP=$(podman logs qbittorrent 2>&1 \
    | grep -oP "temporary password is provided for this session: \K\S+" | tail -1)
  [[ -n "$QBT_TEMP" ]] || { log_error "qBittorrent temp password not found in logs"; exit 1; }

  QBT_COOKIE=$(qbt_login admin "$QBT_TEMP")
  [[ -n "$QBT_COOKIE" ]] || { log_error "qBittorrent login failed with temp password"; exit 1; }

  # Build setPreferences JSON via Python (env-passed, safe with special chars)
  PREFS=$(QBT_USER_VAL="$QBIT_USER" \
          QBT_PASS_VAL="$QBIT_PASS" \
          QBT_PORT="${AIRVPN_FORWARDED_PORT:-54273}" \
          python3 -c '
import os, json
print(json.dumps({
  "web_ui_username": os.environ["QBT_USER_VAL"],
  "web_ui_password": os.environ["QBT_PASS_VAL"],
  "upnp": False,
  "random_port": False,
  "listen_port": int(os.environ["QBT_PORT"]),
}))')

  curl -s -b "SID=$QBT_COOKIE" \
    --data-urlencode "json=$PREFS" \
    "$QBT/api/v2/app/setPreferences" >/dev/null
  log_success "permanent password set"

  sleep 2
  QBT_COOKIE=$(qbt_login "$QBIT_USER" "$QBIT_PASS" || true)
  [[ -n "$QBT_COOKIE" ]] || log_warning "re-login failed, continuing anyway"
else
  log_success "permanent password already configured"
fi

# ---------------------------------------------------------------------------
# Phase 4 — Prowlarr applications (Sonarr + Radarr)
# ---------------------------------------------------------------------------
log_info "Phase 4: Prowlarr applications..."

prowlarr_app_exists() {
  local name="$1"
  NAME="$name" curl -s -H "X-Api-Key: $PROWLARR_KEY" "$PROWLARR/api/v1/applications" \
    | NAME="$name" python3 -c '
import sys, json, os
d = json.load(sys.stdin)
sys.exit(0 if any(a["name"] == os.environ["NAME"] for a in d) else 1)
'
}

add_prowlarr_app() {
  local name="$1" impl="$2" base_url="$3" arr_key="$4" sync_cats_json="$5"
  if prowlarr_app_exists "$name"; then
    log_success "$name already in Prowlarr"
    return 0
  fi
  local payload
  payload=$(NAME="$name" IMPL="$impl" BASE_URL="$base_url" ARR_KEY="$arr_key" \
            SYNC_CATS="$sync_cats_json" python3 -c '
import os, json
fields = [
  {"name": "prowlarrUrl",     "value": "http://prowlarr:9696"},
  {"name": "baseUrl",         "value": os.environ["BASE_URL"]},
  {"name": "apiKey",          "value": os.environ["ARR_KEY"]},
  {"name": "syncCategories",  "value": json.loads(os.environ["SYNC_CATS"])},
]
print(json.dumps({
  "syncLevel":          "fullSync",
  "enable":             True,
  "name":               os.environ["NAME"],
  "implementation":     os.environ["IMPL"],
  "implementationName": os.environ["IMPL"],
  "configContract":     os.environ["IMPL"] + "Settings",
  "fields":             fields,
  "tags":               [],
}))')
  local code
  code=$(post_json "$PROWLARR/api/v1/applications" "X-Api-Key: $PROWLARR_KEY" "$payload")
  if [[ "$code" =~ ^20[01]$ ]]; then
    log_success "$name added to Prowlarr"
  else
    log_error "$name add failed (HTTP $code): $(cat "$RESP")"
    return 1
  fi
}

add_prowlarr_app "Sonarr" "Sonarr" "http://sonarr:8989" "$SONARR_KEY" \
  '[5000,5010,5020,5030,5040,5045,5050,5090]'
add_prowlarr_app "Radarr" "Radarr" "http://radarr:7878" "$RADARR_KEY" \
  '[2000,2010,2020,2030,2040,2045,2050,2060,2070,2080,2090]'

# ---------------------------------------------------------------------------
# Phase 5 — Prowlarr FlareSolverr proxy
# ---------------------------------------------------------------------------
log_info "Phase 5: Prowlarr FlareSolverr proxy..."

flaresolverr_exists() {
  curl -s -H "X-Api-Key: $PROWLARR_KEY" "$PROWLARR/api/v1/indexerproxy" \
    | python3 -c '
import sys, json
d = json.load(sys.stdin)
sys.exit(0 if any(p.get("implementation") == "FlareSolverr" for p in d) else 1)
'
}

if flaresolverr_exists; then
  log_success "FlareSolverr already configured"
else
  payload='{
    "name": "FlareSolverr",
    "implementation": "FlareSolverr",
    "implementationName": "FlareSolverr",
    "configContract": "FlareSolverrSettings",
    "fields": [
      {"name": "host", "value": "http://flaresolverr:8191/"},
      {"name": "requestTimeout", "value": 60}
    ],
    "tags": [],
    "onHealthIssue": false,
    "includeHealthWarnings": false
  }'
  code=$(post_json "$PROWLARR/api/v1/indexerproxy" "X-Api-Key: $PROWLARR_KEY" "$payload")
  if [[ "$code" =~ ^20[01]$ ]]; then
    log_success "FlareSolverr added to Prowlarr"
  else
    log_error "FlareSolverr add failed (HTTP $code): $(cat "$RESP")"
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Phase 6 — Sonarr/Radarr download client (qBittorrent)
# ---------------------------------------------------------------------------
log_info "Phase 6: Sonarr/Radarr → qBittorrent download client..."

arr_dlclient_exists() {
  local arr_url="$1" arr_key="$2"
  curl -s -H "X-Api-Key: $arr_key" "$arr_url/api/v3/downloadclient" \
    | python3 -c '
import sys, json
d = json.load(sys.stdin)
sys.exit(0 if any(c.get("implementation") == "QBittorrent" for c in d) else 1)
'
}

add_qbt_to_arr() {
  local label="$1" arr_url="$2" arr_key="$3" cat_field="$4" cat_value="$5"
  if arr_dlclient_exists "$arr_url" "$arr_key"; then
    log_success "$label already has qBittorrent download client"
    return 0
  fi
  local payload
  payload=$(QBT_HOST="$QBT_INTERNAL_HOST" QBT_PORT="$QBT_INTERNAL_PORT" \
            QBT_USER_VAL="$QBIT_USER" QBT_PASS_VAL="$QBIT_PASS" \
            CAT_FIELD="$cat_field" CAT_VALUE="$cat_value" \
            python3 -c '
import os, json
fields = [
  {"name": "host",              "value": os.environ["QBT_HOST"]},
  {"name": "port",              "value": int(os.environ["QBT_PORT"])},
  {"name": "useSsl",            "value": False},
  {"name": "username",          "value": os.environ["QBT_USER_VAL"]},
  {"name": "password",          "value": os.environ["QBT_PASS_VAL"]},
  {"name": os.environ["CAT_FIELD"], "value": os.environ["CAT_VALUE"]},
]
print(json.dumps({
  "enable":                   True,
  "protocol":                 "torrent",
  "priority":                 1,
  "removeCompletedDownloads": True,
  "removeFailedDownloads":    True,
  "name":                     "qBittorrent",
  "implementation":           "QBittorrent",
  "implementationName":       "qBittorrent",
  "configContract":           "QBittorrentSettings",
  "fields":                   fields,
  "tags":                     [],
}))')
  local code
  code=$(post_json "$arr_url/api/v3/downloadclient" "X-Api-Key: $arr_key" "$payload")
  if [[ "$code" =~ ^20[01]$ ]]; then
    log_success "qBittorrent added to $label"
  else
    log_error "$label download client add failed (HTTP $code): $(cat "$RESP")"
    return 1
  fi
}

add_qbt_to_arr "Sonarr" "$SONARR" "$SONARR_KEY" "tvCategory"    "tv-sonarr"
add_qbt_to_arr "Radarr" "$RADARR" "$RADARR_KEY" "movieCategory" "movies-radarr"

# ---------------------------------------------------------------------------
# Phase 7 — Sonarr/Radarr root folders
# ---------------------------------------------------------------------------
log_info "Phase 7: Sonarr/Radarr root folders..."

add_root_folder() {
  local label="$1" arr_url="$2" arr_key="$3" path="$4"
  local existing
  existing=$(curl -s -H "X-Api-Key: $arr_key" "$arr_url/api/v3/rootfolder" \
    | python3 -c "import sys,json; print(','.join(r.get('path','') for r in json.load(sys.stdin)))")
  if [[ ",$existing," == *",$path,"* ]]; then
    log_success "$label root folder $path already set"
    return 0
  fi
  local code
  code=$(post_json "$arr_url/api/v3/rootfolder" "X-Api-Key: $arr_key" "{\"path\": \"$path\"}")
  if [[ "$code" =~ ^20[01]$ ]]; then
    log_success "$label root folder $path added"
  else
    log_error "$label root folder add failed (HTTP $code): $(cat "$RESP")"
    return 1
  fi
}

add_root_folder "Sonarr" "$SONARR" "$SONARR_KEY" "/tv"
add_root_folder "Radarr" "$RADARR" "$RADARR_KEY" "/movies"

# ---------------------------------------------------------------------------
# Phase 8 — Bazarr → Sonarr/Radarr connection
# ---------------------------------------------------------------------------
log_info "Phase 8: Bazarr → Sonarr/Radarr..."

# Bazarr's POST /api/system/settings expects form-urlencoded keys in the format
# `settings-{section}-{key}` (NOT JSON). Source: Bazarr api/system/settings.py
# which calls save_settings(zip(request.form.keys(), request.form.listvalues())).
bazarr_already_wired() {
  curl -s -H "X-API-KEY: $BAZARR_KEY" "$BAZARR/api/system/settings" \
    | python3 -c '
import sys, json
d = json.load(sys.stdin)
g = d.get("general", {})
s = d.get("sonarr", {})
r = d.get("radarr", {})
ok = (g.get("use_sonarr") and g.get("use_radarr")
      and bool(s.get("apikey")) and bool(r.get("apikey")))
sys.exit(0 if ok else 1)
'
}

if bazarr_already_wired; then
  log_success "Bazarr already connected to Sonarr+Radarr"
else
  code=$(curl -s -o "$RESP" -w '%{http_code}' \
    -X POST -H "X-API-KEY: $BAZARR_KEY" \
    --data-urlencode "settings-general-use_sonarr=true" \
    --data-urlencode "settings-general-use_radarr=true" \
    --data-urlencode "settings-sonarr-apikey=$SONARR_KEY" \
    --data-urlencode "settings-sonarr-ip=sonarr" \
    --data-urlencode "settings-sonarr-port=8989" \
    --data-urlencode "settings-sonarr-ssl=false" \
    --data-urlencode "settings-sonarr-base_url=/" \
    --data-urlencode "settings-radarr-apikey=$RADARR_KEY" \
    --data-urlencode "settings-radarr-ip=radarr" \
    --data-urlencode "settings-radarr-port=7878" \
    --data-urlencode "settings-radarr-ssl=false" \
    --data-urlencode "settings-radarr-base_url=/" \
    "$BAZARR/api/system/settings")
  if [[ "$code" =~ ^20[0-9]$ ]]; then
    log_success "Bazarr connected to Sonarr+Radarr"
  else
    log_error "Bazarr settings update failed (HTTP $code): $(cat "$RESP")"
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo
log_success "All services provisioned. Verify in browser:"
cat <<EOF
  - Prowlarr  http://localhost:9696   Settings → Apps                    (Sonarr + Radarr)
  - Sonarr    http://localhost:8989   Settings → Download Clients        (qBittorrent)
  - Radarr    http://localhost:7878   Settings → Download Clients        (qBittorrent)
  - Bazarr    http://localhost:6767   Settings → Sonarr / Settings → Radarr (green)
  - qBT       http://localhost:8080   Login: \$QBIT_USER / \$QBIT_PASS

Next: add indexers in Prowlarr (Settings → Indexers → Add Indexer)
EOF

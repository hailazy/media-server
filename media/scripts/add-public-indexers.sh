#!/usr/bin/env bash
# media/scripts/add-public-indexers.sh — add all public torrent indexers to Prowlarr.
#
# Idempotent: skips indexers already added (matched by name).
# Builds payloads from Prowlarr's indexer schema, picking sensible defaults:
#   - `select` with selectOptions: first option's value (typically the canonical mirror URL)
#   - other fields: schema default `value`
# Skips indexers requiring manual config (no `baseUrl` selectOptions, e.g. generic RSS).
#
# Usage: ./media/scripts/add-public-indexers.sh
#
# After running: indexers sync to Sonarr/Radarr automatically via Prowlarr's app sync.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MEDIA_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$MEDIA_DIR/.." && pwd)"

# shellcheck source=../../scripts/_lib.sh
source "$ROOT_DIR/scripts/_lib.sh"

DATA_DIR="$MEDIA_DIR/data"
PROWLARR=http://localhost:9696

PROWLARR_KEY=$(grep -oP '(?<=<ApiKey>)[^<]+' "$DATA_DIR/prowlarr/config.xml" 2>/dev/null \
               || podman unshare grep -oP '(?<=<ApiKey>)[^<]+' "$DATA_DIR/prowlarr/config.xml")
[[ -n "$PROWLARR_KEY" ]] || { log_error "Prowlarr ApiKey not found"; exit 1; }

RESP=/tmp/.indexers-resp.$$
SCHEMA_FILE=$(mktemp)
EXISTING_FILE=$(mktemp)
PAYLOADS_FILE=$(mktemp)
trap 'rm -f "$RESP" "$SCHEMA_FILE" "$EXISTING_FILE" "$PAYLOADS_FILE"' EXIT

# ---------------------------------------------------------------------------
# FlareSolverr tag bootstrap
# ---------------------------------------------------------------------------
# Prowlarr only routes through an indexer proxy when both the indexer AND the
# proxy share at least one tag — empty tags on the proxy does NOT auto-apply
# despite the docs claim. Empirical: CF-protected indexers fail validation
# unless explicitly tagged.
# Strategy: ensure tag "flaresolverr" exists, attach to FlareSolverr proxy,
# then tag every new indexer with it. Indexers that don't need CF bypass are
# unaffected (FlareSolverr is only invoked when a CF challenge is detected).

log_info "Ensuring FlareSolverr tag exists..."
TAG_ID=$(curl -s -H "X-Api-Key: $PROWLARR_KEY" "$PROWLARR/api/v1/tag" \
  | python3 -c "import sys,json; tags=json.load(sys.stdin); print(next((t['id'] for t in tags if t['label']=='flaresolverr'), ''))")
if [[ -z "$TAG_ID" ]]; then
  TAG_ID=$(curl -s -X POST -H "X-Api-Key: $PROWLARR_KEY" -H "Content-Type: application/json" \
    -d '{"label":"flaresolverr"}' "$PROWLARR/api/v1/tag" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
  log_success "tag flaresolverr created (id=$TAG_ID)"
else
  log_success "tag flaresolverr already exists (id=$TAG_ID)"
fi

log_info "Tagging FlareSolverr proxy..."
PROXIES=$(curl -s -H "X-Api-Key: $PROWLARR_KEY" "$PROWLARR/api/v1/indexerproxy")
PROXY_ID=$(echo "$PROXIES" | python3 -c "
import sys, json
ps = json.load(sys.stdin)
fs = next((p for p in ps if p.get('implementation')=='FlareSolverr'), None)
print(fs['id'] if fs else '')")
if [[ -z "$PROXY_ID" ]]; then
  log_warning "FlareSolverr proxy not found in Prowlarr — run provision.sh first"
else
  PROXY_TAGS=$(echo "$PROXIES" | T="$TAG_ID" python3 -c "
import sys, json, os
ps = json.load(sys.stdin)
fs = next(p for p in ps if p.get('implementation')=='FlareSolverr')
print(json.dumps(fs.get('tags', [])))")
  if echo "$PROXY_TAGS" | grep -q "$TAG_ID"; then
    log_success "FlareSolverr proxy already tagged"
  else
    PROXY_BODY=$(curl -s -H "X-Api-Key: $PROWLARR_KEY" "$PROWLARR/api/v1/indexerproxy/$PROXY_ID" \
      | T="$TAG_ID" python3 -c "import sys,json,os; d=json.load(sys.stdin); d['tags']=[int(os.environ['T'])]; print(json.dumps(d))")
    code=$(curl -s -o "$RESP" -w '%{http_code}' \
      -X PUT -H "X-Api-Key: $PROWLARR_KEY" -H "Content-Type: application/json" \
      -d "$PROXY_BODY" "$PROWLARR/api/v1/indexerproxy/$PROXY_ID")
    if [[ "$code" =~ ^20[02]$ ]]; then
      log_success "FlareSolverr proxy tagged"
    else
      log_error "Failed to tag FlareSolverr proxy (HTTP $code)"
    fi
  fi
fi

log_info "Fetching indexer schema + existing indexers..."
curl -s -H "X-Api-Key: $PROWLARR_KEY" "$PROWLARR/api/v1/indexer/schema" > "$SCHEMA_FILE"
curl -s -H "X-Api-Key: $PROWLARR_KEY" "$PROWLARR/api/v1/indexer"        > "$EXISTING_FILE"

# Build payload list via Python (much cleaner than bash JSON manipulation for 95 indexers)
SCHEMA_FILE="$SCHEMA_FILE" EXISTING_FILE="$EXISTING_FILE" TAG_ID="$TAG_ID" \
  python3 > "$PAYLOADS_FILE" <<'PY'
import os, json, sys

with open(os.environ["SCHEMA_FILE"]) as f:
    schema = json.load(f)
with open(os.environ["EXISTING_FILE"]) as f:
    existing = {i["name"] for i in json.load(f)}
tag_id = int(os.environ["TAG_ID"]) if os.environ.get("TAG_ID") else None

public_torrent = [i for i in schema if i.get("privacy") == "public"
                                    and i.get("protocol") == "torrent"]

added_count = 0
skipped = []

for idx in public_torrent:
    name = idx["name"]
    if name in existing:
        skipped.append(name)
        continue

    # Carry every schema field through (Prowlarr fills baseUrl/etc. from server-side
    # registry when value is null). Skip only `info` display fields.
    fields = [
        {"name": f["name"], "value": f.get("value")}
        for f in idx.get("fields", [])
        if f.get("type") != "info"
    ]

    payload = {
        "enable":             True,
        "redirect":           False,
        "supportsRss":        idx.get("supportsRss", True),
        "supportsSearch":     idx.get("supportsSearch", True),
        "supportsRedirect":   idx.get("supportsRedirect", False),
        "supportsPagination": idx.get("supportsPagination", True),
        "appProfileId":       1,
        "priority":           25,                              # mid of valid 1-50 range
        "protocol":           idx["protocol"],
        "privacy":            idx["privacy"],
        "name":               name,
        "implementation":     idx["implementation"],
        "implementationName": idx["implementationName"],
        "configContract":     idx["configContract"],
        "infoLink":           idx.get("infoLink", ""),
        "tags":               [tag_id] if tag_id else [],
        "fields":             fields,
        "capabilities":       idx.get("capabilities", {}),
    }
    sys.stdout.write(json.dumps(payload) + "\n")
    added_count += 1

# Summary on stderr (won't pollute the payloads file)
sys.stderr.write(f"to_add={added_count} skipped_existing={len(skipped)}\n")
if skipped:
    sys.stderr.write(f"  existing: {', '.join(skipped)}\n")
PY

TO_ADD=$(wc -l < "$PAYLOADS_FILE")
log_info "Adding $TO_ADD indexers..."

added=0
failed=0
while IFS= read -r payload; do
    [[ -z "$payload" ]] && continue
    name=$(printf '%s' "$payload" | python3 -c 'import sys,json; print(json.load(sys.stdin)["name"])')
    code=$(curl -s -o "$RESP" -w '%{http_code}' \
        -X POST -H "X-Api-Key: $PROWLARR_KEY" -H "Content-Type: application/json" \
        -d "$payload" "$PROWLARR/api/v1/indexer")
    if [[ "$code" =~ ^20[01]$ ]]; then
        printf '  %s + %s\n' "$(printf '\033[32m✓\033[0m')" "$name"
        added=$((added+1))
    else
        # Capture concise error reason (Prowlarr returns array of validation errors)
        reason=$(python3 -c "
import sys, json
try:
  d = json.load(sys.stdin)
  if isinstance(d, list) and d:
    print(d[0].get('errorMessage') or d[0].get('propertyName') or str(d[0]))
  else:
    print(d)
except Exception:
  sys.stdin.seek(0)
  print(sys.stdin.read()[:120])
" < "$RESP" 2>/dev/null || cat "$RESP")
        printf '  %s × %-30s HTTP %s — %s\n' "$(printf '\033[31m✗\033[0m')" "$name" "$code" "$reason"
        failed=$((failed+1))
    fi
done < "$PAYLOADS_FILE"

echo
log_success "Done: $added added, $failed failed"
log_info "Verify in Prowlarr: http://localhost:9696 → Indexers"
log_info "Sync to Sonarr/Radarr: Prowlarr → Sync App Indexers (or wait for next auto-sync)"

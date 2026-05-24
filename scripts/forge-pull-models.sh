#!/usr/bin/env bash
# =============================================================================
# forge-pull-models.sh - Download Forge models from manifest
# =============================================================================
#
# Usage:
#   ./forge-pull-models.sh                       # Pull all missing
#   ./forge-pull-models.sh --only <name>         # Pull single model
#   ./forge-pull-models.sh --check               # Verify existing (no download)
#   ./forge-pull-models.sh --force               # Re-download even if present
#   ./forge-pull-models.sh --generate-checksums  # Compute sha256 for existing
#
# Reads forge/models.yml. Supports hf://, civitai://, url:// sources.
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$REPO_ROOT/forge/models.yml"
MODELS_DIR="$REPO_ROOT/forge/data/forge/models"
ENV_FILE="$REPO_ROOT/.env"

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
log()     { echo -e "\033[36m[forge-pull]\033[0m $*"; }
warn()    { echo -e "\033[33m[warn]\033[0m $*"; }
err()     { echo -e "\033[31m[err]\033[0m $*" >&2; }
success() { echo -e "\033[32m[ok]\033[0m $*"; }

# ─────────────────────────────────────────────────────────────
# Arg parsing
# ─────────────────────────────────────────────────────────────
ONLY=""
CHECK=false
FORCE=false
GEN_SUMS=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --only) ONLY="$2"; shift 2 ;;
        --check) CHECK=true; shift ;;
        --force) FORCE=true; shift ;;
        --generate-checksums) GEN_SUMS=true; shift ;;
        -h|--help) sed -n '4,15p' "$0"; exit 0 ;;
        *) err "Unknown: $1"; exit 1 ;;
    esac
done

# ─────────────────────────────────────────────────────────────
# Dependencies
# ─────────────────────────────────────────────────────────────
command -v yq >/dev/null || { err "yq missing. Install: sudo dnf install yq"; exit 1; }
command -v curl >/dev/null || { err "curl missing"; exit 1; }

# Load .env for CIVITAI_API_KEY
if [[ -f "$ENV_FILE" ]]; then
    set -a; source "$ENV_FILE"; set +a
fi

# ─────────────────────────────────────────────────────────────
# Source handlers
# ─────────────────────────────────────────────────────────────
pull_hf() {
    local src="$1" dest="$2"
    # hf://<repo>/<file>
    local path="${src#hf://}"
    local repo="${path%/*/*}/${path#*/}"
    repo=$(echo "$path" | awk -F/ '{print $1"/"$2}')
    local file=$(echo "$path" | cut -d/ -f3-)

    command -v huggingface-cli >/dev/null || {
        log "Installing huggingface_hub..."
        pip install --user huggingface_hub
    }

    huggingface-cli download "$repo" "$file" \
        --local-dir "$(dirname "$dest")" \
        --local-dir-use-symlinks False

    # huggingface-cli puts file at <dest_dir>/<file>; rename if needed
    local downloaded="$(dirname "$dest")/$file"
    [[ "$downloaded" != "$dest" ]] && /bin/mv "$downloaded" "$dest"
}

pull_civitai() {
    local src="$1" dest="$2"
    # civitai://<modelVersionId>
    local version_id="${src#civitai://}"

    [[ "$version_id" == "TBD" ]] && {
        warn "  TBD modelVersionId — skip (fill in models.yml)"
        return 1
    }

    [[ -z "${CIVITAI_API_KEY:-}" ]] && {
        err "CIVITAI_API_KEY missing in $ENV_FILE"
        return 1
    }

    curl -fL --progress-bar \
        -H "Authorization: Bearer $CIVITAI_API_KEY" \
        -o "$dest" \
        "https://civitai.com/api/download/models/$version_id"
}

pull_url() {
    local src="$1" dest="$2"
    local url="${src#url://}"
    curl -fL --progress-bar -o "$dest" "$url"
}

# ─────────────────────────────────────────────────────────────
# Pull dispatcher
# ─────────────────────────────────────────────────────────────
pull_one() {
    local name="$1" source="$2" target_dir="$3" sha256="$4"
    local dest="$MODELS_DIR/$target_dir/$name"

    mkdir -p "$(dirname "$dest")"

    # Already exists?
    if [[ -f "$dest" ]] && ! $FORCE; then
        if [[ -n "$sha256" && "$sha256" != "null" && "$sha256" != "TBD" ]]; then
            actual=$(sha256sum "$dest" | cut -d' ' -f1)
            if [[ "$actual" == "$sha256" ]]; then
                success "  $name (checksum OK)"
                return 0
            else
                warn "  $name CHECKSUM MISMATCH — expected $sha256, got $actual"
                $CHECK && return 1
            fi
        else
            success "  $name (exists, no checksum to verify)"
            return 0
        fi
    fi

    $CHECK && { warn "  $name MISSING"; return 1; }

    log "  Downloading $name ($source)..."
    case "$source" in
        hf://*)      pull_hf "$source" "$dest" ;;
        civitai://*) pull_civitai "$source" "$dest" ;;
        url://*)     pull_url "$source" "$dest" ;;
        *) err "Unknown source scheme: $source"; return 1 ;;
    esac

    # Post-download checksum
    if [[ -n "$sha256" && "$sha256" != "null" && "$sha256" != "TBD" && -f "$dest" ]]; then
        actual=$(sha256sum "$dest" | cut -d' ' -f1)
        [[ "$actual" != "$sha256" ]] && {
            err "  Checksum failed after download: expected $sha256, got $actual"
            return 1
        }
    fi
    success "  $name done"
}

# ─────────────────────────────────────────────────────────────
# Checksum generator mode
# ─────────────────────────────────────────────────────────────
if $GEN_SUMS; then
    log "Computing sha256 for existing models..."
    for kind in checkpoints loras; do
        count=$(yq ".$kind | length // 0" "$MANIFEST")
        for i in $(seq 0 $((count - 1))); do
            name=$(yq ".$kind[$i].name" "$MANIFEST")
            target_dir=$(yq ".$kind[$i].target_dir" "$MANIFEST")
            file="$MODELS_DIR/$target_dir/$name"
            if [[ -f "$file" ]]; then
                sum=$(sha256sum "$file" | cut -d' ' -f1)
                echo "  $name: sha256: $sum"
            else
                warn "  $name: missing"
            fi
        done
    done
    log "Add these sha256 values to $MANIFEST manually"
    exit 0
fi

# ─────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────
log "Manifest: $MANIFEST"
log "Models dir: $MODELS_DIR"
$CHECK && log "Mode: CHECK (verify only)"
$FORCE && log "Mode: FORCE (re-download)"
[[ -n "$ONLY" ]] && log "Filter: only $ONLY"

failed=0
total=0

for kind in checkpoints loras; do
    count=$(yq ".$kind | length // 0" "$MANIFEST")
    log ""
    log "=== $kind ($count entries) ==="

    for i in $(seq 0 $((count - 1))); do
        name=$(yq ".$kind[$i].name" "$MANIFEST")
        source=$(yq ".$kind[$i].source" "$MANIFEST")
        target_dir=$(yq ".$kind[$i].target_dir" "$MANIFEST")
        sha256=$(yq ".$kind[$i].sha256 // \"\"" "$MANIFEST")

        [[ -n "$ONLY" && "$name" != "$ONLY"* ]] && continue

        ((total++))
        pull_one "$name" "$source" "$target_dir" "$sha256" || ((failed++))
    done
done

log ""
if [[ $failed -eq 0 ]]; then
    success "All $total models OK"
else
    err "$failed/$total failed"
    exit 1
fi

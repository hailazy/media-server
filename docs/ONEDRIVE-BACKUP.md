# OneDrive Backup — Architecture & Implementation Guide

**Status**: design only, not implemented. Document để Hải tham khảo khi rảnh execute.
**Last updated**: 2026-05-24

## Why this exists

home-server có **disaster recovery gap**: nhiều state file critical KHÔNG track trong git (do gitignore — đúng convention), nhưng cũng KHÔNG được backup ra ngoài máy. Nếu NVMe fail hoặc `data/` corrupt → rebuild manual = nhiều giờ tới ngày.

Hải có **5TB OneDrive** (MS 365 Family), hiện chỉ dùng ~55GB. Tận dụng để cover gap này = miễn phí + off-site.

**Scope**: chỉ backup state files KHÔNG ở git. Re-downloadable assets (Forge models 9GB) → skip, tải lại từ HuggingFace khi cần.

## What's NOT in git (the actual gap)

Liệt kê từ `.gitignore` + thực tế trên disk (2026-05-24):

| Category | Path | Size | Sensitivity |
|---|---|---|---|
| **Secrets** | `.env` (top), `dashboard/.env`, `media/.env` | <1KB × 3 | 🔴 Credentials (Civitai key, AirVPN keys, qBT pass) |
| **Forge state** | `forge/data/forge/config/` | 300KB | UI settings + preferences |
| **Forge state** | `forge/data/forge/extensions/` | 15MB | Custom extensions installed |
| **Forge state** | `forge/data/forge/embeddings/` | 0 | Currently empty, future textual inversions |
| **Forge outputs** | `forge/data/forge/outputs/` | 841MB | Generated images, growing |
| **SillyTavern** | `sillytavern/data/` (chats, characters, presets, cookie-secret) | 283MB | 🟡 Chat history nhạy cảm |
| **Media DBs** | `media/data/{sonarr,radarr,prowlarr,bazarr,jellyfin}/` | 32MB | SQLite + metadata, Jellyfin watched state |
| **Media VPN** | `media/data/gluetun/` | <1MB | Cached state, regen-able |
| **Media qBT** | `media/data/qbittorrent/` | varies | Torrent state + categories |
| **Dashboard** | `dashboard/data/{db,redis,trusted-certificates}/` | 6.2MB | Homarr SQLite, dashboard layout |
| **Dashboard backups** | `dashboard/backups/` | varies | Already-tar.gz local snapshots, cần off-site |

**Skipped (re-downloadable / regen-able)**:
- `forge/data/forge/models/` (9GB) — HuggingFace pull
- `media/data/jellyfin-cache/` — auto-regen
- `*.log`, `cache/`, `transcodes/`, `tmp/` — runtime ephemera

**Total critical state** (exclude models, outputs, cache):
- **Tier 1 (secrets + small configs)**: ~50MB compressed
- **Tier 2 (+ SillyTavern + Forge outputs)**: ~900MB-1.2GB compressed

## Current OneDrive setup

- **Client**: `abraunegg/onedrive` (Linux native)
- **Accounts**: Personal + Dev, multi-account
- **Dev sync_dir**: `/home/haint/OneDrive/dev/` (~55GB local)
- **Sync mode**: 2-way full (sync_list rỗng)
- **Existing cron**: brain.db daily 4:07 AM → `OneDrive/dev/brain-backup/`

## Critical constraint

`abraunegg/onedrive` sync **2-way mặc định**. KHÔNG có "Files On-Demand" như Windows client:
- File trong `sync_dir` luôn có physical copy local
- Xóa local = xóa cloud

→ Không thể đơn giản "push folder vào sync_dir" để leverage cloud-only storage.

## Pattern decision: rclone separate remote + GPG encryption

| Pattern | Free local? | Encrypted? | Chọn |
|---|---|---|---|
| Folder trong existing `OneDrive/dev/` | ❌ | ❌ | No |
| rclone copy (one-way) | ✅ | ❌ | No (raw) |
| **rclone copy + GPG encrypt tarball trước push** | ✅ | ✅ | **Yes** |
| rclone crypt remote layer | ✅ | ✅ (transparent) | Alternative |

**Lý do chọn rclone + GPG tarball**:
- True one-way push (không xung đột existing 2-way sync)
- **Encryption MANDATORY** vì `.env` chứa Civitai API key + AirVPN keys + qBT pass. Backup plain text lên OneDrive = secrets sit trên MS server
- GPG tarball linh hoạt: có thể `gpg --decrypt | tar xz` ở bất kỳ máy nào có key, không buộc rclone
- Alternative rclone crypt: encrypt transparent, tốt hơn cho large file cold archive, nhưng setup phức tạp hơn

## Implementation guide (rough)

### Phase 1: rclone + GPG setup (~30 min)

```bash
# Install
sudo dnf install rclone gnupg2

# Configure OneDrive remote (interactive OAuth)
rclone config
# n) New remote → name: onedrive-dev → storage: onedrive → drive_type: personal
# Auto-config: browser auth

# Verify
rclone lsd onedrive-dev:
rclone about onedrive-dev:    # quota check (should show 5TB)

# Generate GPG key for backup (no passphrase = automated, set passphrase = secure but breaks cron)
# Option A: key có passphrase + gpg-agent caching → secure
# Option B: symmetric encrypt với passphrase từ pass-store → portable
# Khuyến nghị B đầu, A sau khi quen workflow

# Example symmetric:
echo "secure-passphrase-here" > ~/.config/home-server-backup.pass
chmod 600 ~/.config/home-server-backup.pass
```

### Phase 2: Backup script (~1h)

`home-server/scripts/cloud-backup.sh`:

```bash
#!/usr/bin/env bash
# Backup home-server non-git state to OneDrive (encrypted)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

REMOTE="onedrive-dev:home-server-backup"
DATE=$(date +%Y-%m-%d)
WORK_DIR=$(mktemp -d)
PASS_FILE="$HOME/.config/home-server-backup.pass"
trap "rm -rf $WORK_DIR" EXIT

# ─────────────────────────────────────────────────────────
# Tier 1: Secrets + small configs (always include)
# ─────────────────────────────────────────────────────────
tar czf "$WORK_DIR/tier1-secrets-$DATE.tar.gz" \
  .env dashboard/.env media/.env \
  forge/data/forge/config \
  forge/data/forge/extensions \
  forge/data/forge/embeddings 2>/dev/null || true

# ─────────────────────────────────────────────────────────
# Tier 2: Service state (DBs need consistent snapshot)
# ─────────────────────────────────────────────────────────

# Dashboard: stop briefly cho SQLite consistency, restart
./scripts/down.sh dashboard
tar czf "$WORK_DIR/tier2-dashboard-$DATE.tar.gz" dashboard/data
./scripts/up.sh dashboard

# Media DBs: cùng pattern (stop section → snapshot → start)
./scripts/down.sh media
tar czf "$WORK_DIR/tier2-media-$DATE.tar.gz" \
  media/data \
  --exclude='media/data/jellyfin-cache' \
  --exclude='media/data/*/logs' \
  --exclude='media/data/*/Logs'
./scripts/up.sh media

# SillyTavern: file-based, có thể tar khi running (chats append-only)
tar czf "$WORK_DIR/tier2-sillytavern-$DATE.tar.gz" \
  sillytavern/data \
  --exclude='sillytavern/data/_cache' \
  --exclude='sillytavern/data/access.log' \
  --exclude='sillytavern/data/content.log'

# ─────────────────────────────────────────────────────────
# Tier 3 (optional): Forge outputs — growing, archive weekly
# ─────────────────────────────────────────────────────────
# Skip mặc định trong daily — uncomment cho weekly cron riêng
# tar czf "$WORK_DIR/tier3-forge-outputs-$DATE.tar.gz" forge/data/forge/outputs

# ─────────────────────────────────────────────────────────
# Encrypt all tarballs với GPG symmetric
# ─────────────────────────────────────────────────────────
for tarball in "$WORK_DIR"/*.tar.gz; do
  gpg --batch --yes --symmetric --cipher-algo AES256 \
    --passphrase-file "$PASS_FILE" \
    --output "${tarball}.gpg" "$tarball"
  rm "$tarball"
done

# ─────────────────────────────────────────────────────────
# Push to cloud
# ─────────────────────────────────────────────────────────
rclone copy "$WORK_DIR" "$REMOTE/daily/" \
  --transfers 4 --progress \
  --bwlimit "07:00,8M 23:00,off"   # cap 8MB/s ban ngày, full ban đêm

# ─────────────────────────────────────────────────────────
# Server-side retention
# ─────────────────────────────────────────────────────────
# Daily: keep 7
rclone delete "$REMOTE/daily/" --min-age 7d --include "tier{1,2}-*.gpg"

# Weekly (Sunday): promote daily → weekly
if [ "$(date +%u)" = "7" ]; then
  rclone copy "$REMOTE/daily/" "$REMOTE/weekly/" --max-age 1d
  rclone delete "$REMOTE/weekly/" --min-age 28d
fi

# Monthly (1st): promote → monthly
if [ "$(date +%d)" = "01" ]; then
  rclone copy "$REMOTE/daily/" "$REMOTE/monthly/" --max-age 1d
  rclone delete "$REMOTE/monthly/" --min-age 365d
fi

echo "Backup complete: $(rclone size $REMOTE)"
```

Schedule:
```cron
# /etc/cron.d/home-server-backup (or user crontab)
# Daily 4:30 AM (sau brain backup 4:07)
30 4 * * * /home/haint/Projects/home-server/scripts/cloud-backup.sh >> /var/log/home-server-backup.log 2>&1
```

### Phase 3: Restore script (~30 min)

`home-server/scripts/cloud-restore.sh`:

```bash
#!/usr/bin/env bash
# Restore single tier từ latest (hoặc specified date) backup
# Usage: ./cloud-restore.sh tier1-secrets [2026-05-20]
set -euo pipefail

TIER="$1"
DATE="${2:-latest}"
REMOTE="onedrive-dev:home-server-backup"
PASS_FILE="$HOME/.config/home-server-backup.pass"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Find latest if needed
if [ "$DATE" = "latest" ]; then
  DATE=$(rclone lsf "$REMOTE/daily/" | grep "^${TIER}-" | sort -r | head -1 | \
    grep -oP '\d{4}-\d{2}-\d{2}')
fi

FILE="${TIER}-${DATE}.tar.gz.gpg"
echo "Restoring $FILE..."

# Pull
rclone copy "$REMOTE/daily/$FILE" /tmp/

# Decrypt
gpg --batch --yes --decrypt --passphrase-file "$PASS_FILE" \
  --output "/tmp/${TIER}-${DATE}.tar.gz" "/tmp/$FILE"

# Confirm before extract (overwrites current state)
echo "Files in archive:"
tar tzf "/tmp/${TIER}-${DATE}.tar.gz" | head -20
read -p "Extract over current state? [y/N] " confirm
[ "$confirm" = "y" ] || exit 1

# Stop affected sections trước extract
case "$TIER" in
  tier2-dashboard) "$REPO_ROOT/scripts/down.sh" dashboard ;;
  tier2-media) "$REPO_ROOT/scripts/down.sh" media ;;
  tier2-sillytavern) "$REPO_ROOT/scripts/down.sh" sillytavern ;;
esac

# Extract
tar xzf "/tmp/${TIER}-${DATE}.tar.gz" -C "$REPO_ROOT"

# Restart
case "$TIER" in
  tier2-dashboard) "$REPO_ROOT/scripts/up.sh" dashboard ;;
  tier2-media) "$REPO_ROOT/scripts/up.sh" media ;;
  tier2-sillytavern) "$REPO_ROOT/scripts/up.sh" sillytavern ;;
esac

echo "Restore complete"
```

### Phase 4: Validation (after first backup)

```bash
# 1. Verify cloud has files
rclone ls onedrive-dev:home-server-backup/daily/

# 2. Test restore vào temp dir (KHÔNG overwrite real state)
gpg --decrypt --passphrase-file ~/.config/home-server-backup.pass \
  /tmp/tier1-secrets-2026-05-24.tar.gz.gpg | tar tz | head

# 3. Drill: full disaster recovery test trên VM hoặc tmp dir
#    - Restore tier1 → verify .env files match
#    - Restore tier2-dashboard → verify Homarr layout OK
```

## Estimated costs

- **Disk local**: ~340MB tarball trước push, xóa sau push → ~0 long-term
- **Bandwidth daily**: ~50-100MB upload, vài phút trên VN internet
- **Tier 3 weekly (Forge outputs)**: 841MB → ~15-20 min upload, schedule 3 AM Sunday
- **OneDrive quota used**: ~3-5GB sau 6 tháng với 7d/4w/12m retention
- **Cloud time**: free (đã có MS 365)

## Open questions

1. **GPG passphrase management**
   - Pass file plain trong `~/.config/` (mode 600) → đơn giản, breach nếu HDD compromised
   - `pass` (Unix password store) với GPG key → secure hơn, cần GPG agent
   - Hardware key (YubiKey) → quá xa cho use case này
   - Khuyến nghị: pass file mode 600 đầu, upgrade `pass` sau khi quen

2. **SD outputs cull workflow**
   - Forge outputs growing 841MB → có script cull existing không?
   - Nếu có: backup chỉ những outputs đã kept (post-cull)
   - Nếu không: backup all hoặc skip Tier 3

3. **Section downtime acceptable?**
   - Dashboard + Media stop ~30s/day cho consistent SQLite snapshot
   - Alternative: `sqlite3 .backup` API → online snapshot (không cần stop), nhưng phức tạp hơn
   - Khuyến nghị: chấp nhận 30s downtime 4:30 AM, simplify code

4. **Encryption granularity**
   - Hiện tại: 1 passphrase cho mọi tarball
   - Alternative: GPG public key encrypt (key trên YubiKey/USB) → restore cần physical key
   - Khuyến nghị: 1 passphrase đủ, upgrade nếu có nhu cầu

## Related

- Existing cron brain.db: `~/Projects/agent/mcp/haingt-brain/.env` (BRAIN_DB, BRAIN_BACKUP_DIR)
- OneDrive setup: `~/Projects/workstation-setup/scripts/onedrive_setup.sh`
- Hardware market context (why off-site backup > buy new SSD): `~/Projects/Idea_Vault/40 Library/My Setup.md`
- Local dashboard backup (already exists, complement không thay): `home-server/scripts/dashboard-backup.sh`

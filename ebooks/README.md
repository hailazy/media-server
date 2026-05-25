# ebooks — Calibre-Web Automated

Web UI cho thư viện Calibre hiện có + auto-ingest sách mới + Send-to-Kindle.

## Endpoint

| URL | Mục đích |
|-----|----------|
| http://localhost:8083 | Web UI + OPDS (localhost-only) |

Default login lần đầu: `admin` / `admin123` — đổi ngay.

## Quick start

```bash
cp ebooks/.env.example ebooks/.env       # default path là /home/haint/Data/Calibre Library
./scripts/up.sh ebooks
xdg-open http://localhost:8083
```

Container DNS từ dashboard/forge/ST: `http://home-ebooks:8083`.

## Operations

| Task | Command |
|------|---------|
| Start | `./scripts/up.sh ebooks` |
| Stop  | `./scripts/down.sh ebooks` |
| Logs  | `./scripts/logs.sh ebooks -f` |
| Status | `./scripts/logs.sh ebooks --status` |
| Backup config | `./scripts/ebooks-backup.sh [name]` → `ebooks/backups/*.tar.gz` |
| Restore config | `./scripts/ebooks-restore.sh <backup.tar.gz>` |

**Backup workflow**: Sau khi setup xong (đổi pass, config SMTP, custom settings) → `./scripts/ebooks-backup.sh post-setup`. Sau này wipe `data/` hoặc setup máy mới → `./scripts/ebooks-restore.sh post-setup.tar.gz` → mọi thứ về nguyên trạng, không phải re-onboard. Backup snapshot `data/config/` (app.db, .key, processed_books/, client_secrets.json), bỏ qua `data/ingest/` vì transient.

## Library mount

Mount thẳng `${CALIBRE_LIBRARY_PATH}` → `/calibre-library` (read-write). Library sống độc lập trên ổ Data, **không trong OneDrive sync mount**. Backup lên OneDrive cloud qua systemd timer `calibre-sync.timer` (daily 22:30, one-way local→cloud bằng `rclone sync` → `onedrive-dev:Calibre Library/`). Manual sync: `systemctl --user start calibre-sync.service`.

Lần đầu login: Admin → Basic Configuration → verify library path là `/calibre-library`. CWA auto-detect khi có `metadata.db`.

## Ingest workflow

```
~/Downloads/foo.epub  →  ebooks/data/ingest/foo.epub
                                   ↓ inotify (~5s)
                         CWA: convert (nếu cần) + metadata + import
                                   ↓
                         /calibre-library/<Author>/<Title>/foo.epub
                                   ↓
                         OneDriveGUI sync lên cloud
```

Hỗ trợ 28 formats (epub, mobi, azw3, pdf, cbz, fb2, ...). Mọi format không phải epub được auto-convert sang epub trước khi import.

## Send-to-Kindle setup (manual, sau lần up đầu tiên)

1. **Gmail App Password**: Tài khoản Google → Security → 2-Step Verification (bật nếu chưa) → App passwords → generate cho "Mail".
2. **CWA SMTP**: Admin → SMTP Settings:
   - Server: `smtp.gmail.com`
   - Port: `587`
   - Encryption: `STARTTLS`
   - User: email Gmail
   - Password: app password vừa tạo
3. **Amazon approved sender**: amazon.com → Manage Your Content and Devices → Preferences → Personal Document Settings → Approved Personal Document E-mail List → Add → email Gmail trên.
4. Test: chọn 1 sách → Send to Kindle → check email Amazon `<name>@kindle.com` trong 1-2 phút.

## Integration

- Network: `home-net` (chung với forge/sillytavern/dashboard).
- Sau khi up, thêm tile Homarr manual (Dashboard → Edit → App):
  - URL: `http://localhost:8083`
  - Ping URL: `http://home-ebooks:8083`
  - Sau khi thêm → `./scripts/dashboard-backup.sh` để snapshot.

## Gotchas

- **`PUID=0`/`PGID=0` — KHÔNG phải 1000/1001.** Counter-intuitive nhưng chính xác cho rootless Podman + bind mount host home dir. Lý do: container UID 0 trong rootless namespace map về host UID `haint` (1000). Nếu set PUID=1000 → CWA process chạy UID 1000 trong container → maps sang **subuid 525287** trên host → CWA chown library sang subuid → haint mất quyền access, OneDriveGUI sync gãy. Confirm bằng `ls -la "$CALIBRE_LIBRARY_PATH"` sau khi container chạy: phải thấy `haint haint`. Đã thử `userns_mode: keep-id` để giữ PUID=1000 mapping về haint — fail vì s6 overlay init không có CAP_SETGID trong namespace đó. Pattern PUID=0 cùng dùng cho `media/` (xem `media/compose.yml`).
- **Library mount mode `:z`** (read-write), NOT `:ro`. CWA cần ghi metadata.db. Read-only sẽ fail preflight ở release CWA mới.
- **Image name fully-qualified**: `docker.io/crocodilestick/...` — podman-compose rootless refuse `crocodilestick/...` short name vì `short-name resolution enforced but cannot prompt without a TTY`. Tất cả compose trong repo đều dùng full registry prefix.
- **Ingest folder local, không nằm trong OneDrive path**. CWA xóa file gốc sau khi import → tránh OneDrive sync version garbage.
- **OneDriveGUI sync conflict**: nếu sau này dùng Calibre desktop trên máy khác cùng library → SQLite lock conflict. Hiện tại 1 máy → an toàn. Đã cài Calibre desktop trên máy này → tránh mở cùng lúc CWA.
- **First boot ~60s**: CWA build index cho library lớn. Healthcheck `start_period: 60s` cover. Sau khi healthy mới mở UI.
- **inotify vs polling**: btrfs local → inotify hoạt động (`NETWORK_SHARE_MODE=false`). Nếu library chuyển sang NFS/SMB sau này → đổi env thành `true`.

## Files

```
ebooks/
├── compose.yml          # service definition
├── .env.example         # CALIBRE_LIBRARY_PATH template
├── .env                 # (gitignored) actual path override
├── .gitignore
├── README.md
└── data/                # (gitignored)
    ├── config/          # CWA app SQLite + settings
    └── ingest/          # drop sách mới ở đây
```

## VRAM

Không dùng GPU. CWA CPU-only (Tesseract OCR + Calibre conversion). Đã thêm vào non-GPU case của `vram-guard.sh` → exit 0 ngay, không check.

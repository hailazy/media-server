# ASF — ArchiSteamFarm (Steam card farming)

Farm trading cards tự động cho account Steam, quản lý qua web UI. Container `home-asf`, image chính chủ `justarchi/archisteamfarm:released`.

- **Web UI (ASF-ui):** http://localhost:1242 — localhost-only. **IPCPassword bắt buộc** dù chỉ bind localhost: podman port-forward làm request đến ASF mang IP gateway container (non-loopback) → ASF đòi auth. Password nằm trong `data/config/ASF.json` (gitignored).
- **Ownership:** container chạy `ASF_UID=0` (container-root, như PUID=0 của media stack) → host thấy files trong `data/` thuộc user thường — sửa config trực tiếp được, DR restore extract là chạy.
- **Backup:** `asf/.env` (tier1) + `asf/data/config/` — gồm bot config, maFile, DBs — (tier2) nằm trong daily-bundle của workstation-setup; restore tự động qua recovery pipeline.
- **Config:** `data/config/` (gitignored — chứa Steam credentials, maFile, bot DB)
- **Hướng dùng card đã chốt:** sell market lấy Steam wallet (mua game research), không craft badge

## Ops

```bash
./scripts/up.sh asf        # start
./scripts/down.sh asf      # stop
./scripts/logs.sh asf -f   # logs
./scripts/update.sh        # pull image mới (ASF core + official plugins) cho mọi section
```

Autostart sau reboot: `restart: always` + `systemctl --user enable podman-restart.service` (đã enable). Máy idle-suspend thì farming pause, dậy chạy tiếp — không giữ máy thức.

## Bot

Tạo/sửa bot qua web UI → Bots → New bot: `SteamLogin`, `SteamPassword`, bật `Enabled`. Steam Guard code nhập qua UI khi được hỏi. Farm card chạy tự động cho mọi game còn drop.

Lệnh hay dùng (tab Commands trong UI): `status asf`, `loot <bot>` (gửi hết card về account nhận), `redeem <bot> <keys>`, `addlicense <bot> <ids>`, `updateplugins`.

## Plugins

| Plugin | Nguồn | Update |
|--------|-------|--------|
| ItemsMatcher, MobileAuthenticator, SteamTokenDumper | official, bundle trong image | theo image pull (`update.sh`) |
| ASFEnhance (2.3.27.0 lúc cài) | `data/plugins/ASFEnhance/` | ASF tự update (PluginsUpdateList) |
| ASFAchievementManager (1.1.0.0 lúc cài) | `data/plugins/ASFAchievementManager/` | ASF tự update (PluginsUpdateList) |

Plugin ngoài mount **từng cái** vào `/app/plugins/<Tên>/` — đừng mount đè cả `/app/plugins` (che mất official plugins). Thêm plugin mới = tạo thư mục trong `data/plugins/`, thêm mount vào `compose.yml`, thêm tên assembly vào `PluginsUpdateList` trong `data/config/ASF.json`.

## 2FA (ASF làm authenticator — joint mode)

ASF giữ `shared_secret`/`identity_secret` trong bot DB → tự confirm trade/market. Setup từ đầu (khi chưa có maFile): gỡ authenticator cũ trên điện thoại (⚠️ trade-hold ~15 ngày, một lần) → `2fainit <bot>` → `2fafinalized <bot> <code>` (joint: app điện thoại vẫn dùng song song). Lưu revocation code vào password manager. Lệnh `2fa <bot>` = lấy code khi cần.

## ItemsMatcher (đang TẮT)

Chỉ phục vụ hoàn badge (đổi card trùng lấy card thiếu qua ASF listing). Đang đi hướng sell market nên không bật. Muốn bật: bot config → `TradingPreferences` thêm flag `SteamTradeMatcher` (+ `MatchableTypes` mặc định trading cards).

## Nếu muốn expose UI ra LAN/Tailscale

IPCPassword đã có sẵn (bắt buộc, xem trên) nên chỉ cần:

1. Đổi ports trong `compose.yml` thành `"${ASF_PORT:-1242}:1242"`
2. `./scripts/down.sh asf && ./scripts/up.sh asf`

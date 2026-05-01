# Dashboard — Homarr

Single pane of glass for the home-server stack. LAN-accessible at `http://<host>:7575`.

## Quick start

```bash
cp .env.example .env
openssl rand -hex 32   # paste into SECRET_ENCRYPTION_KEY in .env
../scripts/up.sh dashboard
```

First boot: open `http://localhost:7575`, complete onboarding (admin user), add apps + boards via UI.

Config persists in `./data/` (bind-mounted to `/appdata` in container — SQLite DB, redis state, certs).

> Homarr v1.x stores config in SQLite (drizzle ORM), not static JSON. tRPC API + bcrypt + encryption layer makes file-level seeding impractical. Setup is one-time via UI; `dashboard-backup.sh` snapshots state for instant recovery.

## Backup / Restore

```bash
../scripts/dashboard-backup.sh                  # snapshot to dashboard/backups/
../scripts/dashboard-restore.sh <backup.tar.gz> # wipe + restore
```

Backup stops dashboard for consistent SQLite snapshot, then restarts (~5s). Output ~2-3MB tar.gz.

## Tiles — App URLs

In Homarr v1.x app form: **Url** = browser click target, **Use different URL for ping** = Homarr container internal probe.

| Service     | Url (click)                  | Ping URL (Homarr container probe)           |
|-------------|------------------------------|---------------------------------------------|
| Jellyfin    | http://localhost:8096        | http://host.containers.internal:8096        |
| Forge UI    | http://localhost:7860        | http://home-forge:7860                      |
| SillyTavern | http://localhost:8000        | http://home-sillytavern:8000                |
| Prowlarr    | http://localhost:9696        | http://host.containers.internal:9696        |
| Sonarr      | http://localhost:8989        | http://host.containers.internal:8989        |
| Radarr      | http://localhost:7878        | http://host.containers.internal:7878        |
| Bazarr      | http://localhost:6767        | http://host.containers.internal:6767        |
| qBittorrent | http://localhost:8080        | http://host.containers.internal:8080        |

**Logic:** Forge + ST share `home-net` with Homarr → resolve via container DNS. Media stack on its own compose network → reach via Podman's `host.containers.internal` host gateway.

## Widget upgrade path (deferred)

Plain "App" widgets are launchpad only. After media stack is set up + integrations configured, upgrade key tiles to specialty widgets for at-a-glance data:

| Service       | Widget upgrade            | Requires                               |
|---------------|---------------------------|----------------------------------------|
| Jellyfin      | Current media server streams | Jellyfin API key                    |
| Prowlarr      | Indexer manager status    | Prowlarr API key                       |
| Sonarr/Radarr | Media releases            | Sonarr + Radarr API keys               |
| qBittorrent   | Download Client           | qBittorrent login                      |

Setup flow: Settings → Integrations → add API key → swap App tile for specialty widget on board.

## VRAM Budget (RTX 4070 Ti Super, 16 GB)

`scripts/vram-guard.sh` enforces these rules before `up.sh` starts a GPU section:

| Section     | Peak load | Hard refuse if free < | Soft warn if free < |
|-------------|-----------|-----------------------|---------------------|
| forge       | ~12 GB    | 2000 MB               | 4000 MB             |
| media       | ~2 GB     | 1000 MB               | —                   |
| sillytavern | 0         | (skipped)             | —                   |
| dashboard   | 0         | (skipped)             | —                   |

Override with `VRAM_GUARD_FORCE=1 ./scripts/up.sh forge` or `--force` flag.

Typical layout: Forge alone fits. Forge + Jellyfin transcode = tight but OK. Don't add a third heavy GPU workload without stopping one.

## Files

- `compose.yml` — Homarr service def, port 7575 on `home-net`. Volume `./data:/appdata:z` (single mount; v1.x uses `/appdata` not `/data`)
- `.env.example` — encryption key template (real `.env` is gitignored)
- `data/` — runtime state (gitignored): `db/db.sqlite`, `redis/`, `trusted-certificates/`
- `backups/` — `*.tar.gz` snapshots from `dashboard-backup.sh` (gitignored — contain secrets)

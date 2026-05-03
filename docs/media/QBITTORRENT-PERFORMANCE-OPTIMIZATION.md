# qBittorrent Performance Optimization

> Configuration for **qBittorrent behind Gluetun (AirVPN WireGuard)** on RTX 4070 Ti SUPER + Ryzen 5 7600X3D + 32GB RAM + NVMe.
> Source of truth: `media/compose.yml` qbittorrent service + `media/.env` AirVPN/PF section.
> Last revised: 2026-05-03.

## TL;DR

The current config targets **500+ concurrent torrents and 1Gbps+ throughput** through an AirVPN WireGuard tunnel. The dominant performance variable isn't qBT itself — it's the VPN tunnel (which is bandwidth-capped by AirVPN's exit nodes) and whether **port forwarding is wired correctly** (currently port 54273, IPv4+IPv6 verified open).

Without PF, you can still download from well-seeded swarms but lose ~30-40% throughput on rare torrents and incur private-tracker ratio penalties.

---

## 1. Network architecture

```
LAN client → host:8080  ─┐
                          ├→ gluetun (network namespace owner)
qBittorrent ──────────────┘
                          │
                          ▼
                  AirVPN WireGuard tunnel
                          │
                          ▼
                  Internet (BitTorrent peers)
```

qBittorrent uses **`network_mode: "container:gluetun"`** — it shares gluetun's network namespace entirely. Consequences:
- All qBT traffic exits via the VPN tunnel; no direct internet access on container interface
- qBT's listening port is reachable from outside *only* via the VPN-side firewall (`FIREWALL_VPN_INPUT_PORTS`)
- LAN access to qBT Web UI on `localhost:8080` works via gluetun's `FIREWALL_INPUT_PORTS=8080` allow-list
- If gluetun crashes, qBT loses network — kill-switch behaviour by design

### 1.1 Port forwarding chain

AirVPN PF requires three things to align:

1. **AirVPN client area** — port allocated per-account (currently 54273, TCP+UDP, IPv4+IPv6). Static; doesn't reset on reconnect.
2. **Gluetun firewall** — `FIREWALL_VPN_INPUT_PORTS=${AIRVPN_FORWARDED_PORT}` opens the port on `tun0` (the WireGuard interface). Verified via `podman logs gluetun | grep "allowed input port"`.
3. **qBittorrent listening port** — must equal AirVPN PF port. Set via API (see §4.2) or UI → Tools → Options → Connection.

If any of the three are misaligned, incoming peer connections are silently dropped. Symptoms: qBT shows `connection_status=firewalled`, AirVPN portchecker shows "Closed" on Test-Open.

### 1.2 Why `VPN_PORT_FORWARDING=false` for AirVPN

Gluetun's `VPN_PORT_FORWARDING=true` only auto-requests ports from providers it has built-in PF support for: Perfect Privacy, PIA, PrivateVPN, ProtonVPN. **Setting `true` for AirVPN crashes gluetun on start** ("port forwarding cannot be enabled"). AirVPN's PF is provisioned via their web UI and exposed automatically on the tunnel — gluetun just needs the firewall hole punched (`FIREWALL_VPN_INPUT_PORTS`).

---

## 2. Current settings (annotated)

### 2.1 Memory + cache (32GB system RAM)
```yaml
- QBT_MEMORY_WORKING_SET_LIMIT=4294967296   # 4GB working set
- QBT_DISK_CACHE=4294967296                 # 4GB disk cache (libtorrent)
- QBT_DISK_WRITE_CACHE_SIZE=64              # 64MB write cache (qBT layer)
- QBT_DISK_WRITE_CACHE_TTL=60               # flush interval (s)
- QBT_CHECKING_MEMORY_USE=512               # 512MB for hash-checking torrents

mem_limit: 8g                # hard cap
mem_reservation: 4g          # guaranteed
shm_size: 1gb
memswap_limit: 8g            # no swap
```

4GB libtorrent disk cache is aggressive — it's what enables sustained 5-10× throughput vs default qBT settings. The 64MB write-cache layer above it batches dirty pages before flushing to NVMe. With NVMe storage, you could drop both lower without much loss; on spinning disks they're load-bearing.

### 2.2 Connection limits
```yaml
- QBT_GLOBAL_MAX_CONNECTIONS=1000           # all torrents combined
- QBT_MAX_CONNECTIONS_PER_TORRENT=100
- QBT_MAX_ACTIVE_DOWNLOADS=10
- QBT_MAX_ACTIVE_UPLOADS=10
- QBT_MAX_ACTIVE_TORRENTS=20                # active = down OR up slot
- QBT_MAX_UPLOADS_PER_TORRENT=20
- QBT_SOCKET_BACKLOG_SIZE=30
- QBT_OUTGOING_PORTS_MIN=6881               # ephemeral source ports
- QBT_OUTGOING_PORTS_MAX=6999

ulimits:
  nofile: { soft: 65536, hard: 65536 }      # plenty for 1000 connections
  nproc:  { soft: 32768, hard: 32768 }
```

1000 concurrent connections is high but reasonable for modern Linux + AirVPN's per-account connection cap (currently 5 simultaneous device connections, but each can multiplex thousands of TCP streams). Don't bump past 2000 — AirVPN's tunnel will throttle aggressive connection spikes.

### 2.3 I/O + threading
```yaml
- QBT_ASYNC_IO_THREADS=8                    # parallel I/O for libtorrent
- QBT_FILE_POOL_SIZE=500                    # open-file cap (mmap'd torrents)
- QBT_DISK_IO_TYPE=1                        # async I/O (vs sync)
- QBT_HASHING_THREADS=2                     # rehash workers
- QBT_COALESCE_READS=true                   # NVMe read coalescing
- QBT_COALESCE_WRITES=true
- QBT_ENABLE_OS_CACHE=true                  # use kernel page cache
- QBT_GUIDED_READ_CACHE=true                # libtorrent read-ahead

cpuset_cpus: "10-11"                        # threads 10-11 (1 physical core)
cpu_shares: 1024                            # half of Jellyfin's 2048
cpus: "1.0"                                 # 1 core time-slice cap
blkio_weight: 500                           # half of Jellyfin's 1000
```

CPU pin to 10-11 isolates qBT from Jellyfin's 0-9 cpuset. The relatively low cpu/blkio weights are intentional: qBT can wait for disk if Jellyfin is transcoding, but Jellyfin should never wait for qBT.

### 2.4 Protocol features
```yaml
- QBT_ENABLE_DHT=true                       # peer discovery without trackers
- QBT_ENABLE_PEX=true                       # peer exchange
- QBT_ENABLE_LSD=true                       # local network discovery
- QBT_ENCRYPTION_STATE=1                    # prefer encrypted (BEP-7)
- QBT_FORCE_PROXY=false
```

Encryption mode 1 = "Prefer encrypted, fall back to plain". Mode 2 = "Required encrypted only" — only set if your tracker requires it (rare); excludes most public swarms.

### 2.5 Network buffers (high-bandwidth tuning)
```yaml
- QBT_SEND_BUFFER_WATERMARK=3145728         # 3MB
- QBT_SEND_BUFFER_LOW_WATERMARK=1048576     # 1MB
- QBT_SEND_SOCKET_BUFFER_SIZE=1048576       # 1MB per-socket
- QBT_RECV_SOCKET_BUFFER_SIZE=1048576
- QBT_CONNECTION_SPEED=0                    # 0 = unlimited new conns/sec
```

These are libtorrent watermarks for fragment buffering. Defaults are smaller (~256KB) and become the bottleneck on >100Mbps connections. Don't push higher — the kernel sysctls (`net.core.rmem_max`) cap the actual buffer size, and those need rootful Podman to bump (commented in compose.yml).

---

## 3. Tuning knobs

### 3.1 Throughput stuck below VPN ceiling
**Symptoms:** AirVPN tunnel rated for 500Mbps but you see 100-150Mbps even on healthy swarms.

Try in order:
1. **Verify PF is actually working** — `connection_status=firewalled` in qBT API → §1.1 chain misaligned
2. **Check VPN exit selection** — `podman exec gluetun wget -qO- https://ipinfo.io` — Singapore exits typically faster from Vietnam than EU
3. **Bump `QBT_DISK_CACHE` to 8GB** (`8589934592`) if you have spare RAM and many active torrents
4. **Raise `QBT_GLOBAL_MAX_CONNECTIONS` to 1500** — only if dozens of torrents active

If you tried all four and still capped at ~150Mbps, the limit is either AirVPN exit congestion or your ISP's QoS — not solvable in qBT.

### 3.2 Many small torrents (private trackers)
**Knobs:**
- `QBT_MAX_ACTIVE_TORRENTS=50` (from 20)
- `QBT_FILE_POOL_SIZE=1500` (from 500)
- `QBT_MAX_CONNECTIONS_PER_TORRENT=50` (down from 100 — diminishing returns per torrent)

The default mix is tuned for ~20 active torrents. For 50-100 active, the file pool needs raising or you'll see `Too many open files` despite the 65536 ulimit.

### 3.3 Low-VRAM coexistence with Forge
**Knob:** `mem_limit: 6g` (down from 8g)

qBT's memory headroom is mostly disk cache. Dropping to 6GB hard cap is safe if you're running Forge SDXL alongside (which wants 12GB VRAM + ~3GB system RAM). Throughput drops <10% from this change.

### 3.4 Spinning-disk media library
If `MEDIA_ROOT` becomes a HDD instead of NVMe (e.g., expanded library to a slow drive):
- Disable `QBT_COALESCE_READS=false` and `QBT_COALESCE_WRITES=false`
- Drop `QBT_ASYNC_IO_THREADS=2` (HDD seek thrashing with 8)
- Bump `QBT_DISK_WRITE_CACHE_SIZE=256` (more buffering before HDD seek)

---

## 4. API control

qBittorrent's `/api/v2` is the reliable way to change settings without UI access. Compose env vars (`QBT_*`) are *defaults at first start* — once the SQLite-backed preferences exist (`./data/qbittorrent/qBittorrent/qBittorrent.conf`), env vars no longer override them. API is the persistent way.

### 4.1 First-run authentication
qBT v4.6+ generates a temporary admin password on first start (no password set). Find it:
```bash
podman logs qbittorrent 2>&1 | grep "temporary password"
# A temporary password is provided for this session: X2Wm96dyp
```

Default user: `admin`. Temp password regenerates on every container recreate until you set a permanent one.

### 4.2 Set listening port to match AirVPN PF
```bash
PORT=54273   # AirVPN forwarded port
USER=admin
PASS=X2Wm96dyp   # temp password from logs

# Login → grab cookie
COOKIE=$(curl -si --data-urlencode "username=$USER" --data-urlencode "password=$PASS" \
  "http://localhost:8080/api/v2/auth/login" \
  | sed -n 's/.*SID=\([^;]*\);.*/\1/p')

# Set port + disable random/UPnP
curl -s -b "SID=$COOKIE" \
  --data-urlencode "json={\"listen_port\":$PORT,\"upnp\":false,\"random_port\":false}" \
  "http://localhost:8080/api/v2/app/setPreferences"

# Verify
curl -s -b "SID=$COOKIE" "http://localhost:8080/api/v2/app/preferences" \
  | python3 -c 'import sys,json; p=json.load(sys.stdin); print(f"port={p[\"listen_port\"]} upnp={p[\"upnp\"]}")'
```

### 4.3 Set permanent admin password
Via UI: Tools → Options → Web UI → set Username/Password → Save.

Via API:
```bash
curl -s -b "SID=$COOKIE" \
  --data-urlencode 'json={"web_ui_username":"newuser","web_ui_password":"newpass"}' \
  "http://localhost:8080/api/v2/app/setPreferences"
```

After change, restart container: `./scripts/down.sh media && ./scripts/up.sh media`.

### 4.4 Bulk pause / resume (maintenance windows)
```bash
# Pause all
curl -b "SID=$COOKIE" "http://localhost:8080/api/v2/torrents/pause?hashes=all"
# Resume all
curl -b "SID=$COOKIE" "http://localhost:8080/api/v2/torrents/resume?hashes=all"
```

Useful before VPN provider maintenance or qBT version upgrades.

---

## 5. VPN integration verification

### 5.1 External IP
```bash
podman exec gluetun wget -qO- https://ipinfo.io
# Expect:
#   "ip": "146.70.67.50"           — AirVPN exit, NOT your home IP
#   "country": "SG"                 — matches AIRVPN_SERVER_COUNTRIES
#   "org": "AS9009 M247 Europe SRL" — AirVPN's upstream
```

If the IP matches your home WAN: qBT is leaking. Check `network_mode: container:gluetun` is set on qBT service.

### 5.2 Port forwarding test
**Live test (qBT-side):**
```bash
curl -s -b "SID=$COOKIE" "http://localhost:8080/api/v2/transfer/info" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["connection_status"])'
# Expect "connected" once peers actually connect inbound
# "firewalled" on cold start is normal — flips to "connected" after ~30s with active torrents
```

**External test (AirVPN-side):**
1. airvpn.org → Client Area → Forwarded Ports
2. Click "Test open" next to your port
3. Expected: TCP IPv4 = Open, TCP IPv6 = Open (UDP shows no badge — no clean handshake)

### 5.3 Why upnp/random_port = false

- **UPnP off**: behind a VPN tunnel, UPnP makes no sense. The tunnel endpoint is AirVPN's gateway, which doesn't speak UPnP from the LAN side.
- **random_port off**: qBT default re-randomizes listen port on every restart. AirVPN PF is per-port; randomizing breaks the chain on every restart.

---

## 6. Anti-patterns

### Don't enable rootful sysctls without measuring first
The compose.yml has commented-out sysctls (`net.core.rmem_max=16777216`, `tcp_congestion_control=bbr`, etc.). These require rootful Podman. They help if you're already saturating defaults — but rootless defaults (`rmem_max=212992`) are fine for AirVPN's per-account cap. Enabling them adds privilege scope without proportional throughput gain.

### Don't run more torrents than your ratio rules allow
`QBT_MAX_ACTIVE_TORRENTS=20` isn't a "more is better" knob. Private trackers care about ratio per torrent; spreading thin = bad ratio per torrent. Public torrents don't care, but seeding bandwidth gets fragmented.

### Don't disable encryption "for speed"
`QBT_ENCRYPTION_STATE=0` (allow plaintext) gains negligible CPU on this hardware. Encryption is per-connection at the BitTorrent protocol layer (BEP-7), not per-byte; it's free.

### Don't set `random_port=true` when using AirVPN PF
If you toggle this in the UI by mistake, qBT starts ignoring `listen_port` and picks ephemeral ports. AirVPN PF only forwards the configured port, so peer connections silently fail. Always re-verify after editing UI prefs.

### Don't `podman exec qbittorrent rm -rf /downloads/X` to clean torrents
The `/downloads` mount is owned by the LSCR linuxserver UID inside the container. From the host, those files have container UID ownership (mapped via subuid). Use `podman unshare rm -rf media/data/qbittorrent/...` on the host, OR delete from qBT UI (which removes via container UID).

### Don't restart gluetun without restarting qBT
qBT's connections live in gluetun's namespace. If gluetun restarts, qBT's sockets become stale but qBT doesn't always notice — connections show "active" but stalled. Always recycle the pair: `./scripts/down.sh media && ./scripts/up.sh media`.

---

## 7. Reference: env vars

From `media/.env`:

| Var | Purpose |
|-----|---------|
| `AIRVPN_FORWARDED_PORT` | Port to forward (54273) — referenced by `FIREWALL_VPN_INPUT_PORTS` |
| `AIRVPN_PORT_FORWARDING` | **Must be `false`** for AirVPN (gluetun limitation) |
| `QBIT_USER` / `QBIT_PASS` | Documented credentials — currently informational only (LSCR image doesn't auto-apply; set via UI/API) |

From `media/compose.yml` qbittorrent service: see §2 above for full annotated list of `QBT_*` vars.

---

## 8. Operational quickref

```bash
# Start / stop
./scripts/up.sh media
./scripts/down.sh media

# Logs
./scripts/logs.sh media -f qbittorrent

# Health
podman ps --filter name=qbittorrent
podman exec gluetun wget -qO- https://ipinfo.io        # verify VPN
curl http://localhost:8080                              # WebUI reachable

# Reset password (lost it)
./scripts/down.sh media && rm -rf media/data/qbittorrent/qBittorrent/qBittorrent.conf
./scripts/up.sh media
podman logs qbittorrent | grep "temporary password"
```

---

## See also
- `../INDEX.md` — current home-server doc index
- `../AIRVPN-VALIDATION-CHECKLIST.md` — full AirVPN setup + 4 chain-bug gotchas
- `../../media/compose.yml` — qbittorrent service definition
- `../../media/.env` — AirVPN credentials + PF port
- `JELLYFIN-PERFORMANCE-OPTIMIZATION.md` — sibling doc, same hardware

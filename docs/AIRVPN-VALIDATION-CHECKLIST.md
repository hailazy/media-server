# AirVPN + Gluetun Validation Checklist

> **For:** verifying media stack VPN setup after first install or after re-creating `media/.env`.
> **Source of truth:** `media/compose.yml` gluetun service + `media/.env`.
> **Last revised:** 2026-05-03 (post chain-bug fix in commit `0238a98`).

The 4 chain-bug section below is the failure mode that motivated this rewrite — **read it first** if your gluetun container is restart-looping.

---

## ⚠️ The 4 chain bugs (read first)

Every gluetun start failure I've seen on this stack is one of these four. They surface one at a time on each retry, so fixing one reveals the next.

### 1. `WIREGUARD_PRESHARED_KEY` is mandatory for AirVPN

Symptom: `ERROR VPN settings: Wireguard settings: pre-shared key is not set`

AirVPN's WireGuard configs **always** include a PSK in the `[Peer]` section. Older guides claim AirVPN doesn't use PSKs — that's wrong. Gluetun rejects empty PSKs with the same error as missing.

Fix:
1. Open your AirVPN WireGuard config file (e.g., `~/Downloads/AirVPN_Singapore_UDP-1637-Entry3.conf`)
2. Copy the `PresharedKey = ...` value from the `[Peer]` section
3. Set `AIRVPN_WIREGUARD_PRESHARED_KEY=<value>` in `media/.env`
4. Confirm `compose.yml` has `- WIREGUARD_PRESHARED_KEY=${AIRVPN_WIREGUARD_PRESHARED_KEY}` in gluetun env

### 2. `AIRVPN_SERVER_COUNTRIES` uses full names, not ISO codes

Symptom: `ERROR VPN settings: ... country specified is not valid: ... none of sg is one of the choices available Austria, Belgium, ..., Singapore, ...`

Gluetun's AirVPN provider expects full country names. ISO codes (`SG`, `JP`) are rejected.

Valid values (current list as of 2026-05): Austria, Belgium, Brazil, Bulgaria, Canada, Czech Republic, Estonia, Germany, Ireland, Japan, Latvia, Netherlands, New Zealand, Norway, Romania, Serbia, Singapore, Spain, Sweden, Switzerland, Taiwan, United Kingdom, United States.

Fix: `AIRVPN_SERVER_COUNTRIES=Singapore` (NOT `SG`). Multiple = comma-separated: `Singapore,Japan,Taiwan`.

### 3. `AIRVPN_PORT_FORWARDING` must be `false` for AirVPN

Symptom: `ERROR VPN settings: provider settings: port forwarding: port forwarding cannot be enabled: value is not one of the possible choices: airvpn must be one of perfect privacy, private internet access, privatevpn or protonvpn`

Gluetun's `VPN_PORT_FORWARDING=on` only works for providers gluetun can auto-request ports from: Perfect Privacy, PIA, PrivateVPN, ProtonVPN. AirVPN does PF differently — you allocate the port via airvpn.org client area, then open it in the gluetun firewall (see §3 below).

Fix: `AIRVPN_PORT_FORWARDING=false`. PF still works; gluetun just doesn't auto-request.

### 4. Hardcoded paths in compose.yml override `.env`

Not a gluetun error per se, but a frequent companion bug. Symptom: containers start, mount fails (`/media/Storage/tv-shows: No such file or directory`).

The first version of `compose.yml` had hardcoded `/media/Storage/...` paths instead of `${TV_PATH}` etc. from `.env`. This was fixed in commit `0238a98`. If you see hardcoded paths reappear (e.g., from a merge), restore env-var refs.

---

## Pre-flight checklist

Run these before `./scripts/up.sh media` for the first time or after editing `.env`.

### `media/.env` is complete

```bash
grep -E '^AIRVPN_(WIREGUARD_(PRIVATE|PRESHARED|ADDRESSES)|SERVER|PORT|FORWARDED)' media/.env
```

Expected (with values, not these placeholders):
```
AIRVPN_WIREGUARD_PRIVATE_KEY=<base64, 44 chars + =>
AIRVPN_WIREGUARD_ADDRESSES=<IPv4>/32,<IPv6>/128
AIRVPN_WIREGUARD_PRESHARED_KEY=<base64, 44 chars + =>
AIRVPN_SERVER_COUNTRIES=Singapore
AIRVPN_PORT_FORWARDING=false
AIRVPN_FORWARDED_PORT=<port from airvpn.org/ports>
```

### Validate key formats

```bash
# Source the env to access vars in shell
set -a; source media/.env; set +a

# WireGuard private key: 44-char base64 ending with =
[[ ${#AIRVPN_WIREGUARD_PRIVATE_KEY} -eq 44 ]] && echo "✓ private key length" || echo "✗ private key length"

# Preshared key: same shape
[[ ${#AIRVPN_WIREGUARD_PRESHARED_KEY} -eq 44 ]] && echo "✓ PSK length" || echo "✗ PSK length"

# Addresses: IPv4 + IPv6
echo "$AIRVPN_WIREGUARD_ADDRESSES" | grep -qE '^[0-9.]+/32,[0-9a-f:]+/128$' && echo "✓ addresses format" || echo "✗ addresses format"
```

### Compose env references match

```bash
grep -E '\$\{AIRVPN_' media/compose.yml
```

Should reference each var defined in `.env`. If `.env` defines `AIRVPN_FOO=` but `compose.yml` references `${AIRVPN_BAR}`, the shell expands to empty — gluetun then sees an empty value and may fail validation (case-by-case).

---

## Port forwarding setup (3 steps, all must align)

AirVPN PF is manual — gluetun won't do it for you. The three things below must all match the same port number.

### Step 1: Allocate port at AirVPN

1. Login at airvpn.org
2. Client Area → **Forwarded Ports**
3. Click **Add** — pick a port (random or specific). Stays per-account, doesn't reset on reconnect.
4. Note the assigned port (e.g., `54273`).

### Step 2: Open the port in gluetun firewall

In `media/.env`:
```env
AIRVPN_FORWARDED_PORT=54273
```

In `media/compose.yml` gluetun env (already set):
```yaml
- FIREWALL_VPN_INPUT_PORTS=${AIRVPN_FORWARDED_PORT}
```

This opens the port on `tun0` (the WireGuard interface). Verify after start:
```bash
podman logs gluetun | grep "allowed input port"
# Expected:
#   ... setting allowed input port 8080 through interface eth0...   ← Web UI from LAN
#   ... setting allowed input port 54273 through interface tun0...  ← BitTorrent peers via VPN
```

> Note: `FIREWALL_INPUT_PORTS=8080` (eth0, LAN) is different from `FIREWALL_VPN_INPUT_PORTS` (tun0, VPN). Putting the BitTorrent port in the wrong one = silently broken.

### Step 3: Set qBittorrent listening port

```bash
PORT=54273
USER=admin
PASS=$(podman logs qbittorrent 2>&1 | grep -oP "temporary password is provided for this session: \K\S+")

COOKIE=$(curl -si --data-urlencode "username=$USER" --data-urlencode "password=$PASS" \
  http://localhost:8080/api/v2/auth/login | sed -n 's/.*SID=\([^;]*\);.*/\1/p')

curl -s -b "SID=$COOKIE" \
  --data-urlencode "json={\"listen_port\":$PORT,\"upnp\":false,\"random_port\":false}" \
  http://localhost:8080/api/v2/app/setPreferences

# Verify
curl -s -b "SID=$COOKIE" http://localhost:8080/api/v2/app/preferences | \
  python3 -c 'import sys,json; p=json.load(sys.stdin); print(f"listen_port={p[\"listen_port\"]} upnp={p[\"upnp\"]} random_port={p[\"random_port\"]}")'
```

`upnp` and `random_port` must be false — UPnP makes no sense behind a VPN, and random_port breaks the chain on every restart.

---

## Verify end-to-end

After `./scripts/up.sh media`:

### 1. All 8 containers healthy

```bash
podman ps --format "{{.Names}}: {{.Status}}" \
  | grep -E "flaresolverr|prowlarr|sonarr|radarr|bazarr|gluetun|qbittorrent|jellyfin"
```

Expected: all show `(healthy)`. Cold-start order: gluetun → qbittorrent (depends on gluetun health) → bazarr/jellyfin. Total time ~60-90s.

### 2. VPN tunnel is AirVPN, not your home WAN

```bash
podman exec gluetun wget -qO- https://ipinfo.io
```

Expected:
```json
{
  "ip": "146.70.67.50",
  "country": "SG",
  "org": "AS9009 M247 Europe SRL",     ← AirVPN's upstream
  ...
}
```

If the IP matches your home WAN, qBittorrent is leaking. Check that qbittorrent has `network_mode: "container:gluetun"` in compose.yml.

### 3. PF is open from outside

Two ways:

**AirVPN's portchecker** (canonical):
- airvpn.org → Client Area → Forwarded Ports
- Click **Test open** next to your port
- Expected: TCP IPv4 = **Open!**, TCP IPv6 = **Open!**, UDP shows no badge (UDP has no clean handshake — normal).

**qBittorrent connection_status:**
```bash
curl -s -b "SID=$COOKIE" http://localhost:8080/api/v2/transfer/info \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["connection_status"])'
```
Cold start: `firewalled` (normal). After ~30s with active torrents: `connected`.

### 4. Kill-switch works

```bash
podman stop gluetun
podman exec qbittorrent curl -s --connect-timeout 5 https://ipinfo.io
# Expected: timeout / connection refused (qBT can't reach internet without gluetun)
podman start gluetun
```

This proves `network_mode: "container:gluetun"` is enforcing isolation. If qBT *can* reach internet without gluetun, you have a leak.

---

## Troubleshooting

### `WIREGUARD_PRIVATE_KEY` rejected as invalid

```bash
echo -n "$AIRVPN_WIREGUARD_PRIVATE_KEY" | wc -c   # must be 44
echo "$AIRVPN_WIREGUARD_PRIVATE_KEY" | base64 -d | wc -c   # must be 32
```
If wrong: regenerate config from airvpn.org Config Generator. Don't transcribe by hand — copy from the `.conf` file.

### Connection times out (no error from gluetun)

```bash
# AirVPN status page
curl -s https://airvpn.org/status/ | head -50

# Test UDP connectivity (WireGuard uses UDP, not TCP)
podman exec gluetun nc -u -z -v sg3.vpn.airdns.org 1637 2>&1 | tail -5
```

ISP UDP throttling is rare but possible. Try a different country: `AIRVPN_SERVER_COUNTRIES=Japan,Taiwan`.

### qBittorrent webUI shows "firewalled" indefinitely

The chain (AirVPN port → `FIREWALL_VPN_INPUT_PORTS` → qBT listen port) has a mismatch.

```bash
# Confirm gluetun opened the port on tun0 (not eth0)
podman logs gluetun | grep "input port .* tun0"

# Confirm qBT is listening
podman exec qbittorrent ss -tlnp 2>/dev/null | grep $AIRVPN_FORWARDED_PORT \
  || podman exec gluetun netstat -ln | grep $AIRVPN_FORWARDED_PORT

# Confirm qBT prefs match
curl -s -b "SID=$COOKIE" http://localhost:8080/api/v2/app/preferences \
  | python3 -c 'import sys,json; p=json.load(sys.stdin); print(p["listen_port"])'
```

If all three match and AirVPN portchecker still shows Closed: try removing + re-adding the port at airvpn.org.

### Gluetun env changes don't take effect

`podman restart gluetun` does NOT re-read `.env`. Env vars are baked at container creation. To apply changes:

```bash
./scripts/down.sh media && ./scripts/up.sh media
```

This recreates the container with new env values.

---

## See also

- [QUICK-REF.md](QUICK-REF.md) — daily commands
- [media/QBITTORRENT-PERFORMANCE-OPTIMIZATION.md](media/QBITTORRENT-PERFORMANCE-OPTIMIZATION.md) — qBT API control, network architecture
- `media/.env.example` — annotated env template (in-file docs explain each var)
- AirVPN docs — https://airvpn.org/faq/
- Gluetun docs (AirVPN) — https://github.com/qdm12/gluetun-wiki/blob/main/setup/providers/airvpn.md

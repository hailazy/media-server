# AirVPN Configuration Validation & Testing Plan

## ⚠️ CRITICAL ISSUES IDENTIFIED

### 🚨 **BLOCKER ISSUES - MUST FIX BEFORE STARTING**

#### 1. **Environment Variable Mismatch (CRITICAL)**
- **Problem**: Current [`core/.env`](../core/.env:1) contains PIA credentials, but [`core/podman-compose.yml`](../core/podman-compose.yml:165) is configured for AirVPN
- **Impact**: VPN will fail to connect, entire stack will be non-functional
- **Fix Required**: Update `.env` file with AirVPN credentials from `.env.example`

#### 2. **Hard-coded Placeholder Values (CRITICAL)**
- **Problem**: [`podman-compose.yml`](../core/podman-compose.yml:200-201) contains literal placeholder text:
  ```yaml
  - WIREGUARD_PRIVATE_KEY=YOUR_PRIVATE_KEY_HERE
  - WIREGUARD_ADDRESSES=YOUR_VPN_IP_ADDRESS_HERE
  ```
- **Impact**: Gluetun will fail to start with invalid credentials
- **Fix Required**: Replace with environment variable references

#### 3. **Missing Environment Variable Integration (CRITICAL)**
- **Problem**: [`podman-compose.yml`](../core/podman-compose.yml:165) doesn't use environment variables from `.env` file
- **Impact**: Configuration changes require editing YAML instead of just `.env`
- **Fix Required**: Implement `${VARIABLE}` substitution pattern

---

## 📋 PRE-FLIGHT VALIDATION CHECKLIST

### Phase 1: Configuration File Validation

#### ✅ **YAML Syntax** *(PASSED)*
- [x] [`podman-compose.yml`](../core/podman-compose.yml:1) has valid YAML syntax
- [x] All service definitions are properly structured
- [x] No syntax errors detected

#### ❌ **Environment Variable Consistency** *(FAILED)*
- [ ] **CRITICAL**: `.env` file uses AirVPN variables instead of PIA
- [ ] **CRITICAL**: `podman-compose.yml` uses environment variable references instead of hard-coded values
- [ ] All required AirVPN variables are defined in `.env`
- [ ] No orphaned PIA variables remain in configuration

#### ❌ **AirVPN Configuration Completeness** *(FAILED)*
Required variables missing or incorrect:
- [ ] `AIRVPN_WIREGUARD_PRIVATE_KEY` - Currently missing from `.env`
- [ ] `AIRVPN_WIREGUARD_ADDRESSES` - Currently missing from `.env`
- [ ] `AIRVPN_SERVER_COUNTRIES` - Currently missing from `.env`
- [ ] `AIRVPN_PORT_FORWARDING` - Currently missing from `.env`

#### ✅ **Service Dependencies** *(PASSED)*
- [x] [`qbittorrent`](../core/podman-compose.yml:243) properly depends on [`gluetun`](../core/podman-compose.yml:167) with health condition
- [x] [`sonarr`](../core/podman-compose.yml:94) and [`radarr`](../core/podman-compose.yml:124) depend on [`prowlarr`](../core/podman-compose.yml:52)
- [x] [`bazarr`](../core/podman-compose.yml:152) depends on both [`sonarr`](../core/podman-compose.yml:78) and [`radarr`](../core/podman-compose.yml:108)
- [x] [`jellyfin`](../core/podman-compose.yml:293) depends on [`sonarr`](../core/podman-compose.yml:78) and [`radarr`](../core/podman-compose.yml:108)

#### ⚠️ **Port & Network Configuration** *(NEEDS REVIEW)*
- [x] [`gluetun`](../core/podman-compose.yml:213) exposes port `8080:8080`
- [x] [`qbittorrent`](../core/podman-compose.yml:233) uses `network_mode: "container:gluetun"`
- [x] [`FIREWALL_INPUT_PORTS=8080`](../core/podman-compose.yml:181) configured
- [x] [`VPN_PORT_FORWARDING=on`](../core/podman-compose.yml:185) enabled
- [ ] **REVIEW NEEDED**: Static port 8080 may conflict with AirVPN's dynamic port forwarding

---

## 🔧 REQUIRED FIXES

### Fix 1: Update Environment Configuration

**Create new `.env` file based on `.env.example`:**

```bash
# Backup current configuration
cp core/.env core/.env.pia-backup

# Copy AirVPN template
cp core/.env.example core/.env

# Edit with your actual AirVPN credentials
nano core/.env
```

**Required updates in `.env`:**
```bash
# Replace these with your actual AirVPN values
AIRVPN_WIREGUARD_PRIVATE_KEY=your_actual_private_key_here
AIRVPN_WIREGUARD_ADDRESSES=your_actual_addresses_here
AIRVPN_SERVER_COUNTRIES=SG,HK,JP
AIRVPN_PORT_FORWARDING=true

# Update credentials
QBIT_USER=your_username
QBIT_PASS=your_secure_password

# Keep existing working values
TZ=Asia/Ho_Chi_Minh
PUID=1000
PGID=1000
MEDIA_ROOT=/media/Storage
```

### Fix 2: Update podman-compose.yml for Environment Variable Integration

**Replace hard-coded values in [`gluetun`](../core/podman-compose.yml:165) service:**

```yaml
environment:
  # Replace hard-coded values with environment variables
  - WIREGUARD_PRIVATE_KEY=${AIRVPN_WIREGUARD_PRIVATE_KEY}
  - WIREGUARD_ADDRESSES=${AIRVPN_WIREGUARD_ADDRESSES}
  - SERVER_COUNTRIES=${AIRVPN_SERVER_COUNTRIES:-SG}
  - VPN_PORT_FORWARDING=${AIRVPN_PORT_FORWARDING:-on}
  
  # Keep existing configuration
  - VPN_SERVICE_PROVIDER=airvpn
  - VPN_TYPE=wireguard
  - FIREWALL=on
  - FIREWALL_INPUT_PORTS=8080
  - LOG_LEVEL=${DEBUG:+debug}${DEBUG:-info}
```

---

## 🧪 COMPREHENSIVE TESTING PLAN

### Phase 1: Pre-Start Validation

#### Step 1.1: Validate Configuration Files
```bash
# Verify YAML syntax
cd core
python3 -c "import yaml; yaml.safe_load(open('podman-compose.yml')); print('✅ YAML valid')"

# Check for placeholder values
grep -n "YOUR_.*_HERE" podman-compose.yml
# Should return no results after fixes

# Verify environment variables exist
grep -E "^AIRVPN_" .env
# Should show all required AirVPN variables
```

#### Step 1.2: Validate AirVPN Credentials
```bash
# Test WireGuard private key format (should be 44 characters base64)
echo $AIRVPN_WIREGUARD_PRIVATE_KEY | wc -c
# Should output: 45 (44 chars + newline)

# Test address format (should contain both IPv4 and IPv6)
echo $AIRVPN_WIREGUARD_ADDRESSES | grep -E "^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/[0-9]+,"
# Should match IPv4 format
```

#### Step 1.3: Validate File Permissions
```bash
# Check media directory permissions
ls -la /media/Storage/
# Should show proper ownership (PUID:PGID)

# Check config directory
ls -la ../configs/
# Should be writable by containers
```

### Phase 2: VPN Connection Testing

#### Step 2.1: Start VPN Container Only
```bash
# Start only gluetun for initial testing
cd core
podman-compose up -d gluetun

# Monitor startup logs
podman-compose logs -f gluetun
```

**Expected Success Indicators:**
- ✅ `WireGuard configuration loaded successfully`
- ✅ `Connected to AirVPN server`
- ✅ `Public IP: [AirVPN IP address]`
- ✅ `Port forwarding enabled on port: [dynamic_port]`

**Failure Indicators:**
- ❌ `Authentication failed`
- ❌ `Invalid private key`
- ❌ `Connection timeout`
- ❌ `DNS resolution failed`

#### Step 2.2: Test VPN Connectivity
```bash
# Test from within gluetun container
podman exec gluetun curl -s ipinfo.io
# Should show AirVPN server IP, not your real IP

# Test port forwarding status
podman exec gluetun curl -s localhost:9999/portforwarded
# Should return the forwarded port number
```

#### Step 2.3: Test DNS Resolution
```bash
# Test DNS resolution through VPN
podman exec gluetun nslookup google.com
# Should resolve successfully

# Test blocked sites (if geo-blocking test is relevant)
podman exec gluetun curl -I https://www.netflix.com
# Should connect (response may vary by region)
```

### Phase 3: qBittorrent Integration Testing

#### Step 3.1: Start qBittorrent
```bash
# Start qBittorrent (depends on gluetun)
podman-compose up -d qbittorrent

# Check dependency satisfaction
podman-compose logs qbittorrent
```

#### Step 3.2: Test Network Isolation
```bash
# Verify qBittorrent uses VPN IP
podman exec qbittorrent curl -s ipinfo.io
# Should show same IP as gluetun container

# Test that qBittorrent can't access internet without VPN
podman stop gluetun
podman exec qbittorrent curl -s --connect-timeout 5 ipinfo.io
# Should fail/timeout (proving network isolation)

# Restart gluetun
podman-compose up -d gluetun
```

#### Step 3.3: Test qBittorrent Web Interface
```bash
# Wait for qBittorrent to be ready
sleep 30

# Test web interface accessibility
curl -I http://localhost:8080
# Should return HTTP 200 or redirect

# Test with credentials
curl -c cookies.txt -d "username=${QBIT_USER}&password=${QBIT_PASS}" \
  http://localhost:8080/api/v2/auth/login
# Should return "Ok."
```

### Phase 4: Port Forwarding Validation

#### Step 4.1: Verify Dynamic Port Assignment
```bash
# Get the assigned port from gluetun
FORWARDED_PORT=$(podman exec gluetun cat /tmp/gluetun/forwarded_port)
echo "Forwarded port: $FORWARDED_PORT"

# Verify port is open
podman exec gluetun nc -zv localhost $FORWARDED_PORT
# Should connect successfully
```

#### Step 4.2: Update qBittorrent Port Configuration
```bash
# Update qBittorrent to use the forwarded port
curl -X POST -b cookies.txt \
  -d "json={\"listen_port\":$FORWARDED_PORT}" \
  http://localhost:8080/api/v2/app/setPreferences

# Verify the change
curl -b cookies.txt http://localhost:8080/api/v2/app/preferences | \
  grep -o '"listen_port":[0-9]*'
```

### Phase 5: Full Stack Testing

#### Step 5.1: Start All Services
```bash
# Start complete stack
podman-compose up -d

# Verify all services are healthy
podman-compose ps
# All services should show "Up" status
```

#### Step 5.2: Test Service Accessibility
```bash
# Test all web interfaces
curl -I http://localhost:9696  # Prowlarr
curl -I http://localhost:8989  # Sonarr
curl -I http://localhost:7878  # Radarr
curl -I http://localhost:6767  # Bazarr
curl -I http://localhost:8080  # qBittorrent (via VPN)
curl -I http://localhost:8096  # Jellyfin
```

#### Step 5.3: Test End-to-End Functionality
```bash
# Add a test indexer in Prowlarr (manual step)
# Configure Sonarr/Radarr to use Prowlarr (manual step)
# Test a download (manual step)
# Verify files appear in media directories (manual step)
```

---

## 🚨 TROUBLESHOOTING GUIDE

### Common AirVPN Issues

#### Issue: "Authentication failed"
**Diagnosis:**
```bash
# Check credential format
echo "Private key length: $(echo $AIRVPN_WIREGUARD_PRIVATE_KEY | wc -c)"
echo "Addresses format: $AIRVPN_WIREGUARD_ADDRESSES"
```
**Solutions:**
- Regenerate WireGuard config from AirVPN client area
- Verify copy/paste didn't introduce extra characters
- Check account status at https://airvpn.org/

#### Issue: "Connection timeout"
**Diagnosis:**
```bash
# Test connectivity to AirVPN servers
ping -c 3 singapore.airdns.org
curl -I https://airvpn.org/status/
```
**Solutions:**
- Try different server countries: `AIRVPN_SERVER_COUNTRIES=HK,JP,KR`
- Check firewall rules blocking WireGuard (UDP 51820)
- Verify network connectivity

#### Issue: "Port forwarding not working"
**Diagnosis:**
```bash
# Check if port forwarding is enabled in AirVPN account
podman exec gluetun curl -s localhost:9999/portforwarded
# Should return a port number, not error
```
**Solutions:**
- Enable port forwarding in AirVPN client area
- Verify `AIRVPN_PORT_FORWARDING=true` in `.env`
- Check gluetun logs for port forwarding messages

#### Issue: "qBittorrent can't connect"
**Diagnosis:**
```bash
# Test network isolation
podman exec qbittorrent ip route
# Should show routes through gluetun

# Test VPN IP
podman exec qbittorrent curl -s ipinfo.io
# Should match gluetun IP
```

### Container-Specific Issues

#### Gluetun Fails to Start
```bash
# Check capabilities and devices
podman inspect gluetun | grep -A 5 -B 5 "CapAdd\|Devices"

# Check SELinux context
ls -Z /dev/net/tun
# Should show proper labeling
```

#### qBittorrent Web Interface Inaccessible
```bash
# Check if container is running
podman ps | grep qbittorrent

# Check port binding
podman port qbittorrent
# Note: No direct ports due to network_mode=container:gluetun

# Test through gluetun
podman exec gluetun curl -I localhost:8080
```

---

## 📊 VALIDATION COMMANDS SUMMARY

### Quick Health Check Script
```bash
#!/bin/bash
# Save as: validate-airvpn.sh

echo "=== AirVPN Configuration Validation ==="

# 1. Check environment variables
echo "1. Checking environment variables..."
if [ -z "$AIRVPN_WIREGUARD_PRIVATE_KEY" ]; then
    echo "❌ AIRVPN_WIREGUARD_PRIVATE_KEY not set"
else
    echo "✅ AIRVPN_WIREGUARD_PRIVATE_KEY configured"
fi

# 2. Check containers
echo "2. Checking container status..."
podman-compose ps

# 3. Check VPN connection
echo "3. Checking VPN connection..."
VPN_IP=$(podman exec gluetun curl -s ipinfo.io/ip 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "✅ VPN connected: $VPN_IP"
else
    echo "❌ VPN connection failed"
fi

# 4. Check port forwarding
echo "4. Checking port forwarding..."
FORWARDED_PORT=$(podman exec gluetun curl -s localhost:9999/portforwarded 2>/dev/null)
if [ $? -eq 0 ] && [ "$FORWARDED_PORT" != "0" ]; then
    echo "✅ Port forwarding active: $FORWARDED_PORT"
else
    echo "❌ Port forwarding not working"
fi

# 5. Check qBittorrent
echo "5. Checking qBittorrent..."
QB_STATUS=$(curl -s -I http://localhost:8080 | head -n1)
if echo "$QB_STATUS" | grep -q "200\|302"; then
    echo "✅ qBittorrent accessible"
else
    echo "❌ qBittorrent not accessible"
fi

echo "=== Validation Complete ==="
```

### Emergency Rollback
```bash
# If AirVPN migration fails, rollback to PIA
cp core/.env.pia-backup core/.env
git checkout core/podman-compose.yml  # If you had PIA version in git
podman-compose down
podman-compose up -d
```

---

## 📋 FINAL CHECKLIST

Before declaring the migration successful, verify:

- [ ] **Configuration**: All placeholder values replaced with actual credentials
- [ ] **VPN Connection**: Gluetun successfully connects to AirVPN
- [ ] **IP Verification**: Public IP shows AirVPN server, not real IP
- [ ] **Port Forwarding**: Dynamic port assigned and accessible
- [ ] **qBittorrent**: Web interface accessible and using VPN IP
- [ ] **Network Isolation**: qBittorrent fails when VPN is down
- [ ] **Media Services**: All *arr services start and are accessible
- [ ] **Download Test**: Can successfully download a test torrent
- [ ] **File Management**: Downloaded files appear in correct directories
- [ ] **Performance**: Download speeds are acceptable through VPN

## 🎯 SUCCESS CRITERIA

The migration is successful when:

1. ✅ All containers start without errors
2. ✅ qBittorrent shows AirVPN IP address
3. ✅ Port forwarding is working (check in qBittorrent status)
4. ✅ Test download completes successfully
5. ✅ All web interfaces are accessible
6. ✅ No network leaks when VPN restarts

**Estimated Migration Time**: 30-60 minutes (depending on troubleshooting needs)
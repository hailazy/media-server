# Media Stack Quick Reference - Roocline Optimization

**🎯 RAPID CONTEXT**: Podman-based media automation stack with VPN protection, automated downloads, and media streaming. All traffic routed through AirVPN with static WireGuard configuration.

## 📖 Project Overview

**What it does**: Complete automated media pipeline from search → download → organize → stream, all through secure VPN tunnel.

**Core Tech Stack**: Podman containers + AirVPN (WireGuard) + qBittorrent + Sonarr/Radarr + Jellyfin + static port forwarding.

**Key Innovation**: Static AirVPN WireGuard configuration from Config Generator, eliminating dynamic config generation complexity.

---

## 🎯 Critical File Priority (READ FIRST)

### **🔥 ESSENTIAL** (Start here for any issue)
1. **[`core/podman-compose.yml`](../core/podman-compose.yml:1)** - Main service definitions, dependencies, networking
2. **[`core/.env`](../core/.env)** / **[`core/.env.example`](../core/.env.example:1)** - All configuration variables (AirVPN creds, ports, paths)
3. **[`maintenance/maintenance.sh`](../maintenance/maintenance.sh:1)** - Comprehensive debugging tool (`./maintenance/maintenance.sh health`)

### **🔧 OPERATIONAL** (Daily use)
4. **[`scripts/podman-up.sh`](../scripts/podman-up.sh)** - Stack startup script
5. **[`maintenance/quick-debug.sh`](../maintenance/quick-debug.sh)** - Fast troubleshooting
6. **[`scripts/podman-logs.sh`](../scripts/podman-logs.sh)** - Log viewing utility

### **📚 CONTEXTUAL** (Reference when needed)
7. **[`docs/README.md`](../docs/README.md:1)** - Complete documentation (996 lines)
8. **[`docs/PODMAN.md`](../docs/PODMAN.md:1)** - Podman-specific setup guide
9. **[`docs/AIRVPN-VALIDATION-CHECKLIST.md`](../docs/AIRVPN-VALIDATION-CHECKLIST.md:1)** - AirVPN validation guide
10. **[`services/gluetun/servers.json`](../services/gluetun/servers.json:1)** - AirVPN server configurations

---

## ⚡ Essential Commands

### **Core Operations**
```bash
# Start entire stack
./scripts/podman-up.sh

# Stop stack  
./scripts/podman-down.sh

# View all logs
./scripts/podman-logs.sh

# Health check (MOST IMPORTANT)
./maintenance/maintenance.sh health
```

### **Debug & Troubleshooting**
```bash
# Enable debug mode
./maintenance/maintenance.sh debug-enable

# Quick health check
./maintenance/quick-debug.sh

# VPN troubleshooting
./maintenance/maintenance.sh troubleshoot-vpn

# Full diagnostic collection
./maintenance/maintenance.sh diagnostic
```

### **Manual Podman Commands**
```bash
# Start with compose
podman-compose -f core/podman-compose.yml up -d

# View specific service logs
podman-compose -f core/podman-compose.yml logs -f gluetun

# Check service status
podman-compose -f core/podman-compose.yml ps

# Test VPN IP
podman-compose -f core/podman-compose.yml exec gluetun wget -qO- https://ipinfo.io
```

### **Emergency/Recovery**
```bash
# Restart VPN service
podman-compose -f core/podman-compose.yml restart gluetun

# Full restart with fresh configs
podman-compose -f core/podman-compose.yml down && podman-compose -f core/podman-compose.yml up -d --force-recreate

# Clean up everything
podman system prune -af
```

---

## 🏗️ Service Architecture (Simplified)

### **Dependency Chain**
```
gluetun (AirVPN) → qbittorrent → media services
      ↓               ↓             ↓
   VPN+PF         Downloads    Organization
```

### **Critical Services & Ports**
| Service | Port | Purpose | Health Check |
|---------|------|---------|--------------|
| **gluetun** | - | VPN gateway | `wget -qO- https://ipinfo.io` |
| **qbittorrent** | 8080 | Downloads | `curl http://localhost:8080` |
| **prowlarr** | 9696 | Indexers | `curl http://localhost:9696` |
| **sonarr** | 8989 | TV Shows | `curl http://localhost:8989` |
| **radarr** | 7878 | Movies | `curl http://localhost:7878` |
| **jellyfin** | 8096 | Media Player | `curl http://localhost:8096` |

### **Key Environment Variables**
```bash
# REQUIRED (from core/.env)
AIRVPN_WIREGUARD_PRIVATE_KEY=your_private_key_here    # From AirVPN Config Generator
AIRVPN_WIREGUARD_ADDRESSES=your_addresses_here        # From AirVPN Config Generator
QBIT_USER=admin                                       # qBittorrent web UI user
QBIT_PASS=secure_password                            # qBittorrent web UI password

# IMPORTANT
AIRVPN_PORT_FORWARDING=true                          # Enable AirVPN port forwarding
AIRVPN_SERVER_COUNTRIES=SG                          # Preferred server countries (Singapore for Vietnam)
DEBUG=false                                          # Enable debug logging (set true for troubleshooting)
```

---

## 🚨 Common Issues & Quick Fixes

### **VPN Connection Failed**
```bash
# Check AirVPN WireGuard configuration
podman-compose -f core/podman-compose.yml logs gluetun

# Verify AirVPN credentials in core/.env
grep -E "(AIRVPN_WIREGUARD_PRIVATE_KEY|AIRVPN_WIREGUARD_ADDRESSES)" core/.env

# Restart VPN service
podman-compose -f core/podman-compose.yml restart gluetun
```

### **Port Forwarding Not Working**
```bash
# Check AirVPN port forwarding status
podman-compose -f core/podman-compose.yml logs gluetun | grep -i "port"

# Verify AirVPN_PORT_FORWARDING=true in core/.env
grep AIRVPN_PORT_FORWARDING core/.env

# Check AirVPN account port forwarding settings
# Visit: https://airvpn.org/client/ → Forwarded Ports
```

### **Downloads Stuck/Slow**
```bash
# Check qBittorrent connectivity
curl http://localhost:8080

# Verify VPN IP is different from host
podman-compose -f core/podman-compose.yml exec gluetun wget -qO- https://ipinfo.io

# Check available disk space
df -h /media/Storage
```

### **Services Not Accessible**
```bash
# Check all service status
./maintenance/maintenance.sh health

# Restart specific service
podman-compose -f core/podman-compose.yml restart SERVICE_NAME

# Check if ports are bound correctly
podman port --all
```

### **Debug Workflow**
1. **Quick Check**: `./maintenance/maintenance.sh health`
2. **Enable Debug**: `./maintenance/maintenance.sh debug-enable` 
3. **Restart Services**: `podman-compose -f core/podman-compose.yml restart`
4. **Collect Logs**: `./maintenance/maintenance.sh diagnostic`
5. **Check Specific Issue**: `./maintenance/maintenance.sh troubleshoot-vpn`

---

## ⚙️ Configuration Essentials

### **Must-Configure Variables** ([`core/.env.example:1`](../core/.env.example:1))
```bash
# Copy and edit
cp core/.env.example .env

# REQUIRED - AirVPN Account
AIRVPN_WIREGUARD_PRIVATE_KEY=your_private_key_here
AIRVPN_WIREGUARD_ADDRESSES=your_addresses_here

# REQUIRED - qBittorrent Web UI  
QBIT_USER=admin
QBIT_PASS=secure_password

# RECOMMENDED
AIRVPN_PORT_FORWARDING=true       # Better download speeds
AIRVPN_SERVER_COUNTRIES=SG        # Optimal server selection (Singapore for Vietnam)
DEBUG=false                       # Enable for troubleshooting
```

### **AirVPN Setup Guide**
1. **Create Account**: Visit https://airvpn.org/
2. **Purchase Subscription**: Choose your plan
3. **Access Config Generator**: Client Area → Config Generator
4. **Select WireGuard**: Choose WireGuard protocol
5. **Choose Servers**: Singapore recommended for Vietnam users
6. **Generate Config**: Extract PrivateKey and Address values
7. **Configure Port Forwarding**: Client Area → Forwarded Ports (optional)

### **Important Paths**
| Path | Purpose | Notes |
|------|---------|-------|
| `/media/Storage/downloads` | qBittorrent downloads | Must exist, adequate space |
| `/media/Storage/movies` | Radarr movie library | Jellyfin serves from here |
| `/media/Storage/tv-shows` | Sonarr TV library | Jellyfin serves from here |
| `./core/` | Core configuration files | Contains podman-compose.yml, .env |
| `./services/gluetun/` | AirVPN configurations | Contains servers.json |

### **Security Considerations**
- **Strong passwords**: Use unique passwords for all services
- **AirVPN credentials**: Keep secure, enable 2FA if available
- **File permissions**: Ensure media directories accessible
- **Debug mode**: Disable in production (may expose sensitive info)
- **VPN verification**: Always verify external IP differs from host
- **WireGuard keys**: Never share your private key

---

## 🔍 Health Check Commands

### **Quick Status**
```bash
# Overall health (BEST FIRST CHECK)
./maintenance/maintenance.sh health

# Service status
podman-compose -f core/podman-compose.yml ps

# Resource usage
podman stats --no-stream
```

### **VPN Verification**
```bash
# Check VPN IP
podman-compose -f core/podman-compose.yml exec gluetun wget -qO- https://ipinfo.io

# Test port forwarding (if enabled)
podman-compose -f core/podman-compose.yml logs gluetun | grep -i "port"

# VPN logs
podman-compose -f core/podman-compose.yml logs -f gluetun | grep -E "(VPN|connection|port)"
```

### **Service Connectivity**
```bash
# Test internal connectivity
podman-compose -f core/podman-compose.yml exec sonarr curl http://prowlarr:9696
podman-compose -f core/podman-compose.yml exec radarr curl http://gluetun:8080

# Test web interfaces
curl -I http://localhost:9696  # Prowlarr
curl -I http://localhost:8096  # Jellyfin
```

---

## 🎯 Quick Start Checklist

### **Setup** (First Time)
- [ ] Clone repository
- [ ] `cp core/.env.example .env` and configure AirVPN credentials
- [ ] `mkdir -p /media/Storage/{downloads,movies,tv-shows}`
- [ ] `./scripts/podman-up.sh`
- [ ] `./maintenance/maintenance.sh health`

### **Daily Operations**
- [ ] Check health: `./maintenance/maintenance.sh health`
- [ ] Monitor logs: `./scripts/podman-logs.sh`
- [ ] Verify VPN: `podman-compose -f core/podman-compose.yml exec gluetun wget -qO- https://ipinfo.io`

### **Weekly Maintenance**
- [ ] `./maintenance/maintenance.sh cleanup`
- [ ] Update containers: `podman-compose -f core/podman-compose.yml pull && podman-compose -f core/podman-compose.yml up -d`
- [ ] Check AirVPN account status at https://airvpn.org/client/

---

**🚀 TIP FOR ROOCLINE**: Start with `./maintenance/maintenance.sh health` for any issue. It covers 90% of common problems and provides specific guidance for failures. Enable `DEBUG=true` in [`core/.env`](../core/.env) when troubleshooting complex issues.
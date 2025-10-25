# Media Stack Quick Reference - Roocline Optimization

**🎯 RAPID CONTEXT**: Podman-based media automation stack with VPN protection, automated downloads, and media streaming. All traffic routed through PIA VPN with automatic WireGuard configuration generation.

## 📖 Project Overview

**What it does**: Complete automated media pipeline from search → download → organize → stream, all through secure VPN tunnel.

**Core Tech Stack**: Podman containers + PIA VPN (WireGuard) + qBittorrent + Sonarr/Radarr + Jellyfin + automated port forwarding.

**Key Innovation**: [`pia-wggen`](pia-wggen/) auto-generates fresh WireGuard configs on startup, eliminating manual VPN setup.

---

## 🎯 Critical File Priority (READ FIRST)

### **🔥 ESSENTIAL** (Start here for any issue)
1. **[`podman-compose.yml`](podman-compose.yml:1)** - Main service definitions, dependencies, networking
2. **[`.env`](.env)** / **[`.env.example`](.env.example:1)** - All configuration variables (PIA creds, ports, paths)
3. **[`maintenance.sh`](maintenance.sh:1)** - Comprehensive debugging tool (`./maintenance.sh health`)

### **🔧 OPERATIONAL** (Daily use)
4. **[`podman-up.sh`](podman-up.sh)** - Stack startup script
5. **[`quick-debug.sh`](quick-debug.sh)** - Fast troubleshooting
6. **[`podman-logs.sh`](podman-logs.sh)** - Log viewing utility

### **📚 CONTEXTUAL** (Reference when needed)
7. **[`README.md`](README.md:1)** - Complete documentation (863 lines)
8. **[`PODMAN.md`](PODMAN.md:1)** - Podman-specific setup guide
9. **[`gluetun/pia_pf_runner.sh`](gluetun/pia_pf_runner.sh:1)** - Port forwarding automation
10. **[`gluetun/update-qb.sh`](gluetun/update-qb.sh:1)** - qBittorrent port updates

---

## ⚡ Essential Commands

### **Core Operations**
```bash
# Start entire stack
./podman-up.sh

# Stop stack  
./podman-down.sh

# View all logs
./podman-logs.sh

# Health check (MOST IMPORTANT)
./maintenance.sh health
```

### **Debug & Troubleshooting**
```bash
# Enable debug mode
./maintenance.sh debug-enable

# Quick health check
./quick-debug.sh

# VPN troubleshooting
./maintenance.sh troubleshoot-vpn

# Full diagnostic collection
./maintenance.sh diagnostic
```

### **Manual Podman Commands**
```bash
# Start with compose
podman-compose -f podman-compose.yml up -d

# View specific service logs
podman-compose logs -f gluetun

# Check service status
podman-compose ps

# Test VPN IP
podman-compose exec gluetun wget -qO- https://ipinfo.io
```

### **Emergency/Recovery**
```bash
# Regenerate VPN config
podman-compose run --rm pia-wggen
podman-compose restart gluetun

# Full restart with fresh configs
podman-compose down && podman-compose up -d --force-recreate

# Clean up everything
podman system prune -af
```

---

## 🏗️ Service Architecture (Simplified)

### **Dependency Chain**
```
pia-wggen → gluetun → qbittorrent → media services
     ↓         ↓          ↓             ↓
   WG Config  VPN+PF   Downloads    Organization
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
# REQUIRED (from .env)
PIA_USER=p1234567              # PIA username
PIA_PASS=your_password         # PIA password  
QBIT_USER=admin               # qBittorrent web UI user
QBIT_PASS=secure_password     # qBittorrent web UI password

# IMPORTANT
PIA_PF=true                   # Enable port forwarding
MAX_LATENCY=0.05             # Server selection latency (seconds)
DEBUG=false                  # Enable debug logging (set true for troubleshooting)
```

---

## 🚨 Common Issues & Quick Fixes

### **VPN Connection Failed**
```bash
# Check WireGuard config generation
podman-compose logs pia-wggen

# Regenerate fresh config
podman-compose run --rm pia-wggen

# Verify PIA credentials in .env
grep -E "(PIA_USER|PIA_PASS)" .env
```

### **Port Forwarding Not Working**
```bash
# Check forwarded port
podman-compose exec gluetun cat /tmp/gluetun/forwarded_port

# Check PIA-PF logs
podman-compose logs pia-pf

# Verify PIA_PF=true in .env
grep PIA_PF .env
```

### **Downloads Stuck/Slow**
```bash
# Check qBittorrent connectivity
curl http://localhost:8080

# Verify VPN IP is different from host
podman-compose exec gluetun wget -qO- https://ipinfo.io

# Check available disk space
df -h /media/Storage
```

### **Services Not Accessible**
```bash
# Check all service status
./maintenance.sh health

# Restart specific service
podman-compose restart SERVICE_NAME

# Check if ports are bound correctly
podman port --all
```

### **Debug Workflow**
1. **Quick Check**: `./maintenance.sh health`
2. **Enable Debug**: `./maintenance.sh debug-enable` 
3. **Restart Services**: `podman-compose restart`
4. **Collect Logs**: `./maintenance.sh diagnostic`
5. **Check Specific Issue**: `./maintenance.sh troubleshoot-vpn|pf|dl`

---

## ⚙️ Configuration Essentials

### **Must-Configure Variables** ([`.env.example:1`](.env.example:1))
```bash
# Copy and edit
cp .env.example .env

# REQUIRED - PIA Account
PIA_USER=p1234567
PIA_PASS=your_password

# REQUIRED - qBittorrent Web UI  
QBIT_USER=admin
QBIT_PASS=secure_password

# RECOMMENDED
PIA_PF=true                    # Better download speeds
MAX_LATENCY=0.05              # Optimal server selection
DEBUG=false                   # Enable for troubleshooting
```

### **Important Paths**
| Path | Purpose | Notes |
|------|---------|-------|
| `/media/Storage/downloads` | qBittorrent downloads | Must exist, adequate space |
| `/media/Storage/movies` | Radarr movie library | Jellyfin serves from here |
| `/media/Storage/tv-shows` | Sonarr TV library | Jellyfin serves from here |
| `./gluetun/` | VPN scripts and configs | Contains [`pia_pf_runner.sh`](gluetun/pia_pf_runner.sh:1) |
| `wireguard-config` volume | Fresh WG configs | Auto-generated by pia-wggen |

### **Security Considerations**
- **Strong passwords**: Use unique passwords for all services
- **PIA credentials**: Keep secure, enable 2FA if available
- **File permissions**: Ensure media directories accessible
- **Debug mode**: Disable in production (may expose sensitive info)
- **VPN verification**: Always verify external IP differs from host

---

## 🔍 Health Check Commands

### **Quick Status**
```bash
# Overall health (BEST FIRST CHECK)
./maintenance.sh health

# Service status
podman-compose ps

# Resource usage
podman stats --no-stream
```

### **VPN Verification**
```bash
# Check VPN IP
podman-compose exec gluetun wget -qO- https://ipinfo.io

# Test port forwarding
podman-compose exec gluetun cat /tmp/gluetun/forwarded_port

# VPN logs
podman-compose logs -f gluetun | grep -E "(VPN|connection|port)"
```

### **Service Connectivity**
```bash
# Test internal connectivity
podman-compose exec sonarr curl http://prowlarr:9696
podman-compose exec radarr curl http://gluetun:8080

# Test web interfaces
curl -I http://localhost:9696  # Prowlarr
curl -I http://localhost:8096  # Jellyfin
```

---

## 🎯 Quick Start Checklist

### **Setup** (First Time)
- [ ] Clone repository
- [ ] `cp .env.example .env` and configure PIA credentials
- [ ] `mkdir -p /media/Storage/{downloads,movies,tv-shows}`
- [ ] `./podman-up.sh`
- [ ] `./maintenance.sh health`

### **Daily Operations**
- [ ] Check health: `./maintenance.sh health`
- [ ] Monitor logs: `./podman-logs.sh`
- [ ] Verify VPN: `podman-compose exec gluetun wget -qO- https://ipinfo.io`

### **Weekly Maintenance**
- [ ] `./maintenance.sh cleanup`
- [ ] Regenerate VPN config: `podman-compose run --rm pia-wggen`
- [ ] Update containers: `podman-compose pull && podman-compose up -d`

---

**🚀 TIP FOR ROOCLINE**: Start with `./maintenance.sh health` for any issue. It covers 90% of common problems and provides specific guidance for failures. Enable `DEBUG=true` in [`.env`](.env) when troubleshooting complex issues.
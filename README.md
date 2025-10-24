# Media Stack with VPN

A complete Podman-based media stack solution with automated downloading, management, and streaming of media content through VPN to ensure privacy and security.

## 📋 Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [System Requirements](#system-requirements)
- [Podman Support](#podman-support)
- [Quick Start Guide](#quick-start-guide)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Debugging & Maintenance](#debugging--maintenance)
- [API Documentation](#api-documentation)
- [Custom Scripts](#custom-scripts)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## 🎯 Overview

This Media Stack includes an integrated suite of applications for:

- **Automated downloading**: Sonarr (TV shows), Radarr (Movies)
- **Indexer management**: Prowlarr
- **Torrent downloading**: qBittorrent (through VPN)
- **Subtitle management**: Bazarr
- **Media streaming**: Jellyfin
- **VPN & Port Forwarding**: Gluetun + PIA + PIA-WGGen
- **CloudFlare bypass**: FlareSolverr
- **Automated WireGuard config**: PIA-WGGen (fresh configs on startup)

### Key Features

- ✅ **Simplified Architecture**: Cleaned and optimized structure with consolidated configuration
- 🔄 **Automated Setup**: Fresh WireGuard configs generated automatically on startup
- 🐛 **Debug Support**: Built-in debugging capabilities with `DEBUG=true` environment variable
- 📊 **Enhanced Monitoring**: Improved logging and error handling across all services
- 🔒 **Security First**: All traffic routed through VPN with automatic port forwarding
- 🛠️ **Easy Maintenance**: Streamlined troubleshooting and configuration management

The entire system operates in Podman containers with high automation and security through VPN.

## 🏗️ System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FlareSolverr  │    │    Prowlarr     │    │    Jellyfin    │
│   (Port 8191)   │    │   (Port 9696)   │    │   (Port 8096)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Sonarr      │◄───┤     Bazarr      │    │     Radarr      │
│   (Port 8989)   │    │   (Port 6767)   │───►│   (Port 7878)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PIA-WGGen (Init Container)                 │
│              ┌─────────────────────────────────────┐            │
│              │ Generates fresh WireGuard configs   │            │
│              │ Finds optimal PIA server by latency │            │
│              └─────────────────────────────────────┘            │
└─────────────────────────────┬───────────────────────────────────┘
                              │ Provides fresh config
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Gluetun VPN                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  qBittorrent    │  │     PIA-PF      │  │   Port Forward  │ │
│  │  (Port 8090)    │  │   (Alpine)      │  │     Scripts     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## 📋 System Requirements

### Hardware
- **CPU**: 4+ cores (recommended 8+ cores for Jellyfin transcoding)
- **RAM**: 8GB+ (recommended 16GB+)
- **Storage**: 
  - 50GB+ for system and configs
  - Large storage space for media content
- **GPU** (optional): NVIDIA GPU for hardware transcoding

### Software
- **OS**: Linux (recommended Ubuntu 20.04+, Fedora 36+)
- **Container Runtime**:
  - **Podman**: 4.0+ with podman-compose (enhanced security and performance)
- **VPN**: Private Internet Access (PIA) account

### Network
- Port forwarding from router (if remote access needed)
- Stable internet connection

## 🐳 Podman Support

This Media Stack is **fully compatible with Podman** - the daemonless, rootless container engine that offers enhanced security and better integration with modern Linux systems.

### ✅ Why Choose Podman?

- **🔒 Enhanced Security**: Rootless containers, no privileged daemon
- **🚀 Better Performance**: Direct container execution without daemon overhead
- **🛡️ SELinux Integration**: Native support for mandatory access controls
- **⚡ systemd Integration**: Native service management and auto-restart
- **🎮 GPU Support**: Full NVIDIA and Intel/AMD GPU acceleration
- **📊 Enterprise Ready**: Red Hat supported, OCI compliant

### 🚀 Quick Start with Podman

```bash
# 1. Install Podman (Fedora - included by default)
sudo dnf install -y podman podman-compose

# 2. Clone and configure
git clone <repository-url>
cd media-stack
cp .env.example .env
# Edit .env with your PIA credentials

# 3. Start with optimized Podman configuration
./podman-up.sh

# 4. View logs and status
./podman-logs.sh
```

### 📚 Comprehensive Documentation

For complete Podman setup, migration guide, SELinux configuration, and troubleshooting:

**👉 [Read the Complete Podman Guide](PODMAN.md)**

The guide includes:
- **Installation** for Fedora, RHEL, Ubuntu systems
- **Migration guide** from Docker to Podman
- **SELinux configuration** and security policies
- **GPU setup** for hardware transcoding
- **Performance optimization** recommendations
- **Troubleshooting** common issues and solutions
- **Service compatibility** status for all components

### 🔧 Available Podman Tools

| Tool | Purpose | Command |
|------|---------|---------|
| [`podman-up.sh`](podman-up.sh) | Start media stack | `./podman-up.sh` |
| [`podman-down.sh`](podman-down.sh) | Stop media stack | `./podman-down.sh` |
| [`podman-logs.sh`](podman-logs.sh) | View logs | `./podman-logs.sh -f` |
| [`podman-compose.yml`](podman-compose.yml) | Podman-optimized config | `podman-compose -f podman-compose.yml up -d` |

### 🏗️ Service Compatibility Status

All services are **fully tested** and **production-ready** with Podman:

| Service | Status | Notes |
|---------|--------|-------|
| **PIA-WGGen** | ✅ Fully Supported | Fresh WireGuard config generation |
| **Gluetun VPN** | ✅ Fully Supported | VPN networking with port forwarding |
| **qBittorrent** | ✅ Fully Supported | Shared networking, automatic port updates |
| **Prowlarr** | ✅ Fully Supported | Indexer management, API integration |
| **Sonarr/Radarr** | ✅ Fully Supported | Media management, cross-service communication |
| **Bazarr** | ✅ Fully Supported | Subtitle management |
| **Jellyfin** | ✅ Fully Supported | GPU transcoding (NVIDIA/Intel/AMD) |
| **FlareSolverr** | ✅ Fully Supported | CloudFlare bypass |

## 🚀 Quick Start Guide

### Prerequisites Checklist
- [ ] **Container Runtime**: Podman 4.0+ installed
- [ ] **Compose Tool**: podman-compose installed
- [ ] **VPN Account**: Active PIA subscription
- [ ] **Resources**: 8GB+ RAM and 50GB+ storage available

### 1. Clone and Setup
```bash
git clone <repository-url>
cd media-stack
cp .env.example .env
```

### 2. Configure Credentials
Edit [`.env`](.env.example:1) with your details:
```bash
# Required: Your PIA account credentials
PIA_USER=p1234567
PIA_PASS=your_pia_password

# Required: Set qBittorrent credentials
QBIT_USER=admin
QBIT_PASS=your_secure_password

# Optional: Enable debug mode for troubleshooting
DEBUG=true
```

### 3. Create Media Directories
```bash
sudo mkdir -p /media/Storage/{downloads,movies,tv-shows}
sudo chown -R $USER:$USER /media/Storage
```

### 4. Start Services
```bash
# Using Podman
./podman-up.sh
# OR
podman-compose -f podman-compose.yml up -d
```

### 5. Verify Setup
```bash
# Check all services are running
./podman-logs.sh --status

# Verify VPN connection
podman-compose exec gluetun wget -qO- https://ipinfo.io

# Check WireGuard config generation
./podman-logs.sh pia-wggen
```

### 6. Access Web Interfaces
- **Prowlarr**: http://localhost:9696 (Configure indexers first)
- **Sonarr**: http://localhost:8989 (TV Shows)
- **Radarr**: http://localhost:7878 (Movies)
- **qBittorrent**: http://localhost:8090 (Downloads)
- **Jellyfin**: http://localhost:8096 (Media Player)
- **Bazarr**: http://localhost:6767 (Subtitles)

## 🚀 Installation

### 1. Clone repository
```bash
git clone <repository-url>
cd media-stack
```

### 2. Create media directory structure
```bash
sudo mkdir -p /media/Storage/{downloads,movies,tv-shows}
sudo chown -R $USER:$USER /media/Storage
```

### 3. Configure environment variables
```bash
cp .env.example .env
nano .env
```

Fill in PIA and qBittorrent information:
```env
# PIA Credentials (Required)
PIA_USER=your_pia_username
PIA_PASS=your_pia_password

# qBittorrent Credentials (Required)
QBIT_USER=your_qbittorrent_username
QBIT_PASS=your_qbittorrent_password

# PIA WireGuard Generator Configuration (Optional)
PIA_PF=true                    # Enable port forwarding
MAX_LATENCY=0.1               # Maximum latency for server selection (seconds)
PREFERRED_REGION=none         # Preferred region ID (or 'none' for auto-selection)
```

### 4. Generate fresh WireGuard configuration
The stack now includes **PIA-WGGen**, an automated WireGuard configuration generator that:
- 🔄 **Automatically generates fresh configs** on every startup
- 🌍 **Finds the optimal PIA server** based on latency
- 🚀 **Supports port forwarding** for faster downloads
- ⚡ **No manual configuration needed**

> **Note**: The old manual WireGuard configuration method is still supported as fallback, but the automated method is recommended for better performance and security.

### 5. Start the stack
```bash
# Using Podman Compose
podman-compose up -d
```

### 6. Check status
```bash
# Check all services
podman-compose ps

# Monitor WireGuard config generation
podman-compose logs -f pia-wggen

# Check VPN connection
podman-compose logs -f gluetun

# Check port forwarding
podman-compose logs -f pia-pf
```

## ⚙️ Configuration

### 📁 Directory Structure

```
media-stack/
├── podman-compose.yml          # Podman configuration with SELinux support
├── .env                       # Environment variables (from .env.example)
├── .env.example              # Configuration template
├── README.md                 # Main documentation
├── PODMAN.md                 # Comprehensive Podman documentation and migration guide
├── podman-up.sh              # Podman stack startup script
├── podman-down.sh            # Podman stack shutdown script
├── podman-logs.sh            # Podman log viewing script
├── bazarr-config/            # Bazarr configuration
├── gluetun/                  # VPN configs and scripts
│   ├── pia_pf_runner.sh     # PIA port forwarding script (with debug support)
│   ├── update-qb.sh         # qBittorrent port update script (optimized)
│   └── wireguard/
│       └── wg0.conf         # WireGuard config (fallback only)
├── jellyfin-config/          # Jellyfin configuration
├── jellyfin-cache/           # Jellyfin cache
├── legacy/                   # Archived legacy components
│   ├── README.md            # Legacy documentation
│   └── manual-connections-script-pia/  # Old manual scripts (archived)
├── pia-wggen/               # PIA WireGuard Generator (primary config method)
│   ├── podman-compose.yml   # Podman-specific compose file
│   ├── src/pia_wggen.py    # Main generator script
│   ├── requirements.txt    # Python dependencies
│   └── README.md           # PIA-WGGen specific documentation
├── prowlarr-config/          # Prowlarr configuration
├── qbittorrent-config/       # qBittorrent configuration
├── radarr-config/           # Radarr configuration
└── sonarr-config/           # Sonarr configuration
```

### 🔧 Key Changes from Legacy Architecture

- ✅ **Consolidated Configuration**: All environment variables now in root [`.env`](.env.example:1) file
- ✅ **Archived Legacy Code**: Old manual connection scripts moved to [`legacy/`](legacy/) directory
- ✅ **Enhanced Scripts**: Improved [`pia_pf_runner.sh`](gluetun/pia_pf_runner.sh:1) and [`update-qb.sh`](gluetun/update-qb.sh:1) with debug support
- ✅ **Simplified Workflow**: PIA-WGGen now primary configuration method (no manual setup needed)

### 🔧 Service Configuration

#### Prowlarr (Port 9696)
1. Access http://localhost:9696
2. Add indexers (torrent sites)
3. Configure FlareSolverr: http://flaresolverr:8191
4. Sync apps with Sonarr and Radarr

#### Sonarr (Port 8989)
1. Access http://localhost:8989
2. **Settings → Media Management**: 
   - Root Folder: `/tv`
   - File naming patterns
3. **Settings → Download Clients**:
   - Add qBittorrent: http://gluetun:8090
4. **Settings → General**: Connect with Prowlarr

#### Radarr (Port 7878)
1. Access http://localhost:7878
2. **Settings → Media Management**:
   - Root Folder: `/movies`
3. **Settings → Download Clients**:
   - Add qBittorrent: http://gluetun:8090
4. **Settings → General**: Connect with Prowlarr

#### Bazarr (Port 6767)
1. Access http://localhost:6767
2. **Settings → Sonarr**: http://sonarr:8989
3. **Settings → Radarr**: http://radarr:7878
4. Configure subtitle providers

#### qBittorrent (Port 8090)
1. Access http://localhost:8090
2. **Tools → Options → Downloads**:
   - Default Save Path: `/downloads`
3. **Connection**: Port will be automatically updated by PIA scripts

#### Jellyfin (Port 8096)
1. Access http://localhost:8096
2. Setup wizard: Create admin user
3. **Library Setup**:
   - Movies: `/movies`
   - TV Shows: `/tv`
4. **Playback → Transcoding**: Configure GPU if available

## 🎮 Usage

### Automated Workflow
1. **Generate fresh VPN config**: PIA-WGGen creates optimal WireGuard configuration
2. **Connect VPN**: Gluetun connects using the fresh configuration
3. **Add content**: Use Sonarr/Radarr to add TV shows/movies
4. **Automatic search**: Prowlarr searches on configured indexers
5. **Download**: qBittorrent downloads through VPN with port forwarding
6. **Organize**: Sonarr/Radarr automatically organize files
7. **Subtitles**: Bazarr automatically downloads subtitles
8. **Stream**: Jellyfin serves content

### Running with Fresh WireGuard Config
```bash
# First time setup (generates fresh config)
podman-compose up pia-wggen
podman-compose up -d

# To regenerate config manually
podman-compose run --rm pia-wggen
podman-compose restart gluetun
```

### Adding TV Shows
```bash
# Through Sonarr web UI:
# 1. Series → Add New Series
# 2. Search by name → Add to library
# 3. Monitor future episodes
```

### Adding Movies
```bash
# Through Radarr web UI:
# 1. Movies → Add New Movie  
# 2. Search by name → Add to library
# 3. Set quality profile
```

### Managing Downloads
```bash
# View download logs
podman-compose logs -f qbittorrent

# View VPN status
podman-compose logs -f gluetun

# View port forwarding logs
podman-compose logs -f gluetun
```

## 📡 API Documentation

### Sonarr API
- **Base URL**: `http://localhost:8989/api/v3/`
- **Authentication**: API Key (Settings → General)

#### Main Endpoints:
```bash
# Get all series
GET /api/v3/series

# Search for series
GET /api/v3/series/lookup?term=SEARCH_TERM

# Add new series
POST /api/v3/series
```

### Radarr API
- **Base URL**: `http://localhost:7878/api/v3/`
- **Authentication**: API Key

#### Main Endpoints:
```bash
# Get all movies  
GET /api/v3/movie

# Search for movies
GET /api/v3/movie/lookup?term=SEARCH_TERM

# Add new movie
POST /api/v3/movie
```

### Jellyfin API
- **Base URL**: `http://localhost:8096/`
- **Authentication**: API Key or session

#### Main Endpoints:
```bash
# Get user libraries
GET /Users/{userId}/Items

# Get media info
GET /Items/{itemId}

# Start playback session
POST /Sessions/Playing
```

### qBittorrent Web API
- **Base URL**: `http://localhost:8090/api/v2/`
- **Authentication**: Login session

#### Main Endpoints:
```bash
# Login
POST /auth/login

# Get torrent list
GET /torrents/info

# Add new torrent
POST /torrents/add
```

## 🛠️ Custom Scripts

### PIA Port Forwarding Script
[`gluetun/pia_pf_runner.sh`](gluetun/pia_pf_runner.sh) - Automatically manages port forwarding:

**Features:**
- Automatically gets forwarded port from PIA
- Updates qBittorrent listening port
- Keepalive and retry logic
- Automatic recovery when connection fails

**Configuration:**
```bash
# Environment variables in docker-compose.yml
SLEEP_KEEPALIVE=900        # Keepalive interval (seconds)
RETRY_MAX=30              # Max retry attempts
```

### qBittorrent Port Update Script  
[`gluetun/update-qb.sh`](gluetun/update-qb.sh) - Updates port for qBittorrent:

**Usage:**
```bash
# Manual run
PORT_FILE=/tmp/gluetun/forwarded_port \
QBIT_HOST=127.0.0.1 \
QBIT_WEBUI_PORT=8090 \
sh gluetun/update-qb.sh
```

## 🐛 Debugging & Maintenance

### Debug Mode

Enable debug mode for enhanced troubleshooting by setting the `DEBUG=true` environment variable in your [`.env`](.env.example:1) file:

```bash
# Enable debug mode
DEBUG=true
```

When debug mode is enabled:
- **Enhanced Logging**: All scripts output detailed debug information
- **Port Forwarding Debug**: [`pia_pf_runner.sh`](gluetun/pia_pf_runner.sh:1) shows detailed PIA API interactions
- **qBittorrent Updates**: [`update-qb.sh`](gluetun/update-qb.sh:1) logs all port update attempts
- **Container Startup**: Extended logging during service initialization

### Log Monitoring

```bash
# Monitor all services in real-time
podman-compose logs -f

# Monitor specific service with debug output
podman-compose logs -f gluetun
podman-compose logs -f pia-wggen

# View recent logs for troubleshooting
podman-compose logs --tail=50 SERVICE_NAME
```

### Health Checks

```bash
# Verify all services are healthy
podman-compose ps

# Check VPN connectivity and IP
podman-compose exec gluetun wget -qO- https://ipinfo.io

# Verify port forwarding is active
podman-compose exec gluetun wget -qO- https://portchecker.co/check

# Test internal service connectivity
podman-compose exec sonarr curl -I http://prowlarr:9696
podman-compose exec radarr curl -I http://gluetun:8090
```

### Configuration Validation

```bash
# Verify environment variables are set correctly
podman-compose config

# Check for common configuration issues
grep -E "(PIA_USER|PIA_PASS|QBIT_USER|QBIT_PASS)" .env

# Validate WireGuard config generation
podman-compose run --rm pia-wggen
```

### Maintenance Tasks

#### Weekly Maintenance
```bash
# Regenerate fresh WireGuard config
podman-compose run --rm pia-wggen
podman-compose restart gluetun

# Update container images
podman-compose pull
podman-compose up -d

# Clean up old containers and images
podman system prune -f
```

#### Monthly Maintenance
```bash
# Full restart with fresh configurations
podman-compose down
podman-compose pull
podman-compose up -d --force-recreate

# Check disk usage and clean up if needed
du -sh /media/Storage/downloads/
# Move or delete completed downloads as needed
```

### Performance Optimization

```bash
# Monitor resource usage
podman stats

# Check available disk space
df -h /media/Storage

# Monitor network throughput
podman-compose exec gluetun iftop
```

## 🔍 Troubleshooting

### VPN Issues
```bash
# Check VPN connection
podman-compose exec gluetun wget -qO- https://ipinfo.io

# Restart VPN with fresh config generation
podman-compose restart pia-wggen gluetun qbittorrent

# Check VPN logs
podman-compose logs gluetun

# Check WireGuard config generation
podman-compose logs pia-wggen
```

### PIA-WGGen Issues
```bash
# Check config generation logs
podman-compose logs pia-wggen

# Manually regenerate config
podman-compose run --rm pia-wggen

# Check generated config
podman volume inspect media-stack_wireguard-config

# Test different PIA region
PREFERRED_REGION=singapore podman-compose run --rm pia-wggen
```

### Port Forwarding Issues
```bash
# Check forwarded port (check logs for port number)
podman-compose logs gluetun | grep -i "port"

# Check Gluetun port forwarding logs
podman-compose logs gluetun

# Manual port test
podman-compose exec gluetun wget -qO- https://portchecker.co/check
```

### Download Issues
```bash
# Check qBittorrent logs
podman-compose logs qbittorrent

# Check if qBittorrent accessible
curl http://localhost:8090

# Check storage permissions
ls -la /media/Storage/downloads
```

### Jellyfin Transcoding Issues
```bash
# Check GPU access
podman-compose exec jellyfin nvidia-smi

# Check transcode logs
tail -f jellyfin-config/log/FFmpeg.Transcode-*.log

# Check hardware acceleration
# Settings → Playback → Hardware acceleration
```

### Service Connection Issues
```bash
# Test internal connectivity
podman-compose exec sonarr curl http://prowlarr:9696
podman-compose exec radarr curl http://qbittorrent:8090

# Restart specific service
podman-compose restart SERVICE_NAME

# Rebuild and restart
podman-compose down
podman-compose up -d --force-recreate
```

### Common Error Solutions

#### "VPN connection failed"
```bash
# Check fresh WireGuard config generation
podman-compose logs pia-wggen

# Check generated config in volume
podman run --rm -v media-stack_wireguard-config:/data alpine ls -la /data

# Verify PIA credentials
echo $PIA_USER $PIA_PASS

# Regenerate config manually
podman-compose run --rm pia-wggen

# Check VPN endpoint connectivity (example IP)
ping 173.239.247.142
```

#### "PIA-WGGen fails to generate config"
```bash
# Check PIA credentials
podman-compose run --rm -e PIA_USER=$PIA_USER -e PIA_PASS=$PIA_PASS pia-wggen

# Try with different latency threshold
MAX_LATENCY=0.5 podman-compose run --rm pia-wggen

# Test specific region
PREFERRED_REGION=singapore podman-compose run --rm pia-wggen

# Check PIA service status
curl -s https://serverlist.piaservers.net/vpninfo/servers/v6 | jq '.regions | length'
```

#### "Port forwarding not working"
```bash
# Check PIA subscription supports port forwarding
# Verify PIA_USER and PIA_PASS in .env
# Check if VPN server supports port forwarding
# Look for port forwarding messages in gluetun logs:
podman-compose logs gluetun | grep -i "port"
```

#### "Download stuck in queue"
```bash
# Check available disk space
df -h /media/Storage

# Check qBittorrent connection status
curl http://localhost:8090

# Verify indexer connectivity in Prowlarr
# Check qBittorrent logs for connection issues
podman-compose logs qbittorrent
```

## 🤝 Contributing

### Bug Reports
1. Describe the issue in detail
2. Provide relevant logs
3. Environment information (OS, Podman version, etc.)
4. Steps to reproduce

### Code Contributions
1. Fork repository
2. Create feature branch: `git checkout -b feature/new-feature`
3. Commit changes: `git commit -m 'Add new feature'`
4. Push branch: `git push origin feature/new-feature`  
5. Create Pull Request

### Documentation Improvements
- Update README with new information
- Add examples and use cases
- Translate to other languages
- Add troubleshooting scenarios

### Development Setup
```bash
# Clone repo
git clone <repo-url>
cd media-stack

# Create development branch
git checkout -b dev/your-feature

# Test changes
podman-compose -f podman-compose.yml up -d

# Run tests
./scripts/test.sh
```

## 📄 License

This project is distributed under the **MIT License**.

### MIT License
```
Copyright (c) 2024 Media Stack Project

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 🙏 Acknowledgments

Thanks to the following open source projects:
- [Sonarr](https://sonarr.tv/) - TV series management
- [Radarr](https://radarr.video/) - Movie management  
- [Prowlarr](https://prowlarr.com/) - Indexer management
- [Bazarr](https://www.bazarr.media/) - Subtitle management
- [Jellyfin](https://jellyfin.org/) - Media server
- [qBittorrent](https://www.qbittorrent.org/) - BitTorrent client
- [Gluetun](https://github.com/qdm12/gluetun) - VPN client
- [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) - CloudFlare bypass

---

## 📞 Support

If you encounter issues or have questions:

1. **Read Documentation**: Check README and troubleshooting section
2. **Search Issues**: Look in GitHub issues for solutions
3. **Create Issue**: Create new issue with detailed information
4. **Community**: Join Discord/forum of each service

**Important note**: Ensure compliance with local laws when using this system.
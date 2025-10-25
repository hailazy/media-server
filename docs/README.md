# Media Stack with VPN

A complete Podman-based media stack solution with automated downloading, management, and streaming of media content through VPN to ensure privacy and security.

## ⚡ Quick Start - Roocline Optimized

**🎯 For immediate context and rapid deployment:** See [`docs/ROOCLINE-QUICK-REF.md`](ROOCLINE-QUICK-REF.md:1) for essential commands and troubleshooting.

### Essential Commands (New Convenience Scripts)
```bash
# Core operations using new convenience scripts
./start.sh      # Start entire stack
./stop.sh       # Stop all services
./logs.sh       # View real-time logs
./debug.sh      # Quick troubleshooting

# Health check (most important for issues)
./maintenance/maintenance.sh health
```

### New Project Structure Overview
```
├── core/                 # Core configuration files
│   ├── podman-compose.yml    # Main service definitions
│   ├── .env.example         # Configuration template
│   └── media-stack.service  # SystemD service file
├── scripts/              # Podman management scripts
│   ├── podman-up.sh         # Start services
│   ├── podman-down.sh       # Stop services
│   └── podman-logs.sh       # Log management
├── services/             # Service-specific configurations
│   └── gluetun/             # VPN and port forwarding
├── maintenance/          # Maintenance and debugging tools
│   ├── maintenance.sh       # Comprehensive maintenance
│   └── quick-debug.sh       # Fast troubleshooting
└── docs/                 # Documentation
    ├── README.md            # This file
    ├── PODMAN.md            # Podman-specific guide
    └── ROOCLINE-QUICK-REF.md # Quick reference
```

## 📋 Table of Contents

- [Quick Start - Roocline Optimized](#quick-start---roocline-optimized)
- [Overview](#overview)
- [System Architecture](#system-architecture)
- [System Requirements](#system-requirements)
- [Podman Support](#podman-support)
- [Installation & Setup](#installation--setup)
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
- **VPN & Port Forwarding**: Gluetun + AirVPN + Native WireGuard
- **CloudFlare bypass**: FlareSolverr
- **Native AirVPN WireGuard**: Pre-configured via AirVPN Config Generator

### Key Features

- ✅ **Simplified Architecture**: Cleaned and optimized structure with consolidated configuration
- 🔄 **Native AirVPN Setup**: Pre-configured WireGuard setup via AirVPN Config Generator
- 🐛 **Debug Support**: Built-in debugging capabilities with `DEBUG=true` environment variable
- 📊 **Enhanced Monitoring**: Improved logging and error handling across all services
- 🔒 **Security First**: All traffic routed through VPN with AirVPN port forwarding
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
│                    AirVPN WireGuard VPN                        │
│              ┌─────────────────────────────────────┐            │
│              │ Pre-configured WireGuard setup      │            │
│              │ AirVPN Config Generator based       │            │
│              └─────────────────────────────────────┘            │
└─────────────────────────────┬───────────────────────────────────┘
                              │ Native configuration
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Gluetun VPN                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  qBittorrent    │  │   AirVPN Port   │  │   Port Forward  │ │
│  │  (Port 8080)    │  │   Forwarding    │  │   Management    │ │
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
- **VPN**: AirVPN account with active subscription

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
cp core/.env.example .env
# Edit .env with your AirVPN credentials

# 3. Start with new convenience scripts
./start.sh

# 4. View logs and status
./logs.sh
```

### 📚 Comprehensive Documentation

For complete Podman setup, migration guide, SELinux configuration, and troubleshooting:

**👉 [Read the Complete Podman Guide](docs/PODMAN.md)**

The guide includes:
- **Installation** for Fedora, RHEL, Ubuntu systems
- **Migration guide** from Docker to Podman
- **SELinux configuration** and security policies
- **GPU setup** for hardware transcoding
- **Performance optimization** recommendations
- **Troubleshooting** common issues and solutions
- **Service compatibility** status for all components

### 🔧 Available Tools

| Tool | Purpose | Location | Command |
|------|---------|----------|---------|
| [`start.sh`](start.sh) | Start media stack | Root | `./start.sh` |
| [`stop.sh`](stop.sh) | Stop media stack | Root | `./stop.sh` |
| [`logs.sh`](logs.sh) | View logs | Root | `./logs.sh -f` |
| [`debug.sh`](debug.sh) | Quick troubleshooting | Root | `./debug.sh` |
| [`scripts/podman-up.sh`](scripts/podman-up.sh) | Advanced startup | scripts/ | `./scripts/podman-up.sh` |
| [`scripts/podman-logs.sh`](scripts/podman-logs.sh) | Advanced logging | scripts/ | `./scripts/podman-logs.sh` |
| [`core/podman-compose.yml`](core/podman-compose.yml) | Main configuration | core/ | `podman-compose -f core/podman-compose.yml up -d` |
| [`maintenance/maintenance.sh`](maintenance/maintenance.sh) | Comprehensive maintenance | maintenance/ | `./maintenance/maintenance.sh health` |

### 🏗️ Service Compatibility Status

All services are **fully tested** and **production-ready** with Podman:

| Service | Status | Notes |
|---------|--------|-------|
| **AirVPN WireGuard** | ✅ Fully Supported | Native WireGuard configuration |
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
- [ ] **VPN Account**: Active AirVPN subscription
- [ ] **Resources**: 8GB+ RAM and 50GB+ storage available

### 1. Clone and Setup
```bash
git clone <repository-url>
cd media-stack
cp .env.example .env
```

### 2. Configure Credentials
Edit [`.env`](core/.env.example:1) with your details:
```bash
# Required: Your AirVPN WireGuard credentials
AIRVPN_WIREGUARD_PRIVATE_KEY=your_private_key_here
AIRVPN_WIREGUARD_ADDRESSES=your_addresses_here

# Required: Set qBittorrent credentials
QBIT_USER=admin
QBIT_PASS=your_secure_password

# Optional: Preferred server countries (Singapore recommended for Vietnam)
AIRVPN_SERVER_COUNTRIES=SG

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

# Check AirVPN VPN connection
./podman-logs.sh gluetun
```

### 6. Access Web Interfaces
- **Prowlarr**: http://localhost:9696 (Configure indexers first)
- **Sonarr**: http://localhost:8989 (TV Shows)
- **Radarr**: http://localhost:7878 (Movies)
- **qBittorrent**: http://localhost:8080 (Downloads)
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

Fill in AirVPN and qBittorrent information:
```env
# AirVPN WireGuard Credentials (Required)
AIRVPN_WIREGUARD_PRIVATE_KEY=your_private_key_here
AIRVPN_WIREGUARD_ADDRESSES=your_addresses_here

# qBittorrent Credentials (Required)
QBIT_USER=your_qbittorrent_username
QBIT_PASS=your_qbittorrent_password

# AirVPN Configuration (Optional)
AIRVPN_PORT_FORWARDING=true   # Enable port forwarding (configure in AirVPN client area)
AIRVPN_SERVER_COUNTRIES=SG    # Preferred server countries (Singapore for Vietnam users)
AIRVPN_SERVER_NAMES=          # Specific server names (leave empty for auto-selection)
```

### 4. Configure AirVPN WireGuard
The stack uses **AirVPN's native WireGuard configuration** that provides:
- 🔄 **Static WireGuard configuration** from AirVPN Config Generator
- 🌍 **Optimal server selection** for your region (Singapore recommended for Vietnam)
- 🚀 **Built-in port forwarding** configured through AirVPN client area
- ⚡ **No dynamic config generation needed**

> **Note**: Get your WireGuard configuration from AirVPN's Config Generator at https://airvpn.org/generator/. Select WireGuard protocol and copy the PrivateKey and Address values to your `.env` file.

### 5. Start the stack
```bash
# Using new convenience script (recommended)
./start.sh

# OR using Podman Compose directly
podman-compose -f core/podman-compose.yml up -d
```

### 6. Check status
```bash
# Comprehensive health check (recommended)
./maintenance/maintenance.sh health

# Check all services
podman-compose -f core/podman-compose.yml ps

# Monitor AirVPN VPN connection
./logs.sh gluetun

# Check VPN connection
./logs.sh gluetun

# Quick debug
./debug.sh
```

## ⚙️ Configuration

### 📁 Directory Structure

```
media-stack/
├── core/                     # Core configuration files
│   ├── podman-compose.yml   # Main service definitions with SELinux support
│   ├── .env.example         # Configuration template
│   └── media-stack.service  # SystemD service file
├── scripts/                  # Podman management scripts
│   ├── podman-up.sh         # Advanced stack startup script
│   ├── podman-down.sh       # Stack shutdown script
│   ├── podman-logs.sh       # Log viewing script with options
│   └── podman-systemd-wrapper.sh # SystemD integration wrapper
├── services/                 # Service-specific configurations
│   └── gluetun/             # VPN configs and scripts
│       ├── update-qb.sh     # qBittorrent port update script (optimized)
│       └── wireguard/       # WireGuard config directory
├── maintenance/              # Maintenance and debugging tools
│   ├── maintenance.sh       # Comprehensive maintenance and health checks
│   └── quick-debug.sh       # Fast troubleshooting script
├── docs/                     # Documentation
│   ├── README.md            # This file (main documentation)
│   ├── PODMAN.md            # Podman-specific setup guide
│   └── ROOCLINE-QUICK-REF.md # Quick reference for rapid deployment
├── .env                     # Environment variables (from core/.env.example)
├── start.sh                 # Convenience script - start entire stack
├── stop.sh                  # Convenience script - stop all services
├── logs.sh                  # Convenience script - view logs
├── debug.sh                 # Convenience script - quick troubleshooting
├── bazarr-config/           # Bazarr configuration
├── jellyfin-config/         # Jellyfin configuration
├── jellyfin-cache/          # Jellyfin cache
├── prowlarr-config/         # Prowlarr configuration
├── qbittorrent-config/      # qBittorrent configuration
├── radarr-config/           # Radarr configuration
└── sonarr-config/           # Sonarr configuration
```

### 🔧 Key Features of New Architecture

- ✅ **Organized Structure**: Clear separation of core config, scripts, services, and maintenance tools
- ✅ **Convenience Scripts**: Root-level scripts ([`start.sh`](start.sh), [`stop.sh`](stop.sh), [`logs.sh`](logs.sh), [`debug.sh`](debug.sh)) for easy access
- ✅ **Enhanced Scripts**: Improved [`services/gluetun/update-qb.sh`](services/gluetun/update-qb.sh:1) with AirVPN port forwarding support
- ✅ **Comprehensive Maintenance**: [`maintenance/maintenance.sh`](maintenance/maintenance.sh:1) provides health checks and diagnostics
- ✅ **Simplified Workflow**: Native AirVPN WireGuard configuration via Config Generator

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
   - Add qBittorrent: http://gluetun:8080
4. **Settings → General**: Connect with Prowlarr

#### Radarr (Port 7878)
1. Access http://localhost:7878
2. **Settings → Media Management**:
   - Root Folder: `/movies`
3. **Settings → Download Clients**:
   - Add qBittorrent: http://gluetun:8080
4. **Settings → General**: Connect with Prowlarr

#### Bazarr (Port 6767)
1. Access http://localhost:6767
2. **Settings → Sonarr**: http://sonarr:8989
3. **Settings → Radarr**: http://radarr:7878
4. Configure subtitle providers

#### qBittorrent (Port 8080)
1. Access http://localhost:8080
2. **Tools → Options → Downloads**:
   - Default Save Path: `/downloads`
3. **Connection**: Port will be automatically updated by AirVPN port forwarding

#### Jellyfin (Port 8096)
1. Access http://localhost:8096
2. Setup wizard: Create admin user
3. **Library Setup**:
   - Movies: `/movies`
   - TV Shows: `/tv`
4. **Playback → Transcoding**: Configure GPU if available

## 🎮 Usage

### Automated Workflow
1. **Pre-configured VPN**: AirVPN WireGuard configuration from Config Generator
2. **Connect VPN**: Gluetun connects using static AirVPN configuration
3. **Add content**: Use Sonarr/Radarr to add TV shows/movies
4. **Automatic search**: Prowlarr searches on configured indexers
5. **Download**: qBittorrent downloads through VPN with AirVPN port forwarding
6. **Organize**: Sonarr/Radarr automatically organize files
7. **Subtitles**: Bazarr automatically downloads subtitles
8. **Stream**: Jellyfin serves content

### Running with AirVPN WireGuard Config
```bash
# First time setup (uses pre-configured AirVPN credentials)
podman-compose up -d

# To update AirVPN configuration
# 1. Generate new config at https://airvpn.org/generator/
# 2. Update AIRVPN_WIREGUARD_PRIVATE_KEY and AIRVPN_WIREGUARD_ADDRESSES in .env
# 3. Restart VPN container
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
- **Base URL**: `http://localhost:8080/api/v2/`
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

### Convenience Scripts (Root Level)

| Script | Purpose | Usage |
|--------|---------|-------|
| [`start.sh`](start.sh) | Start entire stack | `./start.sh` |
| [`stop.sh`](stop.sh) | Stop all services | `./stop.sh` |
| [`logs.sh`](logs.sh) | View real-time logs | `./logs.sh [service]` |
| [`debug.sh`](debug.sh) | Quick troubleshooting | `./debug.sh` |

### Management Scripts (scripts/)

| Script | Purpose | Usage |
|--------|---------|-------|
| [`scripts/podman-up.sh`](scripts/podman-up.sh) | Advanced startup with options | `./scripts/podman-up.sh` |
| [`scripts/podman-down.sh`](scripts/podman-down.sh) | Advanced shutdown | `./scripts/podman-down.sh` |
| [`scripts/podman-logs.sh`](scripts/podman-logs.sh) | Advanced log viewing | `./scripts/podman-logs.sh -f service` |

### Maintenance Scripts (maintenance/)

| Script | Purpose | Usage |
|--------|---------|-------|
| [`maintenance/maintenance.sh`](maintenance/maintenance.sh) | Comprehensive health checks | `./maintenance/maintenance.sh health` |
| [`maintenance/quick-debug.sh`](maintenance/quick-debug.sh) | Fast troubleshooting | `./maintenance/quick-debug.sh` |

### Service Scripts (services/)

#### AirVPN Port Forwarding Management
[`services/gluetun/update-qb.sh`](services/gluetun/update-qb.sh) - Manages qBittorrent port configuration:

**Features:**
- Updates qBittorrent listening port for AirVPN forwarded ports
- Automatic port detection and configuration
- Error handling and retry logic
- Compatible with AirVPN's static port forwarding

**Configuration:**
```bash
# Environment variables in core/podman-compose.yml
AIRVPN_PORT_FORWARDING=true  # Enable AirVPN port forwarding support
VPN_RETRY_MAX=5             # Max retry attempts
VPN_CONNECT_TIMEOUT=30      # Connection timeout (seconds)
```

#### qBittorrent Port Update Script
[`services/gluetun/update-qb.sh`](services/gluetun/update-qb.sh) - Updates port for qBittorrent:

**Usage:**
```bash
# Manual run
PORT_FILE=/tmp/gluetun/forwarded_port \
QBIT_HOST=127.0.0.1 \
QBIT_WEBUI_PORT=8080 \
sh services/gluetun/update-qb.sh
```

## 🐛 Debugging & Maintenance

### Debug Mode

Enable debug mode for enhanced troubleshooting by setting the `DEBUG=true` environment variable in your [`.env`](core/.env.example:1) file:

```bash
# Enable debug mode
DEBUG=true
```

When debug mode is enabled:
- **Enhanced Logging**: All scripts output detailed debug information
- **Port Forwarding Debug**: AirVPN port forwarding interactions and status updates
- **qBittorrent Updates**: [`services/gluetun/update-qb.sh`](services/gluetun/update-qb.sh:1) logs all port update attempts
- **Container Startup**: Extended logging during service initialization

### Log Monitoring

```bash
# Monitor all services in real-time (convenience script)
./logs.sh

# Monitor specific service
./logs.sh gluetun
./logs.sh qbittorrent

# Advanced log monitoring
./scripts/podman-logs.sh -f --tail=50 SERVICE_NAME

# Direct podman-compose (specify config file)
podman-compose -f core/podman-compose.yml logs -f gluetun
```

### Health Checks

```bash
# Comprehensive health check (RECOMMENDED)
./maintenance/maintenance.sh health

# Quick debugging
./debug.sh

# Verify all services are healthy
podman-compose -f core/podman-compose.yml ps

# Check VPN connectivity and IP
podman-compose -f core/podman-compose.yml exec gluetun wget -qO- https://ipinfo.io

# Verify port forwarding is active
podman-compose -f core/podman-compose.yml exec gluetun wget -qO- https://portchecker.co/check

# Test internal service connectivity
podman-compose -f core/podman-compose.yml exec sonarr curl -I http://prowlarr:9696
podman-compose -f core/podman-compose.yml exec radarr curl -I http://gluetun:8080
```

### Configuration Validation

```bash
# Verify environment variables are set correctly
podman-compose -f core/podman-compose.yml config

# Check for common configuration issues
grep -E "(AIRVPN_WIREGUARD_PRIVATE_KEY|AIRVPN_WIREGUARD_ADDRESSES|QBIT_USER|QBIT_PASS)" .env

# Validate AirVPN configuration
grep -E "(AIRVPN_WIREGUARD_PRIVATE_KEY|AIRVPN_WIREGUARD_ADDRESSES)" .env
```

### Maintenance Tasks

#### Weekly Maintenance
```bash
# Use convenience scripts (recommended)
./stop.sh
./start.sh

# OR use comprehensive maintenance script
./maintenance/maintenance.sh cleanup

# OR manual approach - update AirVPN config if needed
# 1. Get new config from https://airvpn.org/generator/
# 2. Update .env with new credentials
podman-compose -f core/podman-compose.yml restart gluetun

# Update container images
podman-compose -f core/podman-compose.yml pull
podman-compose -f core/podman-compose.yml up -d

# Clean up old containers and images
podman system prune -f
```

#### Monthly Maintenance
```bash
# Full restart with fresh configurations (convenience)
./stop.sh
./start.sh

# OR manual approach
podman-compose -f core/podman-compose.yml down
podman-compose -f core/podman-compose.yml pull
podman-compose -f core/podman-compose.yml up -d --force-recreate

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
podman-compose -f core/podman-compose.yml exec gluetun iftop
```

## 🔍 Troubleshooting

### VPN Issues
```bash
# Quick troubleshooting (recommended)
./debug.sh

# Check VPN connection
podman-compose -f core/podman-compose.yml exec gluetun wget -qO- https://ipinfo.io

# Restart VPN with fresh config generation (convenience)
./maintenance/maintenance.sh restart-vpn

# OR manual restart
podman-compose -f core/podman-compose.yml restart gluetun qbittorrent

# Check VPN logs
./logs.sh gluetun

# Check AirVPN connection status
podman-compose -f core/podman-compose.yml exec gluetun wget -qO- https://ipinfo.io
```

### AirVPN Configuration Issues
```bash
# Check AirVPN connection logs
./logs.sh gluetun

# Verify AirVPN credentials in .env
grep -E "(AIRVPN_WIREGUARD_PRIVATE_KEY|AIRVPN_WIREGUARD_ADDRESSES)" .env

# Test different AirVPN server region
# Update AIRVPN_SERVER_COUNTRIES in .env (e.g., SG,HK,JP)
podman-compose -f core/podman-compose.yml restart gluetun

# Verify AirVPN account status at https://airvpn.org/client/
```

### Port Forwarding Issues
```bash
# Check forwarded port (check logs for port number)
./logs.sh gluetun | grep -i "port"

# Check Gluetun port forwarding logs
./logs.sh gluetun

# Manual port test
podman-compose -f core/podman-compose.yml exec gluetun wget -qO- https://portchecker.co/check
```

### Download Issues
```bash
# Check qBittorrent logs
./logs.sh qbittorrent

# Check if qBittorrent accessible
curl http://localhost:8080

# Check storage permissions
ls -la /media/Storage/downloads
```

### Jellyfin Transcoding Issues
```bash
# Check GPU access
podman-compose -f core/podman-compose.yml exec jellyfin nvidia-smi

# Check transcode logs
tail -f jellyfin-config/log/FFmpeg.Transcode-*.log

# Check hardware acceleration
# Settings → Playback → Hardware acceleration
```

### Service Connection Issues
```bash
# Test internal connectivity
podman-compose -f core/podman-compose.yml exec sonarr curl http://prowlarr:9696
podman-compose -f core/podman-compose.yml exec radarr curl http://qbittorrent:8080

# Restart specific service
podman-compose -f core/podman-compose.yml restart SERVICE_NAME

# Rebuild and restart (convenience)
./stop.sh
./start.sh

# OR manual rebuild
podman-compose -f core/podman-compose.yml down
podman-compose -f core/podman-compose.yml up -d --force-recreate
```

### Common Error Solutions

#### "VPN connection failed"
```bash
# Quick troubleshooting first
./debug.sh

# Check AirVPN connection status
./logs.sh gluetun

# Check AirVPN WireGuard configuration
podman-compose -f core/podman-compose.yml exec gluetun cat /etc/wireguard/wg0.conf

# Verify AirVPN credentials
grep -E "(AIRVPN_WIREGUARD_PRIVATE_KEY|AIRVPN_WIREGUARD_ADDRESSES)" .env

# Update AirVPN configuration if needed
# 1. Get new config from https://airvpn.org/generator/
# 2. Update .env file with new credentials
# 3. Restart container
podman-compose -f core/podman-compose.yml restart gluetun

# Check VPN endpoint connectivity (example IP)
ping 173.239.247.142
```

#### "AirVPN connection fails"
```bash
# Check AirVPN credentials and configuration
grep -E "(AIRVPN_WIREGUARD_PRIVATE_KEY|AIRVPN_WIREGUARD_ADDRESSES)" .env

# Test with different AirVPN server region
# Edit .env and change AIRVPN_SERVER_COUNTRIES (e.g., SG,HK,JP,KR)
podman-compose -f core/podman-compose.yml restart gluetun

# Verify AirVPN account status and server availability
# Check: https://airvpn.org/status/
# Verify your account at: https://airvpn.org/client/

# Test WireGuard configuration manually
# Get config from https://airvpn.org/generator/
```

#### "Port forwarding not working"
```bash
# Use maintenance script for diagnosis
./maintenance/maintenance.sh troubleshoot-pf

# Check AirVPN account supports port forwarding
# 1. Log into https://airvpn.org/client/
# 2. Go to "Forwarded Ports" section
# 3. Configure port forwarding if not already done
# 4. Verify AIRVPN_PORT_FORWARDING=true in .env
# Look for port forwarding messages in gluetun logs:
./logs.sh gluetun | grep -i "port"
```

#### "Download stuck in queue"
```bash
# Quick health check
./maintenance/maintenance.sh health

# Check available disk space
df -h /media/Storage

# Check qBittorrent connection status
curl http://localhost:8080

# Verify indexer connectivity in Prowlarr
# Check qBittorrent logs for connection issues
./logs.sh qbittorrent
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
./start.sh

# OR test with core compose file directly
podman-compose -f core/podman-compose.yml up -d

# Run tests (if available)
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
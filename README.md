# Media Stack with VPN

A complete Docker-based media stack solution with automated downloading, management, and streaming of media content through VPN to ensure privacy and security.

## 📋 Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
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
- **VPN & Port Forwarding**: Gluetun + PIA
- **CloudFlare bypass**: FlareSolverr

The entire system operates in Docker containers with high automation and security through VPN.

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
- **OS**: Linux (recommended Ubuntu 20.04+)
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **VPN**: Private Internet Access (PIA) account

### Network
- Port forwarding from router (if remote access needed)
- Stable internet connection

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
PIA_USER=your_pia_username
PIA_PASS=your_pia_password
QBIT_USER=your_qbittorrent_username
QBIT_PASS=your_qbittorrent_password
```

### 4. Configure WireGuard
Replace the content of [`gluetun/wireguard/wg0.conf`](gluetun/wireguard/wg0.conf) with WireGuard configuration from PIA:

```ini
[Interface]
Address = YOUR_VPN_IP/32
PrivateKey = YOUR_PRIVATE_KEY

[Peer]
PersistentKeepalive = 25
PublicKey = YOUR_PUBLIC_KEY
AllowedIPs = 0.0.0.0/0
Endpoint = YOUR_ENDPOINT:PORT
```

### 5. Start the stack
```bash
docker-compose up -d
```

### 6. Check status
```bash
docker-compose ps
docker-compose logs -f gluetun
```

## ⚙️ Configuration

### 📁 Directory Structure

```
media-stack/
├── docker-compose.yml          # Services definition
├── .env                       # Environment variables
├── .env.example              # Template for .env
├── bazarr-config/            # Bazarr configuration
├── gluetun/                  # VPN configs and scripts
│   ├── pia_pf_runner.sh     # PIA port forwarding script
│   ├── update-qb.sh         # qBittorrent port update script
│   └── wireguard/
│       └── wg0.conf         # WireGuard config
├── jellyfin-config/          # Jellyfin configuration
├── jellyfin-cache/           # Jellyfin cache
├── prowlarr-config/          # Prowlarr configuration
├── qbittorrent-config/       # qBittorrent configuration
├── radarr-config/           # Radarr configuration
└── sonarr-config/           # Sonarr configuration
```

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
1. **Add content**: Use Sonarr/Radarr to add TV shows/movies
2. **Automatic search**: Prowlarr searches on configured indexers
3. **Download**: qBittorrent downloads through VPN
4. **Organize**: Sonarr/Radarr automatically organize files
5. **Subtitles**: Bazarr automatically downloads subtitles
6. **Stream**: Jellyfin serves content

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
docker-compose logs -f qbittorrent

# View VPN status
docker-compose logs -f gluetun

# View port forwarding
docker-compose logs -f pia-pf
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

## 🔍 Troubleshooting

### VPN Issues
```bash
# Check VPN connection
docker-compose exec gluetun wget -qO- https://ipinfo.io

# Restart VPN
docker-compose restart gluetun pia-pf qbittorrent

# Check VPN logs
docker-compose logs gluetun
```

### Port Forwarding Issues
```bash
# Check forwarded port
cat gluetun/forwarded_port

# Check PIA logs
docker-compose logs pia-pf

# Manual port test
docker-compose exec gluetun wget -qO- https://portchecker.co/check
```

### Download Issues
```bash
# Check qBittorrent logs
docker-compose logs qbittorrent

# Check if qBittorrent accessible
curl http://localhost:8090

# Check storage permissions
ls -la /media/Storage/downloads
```

### Jellyfin Transcoding Issues
```bash
# Check GPU access
docker-compose exec jellyfin nvidia-smi

# Check transcode logs
tail -f jellyfin-config/log/FFmpeg.Transcode-*.log

# Check hardware acceleration
# Settings → Playback → Hardware acceleration
```

### Service Connection Issues
```bash
# Test internal connectivity
docker-compose exec sonarr curl http://prowlarr:9696
docker-compose exec radarr curl http://qbittorrent:8090

# Restart specific service
docker-compose restart SERVICE_NAME

# Rebuild and restart
docker-compose down
docker-compose up -d --force-recreate
```

### Common Error Solutions

#### "VPN connection failed"
```bash
# Check WireGuard config
cat gluetun/wireguard/wg0.conf

# Verify PIA credentials
echo $PIA_USER $PIA_PASS

# Check VPN endpoint connectivity
ping 173.239.247.142
```

#### "Port forwarding not working"
```bash
# Check PIA subscription supports port forwarding
# Verify PIA_USER and PIA_PASS in .env
# Check if VPN server supports port forwarding
```

#### "Download stuck in queue"
```bash
# Check available disk space
df -h /media/Storage

# Check qBittorrent connection status
# Verify indexer connectivity in Prowlarr
```

## 🤝 Contributing

### Bug Reports
1. Describe the issue in detail
2. Provide relevant logs
3. Environment information (OS, Docker version, etc.)
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
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

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
# Media Stack with VPN
Start here: [docs/INDEX.md](docs/INDEX.md:1)
Reading order: 2/8 • Essential

A complete Podman-based media stack solution with automated downloading, management, and streaming of media content through VPN to ensure privacy and security.

## ⚡ Quick Start

**🎯 For immediate context and rapid deployment:** See [`docs/QUICK-REF.md`](QUICK-REF.md:1) for essential commands and troubleshooting.

### Essential Commands
```bash
# Core operations
./scripts/podman-up.sh      # Start entire stack
./scripts/podman-down.sh    # Stop all services
./scripts/podman-logs.sh    # View real-time logs
./maintenance/quick-debug.sh  # Quick troubleshooting

# Health check (most important for issues)
./maintenance/maintenance.sh health
```

### New Project Structure Overview
```
├── core/                 # Core configuration files
│   ├── podman-compose.yml    # Main service definitions
│   ├── .env.example         # Configuration template
├── scripts/              # Podman management scripts
│   ├── podman-up.sh         # Start services
│   ├── podman-down.sh       # Stop services
│   ├── podman-logs.sh       # Log management
│   └── podman-systemd-wrapper.sh # SystemD integration wrapper
├── services/             # Service-specific configurations
│   └── gluetun/             # VPN and port forwarding
├── maintenance/          # Maintenance and debugging tools
│   ├── maintenance.sh       # Comprehensive maintenance
│   └── quick-debug.sh       # Fast troubleshooting
└── docs/                 # Documentation
    ├── README.md            # This file
    ├── PODMAN.md            # Podman-specific guide
    └── QUICK-REF.md # Quick reference
```

## 📋 Table of Contents

- [Media Stack with VPN](#media-stack-with-vpn)
	- [⚡ Quick Start](#-quick-start)
		- [Essential Commands](#essential-commands)
		- [New Project Structure Overview](#new-project-structure-overview)
	- [📋 Table of Contents](#-table-of-contents)
	- [🎯 Overview](#-overview)
		- [Key Features](#key-features)
	- [🏗️ System Architecture](#️-system-architecture)
	- [📋 System Requirements](#-system-requirements)
		- [Hardware](#hardware)
		- [Software](#software)
		- [Network](#network)
	- [🐳 Podman Support](#-podman-support)
		- [✅ Why Choose Podman?](#-why-choose-podman)
		- [🚀 Quick Start with Podman](#-quick-start-with-podman)
		- [2. Configure Credentials](#2-configure-credentials)
		- [📚 Comprehensive Documentation](#-comprehensive-documentation)
		- [🔧 Available Tools](#-available-tools)
		- [🏗️ Service Compatibility Status](#️-service-compatibility-status)
	- [🤝 Contributing](#-contributing)

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

# 2. Clone and setup
git clone <repository-url>
cd media-stack
cp core/.env.example core/.env
```

### 2. Configure Credentials
Edit [`core/.env`](core/.env:1) with your details:
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

### 📚 Comprehensive Documentation

For complete Podman setup, migration guide, SELinux configuration, and troubleshooting:

**👉 [Read the Complete Podman Guide](PODMAN.md:1)**

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
| [`scripts/podman-up.sh`](scripts/podman-up.sh:1) | Start media stack | scripts | `./scripts/podman-up.sh` |
| [`scripts/podman-down.sh`](scripts/podman-down.sh:1) | Stop media stack | scripts | `./scripts/podman-down.sh` |
| [`scripts/podman-logs.sh`](scripts/podman-logs.sh:1) | View logs | scripts | `./scripts/podman-logs.sh -f` |
| [`maintenance/quick-debug.sh`](maintenance/quick-debug.sh:1) | Quick troubleshooting | maintenance | `./maintenance/quick-debug.sh` |
| [`maintenance/maintenance.sh`](maintenance/maintenance.sh:1) | Comprehensive maintenance | maintenance | `./maintenance/maintenance.sh health` |
| [`core/podman-compose.yml`](core/podman-compose.yml:1) | Main configuration | core | `podman-compose -f core/podman-compose.yml up -d` |

### 🏗️ Service Compatibility Status

All services are **fully tested** and **production-ready** with Podman:

| Service | Status | Notes |
|---------|--------|-------|
| **AirVPN WireGuard** | ✅ Fully Supported | Native WireGuard configuration |
| **Gluetun VPN** | ✅ Fully Supported | VPN networking with port forwarding |
| **qBittorrent** | ✅ Fully Supported | Shared networking, automatic port updates |

The entire system is containerized with Podman, providing secure, isolated environments for each service.

## 🤝 Contributing

We welcome contributions! Please see the [Development & Contributing](QUICK-REF.md#development--contributing) section in the Quick Reference guide for details on:
- Setting up Git hooks
- Commit message conventions
- Pre-commit checks
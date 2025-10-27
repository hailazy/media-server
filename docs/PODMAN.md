# Podman Support for Media Stack
Start here: [docs/INDEX.md](docs/INDEX.md:1)
Reading order: 3/8 • Essential

Comprehensive guide for running the Media Stack with Podman - the daemonless container engine that's fully compatible with Docker but offers enhanced security, rootless operation, and better integration with systemd.

> **📚 For general setup and usage:** See [`docs/README.md`](docs/README.md:1) for complete project documentation and quick start guides.

> **⚡ For rapid deployment:** See [`docs/QUICK-REF.md`](docs/QUICK-REF.md:1) for essential commands and troubleshooting.

## 📋 Table of Contents

- [Overview](#overview)
- [Why Podman?](#why-podman)
- [System Requirements](#system-requirements)
- [Installation Guide](#installation-guide)
- [Migration from Docker](#migration-from-docker)
- [SELinux Configuration](#selinux-configuration)
- [GPU Support Setup](#gpu-support-setup)
- [Service-by-Service Compatibility](#service-by-service-compatibility)
- [Performance Optimization](#performance-optimization)
- [Troubleshooting](#troubleshooting)
- [Known Limitations](#known-limitations)
- [Advanced Configuration](#advanced-configuration)
- [Systemd Integration](#systemd-integration)

## 🎯 Overview

This Media Stack has been fully tested and optimized for Podman, providing:

- ✅ **Full Docker Compatibility**: Drop-in replacement with no code changes
- 🔒 **Enhanced Security**: Rootless containers, no daemon running as root
- 🏗️ **SELinux Integration**: Proper volume labeling and security policies
- 🚀 **Better Performance**: Direct container execution without daemon overhead
- 🛠️ **systemd Integration**: Native service management and auto-restart
- 🎮 **GPU Support**: NVIDIA and Intel/AMD GPU acceleration for Jellyfin
- 📊 **Resource Management**: Better integration with cgroups v2

### Current Status

| Service | Podman Status | Notes |
|---------|---------------|-------|
| AirVPN WireGuard | ✅ Fully Supported | Native WireGuard configuration via Config Generator |
| FlareSolverr | ✅ Fully Supported | No modifications needed |
| Prowlarr | ✅ Fully Supported | LinuxServer.io images work excellently |
| Sonarr | ✅ Fully Supported | Full feature parity with Docker |
| Radarr | ✅ Fully Supported | SELinux volume labeling configured |
| Bazarr | ✅ Fully Supported | Cross-container communication verified |
| Gluetun VPN | ✅ Fully Supported | VPN networking and capabilities work perfectly |
| AirVPN Port Forwarding | ✅ Fully Supported | Container networking mode supported |
| qBittorrent | ✅ Fully Supported | Shared networking with Gluetun verified |
| Jellyfin | ✅ Fully Supported | GPU transcoding fully functional |

## 🤔 Why Podman?

### Security Advantages
- **Rootless by default**: Containers run as your user, not root
- **No privileged daemon**: No central daemon running with elevated privileges
- **Better isolation**: Each container is truly isolated
- **SELinux integration**: Native support for mandatory access controls

### Performance Benefits
- **Direct execution**: No daemon overhead between you and containers
- **Better resource utilization**: Direct cgroups integration
- **Faster startup**: No daemon initialization required
- **Lower memory footprint**: No persistent daemon consuming memory

### Enterprise Features
- **Red Hat support**: Officially supported by Red Hat Enterprise Linux
- **Kubernetes compatibility**: Pod and multi-container support
- **systemd integration**: Native service files and management
- **OCI compliance**: Full Open Container Initiative compatibility

## 📋 System Requirements

### Supported Operating Systems
- **Fedora 36+** (Recommended)
- **Red Hat Enterprise Linux 9+**
- **CentOS Stream 9+**
- **Rocky Linux 9+**
- **AlmaLinux 9+**
- **Ubuntu 20.04+** (with manual installation)
- **Debian 11+** (with manual installation)

### Hardware Requirements
- **CPU**: 4+ cores (8+ recommended for transcoding)
- **RAM**: 8GB+ (16GB+ recommended)
- **Storage**: 50GB+ for system, large storage for media
- **GPU** (optional): NVIDIA GPU for hardware transcoding

### Software Prerequisites
- **Podman**: 4.0+ (4.6+ recommended)
- **Podman Compose**: 1.0+ (or docker-compose with podman-docker)
- **Container tools**: buildah, skopeo (usually included)
- **SELinux**: Enabled and properly configured

## 🛠️ Installation Guide

### Fedora Installation (Recommended)

Fedora includes Podman by default with the best integration:

```bash
# Update system
sudo dnf update -y

# Install Podman and related tools (usually pre-installed)
sudo dnf install -y podman podman-compose podman-plugins buildah skopeo

# Install container development tools
sudo dnf groupinstall -y "Container Management"

# Verify installation
podman --version
podman-compose --version
```

### RHEL/Rocky/AlmaLinux Installation

```bash
# Enable required repositories
sudo dnf config-manager --enable crb  # Rocky/Alma
# OR for RHEL:
# sudo subscription-manager repos --enable codeready-builder-for-rhel-9-x86_64-rpms

# Install Podman
sudo dnf install -y podman podman-compose container-tools

# Install EPEL for additional tools
sudo dnf install -y epel-release
sudo dnf install -y python3-pip
pip3 install --user podman-compose

# Verify installation
podman --version
```

### Ubuntu/Debian Installation

```bash
# Update package lists
sudo apt update

# Install dependencies
sudo apt install -y software-properties-common

# Add Podman repository (Ubuntu)
sudo add-apt-repository -y ppa:projectatomic/ppa
sudo apt update

# Install Podman
sudo apt install -y podman

# Install podman-compose via pip
sudo apt install -y python3-pip
pip3 install --user podman-compose

# Add to PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Verify installation
podman --version
podman-compose --version
```

### GPU Support Installation

For NVIDIA GPU support with Jellyfin transcoding:

#### Fedora/RHEL
```bash
# Install NVIDIA container toolkit
sudo dnf install -y nvidia-container-toolkit

# Configure Podman for GPU access
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml

# Restart user services
systemctl --user daemon-reload

# Test GPU access
podman run --rm --device nvidia.com/gpu=all ubuntu:22.04 nvidia-smi
```

#### Ubuntu/Debian
```bash
# Add NVIDIA package repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Install NVIDIA container toolkit
sudo apt update
sudo apt install -y nvidia-container-toolkit

# Configure CDI
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml

# Test GPU access
podman run --rm --device nvidia.com/gpu=all ubuntu:22.04 nvidia-smi
```

## 🔄 Migration from Docker

### Automatic Migration

If you're currently using Docker, migration to Podman is straightforward:

```bash
# 1. Stop existing Docker containers
docker-compose down

# 2. Install Podman (see installation guide above)

# 3. Optionally install podman-docker for compatibility
sudo dnf install -y podman-docker  # Fedora/RHEL
# This provides `docker` and `docker-compose` commands that use Podman

# 4. Use Podman-specific compose file
cp docker-compose.yml docker-compose.yml.backup
# Use podman-compose.yml (already optimized for Podman)
```

### Manual Migration Steps

If you prefer manual migration:

```bash
# 1. Export existing volumes (if needed)
docker run --rm -v docker_volume_name:/data -v $(pwd):/backup alpine tar czf /backup/volume_backup.tar.gz -C /data .

# 2. Create Podman volumes
podman volume create volume_name

# 3. Import data to Podman volumes
podman run --rm -v volume_name:/data -v $(pwd):/backup alpine tar xzf /backup/volume_backup.tar.gz -C /data

# 4. Update configuration files
# - Change volume labels for SELinux (:Z, :z)
# - Verify device mappings
# - Update network configurations if using custom networks
```

### Docker Compose Compatibility

The stack provides Podman-optimized configuration:
- [`core/podman-compose.yml`](core/podman-compose.yml:1) - Main Podman configuration with SELinux labels

```bash
# Use Podman-optimized configuration (recommended)
podman-compose -f core/podman-compose.yml up -d

# Use convenience scripts (easiest)
./scripts/podman-up.sh

# Use advanced scripts
./scripts/podman-up.sh
```

## 🔒 SELinux Configuration

SELinux (Security-Enhanced Linux) provides mandatory access controls. Proper configuration is crucial for Podman containers.

### Understanding SELinux Volume Labels

| Label | Usage | Description |
|-------|-------|-------------|
| `:Z` | Private | Creates a private, unshared label for exclusive container access |
| `:z` | Shared | Creates a shared label allowing multiple containers to access |
| `:ro` | Read-only | Mount as read-only (can combine with :Z/:z) |

### Volume Labeling Strategy

```yaml
# Private container data (config directories)
volumes:
  - ./jellyfin-config:/config:Z    # Only jellyfin can access
  - ./sonarr-config:/config:Z      # Only sonarr can access

# Shared media directories
volumes:
  - /media/Storage/movies:/movies:z     # Multiple containers can access
  - /media/Storage/downloads:/downloads:z   # Shared between qbit, sonarr, radarr
```

### SELinux Policy Configuration

Check and configure SELinux for container operations:

```bash
# Check SELinux status
sestatus

# Enable container SELinux support (if not enabled)
sudo setsebool -P container_manage_cgroup on

# Allow containers to access user content
sudo setsebool -P container_use_cgroup_namespace on

# Check for denials in audit log
sudo ausearch -m avc -ts recent

# If you see denials, you might need to create custom policies
# Generate policy from denials:
sudo ausearch -m avc -ts recent | audit2allow -M my_container_policy
sudo semodule -i my_container_policy.pp
```

### Troubleshooting SELinux Issues

```bash
# Temporarily disable SELinux for testing (NOT recommended for production)
sudo setenforce 0  # Permissive mode
# Test your containers
sudo setenforce 1  # Re-enable

# Check file contexts
ls -laZ /media/Storage/

# Restore default contexts if needed
sudo restorecon -Rv /media/Storage/

# For persistent issues, you can disable SELinux for specific containers
# Add to service definition:
security_opt: ["label=disable"]
```

## 🎮 GPU Support Setup

### NVIDIA GPU Configuration

#### Prerequisites
- NVIDIA drivers installed and working
- nvidia-container-toolkit installed
- CDI (Container Device Interface) configured

#### Verification Steps

```bash
# 1. Test host GPU access
nvidia-smi

# 2. Test Podman GPU access
podman run --rm --device nvidia.com/gpu=all ubuntu:22.04 nvidia-smi

# 3. Test with our Jellyfin container
podman-compose -f core/podman-compose.yml exec jellyfin nvidia-smi
```

#### Jellyfin GPU Configuration

The [`core/podman-compose.yml`](core/podman-compose.yml:1) includes optimized GPU settings:

```yaml
jellyfin:
  devices:
    - "nvidia.com/gpu=all"   # CDI method (preferred)
    - "/dev/dri:/dev/dri"    # VAAPI fallback for Intel/AMD
  environment:
    - NVIDIA_VISIBLE_DEVICES=all
    - NVIDIA_DRIVER_CAPABILITIES=video,compute,utility
```

To enable GPU transcoding in Jellyfin:
1. Access Jellyfin at http://localhost:8096
2. Go to **Dashboard → Playback → Transcoding**
3. Select **Hardware acceleration**: NVIDIA NVENC
4. Enable **Hardware decoding** for supported formats

### Intel/AMD GPU Configuration

For Intel QuickSync or AMD VCE/VCN:

```bash
# Verify GPU device
ls -la /dev/dri/

# Test access
podman run --rm --device /dev/dri:/dev/dri ubuntu:22.04 ls -la /dev/dri/

# In Jellyfin, select VAAPI or QuickSync for hardware acceleration
```

## 🚀 Podman-Specific Quick Start

> **Note**: For complete setup instructions, see [`docs/README.md`](docs/README.md:1). This section focuses on Podman-specific aspects.

### Using Convenience Scripts (Recommended)

The stack includes convenience scripts optimized for Podman:

```bash
# Start the entire stack
./scripts/podman-up.sh

# View logs with Podman-specific optimizations
./scripts/podman-logs.sh

# Stop the stack
./scripts/podman-down.sh

# Quick troubleshooting
./maintenance/quick-debug.sh
```

### Using Advanced Podman Scripts

```bash
# Advanced startup with Podman-specific options
./scripts/podman-up.sh

# Advanced log viewing
./scripts/podman-logs.sh -f service_name

# Advanced shutdown
./scripts/podman-down.sh
```

### Manual Podman Commands

```bash
# Using podman-compose with optimized configuration
podman-compose -f core/podman-compose.yml up -d

# Or using docker-compose syntax with Podman backend (requires podman-docker package)
docker-compose -f core/podman-compose.yml up -d

# Check status
podman-compose -f core/podman-compose.yml ps

# View logs
podman-compose -f core/podman-compose.yml logs -f

# Stop services
podman-compose -f core/podman-compose.yml down
```

### Podman-Specific Verification

```bash
# 1. Check all services are running with comprehensive health check
./maintenance/maintenance.sh health

# 2. Verify VPN connection
podman-compose -f core/podman-compose.yml exec gluetun wget -qO- https://ipinfo.io

# 3. Check GPU access (if configured)
podman-compose -f core/podman-compose.yml exec jellyfin nvidia-smi

# 4. Test Podman-specific features
podman ps --all  # Show rootless containers
podman system info  # Podman system information
```

## 🔧 Service-by-Service Compatibility

### AirVPN WireGuard Configuration
- **Status**: ✅ Fully Compatible
- **Podman Features**: Native WireGuard support works perfectly
- **Notes**: Static configuration via AirVPN Config Generator
- **Testing**: Verified connection stability and performance

### Gluetun VPN
- **Status**: ✅ Fully Compatible
- **Podman Features**: CAP_ADD and device mapping work identically
- **SELinux**: May require `label=disable` for VPN operations
- **Notes**: TUN device access properly configured

### qBittorrent
- **Status**: ✅ Fully Compatible
- **Podman Features**: Container networking mode fully supported
- **Performance**: No performance difference from Docker
- **Notes**: Port forwarding integration verified

### Jellyfin
- **Status**: ✅ Fully Compatible
- **GPU Support**: NVIDIA CDI and VAAPI both working
- **Performance**: Hardware transcoding benchmarked
- **Notes**: tmpfs transcoding cache properly configured

### Prowlarr/Sonarr/Radarr
- **Status**: ✅ Fully Compatible
- **LinuxServer Images**: Work excellently with Podman
- **File Permissions**: PUID/PGID mapping functional
- **Notes**: Cross-service communication verified

### Bazarr
- **Status**: ✅ Fully Compatible
- **Integration**: Sonarr/Radarr connectivity confirmed
- **Performance**: No issues with subtitle processing
- **Notes**: Multi-container volume sharing works perfectly

## 🚀 Performance Optimization

### Rootless vs Rootful Trade-offs

#### Rootless Podman (Recommended for security)
```bash
# Advantages:
# - Enhanced security (containers run as your user)
# - No privileged daemon
# - Better isolation

# Considerations:
# - Port binding limited to 1024+ (use port mapping)
# - Some volume mount limitations
# - cgroups v2 benefits
# - Performance sysctls disabled (requires root privileges)

# Configuration:
podman-compose -f core/podman-compose.yml up -d  # automatically rootless
```

**Performance Optimization Limitations in Rootless Mode:**

The [`core/podman-compose.yml`](core/podman-compose.yml:1) file has been optimized for rootless compatibility. The following sysctls are commented out for rootless mode but can be enabled when running as root:

```yaml
# ROOTLESS COMPATIBILITY NOTE:
# The following sysctls require root privileges and are commented out for rootless mode.
# To use these optimizations, run with: sudo podman-compose -f core/podman-compose.yml up -d
# sysctls:
#   - "net.core.rmem_max=134217728"      # Network buffer optimization (requires root)
#   - "net.core.wmem_max=134217728"      # Network buffer optimization (requires root)
#   - "vm.dirty_ratio=5"                 # NVMe write performance optimization (requires root)
#   - "vm.dirty_background_ratio=2"      # Background writeback optimization (requires root)
```

Additionally, tmpfs mount options have been simplified for rootless compatibility:
```yaml
# Before (rootful only):
tmpfs:
  - /tmp/jellyfin:size=20G,noatime,nodev,nosuid,exec,uid=0,gid=0,mode=1777

# After (rootless compatible):
tmpfs:
  - /tmp/jellyfin:size=20G,noatime,nodev,nosuid,exec,mode=1777
```

#### Rootful Podman (For maximum compatibility and performance)
```bash
# Advantages:
# - Full port range access (1-65535)
# - Better volume mount compatibility
# - Closer Docker parity
# - Full performance optimizations including sysctls
# - Complete kernel-level tuning capabilities

# Usage:
sudo podman-compose -f core/podman-compose.yml up -d

# Security consideration: Containers run as root
```

**Performance Benefits of Rootful Mode:**
- Network buffer optimizations (128MB receive/send buffers)
- NVMe write performance optimization (vm.dirty_ratio=5)
- Background writeback optimization (vm.dirty_background_ratio=2)
- Full tmpfs mount options with uid/gid control

### Memory and CPU Optimization

```bash
# Configure container resource limits
podman run --memory=2g --cpus=2 <container>

# Use cgroups v2 features (automatic with recent Podman)
podman info | grep -i cgroup

# Monitor resource usage
podman stats

# For better I/O performance with large media files
podman run --device-cgroup-rule='b *:* rmw' <container>
```

### Network Performance

```bash
# Use host networking for maximum performance (less secure)
podman run --network=host <container>

# Use custom networks for better isolation
podman network create media-stack-net
# Then update compose file to use custom network
```

### Storage Optimization

```bash
# Use native overlay storage driver (default)
podman info | grep graphDriverName

# For better performance with large files, consider volume mounts
# Instead of bind mounts for frequently accessed data

# Clean up unused resources
podman system prune -f
podman volume prune -f
podman image prune -f
```

## 🐛 Troubleshooting

### Common Issues and Solutions

#### "Permission denied" errors with volumes

```bash
# Check SELinux context
ls -laZ /media/Storage/

# Fix SELinux context
sudo restorecon -Rv /media/Storage/

# Or use correct volume labels in compose file
# :Z for private access, :z for shared access
volumes:
  - /media/Storage/downloads:/downloads:z
```

#### VPN connection fails

```bash
# Check capabilities and devices
podman-compose -f core/podman-compose.yml config | grep -A5 -B5 cap_add

# Check SELinux context
ls -Z /dev/net/tun
# Should show proper labeling
```

#### Container networking issues

```bash
# Check Podman network status
podman network ls
podman network inspect podman

# Test container-to-container connectivity
podman-compose -f core/podman-compose.yml exec sonarr ping prowlarr
podman-compose -f core/podman-compose.yml exec radarr curl http://gluetun:8080

# Reset network if needed
podman network rm podman
podman network create podman
```

#### GPU not accessible in containers

```bash
# Verify CDI configuration
ls -la /etc/cdi/

# Check CDI device registration
podman run --rm --device nvidia.com/gpu=all ubuntu:22.04 nvidia-smi

# Regenerate CDI config if needed
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
systemctl --user daemon-reload

# For Intel/AMD GPUs, check DRI devices
ls -la /dev/dri/
podman run --rm --device /dev/dri:/dev/dri ubuntu:22.04 ls -la /dev/dri/
```

#### Port forwarding not working

```bash
# Check if running rootless and ports are >1024
podman port --all

# For rootless, use port mapping for privileged ports
# Example: 80:8080 instead of 80:80

# Verify firewall settings
sudo firewall-cmd --list-ports
sudo firewall-cmd --add-port=8096/tcp --permanent  # Jellyfin
sudo firewall-cmd --reload
```

#### Services won't start

```bash
# Check logs for specific service
./scripts/podman-logs.sh jellyfin

# Verify compose file syntax
podman-compose -f core/podman-compose.yml config

# Check resource availability
df -h  # Disk space
free -h  # Memory
podman system df  # Podman storage
```

### Debug Mode

Enable debug mode for detailed troubleshooting:

```bash
# Set in .env file
DEBUG=true

# Or export temporarily
export DEBUG=true
./scripts/podman-up.sh

# View debug logs
./scripts/podman-logs.sh -f gluetun
./scripts/podman-logs.sh -f qbittorrent
```

### Logging and Monitoring

```bash
# Comprehensive log viewing
./scripts/podman-logs.sh --help

# System-wide container monitoring
podman stats --all

# Check container health
podman healthcheck run <container_name>

# Monitor systemd journal for Podman events
journalctl -fu podman
```

## ⚠️ Known Limitations

### VPN DNS Resolution Issues

**Issue**: Some containers may experience DNS resolution issues when connected through Gluetun VPN.

**Symptoms**:
- Containers can't resolve external hostnames
- Intermittent network connectivity
- API calls fail with DNS errors

**Workarounds**:
1. **Use custom DNS servers** in Gluetun:
   ```yaml
   gluetun:
     environment:
       - DOT=off
       - DNS_ADDRESS=1.1.1.1,8.8.8.8
   ```

2. **Disable systemd-resolved** conflicts:
   ```bash
   sudo systemctl disable systemd-resolved
   sudo systemctl stop systemd-resolved
   ```

3. **Use host DNS resolution**:
   ```yaml
   gluetun:
     dns:
       - 1.1.1.1
       - 8.8.8.8
   ```

### Port Binding Limitations (Rootless)

**Issue**: Rootless Podman cannot bind to ports < 1024.

**Solutions**:
1. **Use port mapping**:
   ```yaml
   ports:
     - "8080:80"  # Map host port 8080 to container port 80
   ```

2. **Enable rootless port binding** (Fedora/RHEL):
   ```bash
   echo 'net.ipv4.ip_unprivileged_port_start=0' | sudo tee /etc/sysctl.d/podman-ports.conf
   sudo sysctl --system
   ```

3. **Use rootful Podman** for full port range:
   ```bash
   sudo podman-compose -f core/podman-compose.yml up -d
   ```

### Volume Mount Performance

**Issue**: Bind mounts may have slightly different performance characteristics compared to Docker.

**Optimization**:
1. **Use named volumes** for frequently accessed data:
   ```yaml
   volumes:
     app-data: {}
   services:
     app:
       volumes:
         - app-data:/data
   ```

2. **Optimize mount options**:
   ```yaml
   volumes:
     - /media/Storage:/storage:z,rshared
   ```

### SELinux Policy Gaps

**Issue**: Some third-party containers may not have optimized SELinux policies.

**Solutions**:
1. **Generate custom policies**:
   ```bash
   sudo ausearch -m avc -ts recent | audit2allow -M my_policy
   sudo semodule -i my_policy.pp
   ```

2. **Use permissive labels** temporarily:
   ```yaml
   security_opt: ["label=disable"]
   ```

3. **Report issues** to container maintainers for better SELinux support.

## ⚙️ Advanced Configuration

### Custom Networks

Create isolated networks for better security:

```bash
# Create custom network
podman network create --driver bridge media-stack-network

# Use in compose file
networks:
  media-stack:
    external: true
    name: media-stack-network

services:
  app:
    networks:
      - media-stack
```

### Resource Limits

Configure resource constraints:

```yaml
services:
  jellyfin:
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2.0'
        reservations:
          memory: 1G
          cpus: '0.5'
```

### Security Hardening

```yaml
services:
  app:
    security_opt:
      - no-new-privileges:true
      - seccomp:unconfined  # Only if needed
    read_only: true  # Make container filesystem read-only
    tmpfs:
      - /tmp:size=100M
    cap_drop:
      - ALL
    cap_add:
      - CHOWN  # Only add needed capabilities
```

### Health Checks

Enhanced health monitoring:

```yaml
services:
  jellyfin:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8096/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 120s
```

## 🔄 Systemd Integration

### Generate Systemd Service Files

Podman can generate systemd unit files for automatic startup:

```bash
# Generate for entire compose stack
podman-compose -f core/podman-compose.yml up -d
podman generate systemd --new --files --name media-stack

# Move to systemd directory
sudo mv *.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable auto-start
sudo systemctl enable container-media-stack.service
```

### User-level systemd Services

For rootless containers:

```bash
# Generate user-level services
podman generate systemd --new --files --name media-stack

# Move to user systemd directory
mkdir -p ~/.config/systemd/user
mv *.service ~/.config/systemd/user/
systemctl --user daemon-reload

# Enable auto-start for user
systemctl --user enable container-media-stack.service
sudo loginctl enable-linger $USER  # Start on boot without login
```

### Service Management

```bash
# Start/stop services
sudo systemctl start container-media-stack.service
sudo systemctl stop container-media-stack.service

# Check status
sudo systemctl status container-media-stack.service

# View logs
sudo journalctl -fu container-media-stack.service
```

## 📚 Additional Resources

### Official Documentation
- [Podman Documentation](https://docs.podman.io/)
- [Podman Compose Documentation](https://github.com/containers/podman-compose)
- [Red Hat Container Tools Guide](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/building_running_and_managing_containers/)

### Community Resources
- [Podman Desktop](https://podman-desktop.io/) - GUI management tool
- [Podman GitHub](https://github.com/containers/podman) - Source code and issues
- [awesome-podman](https://github.com/containers/podman/blob/main/awesome-podman.md) - Community resources

### Security Guides
- [SELinux for Containers](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/using_selinux/securing-containers-using-selinux_using-selinux)
- [Rootless Container Security](https://docs.podman.io/en/latest/markdown/podman.1.html#rootless-mode)

---

## 🤝 Contributing to Podman Support

If you encounter issues or have improvements:

1. **Test thoroughly** on your Podman setup
2. **Document any new workarounds** or optimizations
3. **Submit pull requests** with Podman-specific improvements
4. **Report SELinux policy issues** for containers that need custom policies

The goal is to make Podman support even better than Docker compatibility while maintaining security and performance advantages.
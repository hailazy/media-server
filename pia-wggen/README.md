# PIA WireGuard Generator

A one-shot Podman service that generates fresh WireGuard configurations for the closest PF-capable Private Internet Access (PIA) region.

## Features

- 🔄 **Automated Generation**: Creates fresh WireGuard configs on every startup
- 🌍 **Smart Server Selection**: Finds the closest PIA region with lowest latency
- 🚀 **Port Forwarding Support**: Supports PF-capable regions when enabled
- 📊 **Comprehensive Metadata**: Generates detailed region and server information
- 🐳 **Container Integration**: Seamlessly integrates with the media stack
- ⚡ **Lightweight**: Alpine-based container with minimal footprint
- 🔒 **Secure**: Uses PIA's official API with certificate verification

## Integration with Media Stack

This service is **integrated into the main media stack** and uses **consolidated configuration** from the root [`.env`](../.env.example:1) file. No separate configuration is needed.

### Key Benefits in Media Stack Context

- ✅ **Zero Manual Configuration**: Automatically generates optimal configs on startup
- ✅ **Consolidated Settings**: All configuration managed from root `.env` file
- ✅ **Enhanced Performance**: Finds fastest PIA servers based on latency testing
- ✅ **Debug Support**: Enhanced logging when `DEBUG=true` is set
- ✅ **Maintenance-Free**: No need to manually update WireGuard configurations

## Usage

### Build the Container

#### Using Podman
```bash
cd pia-wggen
podman build -t pia-wggen .
```

### Run as One-Shot Container

#### Using Podman
```bash
podman run --rm \
  -e PIA_USER=p1234567 \
  -e PIA_PASS=your_password \
  -e PIA_PF=true \
  -v $(pwd)/output:/output \
  pia-wggen
```

### Environment Variables

All configuration is managed through the root [`.env`](../.env.example:1) file. The following variables control PIA-WGGen behavior:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PIA_USER` | ✓ | - | PIA username (format: p1234567) |
| `PIA_PASS` | ✓ | - | PIA password |
| `PIA_PF` | ✗ | true | Enable port forwarding (recommended: true) |
| `MAX_LATENCY` | ✗ | 0.05 | Maximum latency for server selection (recommended: 0.05) |
| `PREFERRED_REGION` | ✗ | none | Force specific region or 'none' for auto-selection |
| `DEBUG` | ✗ | false | Enable detailed debug logging |

> **Note**: These variables are configured in the root [`.env`](../.env.example:1) file, not in a separate pia-wggen configuration file.

### Output Files

After successful execution, the following files will be created in the output directory:

#### `/output/wg0.conf`
WireGuard configuration file ready to use with WireGuard clients or gluetun.

#### `/output/region-metadata.json`
JSON metadata file containing:
- Selected region information (name, country, capabilities)
- Server details (hostname, IP, port, public key)
- Configuration details (peer IP, DNS servers, port forwarding status)
- Generation timestamp

## Podman Support for Fedora Workstation

This service is fully compatible with Podman, the default container engine for Fedora Workstation. Podman can run all the same containers without requiring root privileges or a daemon.

### Installing Podman on Fedora

Podman comes pre-installed on Fedora Workstation 31+. If you need to install it:

```bash
sudo dnf install podman podman-compose
```

### Using Podman Compose

You can use podman-compose for container orchestration:

```bash
# Install podman-compose if not already available
sudo dnf install podman-compose

# Use podman-compose for container orchestration
podman-compose up
podman-compose down
```

### Alternative: Using Podman with Compose Files

Podman 3.0+ includes built-in compose support:

```bash
# Generate Kubernetes YAML from compose file
podman-compose -f podman-compose.yml config > pia-wggen-pod.yaml

# Run with podman play
podman play kube pia-wggen-pod.yaml

# Stop the pod
podman pod stop pia-wggen
podman pod rm pia-wggen
```

### Podman-Specific Considerations

1. **Rootless by Default**: Podman runs containers without root privileges by default
2. **No Daemon**: Podman doesn't require a running daemon
3. **SELinux Compatibility**: Podman works seamlessly with Fedora's SELinux policies
4. **Systemd Integration**: Podman containers can be managed as systemd services

### Running with Podman Systemd Integration

You can run the pia-wggen service as a systemd user service:

```bash
# Generate systemd unit file
podman generate systemd --name pia-wggen --files --new

# Move the unit file to user systemd directory
mkdir -p ~/.config/systemd/user
mv container-pia-wggen.service ~/.config/systemd/user/

# Enable and start the service
systemctl --user daemon-reload
systemctl --user enable container-pia-wggen.service
systemctl --user start container-pia-wggen.service
```

### Volume Mounting with Podman

Podman handles volume mounting slightly differently. Use absolute paths or ensure proper SELinux contexts:

```bash
# Using absolute path
podman run --rm \
  -e PIA_USER=p1234567 \
  -e PIA_PASS=your_password \
  -e PIA_PF=true \
  -v /home/$(whoami)/pia-output:/output:Z \
  pia-wggen

# The :Z flag ensures proper SELinux labeling for Fedora
```

## Integration with Podman Compose

### As Init Container for Gluetun

#### Podman Compose
```yaml
version: '3.8'

services:
  pia-wggen:
    build: ./pia-wggen
    environment:
      - PIA_USER=${PIA_USER}
      - PIA_PASS=${PIA_PASS}
      - PIA_PF=true
    volumes:
      - wireguard-config:/output
    restart: "no"

  gluetun:
    image: qmcgaw/gluetun
    depends_on:
      pia-wggen:
        condition: service_completed_successfully
    cap_add:
      - NET_ADMIN
    environment:
      - VPN_SERVICE_PROVIDER=custom
      - VPN_TYPE=wireguard
      - VPN_ENDPOINT_IP=# Will be set by init script
      - VPN_ENDPOINT_PORT=# Will be set by init script
      - WIREGUARD_PRIVATE_KEY=# Will be set by init script
      - WIREGUARD_PUBLIC_KEY=# Will be set by init script
      - WIREGUARD_ADDRESSES=# Will be set by init script
    volumes:
      - wireguard-config:/gluetun/wireguard:ro
    ports:
      - "8888:8888/tcp" # HTTP proxy
      - "8388:8388/tcp" # Shadowsocks
    restart: unless-stopped

volumes:
  wireguard-config:
```

#### Using Podman Compose
Run with podman-compose:

```bash
# Using podman-compose
podman-compose -f podman-compose.yml up

# Or using podman play kube (convert first)
podman-compose -f podman-compose.yml config > pia-gluetun-stack.yaml
podman play kube pia-gluetun-stack.yaml
```

#### Podman Pod Alternative
For a pure Podman approach without compose:

```bash
# Create a pod for the services
podman pod create --name pia-stack -p 8888:8888 -p 8388:8388

# Create shared volume
podman volume create wireguard-config

# Run pia-wggen first
podman run --pod pia-stack --rm \
  -e PIA_USER=${PIA_USER} \
  -e PIA_PASS=${PIA_PASS} \
  -e PIA_PF=true \
  -v wireguard-config:/output \
  pia-wggen

# Then run gluetun (after pia-wggen completes)
podman run --pod pia-stack -d \
  --cap-add NET_ADMIN \
  --name gluetun \
  -e VPN_SERVICE_PROVIDER=custom \
  -e VPN_TYPE=wireguard \
  -v wireguard-config:/gluetun/wireguard:ro \
  qmcgaw/gluetun
```

### Configuration Example

The PIA-WGGen service uses the main media stack configuration. Edit the root [`.env`](../.env.example:1) file:

```bash
# PIA Credentials (Required)
PIA_USER=p1234567
PIA_PASS=your_password_here

# PIA WireGuard Generator Configuration
PIA_PF=true
MAX_LATENCY=0.05
PREFERRED_REGION=none

# Debug mode (optional)
DEBUG=false
```

> **Important**: No separate `.env` file is needed for PIA-WGGen. All configuration is consolidated in the root `.env` file.

### Podman Compose File

A Podman-optimized compose file is provided as [`podman-compose.yml`](podman-compose.yml) with the following enhancements for Fedora Workstation:

- SELinux-compatible volume mounting (`:Z` flag)
- Proper container labeling for security
- Optimized for rootless Podman operation
- Includes gluetun integration example

Use it with:

```bash
# Using podman-compose
podman-compose -f podman-compose.yml up

# Or convert to Kubernetes YAML for podman play
podman-compose -f podman-compose.yml config > pia-wggen-pod.yaml
podman play kube pia-wggen-pod.yaml

# Clean up
podman pod stop pia-wggen-pod
podman pod rm pia-wggen-pod
```

### Quick Start for Fedora Users

1. **Install dependencies** (if not already installed):
   ```bash
   sudo dnf install podman podman-compose
   ```

2. **Setup media stack**:
   ```bash
   cd media-stack
   cp .env.example .env
   # Edit .env with your PIA credentials and configuration
   ```

3. **Start the complete stack**:
   ```bash
   podman-compose up -d
   ```

4. **Verify config generation**:
   ```bash
   # Check PIA-WGGen logs
   podman-compose logs pia-wggen
   
   # Verify WireGuard config was created
   podman volume inspect media-stack_wireguard-config
   ```

### Standalone Usage (Advanced)

For standalone usage outside the media stack:

```bash
# Build the container
podman build -t pia-wggen .

# Run with environment variables
podman run --rm \
  -e PIA_USER=p1234567 \
  -e PIA_PASS=your_password \
  -e PIA_PF=true \
  -e DEBUG=true \
  -v $(pwd)/output:/output:Z \
  pia-wggen
```

## Error Handling

The service will exit with code 1 and log errors for:
- Missing or invalid PIA credentials
- Network connectivity issues
- No suitable regions found (when PF is required)
- API authentication failures
- Configuration generation failures

## Security Notes

- The container runs as a one-shot service and exits after generating the configuration
- No persistent storage of credentials within the container
- Uses PIA's official CA certificate for API verification
- Generated private keys are ephemeral and not stored persistently
- Supports latest PIA WireGuard API endpoints

## License

This project follows the same MIT license as the original PIA manual connections scripts.
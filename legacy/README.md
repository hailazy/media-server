# Legacy Components

This directory contains deprecated and redundant components that have been superseded by more modern and efficient implementations.

## Contents

### manual-connections-script-pia/

**Status:** DEPRECATED - DO NOT USE

**Reason for deprecation:** This directory contained manual PIA (Private Internet Access) connection scripts that provided redundant functionality. The modern media-stack now uses a more efficient approach:

- **Modern Implementation:** [`pia-wggen`](../pia-wggen/) + [`gluetun`](../gluetun/) combination
- **Benefits of new approach:**
  - Cleaner Docker integration
  - Automatic WireGuard configuration generation
  - Better separation of concerns
  - Simplified maintenance
  - Reduced code duplication

**What was moved:**
- All shell scripts for manual OpenVPN/WireGuard connections
- Static configuration files
- Legacy CA certificates
- Manual port forwarding scripts

**Migration notes:**
- All PIA functionality is now handled by the `pia-wggen` init container
- WireGuard configurations are automatically generated and mounted to `gluetun`
- Port forwarding is managed by the `pia-pf` service
- No manual intervention required for VPN setup

## Usage

These components are preserved for historical reference only. **Do not use them in production.**

If you need to reference the old implementation for any reason, the files are preserved exactly as they were when moved to this legacy directory.

For current VPN functionality, refer to:
- [`pia-wggen/README.md`](../pia-wggen/README.md) - WireGuard config generation
- [`gluetun/`](../gluetun/) - VPN container and scripts
- Main project [`README.md`](../README.md) - Complete setup instructions

---

**Moved on:** 2025-10-24  
**Part of cleanup initiative:** Remove redundant VPN implementations and consolidate configuration
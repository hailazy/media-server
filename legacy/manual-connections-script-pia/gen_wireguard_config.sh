#!/bin/bash

# This script generates WireGuard configuration for PIA VPN
# using username, password, preferred region and port forwarding option

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

# Source environment variables if exists
if [[ -f "./env_var.sh" ]]; then
    source ./env_var.sh
fi

# Check required variables
if [[ -z $PIA_USER || -z $PIA_PASS ]]; then
    echo "Please set PIA_USER and PIA_PASS environment variables"
    echo "Example:"
    echo "export PIA_USER=pXXXXXX"
    echo "export PIA_PASS=your_password"
    exit 1
fi

# Set defaults if not provided
PREFERRED_REGION=${PREFERRED_REGION:-"none"}
PIA_PF=${PIA_PF:-"false"}

# Export required variables
export PIA_USER
export PIA_PASS
export PREFERRED_REGION
export PIA_PF
export VPN_PROTOCOL="wireguard"

echo "Generating WireGuard configuration..."
echo "Username: $PIA_USER"
echo "Preferred Region: $PREFERRED_REGION"
echo "Port Forwarding: $PIA_PF"

# Get authentication token
if ! ./get_token.sh; then
    echo "Failed to get authentication token"
    exit 1
fi

# Get token from file
PIA_TOKEN=$(head -n 1 /opt/piavpn-manual/token)
export PIA_TOKEN

# Get region and connect
if ! ./get_region.sh; then
    echo "Failed to get region information"
    rm -f /opt/piavpn-manual/token
    exit 1
fi

echo "WireGuard configuration has been generated successfully"
echo "Configuration file is located at: /etc/wireguard/pia.conf"

# Cleanup
# rm -f /opt/piavpn-manual/token
# rm -f /opt/piavpn-manual/latencyList
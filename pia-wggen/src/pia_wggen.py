#!/usr/bin/env python3
"""
PIA WireGuard Configuration Generator

This script generates a fresh WireGuard configuration for the closest
PF-capable PIA region using PIA's API.
"""

import os
import sys
import json
import time
import base64
import logging
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
import urllib3


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class PIAWGGen:
    """PIA WireGuard Configuration Generator"""
    
    def __init__(self):
        self.serverlist_url = "https://serverlist.piaservers.net/vpninfo/servers/v6"
        self.token_url = "https://www.privateinternetaccess.com/api/client/v2/token"
        self.ca_cert_path = "/app/ca.rsa.4096.crt"
        self.output_dir = "/output"
        
        # Get environment variables
        self.pia_user = os.getenv('PIA_USER')
        self.pia_pass = os.getenv('PIA_PASS')
        self.pia_pf = os.getenv('PIA_PF', 'false').lower() == 'true'
        self.max_latency = float(os.getenv('MAX_LATENCY', '0.05'))
        self.preferred_region = os.getenv('PREFERRED_REGION', 'none')
        
        # Validate required credentials
        if not self.pia_user or not self.pia_pass:
            logger.error("PIA_USER and PIA_PASS environment variables are required")
            sys.exit(1)
            
        logger.info(f"PIA_USER: {self.pia_user}")
        logger.info(f"Port Forwarding: {self.pia_pf}")
        logger.info(f"Max Latency: {self.max_latency}s")
        logger.info(f"Preferred Region: {self.preferred_region}")

    def get_auth_token(self):
        """Authenticate with PIA and get auth token"""
        logger.info("Getting authentication token...")
        
        try:
            response = requests.post(
                self.token_url,
                data={
                    'username': self.pia_user,
                    'password': self.pia_pass
                },
                timeout=30
            )
            response.raise_for_status()
            
            token_data = response.json()
            token = token_data.get('token')
            
            if not token:
                logger.error("Failed to authenticate with PIA")
                sys.exit(1)
                
            logger.info("Successfully authenticated")
            return token
            
        except requests.RequestException as e:
            logger.error(f"Failed to get auth token: {e}")
            sys.exit(1)

    def get_server_list(self):
        """Get list of PIA servers"""
        logger.info("Getting server list...")
        
        try:
            response = requests.get(self.serverlist_url, timeout=30)
            response.raise_for_status()
            
            # PIA API returns JSON followed by base64-encoded certificate data
            # Find the actual end of the complete JSON object
            response_text = response.text
            
            # Search backwards from the end to find the last valid JSON ending
            json_part = None
            for i in range(len(response_text)-1, max(0, len(response_text)-10000), -1):
                if response_text[i] == '}':
                    # Try parsing from start to this position
                    try:
                        candidate = response_text[:i+1]
                        server_data = json.loads(candidate)
                        json_part = candidate
                        break
                    except json.JSONDecodeError:
                        continue
            
            if json_part is None:
                # Fallback to normal JSON parsing if extraction fails
                server_data = response.json()
            
            if len(response_text) < 1000:
                logger.error("Invalid server data received")
                sys.exit(1)
                
            logger.info("Successfully retrieved server list")
            return server_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse server list JSON: {e}")
            sys.exit(1)
        except requests.RequestException as e:
            logger.error(f"Failed to get server list: {e}")
            sys.exit(1)

    def test_server_latency(self, server_ip, region_id, region_name, is_geo):
        """Test latency to a specific server"""
        try:
            start_time = time.time()
            response = requests.get(
                f"http://{server_ip}:443",
                timeout=self.max_latency,
                allow_redirects=False
            )
            latency = time.time() - start_time
            
            geo_suffix = " (geo)" if is_geo else ""
            logger.info(f"Got latency {latency:.3f}s for region: {region_name}{geo_suffix}")
            
            return {
                'latency': latency,
                'region_id': region_id,
                'region_name': region_name,
                'server_ip': server_ip,
                'is_geo': is_geo
            }
            
        except (requests.RequestException, Exception):
            return None

    def find_best_region(self, server_data):
        """Find the best region based on latency and requirements"""
        regions = server_data.get('regions', [])
        
        if self.preferred_region != 'none':
            # Use specific region if provided
            for region in regions:
                if region['id'] == self.preferred_region:
                    if self.pia_pf and not region.get('port_forward', False):
                        logger.error(f"Region {self.preferred_region} does not support port forwarding")
                        sys.exit(1)
                    logger.info(f"Using preferred region: {region['name']}")
                    return region
            # Log available regions for debugging
            available_regions = [f"{r['id']} ({r['name']})" for r in regions[:10]]  # Show first 10
            logger.error(f"Preferred region {self.preferred_region} not found")
            logger.info(f"Available regions (first 10): {', '.join(available_regions)}")
            sys.exit(1)
        
        # Filter regions based on port forwarding requirement
        if self.pia_pf:
            logger.info("Port Forwarding enabled, filtering PF-capable regions")
            regions = [r for r in regions if r.get('port_forward', False)]
            
        if not regions:
            logger.error("No suitable regions found")
            sys.exit(1)
        
        logger.info(f"Testing {len(regions)} regions for latency...")
        
        # Test latency to regions
        latency_results = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            
            for region in regions:
                if region.get('servers', {}).get('meta'):
                    server_ip = region['servers']['meta'][0]['ip']
                    future = executor.submit(
                        self.test_server_latency,
                        server_ip,
                        region['id'],
                        region['name'],
                        region.get('geo', False)
                    )
                    futures.append(future)
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    latency_results.append(result)
        
        if not latency_results:
            logger.error(f"No regions responded within {self.max_latency}s")
            sys.exit(1)
        
        # Sort by latency and get the best one
        latency_results.sort(key=lambda x: x['latency'])
        best_result = latency_results[0]
        
        # Find the full region data
        best_region = None
        for region in regions:
            if region['id'] == best_result['region_id']:
                best_region = region
                break
        
        if not best_region:
            logger.error("Failed to find best region data")
            sys.exit(1)
        
        logger.info(f"Selected region: {best_region['name']} (latency: {best_result['latency']:.3f}s)")
        return best_region

    def generate_wireguard_keys(self):
        """Generate WireGuard private and public keys"""
        private_key = X25519PrivateKey.generate()
        
        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_key_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        private_key_b64 = base64.b64encode(private_key_bytes).decode('ascii')
        public_key_b64 = base64.b64encode(public_key_bytes).decode('ascii')
        
        return private_key_b64, public_key_b64

    def get_wireguard_config(self, region, token):
        """Get WireGuard configuration from PIA API"""
        logger.info("Generating WireGuard configuration...")
        
        # Get WireGuard server details
        wg_servers = region.get('servers', {}).get('wg', [])
        if not wg_servers:
            logger.error("No WireGuard servers available for this region")
            sys.exit(1)
        
        wg_server = wg_servers[0]
        server_ip = wg_server['ip']
        hostname = wg_server['cn']
        
        # Generate keys
        private_key, public_key = self.generate_wireguard_keys()
        
        # Call PIA WireGuard API
        try:
            # Disable SSL hostname verification warnings for IP-based connections
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            response = requests.get(
                f"https://{server_ip}:1337/addKey",
                params={
                    'pt': token,
                    'pubkey': public_key
                },
                verify=False,  # Skip SSL verification since we're using IP instead of hostname
                timeout=30,
                headers={
                    'Host': hostname
                }
            )
            response.raise_for_status()
            
            wg_data = response.json()
            
            if wg_data.get('status') != 'OK':
                logger.error("PIA WireGuard API did not return OK")
                sys.exit(1)
            
            logger.info("Successfully generated WireGuard configuration")
            
            return {
                'private_key': private_key,
                'public_key': public_key,
                'server_ip': server_ip,
                'hostname': hostname,
                'peer_ip': wg_data['peer_ip'],
                'server_key': wg_data['server_key'],
                'server_port': wg_data['server_port'],
                'dns_servers': wg_data.get('dns_servers', [])
            }
            
        except requests.RequestException as e:
            logger.error(f"Failed to get WireGuard config: {e}")
            sys.exit(1)

    def write_wireguard_config(self, wg_config):
        """Write WireGuard configuration file"""
        config_path = os.path.join(self.output_dir, "wg0.conf")
        
        config_content = f"""[Interface]
Address = {wg_config['peer_ip']}
PrivateKey = {wg_config['private_key']}
DNS = {', '.join(wg_config['dns_servers'])}

[Peer]
PublicKey = {wg_config['server_key']}
AllowedIPs = 0.0.0.0/0
Endpoint = {wg_config['server_ip']}:{wg_config['server_port']}
PersistentKeepalive = 25
"""
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        logger.info(f"WireGuard configuration written to {config_path}")
        return config_path

    def write_metadata(self, region, wg_config):
        """Write region metadata file"""
        metadata_path = os.path.join(self.output_dir, "region-metadata.json")
        
        metadata = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'region': {
                'id': region['id'],
                'name': region['name'],
                'country': region.get('country', ''),
                'geo': region.get('geo', False),
                'port_forward': region.get('port_forward', False),
                'dns': region.get('dns', '')
            },
            'server': {
                'hostname': wg_config['hostname'],
                'ip': wg_config['server_ip'],
                'port': wg_config['server_port'],
                'public_key': wg_config['server_key']
            },
            'config': {
                'peer_ip': wg_config['peer_ip'],
                'dns_servers': wg_config['dns_servers'],
                'port_forwarding_enabled': self.pia_pf
            }
        }
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Metadata written to {metadata_path}")
        return metadata_path

    def run(self):
        """Main execution function"""
        logger.info("Starting PIA WireGuard configuration generation")
        
        try:
            # Step 1: Get authentication token
            token = self.get_auth_token()
            
            # Step 2: Get server list
            server_data = self.get_server_list()
            
            # Step 3: Find best region
            best_region = self.find_best_region(server_data)
            
            # Step 4: Generate WireGuard configuration
            wg_config = self.get_wireguard_config(best_region, token)
            
            # Step 5: Write configuration file
            config_path = self.write_wireguard_config(wg_config)
            
            # Step 6: Write metadata
            metadata_path = self.write_metadata(best_region, wg_config)
            
            logger.info("PIA WireGuard configuration generation completed successfully")
            logger.info(f"Configuration: {config_path}")
            logger.info(f"Metadata: {metadata_path}")
            
        except Exception as e:
            logger.error(f"Failed to generate configuration: {e}")
            sys.exit(1)


if __name__ == "__main__":
    generator = PIAWGGen()
    generator.run()
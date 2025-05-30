# file: src/k3s_deploy_cli/proxmox_client.py
"""
Client for interacting with the Proxmox VE API.
"""
import warnings
from typing import Any, Dict, List, Optional

from loguru import logger
from proxmoxer import ProxmoxAPI
from proxmoxer.core import (
    ResourceException,  # Changed ProxmoxResourceException to ResourceException
)
from urllib3.exceptions import InsecureRequestWarning

from .exceptions import ConfigurationError, ProxmoxInteractionError

# Suppress InsecureRequestWarning when verify_ssl is False
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

K3S_TAGS: List[str] = ["k3s-server", "k3s-agent", "k3s-storage"]


def get_proxmox_api_client(config: Dict[str, Any]) -> ProxmoxAPI:
    """
    Initializes and returns a ProxmoxAPI client instance based on configuration.

    Args:
        config: The 'proxmox' section of the application configuration.
                Expected keys: 'host', 'user', and either 'password' or
                ('api_token_id' and 'api_token_secret').
                Optional keys: 'verify_ssl' (default True), 'timeout' (default 10).

    Returns:
        An initialized ProxmoxAPI client.

    Raises:
        ConfigurationError: If essential Proxmox configuration is missing or invalid.
        ProxmoxInteractionError: If connection to Proxmox API fails.
    """
    host: Optional[str] = config.get("host")
    user: Optional[str] = config.get("user")
    password: Optional[str] = config.get("password")
    api_token_id: Optional[str] = config.get("api_token_id")
    api_token_secret: Optional[str] = config.get("api_token_secret")
    verify_ssl: bool = config.get("verify_ssl", True)  # Default to True as per schema
    timeout: int = config.get("timeout", 10) # Default timeout

    if not host or not user:
        raise ConfigurationError("Proxmox host and user must be configured.")

    auth_kwargs: Dict[str, Any] = {"user": user, "verify_ssl": verify_ssl, "timeout": timeout}

    if password:
        auth_kwargs["password"] = password
    elif api_token_id and api_token_secret:
        # Proxmoxer expects user to be the token ID and password to be the secret
        # if using API tokens this way.
        # The schema description for api_token_id is "API Token ID for Proxmox VE authentication (e.g., user@pam!mytoken)"
        # This implies api_token_id is the full user string for token auth.
        auth_kwargs["user"] = api_token_id # Override user with full token ID
        auth_kwargs["password"] = api_token_secret
    else:
        raise ConfigurationError(
            "Proxmox authentication not configured. "
            "Provide 'password' or both 'api_token_id' and 'api_token_secret'."
        )

    try:
        logger.debug(
            f"Attempting to connect to Proxmox API at {host} "
            f"with user {auth_kwargs['user']}"
        )
        proxmox = ProxmoxAPI(host, **auth_kwargs)
        # A simple call to verify authentication and connectivity
        proxmox.version.get()
        logger.info(f"Successfully connected to Proxmox API at {host}")
        return proxmox
    except ResourceException as e:  # Changed ProxmoxResourceException to ResourceException
        # More specific error for auth failures or resource issues
        logger.error(f"Proxmox API resource error for {host}: {e.status_code} - {e.content}")
        raise ProxmoxInteractionError(
            f"Proxmox API error for {host}: {e.status_code} - {e.content}"
        ) from e
    except Exception as e:
        logger.error(f"Failed to connect to Proxmox API at {host}: {e}")
        raise ProxmoxInteractionError(
            f"Failed to connect to Proxmox API at {host}: {e}"
        ) from e

def get_cluster_status(proxmox_client: ProxmoxAPI) -> Dict[str, Any]:
    """
    Retrieves the cluster status from Proxmox VE.

    Args:
        proxmox_client: An initialized ProxmoxAPI client.

    Returns:
        A dictionary containing the cluster status data. 
        Actually, the Proxmox API returns a list of dictionaries here.

    Raises:
        ProxmoxInteractionError: If fetching cluster status fails.
    """
    try:
        logger.debug("Fetching Proxmox cluster status...")
        # The /cluster/status endpoint returns a list of dictionaries,
        # one for each cluster member (node, qdevice).
        status_list = proxmox_client.cluster.status.get()
        logger.debug(f"Successfully fetched cluster status list: {status_list}")
        # For consistency with original intent if a single dict was expected,
        # but acknowledging it's a list. The caller will need to handle the list.
        return status_list # Return the list directly
    except ResourceException as e:
        logger.error(f"Error fetching Proxmox cluster status: {e.status_code} - {e.content}")
        raise ProxmoxInteractionError(
            f"Error fetching Proxmox cluster status: {e.status_code} - {e.content}"
        ) from e
    except Exception as e:
        logger.error(f"Error fetching Proxmox cluster status: {e}")
        raise ProxmoxInteractionError(
            f"Error fetching Proxmox cluster status: {e}"
        ) from e

def get_proxmox_version_info(proxmox_client: ProxmoxAPI) -> Dict[str, Any]:
    """
    Retrieves the Proxmox VE version information.

    Args:
        proxmox_client: An initialized ProxmoxAPI client.

    Returns:
        A dictionary containing the version data (e.g., version, release, repoversion).

    Raises:
        ProxmoxInteractionError: If fetching version information fails.
    """
    try:
        logger.debug("Fetching Proxmox version information...")
        version_info = proxmox_client.version.get()
        logger.debug(f"Successfully fetched Proxmox version info: {version_info}")
        return version_info
    except ResourceException as e:
        logger.error(f"Error fetching Proxmox version information: {e.status_code} - {e.content}")
        raise ProxmoxInteractionError(
            f"Error fetching Proxmox version information: {e.status_code} - {e.content}"
        ) from e
    except Exception as e:
        logger.error(f"Error fetching Proxmox version information: {e}")
        raise ProxmoxInteractionError(
            f"Error fetching Proxmox version information: {e}"
        ) from e

def get_vms_with_k3s_tags(proxmox_client: ProxmoxAPI, node_name: str) -> List[Dict[str, Any]]:
    """
    Retrieves a list of VMs on a given Proxmox node that have exactly one K3s tag.

    Args:
        proxmox_client: An initialized ProxmoxAPI client.
        node_name: The name of the Proxmox node to query.

    Returns:
        A list of dictionaries, where each dictionary contains information
        about a tagged VM (vmid, name, status, k3s_tag).

    Raises:
        ProxmoxInteractionError: If there's an issue communicating with the Proxmox API.
    """
    tagged_vms: List[Dict[str, Any]] = []
    try:
        logger.debug(f"Fetching VMs from node '{node_name}' for K3s tag check.")
        # Ensure the API path is correct for listing VMs on a node.
        # Typically, it's proxmox_client.nodes(node_name).qemu.get()
        vms_on_node = proxmox_client.nodes(node_name).qemu.get()
        
        for vm in vms_on_node:
            vm_tags_str = vm.get("tags", "")
            if not vm_tags_str:  # Handles None or empty string
                continue

            vm_tags_list = [tag.strip() for tag in vm_tags_str.split(';')]
            
            found_k3s_tags = []
            for k3s_tag in K3S_TAGS:
                if k3s_tag in vm_tags_list:
                    found_k3s_tags.append(k3s_tag)
            
            if len(found_k3s_tags) == 1:
                logger.trace(f"VMID {vm.get('vmid')} on node '{node_name}' matched with tag: {found_k3s_tags[0]}")
                
                # Get QGA status for this VM
                vmid = vm.get("vmid")
                qga_status = get_vm_qga_status(proxmox_client, node_name, vmid)
                
                tagged_vms.append({
                    "vmid": vmid,
                    "name": vm.get("name"),
                    "status": vm.get("status"),
                    "k3s_tag": found_k3s_tags[0],
                    "qga_enabled": qga_status["enabled"],
                    "qga_running": qga_status["running"],
                    "qga_version": qga_status["version"],
                    "qga_error": qga_status["error"]
                })
        
        # Sort VMs by VMID for consistent display
        tagged_vms.sort(key=lambda vm: vm.get("vmid", 0))
        
        logger.debug(f"Found {len(tagged_vms)} K3s-tagged VMs on node '{node_name}'.")
        return tagged_vms
    except Exception as e:  # Catches exceptions from proxmoxer call or processing
        err_msg = f"Failed to retrieve K3s-tagged VMs from node '{node_name}': {e}"
        logger.error(err_msg)
        raise ProxmoxInteractionError(err_msg) from e

def get_node_dns_info(proxmox_client: ProxmoxAPI, node_name: str) -> Optional[str]:
    """
    Retrieves DNS domain information for a specific Proxmox node.

    Args:
        proxmox_client: An initialized ProxmoxAPI client.
        node_name: The name of the Proxmox node.

    Returns:
        The domain name if available, otherwise None.
        
    Note:
        This function handles API errors gracefully and returns None
        if domain information cannot be retrieved, allowing the caller
        to display "N/A" or similar fallback text.
    """
    try:
        logger.debug(f"Retrieving DNS info for node '{node_name}'")
        dns_info = proxmox_client.nodes(node_name).dns.get()
        
        # Extract domain from the DNS configuration
        # Common fields that might contain domain: 'domain', 'search'
        domain = dns_info.get('domain')
        if domain:
            logger.debug(f"Found domain '{domain}' for node '{node_name}'")
            return domain
        # Fallback to search domains if no primary domain
        search_domains = dns_info.get('search')
        if search_domains:
            # search_domains might be a space-separated string
            if isinstance(search_domains, str) and search_domains.strip():
                first_search_domain = search_domains.strip().split()[0]
                logger.debug(f"Using search domain '{first_search_domain}' for node '{node_name}'")
                return first_search_domain
        
        logger.debug(f"No domain information found for node '{node_name}'")
        return None
        
    except ResourceException as e:
        logger.warning(f"DNS API error for node '{node_name}': {e.status_code} - {e.content}")
        return None
    except Exception as e:
        logger.warning(f"Failed to retrieve DNS info for node '{node_name}': {e}")
        return None

def discover_k3s_nodes(proxmox_client: ProxmoxAPI) -> List[Dict[str, Any]]:
    """
    Discovers K3s-tagged VMs across all online Proxmox nodes and returns
    basic configuration information suitable for the config.json nodes array.

    Args:
        proxmox_client: An initialized ProxmoxAPI client.

    Returns:
        A list of dictionaries containing basic node information:
        - vmid: VM ID (int)
        - role: K3s role based on tag (str)
        - node: Proxmox node name where VM resides (str)
        - name: VM name (str)
        - status: VM status (str)

    Raises:
        ProxmoxInteractionError: If there's an issue communicating with the Proxmox API.
    """
    discovered_nodes: List[Dict[str, Any]] = []
    
    try:
        # Get cluster status to find online nodes
        logger.debug("Getting cluster status for node discovery...")
        cluster_status = get_cluster_status(proxmox_client)
        # Filter to get only online nodes
        online_nodes = [
            node for node in cluster_status 
            if node.get("type") == "node" and node.get("online") == 1
        ]
        
        if not online_nodes:
            logger.warning("No online Proxmox nodes found for K3s discovery")
            return discovered_nodes
        
        logger.info(f"Scanning {len(online_nodes)} online Proxmox nodes for K3s VMs...")
        
        # Scan each online node for K3s-tagged VMs
        for node in online_nodes:
            node_name = node.get("name")
            if not node_name:
                logger.warning(f"Node found without name, skipping: {node}")
                continue
                
            logger.debug(f"Discovering K3s VMs on node '{node_name}'...")
            
            try:
                tagged_vms = get_vms_with_k3s_tags(proxmox_client, node_name)
                for vm in tagged_vms:
                    # Map K3s tag to role
                    k3s_tag = vm.get("k3s_tag", "")
                    role_mapping = {
                        "k3s-server": "server",
                        "k3s-agent": "agent", 
                        "k3s-storage": "storage"
                    }
                    role = role_mapping.get(k3s_tag)
                    
                    if not role:
                        logger.warning(f"Unknown K3s tag '{k3s_tag}' for VMID {vm.get('vmid')}, skipping")
                        continue
                    
                    discovered_node = {
                        "vmid": vm.get("vmid"),
                        "role": role,
                        "node": node_name,
                        "name": vm.get("name", "N/A"),
                        "status": vm.get("status", "N/A"),
                        "qga_enabled": vm.get("qga_enabled", False),
                        "qga_running": vm.get("qga_running", False),
                        "qga_version": vm.get("qga_version")
                    }
                    discovered_nodes.append(discovered_node)
                    logger.debug(f"Discovered K3s node: VMID {discovered_node['vmid']}, role '{role}' on '{node_name}'")
                    
            except ProxmoxInteractionError as e:
                logger.error(f"Failed to get K3s VMs from node '{node_name}': {e}")
                # Continue with other nodes rather than failing completely
                continue
        
        # Sort by VMID for consistent output
        discovered_nodes.sort(key=lambda node: node.get("vmid", 0))
        
        logger.info(f"Discovery complete: found {len(discovered_nodes)} K3s VMs across {len(online_nodes)} nodes")
        return discovered_nodes
        
    except Exception as e:
        err_msg = f"Failed to discover K3s nodes: {e}"
        logger.error(err_msg)
        raise ProxmoxInteractionError(err_msg) from e

def get_vm_config(proxmox_client: ProxmoxAPI, node_name: str, vmid: int) -> Dict[str, Any]:
    """
    Retrieves VM configuration including QGA enabled status.
    
    Args:
        proxmox_client: An initialized ProxmoxAPI client.
        node_name: The name of the Proxmox node.
        vmid: The VM ID.
    
    Returns:
        VM configuration dictionary with 'agent' property.
        
    Raises:
        ProxmoxInteractionError: If fetching VM config fails.
    """
    try:
        logger.debug(f"Fetching config for VM {vmid} on node '{node_name}'")
        vm_config = proxmox_client.nodes(node_name).qemu(vmid).config.get()
        logger.debug(f"Successfully fetched config for VM {vmid}")
        return vm_config
    except ResourceException as e:
        logger.error(f"Error fetching VM {vmid} config: {e.status_code} - {e.content}")
        raise ProxmoxInteractionError(
            f"Error fetching VM {vmid} config: {e.status_code} - {e.content}"
        ) from e
    except Exception as e:
        logger.error(f"Error fetching VM {vmid} config: {e}")
        raise ProxmoxInteractionError(
            f"Error fetching VM {vmid} config: {e}"
        ) from e


def get_vm_agent_info(proxmox_client: ProxmoxAPI, node_name: str, vmid: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves QGA runtime information for a running VM.
    
    Args:
        proxmox_client: An initialized ProxmoxAPI client.
        node_name: The name of the Proxmox node.
        vmid: The VM ID.
    
    Returns:
        Agent info dictionary if QGA is running, None if not available.
        
    Note:
        This function gracefully handles cases where QGA is not running
        or not responding, returning None instead of raising exceptions.
    """
    try:
        logger.debug(f"Checking QGA runtime status for VM {vmid} on node '{node_name}'")
        agent_info = proxmox_client.nodes(node_name).qemu(vmid).agent.get('info')
        logger.debug(f"Successfully fetched QGA info for VM {vmid}")
        return agent_info
    except ResourceException as e:
        # QGA not running or not responding is expected for some VMs
        logger.debug(f"QGA not available for VM {vmid}: {e.status_code} - {e.content}")
        return None
    except Exception as e:
        logger.debug(f"QGA check failed for VM {vmid}: {e}")
        return None


def get_vm_qga_status(proxmox_client: ProxmoxAPI, node_name: str, vmid: int) -> Dict[str, Any]:
    """
    Retrieves QGA (Qemu Guest Agent) configuration and runtime status for a VM.
    
    Args:
        proxmox_client: An initialized ProxmoxAPI client.
        node_name: The name of the Proxmox node.
        vmid: The VM ID.
    
    Returns:
        Dict containing:
        - enabled: bool - Whether QGA is enabled in VM config
        - running: bool - Whether QGA is currently running
        - version: str|None - QGA version if running
        - error: str|None - Error message if status check failed
    """
    qga_status = {
        "enabled": False,
        "running": False,
        "version": None,
        "error": None
    }
    
    try:
        # Check if QGA is enabled in VM configuration
        try:
            vm_config = get_vm_config(proxmox_client, node_name, vmid)
            agent_config = vm_config.get("agent", "")
            
            # Parse agent configuration - can be "1", "enabled=1", or complex string
            if isinstance(agent_config, str):
                # Handle cases like "enabled=1" or "1"
                qga_status["enabled"] = (
                    agent_config == "1" or 
                    "enabled=1" in agent_config or
                    agent_config.lower() == "true"
                )
            elif isinstance(agent_config, int):
                qga_status["enabled"] = bool(agent_config)
            else:
                qga_status["enabled"] = bool(agent_config)
                
        except ProxmoxInteractionError as e:
            qga_status["error"] = f"Config check failed: {str(e)}"
            logger.warning(f"Failed to check QGA config for VM {vmid}: {e}")
        
        # Check if QGA is currently running (only if enabled)
        if qga_status["enabled"]:
            try:
                agent_info = get_vm_agent_info(proxmox_client, node_name, vmid)
                if agent_info:
                    qga_status["running"] = True
                    qga_status["version"] = agent_info.get("version", "Unknown")
                else:
                    qga_status["running"] = False
            except Exception as e:
                logger.debug(f"QGA runtime check failed for VM {vmid}: {e}")
                qga_status["running"] = False
        
        logger.debug(f"QGA status for VM {vmid}: enabled={qga_status['enabled']}, running={qga_status['running']}")
        return qga_status
        
    except Exception as e:
        error_msg = f"Unexpected error checking QGA status for VM {vmid}: {e}"
        logger.error(error_msg)
        qga_status["error"] = error_msg
        return qga_status
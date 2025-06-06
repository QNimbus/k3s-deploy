# file: src/k3s_deploy_cli/proxmox_core.py
"""Provides core functionalities for interacting with the Proxmox VE API.

This module includes functions to establish a connection with the Proxmox API,
retrieve general cluster information such as status and version,
and fetch specific details about Proxmox nodes like DNS and snippet storage.
"""
import hashlib
import json
import warnings
from typing import Any, Dict, List, Optional

from loguru import logger
from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException
from urllib3.exceptions import InsecureRequestWarning

from .exceptions import ConfigurationError, ProxmoxInteractionError

# Suppress InsecureRequestWarning when verify_ssl is False
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

# Module-level cache for proxmox clients
_PROXMOX_CLIENTS: Dict[str, ProxmoxAPI] = {}

def _clear_client_cache() -> None:
    """
    Clear the Proxmox client cache. 
    
    This function is primarily intended for testing purposes to ensure
    test isolation when testing the singleton pattern behavior.
    """
    global _PROXMOX_CLIENTS
    _PROXMOX_CLIENTS.clear()

def _get_config_hash(config: Dict[str, Any]) -> str:
    """
    Generate a unique hash for a Proxmox configuration to use as a cache key.
    
    Args:
        config: Proxmox configuration dictionary
        
    Returns:
        A string hash representing this configuration
    """
    # Extract relevant configuration for hashing
    hash_dict = {
        "host": config.get("host"),
        "user": config.get("user"),
        "password": config.get("password"),
        "api_token_id": config.get("api_token_id"),
        "api_token_secret": config.get("api_token_secret"),
        "verify_ssl": config.get("verify_ssl", True),
        "timeout": config.get("timeout", 10)
    }
    
    # Create a stable JSON representation and hash it
    config_str = json.dumps(hash_dict, sort_keys=True)
    return hashlib.md5(config_str.encode()).hexdigest()

def get_proxmox_api_client(config: Dict[str, Any]) -> ProxmoxAPI:
    """
    Initializes and returns a ProxmoxAPI client instance based on configuration.
    Uses a singleton pattern to reuse existing connections with the same configuration.

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
    
    # Check if we already have a client with this configuration
    config_hash = _get_config_hash(config)
    if config_hash in _PROXMOX_CLIENTS:
        logger.debug(f"Reusing existing Proxmox API connection to {host}")
        return _PROXMOX_CLIENTS[config_hash]

    auth_kwargs: Dict[str, Any] = {"user": user, "verify_ssl": verify_ssl, "timeout": timeout}

    if password:
        auth_kwargs["password"] = password
    elif api_token_id and api_token_secret:
        # For API tokens, the user should be in the format 'tokenid@realm!tokenname'
        # Proxmoxer expects the full api_token_id as the 'user' and api_token_secret as 'password'
        # Ensure the user field is correctly formatted if it's an API token ID.
        # The proxmoxer library handles this by passing the token ID as user and secret as password.
        auth_kwargs["user"] = api_token_id
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
        proxmox.version.get() # Test connection
        logger.info(f"Successfully connected to Proxmox API at {host}")
        
        # Store the client in the cache
        _PROXMOX_CLIENTS[config_hash] = proxmox
        return proxmox
    except ResourceException as e:
        logger.error(f"Proxmox API resource error for {host}: {e.status_code} - {e.content}")
        raise ProxmoxInteractionError(
            f"Proxmox API error for {host}: {e.status_code} - {e.content}"
        ) from e
    except Exception as e:
        logger.error(f"Failed to connect to Proxmox API at {host}: {e}")
        raise ProxmoxInteractionError(
            f"Failed to connect to Proxmox API at {host}: {e}"
        ) from e

def get_cluster_status(proxmox_client: ProxmoxAPI) -> List[Dict[str, Any]]:
    """
    Retrieves the cluster status from Proxmox VE.

    Args:
        proxmox_client: An initialized ProxmoxAPI client.

    Returns:
        A list of dictionaries, where each dictionary contains status data
        for a cluster member (node, qdevice).

    Raises:
        ProxmoxInteractionError: If fetching cluster status fails.
    """
    try:
        logger.debug("Fetching Proxmox cluster status...")
        status_list = proxmox_client.cluster.status.get()
        logger.debug(f"Successfully fetched cluster status list: {len(status_list)} members found.")
        return status_list
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

def get_node_dns_info(client: ProxmoxAPI, node_name: str) -> Optional[str]:
    """
    Get DNS search domain for a specific Proxmox node.

    Args:
        client: Proxmox API client
        node_name: Name of the Proxmox node

    Returns:
        str: DNS search domain or None if not configured.

    Raises:
        ProxmoxInteractionError: If API call fails
    """
    try:
        logger.debug(f"Fetching DNS info for node '{node_name}'...")
        dns_info = client.nodes(node_name).dns.get()
        search_domain = dns_info.get('search') # Use .get() to safely access, defaults to None

        if not search_domain: # Checks for None or empty string
            logger.debug(f"No DNS search domain configured for node '{node_name}'.")
            return None

        logger.debug(f"Successfully fetched DNS search domain for node '{node_name}': {search_domain}")
        return search_domain
    except ResourceException as e:
        logger.error(f"Error fetching DNS info for node '{node_name}': {e.status_code} - {e.content}")
        raise ProxmoxInteractionError(
            f"Error fetching DNS info for node '{node_name}': {e.status_code} - {e.content}"
        ) from e
    except Exception as e:
        logger.error(f"Failed to get DNS info for node '{node_name}': {str(e)}")
        raise ProxmoxInteractionError(
            f"Failed to get DNS info for node '{node_name}': {str(e)}"
        ) from e

def get_node_snippet_storage(proxmox_client: ProxmoxAPI, node_name: str) -> Dict[str, Any]:
    """
    Get snippet-capable storage information for a specific Proxmox node.

    Checks all storage configurations on the node to find storage that supports
    'snippets' content type and is both enabled and active.

    Args:
        proxmox_client: An initialized ProxmoxAPI client
        node_name: Name of the Proxmox node to check

    Returns:
        Dict containing storage information if snippet-capable storage exists:
        {
            "storage_name": "local",
            "type": "dir",
            "enabled": True, (Optional)
            "active": True, (Optional)
            "shared": False (Optional)
        }
        Empty dict {} if no snippet-capable storage is available.

    Raises:
        ProxmoxInteractionError: If API call fails or node is inaccessible
    """
    try:
        logger.debug(f"Fetching storage configurations for node '{node_name}'...")

        storage_list = proxmox_client.nodes(node_name).storage.get()
        logger.debug(f"Retrieved {len(storage_list)} storage configurations for node '{node_name}'")

        for storage_item in storage_list:
            storage_name = storage_item.get("storage", "")
            content = storage_item.get("content", "")
            enabled = storage_item.get("enabled", 0) == 1
            active = storage_item.get("active", 0) == 1

            if "snippets" in content and enabled and active:
                logger.debug(f"Found snippet-capable storage '{storage_name}' on node '{node_name}'")
                
                # Check if we have detailed info in the storage_item itself
                storage_type = storage_item.get("type", "")
                storage_path = storage_item.get("path")
                storage_shared = storage_item.get("shared")
                
                # If we have complete info from the first call, use it directly
                if "path" in storage_item and "shared" in storage_item:
                    logger.debug(f"Using direct storage info for '{storage_name}' from nodes API")
                    return {
                        "storage_name": storage_name,
                        "enabled": True,
                        "active": True,
                        "type": storage_type,
                        "path": storage_path,
                        "shared": bool(storage_shared)
                    }
                
                # Fall back to detailed API call if info is incomplete
                try:
                    storage_details = proxmox_client.storage(storage_name).get()
                    logger.debug(f"Retrieved detailed info for storage '{storage_name}' via storage API")
                    
                    return {
                        "storage_name": storage_name,
                        "enabled": True,
                        "active": True,
                        "type": storage_details.get("type", storage_type),
                        "path": storage_details.get("path"),
                        "shared": bool(storage_details.get("shared", 0))
                    }
                except ResourceException as e:
                    logger.warning(f"Could not fetch details for storage '{storage_name}': {e.status_code} - {e.content}")
                    # Fall back to basic info without path
                    return {
                        "storage_name": storage_name,
                        "enabled": True,
                        "active": True,
                        "type": storage_type,
                        "path": None,
                        "shared": bool(storage_shared) if storage_shared is not None else False
                    }

        logger.debug(f"No snippet-capable storage found on node '{node_name}'")
        return {}

    except ResourceException as e:
        logger.error(f"Error fetching storage info for node {node_name}: {e.status_code} - {e.content}")
        raise ProxmoxInteractionError(
            f"Error fetching storage info for node {node_name}: {e.status_code} - {e.content}"
        ) from e
    except Exception as e:
        logger.error(f"Failed to get storage info for node {node_name}: {e}")
        raise ProxmoxInteractionError(
            f"Failed to get storage info for node {node_name}: {e}"
        ) from e

def is_storage_shared(
    proxmox_client: ProxmoxAPI,
    node_name: str,
    storage_name: Optional[str] = None
) -> bool:
    """
    Check if the specified storage (or default snippet storage) is shared across nodes.
    
    Args:
        proxmox_client: Initialized ProxmoxAPI client
        node_name: Name of the Proxmox node
        storage_name: Specific storage name (auto-detected if None)
        
    Returns:
        True if storage is shared, False if local to the node
        
    Raises:
        ProxmoxInteractionError: If storage info cannot be retrieved
    """
    try:
        if storage_name is None:
            # Auto-detect snippet storage
            storage_info = get_node_snippet_storage(proxmox_client, node_name)
            if not storage_info:
                logger.warning(f"No snippet storage found on node {node_name}")
                return False  # Assume local if no storage found
            storage_name = storage_info["storage_name"]
            shared = storage_info.get("shared", False)
        else:
            # Get specific storage details
            try:
                storage_details = proxmox_client.storage(storage_name).get()
                shared = bool(storage_details.get("shared", 0))
            except ResourceException as e:
                logger.error(f"Could not fetch details for storage '{storage_name}': {e.status_code} - {e.content}")
                raise ProxmoxInteractionError(
                    f"Could not fetch details for storage '{storage_name}': {e.status_code} - {e.content}"
                ) from e
        
        logger.debug(f"Storage '{storage_name}' on node '{node_name}' is {'shared' if shared else 'local'}")
        return shared
        
    except Exception as e:
        logger.error(f"Failed to check storage sharing for '{storage_name}' on node {node_name}: {e}")
        raise ProxmoxInteractionError(
            f"Failed to check storage sharing for '{storage_name}' on node {node_name}: {e}"
        ) from e
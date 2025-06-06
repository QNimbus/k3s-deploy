"""
Configuration utilities for merging global and VM-specific cloud-init settings.

This module provides utilities to combine global cloud-init configuration
with VM-specific overrides, supporting the flexible configuration architecture
where VMs can override global defaults on a per-setting basis.

Key features:
- Simple replacement merge strategy (no deep merging of arrays)
- Support for packages, users, runcmd, and package management settings
- Graceful handling of missing configuration sections
- Type-safe operations with comprehensive error handling
- Network configuration extraction and separation for cloud-init provisioning
"""

from typing import Any, Dict, List, Optional

import yaml
from loguru import logger


def clean_cloud_init_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean cloud-init configuration by removing empty lists and None values.
    
    Cloud-init schema validation requires that properties like 'groups' are either:
    - A non-empty list
    - A string 
    - An object
    - Or completely omitted
    
    This function recursively removes empty lists and None values to ensure
    cloud-init schema compliance.
    
    Args:
        config: Cloud-init configuration dictionary to clean
        
    Returns:
        Cleaned configuration dictionary with empty lists and None values removed
        
    Examples:
        >>> config = {
        ...     "users": [{"name": "ubuntu", "groups": []}],
        ...     "packages": [],
        ...     "network": {"version": 2}
        ... }
        >>> clean_cloud_init_config(config)
        {"users": [{"name": "ubuntu"}], "network": {"version": 2}}
    """
    logger.debug("Cleaning cloud-init configuration")
    
    if not isinstance(config, dict):
        return config
    
    cleaned_config = {}
    
    for key, value in config.items():
        if value is None:
            # Skip None values
            logger.debug(f"Removing None value for key '{key}'")
            continue
        elif isinstance(value, list):
            if not value:  # Empty list
                logger.debug(f"Removing empty list for key '{key}'")
                continue
            else:
                # Recursively clean list items
                cleaned_list = []
                for item in value:
                    if isinstance(item, dict):
                        cleaned_item = clean_cloud_init_config(item)
                        if cleaned_item:  # Only add non-empty dictionaries
                            cleaned_list.append(cleaned_item)
                    elif item is not None:
                        cleaned_list.append(item)
                
                if cleaned_list:  # Only add non-empty lists
                    cleaned_config[key] = cleaned_list
                else:
                    logger.debug(f"Removing empty list after cleaning for key '{key}'")
        elif isinstance(value, dict):
            # Recursively clean nested dictionaries
            cleaned_dict = clean_cloud_init_config(value)
            if cleaned_dict:  # Only add non-empty dictionaries
                cleaned_config[key] = cleaned_dict
            else:
                logger.debug(f"Removing empty dict after cleaning for key '{key}'")
        else:
            # Keep all other values (strings, numbers, booleans)
            cleaned_config[key] = value
    
    logger.debug(f"Cleaned config keys: {list(cleaned_config.keys())}")
    return cleaned_config


def find_node_by_vmid(nodes: List[Dict], vmid: int) -> Optional[Dict]:
    """
    Find node configuration by VMID.
    
    Searches through the nodes list to find a node configuration that
    matches the specified VMID.
    
    Args:
        nodes: List of node configuration dictionaries
        vmid: VM ID to search for
        
    Returns:
        Node configuration dictionary if found, None otherwise
    """
    logger.debug(f"Searching for node with VMID {vmid} in {len(nodes)} nodes")
    
    for node in nodes:
        if isinstance(node, dict) and node.get('vmid') == vmid:
            logger.debug(f"Found node configuration for VMID {vmid}")
            return node
    
    logger.debug(f"No node configuration found for VMID {vmid}")
    return None


def merge_cloud_init_config(global_config: Dict, vm_config: Dict) -> Dict:
    """
    Merge VM-specific cloud-init config over global config.
    
    Implements simple replacement merge strategy where VM settings
    completely replace corresponding global settings. No deep merging
    of arrays - VM arrays completely replace global arrays.
    
    Supported settings:
    - packages: List of packages to install
    - package_update: Boolean for package update
    - package_upgrade: Boolean for package upgrade  
    - package_reboot_if_required: Boolean for reboot after package operations
    - runcmd: List of commands to run
    - users: List of user configurations
    
    Args:
        global_config: Global cloud-init configuration
        vm_config: VM-specific cloud-init configuration
        
    Returns:
        Merged configuration dictionary with VM settings taking precedence
    """
    logger.debug("Merging cloud-init configurations")
    logger.debug(f"Global config keys: {list(global_config.keys())}")
    logger.debug(f"VM config keys: {list(vm_config.keys())}")
    
    # Start with a copy of global config
    merged_config = global_config.copy()
    
    # VM config completely replaces corresponding global settings
    for key, value in vm_config.items():
        if value is not None:  # Only override if VM config value is not None
            logger.debug(f"VM config overriding '{key}': {type(value).__name__}")
            merged_config[key] = value
    
    logger.debug(f"Merged config keys: {list(merged_config.keys())}")
    return merged_config


def get_merged_cloud_init_for_vm(config: Dict, vmid: int) -> Dict:
    """
    Main interface: get merged cloud-init config for specific VM.
    
    This is the primary function for retrieving cloud-init configuration
    for a specific VM, combining global defaults with VM-specific overrides.
    
    Process:
    1. Extract global cloud-init config from top-level 'cloud_init' section
    2. Find VM-specific node configuration by VMID
    3. Extract VM-specific cloud-init config from node
    4. Merge VM config over global config using simple replacement strategy
    5. Return merged configuration
    
    Args:
        config: Full configuration dictionary
        vmid: VM ID to get merged configuration for
        
    Returns:
        Merged cloud-init configuration dictionary
        
    Examples:
        >>> config = {
        ...     "cloud_init": {"packages": ["git", "curl"]},
        ...     "nodes": [{"vmid": 100, "cloud_init": {"packages": ["vim"]}}]
        ... }
        >>> get_merged_cloud_init_for_vm(config, 100)
        {"packages": ["vim"]}  # VM packages completely replace global packages
    """
    logger.debug(f"Getting merged cloud-init configuration for VM {vmid}")
    
    # Extract global cloud-init config
    global_cloud_init = config.get('cloud_init', {})
    logger.debug(f"Global cloud-init config: {list(global_cloud_init.keys()) if global_cloud_init else 'None'}")
    
    # Find VM-specific node configuration
    nodes = config.get('nodes', [])
    node_config = find_node_by_vmid(nodes, vmid)
    
    # Extract VM-specific cloud-init config
    vm_cloud_init = {}
    if node_config:
        vm_cloud_init = node_config.get('cloud_init', {})
        logger.debug(f"VM-specific cloud-init config: {list(vm_cloud_init.keys()) if vm_cloud_init else 'None'}")
    else:
        logger.debug(f"No node configuration found for VM {vmid}, using global config only")
    
    # Merge configurations
    merged_config = merge_cloud_init_config(global_cloud_init, vm_cloud_init)
    
    logger.info(f"Merged cloud-init configuration for VM {vmid}: {list(merged_config.keys()) if merged_config else 'empty'}")
    return merged_config


def extract_network_config(cloud_init_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract network configuration from cloud-init config.
    
    Extracts the 'network' section from a cloud-init configuration dictionary
    if it exists and contains meaningful configuration data.
    
    Args:
        cloud_init_config: Complete cloud-init configuration dictionary
        
    Returns:
        Network configuration dictionary if present and non-empty, None otherwise
        
    Examples:
        >>> config = {"network": {"version": 2, "ethernets": {"eth0": {"dhcp4": True}}}}
        >>> extract_network_config(config)
        {"version": 2, "ethernets": {"eth0": {"dhcp4": True}}}
        
        >>> config = {"users": [{"name": "ubuntu"}]}
        >>> extract_network_config(config)
        None
    """
    logger.debug("Extracting network configuration from cloud-init config")
    
    network_config = cloud_init_config.get('network')
    
    if network_config is None:
        logger.debug("No network configuration found in cloud-init config")
        return None
    
    if not isinstance(network_config, dict):
        logger.warning(f"Network configuration is not a dictionary: {type(network_config)}")
        return None
    
    if not network_config:
        logger.debug("Network configuration is empty")
        return None
    
    logger.debug(f"Found network configuration with keys: {list(network_config.keys())}")
    return network_config


def create_network_config_yaml(network_config: Dict[str, Any]) -> str:
    """
    Generate cloud-init network configuration YAML.
    
    Converts a network configuration dictionary into a properly formatted
    cloud-init network configuration YAML string.
    
    Args:
        network_config: Network configuration dictionary
        
    Returns:
        YAML string containing network configuration in cloud-init format
        
    Raises:
        ValueError: If network_config is empty or invalid
        
    Examples:
        >>> config = {"version": 2, "ethernets": {"eth0": {"dhcp4": True}}}
        >>> create_network_config_yaml(config)
        'network:\\n  version: 2\\n  ethernets:\\n    eth0:\\n      dhcp4: true\\n'
    """
    logger.debug("Generating network configuration YAML")
    
    if not network_config:
        raise ValueError("Network configuration cannot be empty")
    
    if not isinstance(network_config, dict):
        raise ValueError(f"Network configuration must be a dictionary, got {type(network_config)}")
    
    try:
        # Clean network config to remove empty lists and None values
        cleaned_network_config = clean_cloud_init_config(network_config)
        
        # Wrap network config in the proper cloud-init structure
        cloud_init_network = {"network": cleaned_network_config}

        # Convert to YAML with cloud-config header
        yaml_content = "#cloud-config\n" + yaml.dump(
            cloud_init_network, 
            default_flow_style=False,
            sort_keys=False
        )

        logger.debug(f"Generated network YAML ({len(yaml_content)} characters)")
        return yaml_content
        
    except Exception as e:
        logger.error(f"Failed to generate network configuration YAML: {e}")
        raise ValueError(f"Failed to generate network YAML: {e}")


def create_user_config_without_network(cloud_init_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create user cloud-init config with network section removed.
    
    Creates a copy of the cloud-init configuration with the network section
    excluded, suitable for generating separate user and network configuration files.
    
    Args:
        cloud_init_config: Complete cloud-init configuration dictionary
        
    Returns:
        Cloud-init configuration with network section excluded
        
    Examples:
        >>> config = {
        ...     "users": [{"name": "ubuntu"}],
        ...     "packages": ["git"],
        ...     "network": {"version": 2, "ethernets": {"eth0": {"dhcp4": True}}}
        ... }
        >>> create_user_config_without_network(config)
        {"users": [{"name": "ubuntu"}], "packages": ["git"]}
    """
    logger.debug("Creating user configuration without network section")
    
    # Create a copy of the configuration
    user_config = cloud_init_config.copy()
    
    # Remove network section if it exists
    if 'network' in user_config:
        del user_config['network']
        logger.debug("Removed network section from user configuration")
    else:
        logger.debug("No network section found to remove")
    
    # Clean configuration to remove empty lists and None values
    cleaned_config = clean_cloud_init_config(user_config)
    
    logger.debug(f"User config keys: {list(cleaned_config.keys())}")
    return cleaned_config

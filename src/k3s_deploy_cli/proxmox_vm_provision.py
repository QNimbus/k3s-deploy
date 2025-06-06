"""
Proxmox VM provisioning module for cloud-init configuration and deployment.

This module handles the generation and deployment of cloud-init configurations
to Proxmox VMs, including:
- Cloud-init YAML generation with qemu-guest-agent, user creation, SSH keys
- SFTP upload to Proxmox snippet storage
- VM configuration via Proxmox API
- Cloud-init reconfiguration triggering

Follows established project patterns with comprehensive error handling and logging.
"""

from typing import Any, Dict, Optional

import yaml
from loguru import logger

from k3s_deploy_cli.cloud_init import create_cloud_init_config
from k3s_deploy_cli.config_utils import (
    clean_cloud_init_config,
    create_network_config_yaml,
    create_user_config_without_network,
    extract_network_config,
    get_merged_cloud_init_for_vm,
)
from k3s_deploy_cli.ssh_operations import (
    establish_node_ssh_connection,
    validate_ssh_public_key,
)

from .exceptions import ProvisionError, VMOperationError
from .proxmox_core import (
    get_node_snippet_storage,
    get_proxmox_api_client,
    is_storage_shared,
)
from .proxmox_vm_operations import find_vm_node, get_vm_status
from .ssh_operations import establish_ssh_connection

# Function moved to cloud_init.py as create_cloud_init_config()


def upload_cloud_init_to_snippet_storage(
    vmid: int,
    node_name: str, 
    cloud_init_content: str,
    proxmox_config: Dict[str, Any],
    snippet_storage: Optional[str] = None
) -> bool:
    """
    Upload cloud-init configuration to Proxmox snippet storage via SFTP.
    
    Args:
        vmid: VM ID for file naming
        node_name: Proxmox node name
        cloud_init_content: Cloud-init YAML content to upload
        proxmox_config: Proxmox connection configuration
        snippet_storage: Specific storage name (auto-detected if None)
        
    Returns:
        True if upload successful
        
    Raises:
        ProvisionError: If upload fails or storage not found
    """
    logger.debug(f"Uploading cloud-init config for VM {vmid} to node {node_name}")
    
    try:
        # Get snippet storage information
        if snippet_storage:
            # Use specified storage (assume it exists and supports snippets)
            storage_name = snippet_storage
            # We'll need to get the path - for now use a placeholder approach
            storage_path = "/var/lib/vz"  # Common default, should be retrieved properly
            # Check if storage is shared for specified storage
            client = get_proxmox_api_client(proxmox_config)
            storage_shared = is_storage_shared(client, node_name, storage_name)
        else:
            # Get Proxmox client for storage detection
            client = get_proxmox_api_client(proxmox_config)
            storage_info = get_node_snippet_storage(client, node_name)
            if not storage_info:
                raise ProvisionError(f"No snippet-capable storage found on node {node_name}")
            storage_name = storage_info["storage_name"]
            storage_path = storage_info["path"] or "/var/lib/vz"
            storage_shared = storage_info.get("shared", False)

        logger.debug(f"Using snippet storage '{storage_name}' at path '{storage_path}' (shared: {storage_shared})")
        
        # Establish SSH connection based on storage type
        if storage_shared:
            # Use primary host connection for shared storage
            logger.debug("Using primary host connection for shared storage")
            ssh_client = establish_ssh_connection(proxmox_config)
        else:
            # Use node-specific connection for local storage
            logger.debug(f"Using node-specific connection for local storage to {node_name}")
            ssh_client = establish_node_ssh_connection(proxmox_config, node_name)
        
        try:
            # Upload via SFTP
            sftp = ssh_client.open_sftp()
            
            # Construct file path
            filename = f"userconfig-{vmid}.yaml"
            remote_path = f"{storage_path}/snippets/{filename}"
            
            logger.debug(f"Uploading to remote path: {remote_path} on node {node_name}")
            
            # Ensure snippets directory exists
            try:
                sftp.mkdir(f"{storage_path}/snippets")
            except OSError:
                # Directory likely already exists
                pass
            
            # Write cloud-init content
            with sftp.open(remote_path, 'w') as remote_file:
                remote_file.write(cloud_init_content)
            
            sftp.close()
            logger.info(f"Successfully uploaded cloud-init config to {remote_path} on node {node_name}")
            return True
            
        finally:
            ssh_client.close()
            
    except Exception as e:
        logger.error(f"Failed to upload cloud-init config for VM {vmid}: {e}")
        raise ProvisionError(f"Failed to upload cloud-init configuration: {e}", e)


def upload_network_config_to_snippet_storage(
    vmid: int,
    node_name: str,
    network_config_content: str,
    proxmox_config: Dict[str, Any],
    snippet_storage: Optional[str] = None
) -> bool:
    """
    Upload network configuration to Proxmox snippet storage via SFTP.
    
    Args:
        vmid: VM ID for file naming
        node_name: Proxmox node name
        network_config_content: Network config YAML content to upload
        proxmox_config: Proxmox connection configuration
        snippet_storage: Specific storage name (auto-detected if None)
        
    Returns:
        True if upload successful
        
    Raises:
        ProvisionError: If upload fails
    """
    logger.debug(f"Uploading network configuration for VM {vmid}")
    
    try:
        # Determine storage and get path
        if snippet_storage:
            storage_name = snippet_storage
            logger.debug(f"Using specified snippet storage: {storage_name}")
            # Check if storage is shared for specified storage
            client = get_proxmox_api_client(proxmox_config)
            storage_shared = is_storage_shared(client, node_name, storage_name)
        else:
            logger.debug("Auto-detecting snippet storage...")
            # Get Proxmox client for storage detection
            client = get_proxmox_api_client(proxmox_config)
            storage_info = get_node_snippet_storage(client, node_name)
            if not storage_info:
                raise ProvisionError(f"No snippet-capable storage found on node {node_name}")
            storage_name = storage_info["storage_name"]
            storage_shared = storage_info.get("shared", False)
            logger.debug(f"Auto-detected snippet storage: {storage_name}")
        
        # Get storage path 
        storage_path = "/var/lib/vz"  # Standard Proxmox storage path
        
        logger.debug(f"Using snippet storage '{storage_name}' (shared: {storage_shared})")
        
        # Establish SSH connection based on storage type
        if storage_shared:
            # Use primary host connection for shared storage
            logger.debug("Using primary host connection for shared storage")
            ssh_client = establish_ssh_connection(proxmox_config)
        else:
            # Use node-specific connection for local storage
            logger.debug(f"Using node-specific connection for local storage to {node_name}")
            ssh_client = establish_node_ssh_connection(proxmox_config, node_name)
        
        try:
            # Upload via SFTP
            sftp = ssh_client.open_sftp()
            
            # Construct file path
            filename = f"networkconfig-{vmid}.yaml"
            remote_path = f"{storage_path}/snippets/{filename}"
            
            logger.debug(f"Uploading network config to remote path: {remote_path} on node {node_name}")
            
            # Ensure snippets directory exists
            try:
                sftp.mkdir(f"{storage_path}/snippets")
            except OSError:
                # Directory likely already exists
                pass
            
            # Write network config content
            with sftp.open(remote_path, 'w') as remote_file:
                remote_file.write(network_config_content)
            
            sftp.close()
            logger.info(f"Successfully uploaded network config to {remote_path} on node {node_name}")
            return True
            
        finally:
            ssh_client.close()
            
    except Exception as e:
        logger.error(f"Failed to upload network config for VM {vmid}: {e}")
        raise ProvisionError(f"Failed to upload network configuration: {e}", e)


def configure_vm_cloud_init_files(
    vmid: int,
    node_name: str,
    storage_name: str,
    proxmox_config: Dict[str, Any],
    has_network_config: bool = False
) -> bool:
    """
    Configure VM to use cloud-init files with adaptive cicustom parameter.
    
    Configures the VM to use cloud-init files via Proxmox API with conditional
    network configuration support. Uses user-only or user+network cicustom
    parameter based on whether network configuration exists.
    
    Args:
        vmid: VM ID to configure
        node_name: Proxmox node name hosting the VM
        storage_name: Storage name containing the cloud-init files
        proxmox_config: Proxmox connection configuration
        has_network_config: Whether network config file exists for conditional cicustom
        
    Returns:
        True if configuration successful
        
    Raises:
        ProvisionError: If VM configuration fails
    """
    logger.debug(f"Configuring VM {vmid} on node {node_name} to use cloud-init files")
    
    try:
        # Get Proxmox client
        client = get_proxmox_api_client(proxmox_config)
        
        # Configure cicustom parameter conditionally
        user_filename = f"userconfig-{vmid}.yaml"
        
        if has_network_config:
            # Both user and network configuration files
            network_filename = f"networkconfig-{vmid}.yaml"
            cicustom_value = f"user={storage_name}:snippets/{user_filename},network={storage_name}:snippets/{network_filename}"
            logger.debug(f"Setting cicustom with network config: {cicustom_value}")
        else:
            # User configuration file only
            cicustom_value = f"user={storage_name}:snippets/{user_filename}"
            logger.debug(f"Setting cicustom without network config: {cicustom_value}")
        
        # Update VM configuration
        client.nodes(node_name).qemu(vmid).config.post(cicustom=cicustom_value)
        
        if has_network_config:
            logger.info(f"Successfully configured VM {vmid} to use user and network cloud-init files")
        else:
            logger.info(f"Successfully configured VM {vmid} to use user cloud-init file only")
        return True
        
    except Exception as e:
        logger.error(f"Failed to configure VM {vmid} cloud-init: {e}")
        raise ProvisionError(f"Failed to configure VM cloud-init: {e}", e)


# Backward compatibility function (deprecated)
def configure_vm_cloud_init(
    vmid: int,
    node_name: str,
    storage_name: str,
    proxmox_config: Dict[str, Any]
) -> bool:
    """
    Configure VM to use cloud-init file via Proxmox API.
    
    DEPRECATED: Use configure_vm_cloud_init_files() instead for network config support.
    
    Args:
        vmid: VM ID to configure
        node_name: Proxmox node name hosting the VM
        storage_name: Storage name containing the cloud-init file
        proxmox_config: Proxmox connection configuration
        
    Returns:
        True if configuration successful
        
    Raises:
        ProvisionError: If VM configuration fails
    """
    logger.warning("configure_vm_cloud_init() is deprecated, use configure_vm_cloud_init_files() instead")
    return configure_vm_cloud_init_files(vmid, node_name, storage_name, proxmox_config, has_network_config=False)


def trigger_cloud_init_reconfiguration(
    vmid: int,
    node_name: str,
    proxmox_config: Dict[str, Any]
) -> bool:
    """
    Trigger cloud-init reconfiguration on the VM using Proxmox cloud-init API.
    
    This uses the Proxmox API endpoint PUT /api2/json/nodes/{node}/qemu/{vmid}/cloudinit
    to trigger cloud-init reconfiguration without restarting the VM.
    
    Args:
        vmid: VM ID to reconfigure
        node_name: Proxmox node name hosting the VM
        proxmox_config: Proxmox connection configuration
        
    Returns:
        True if reconfiguration triggered successfully
        
    Raises:
        ProvisionError: If reconfiguration fails
    """
    logger.debug(f"Triggering cloud-init reconfiguration for VM {vmid}")
    
    try:
        client = get_proxmox_api_client(proxmox_config)
        
        # Use Proxmox cloud-init API endpoint to trigger reconfiguration
        logger.debug(f"Calling Proxmox cloud-init API for VM {vmid} on node {node_name}")
        client.nodes(node_name).qemu(vmid).cloudinit.put()

        logger.info(f"Successfully triggered cloud-init reconfiguration for VM {vmid}")

        # Check VM status before attempting restart
        try:
            vm_status = get_vm_status(client, node_name, vmid)
            current_status = vm_status.get("status", "unknown").lower()
            
            if current_status == "stopped":
                logger.info(f"VM {vmid} is currently stopped. Cloud-init configuration has been applied but will take effect when the VM is started.")
                logger.info(f"To apply the cloud-init configuration, please start VM {vmid} manually using: k3s-deploy start {vmid}")
                return True
            elif current_status == "running":
                # Restart VM to trigger cloud-init reconfiguration
                from .proxmox_vm_operations import restart_vm
                restart_vm(client, node_name, vmid)
                logger.info(f"Successfully restarted VM {vmid} to trigger cloud-init reconfiguration")
                return True
            else:
                logger.warning(f"VM {vmid} is in '{current_status}' state. Cloud-init configuration has been applied but may not take effect until the VM is restarted.")
                return True
                
        except Exception as status_error:
            logger.warning(f"Could not check VM {vmid} status: {status_error}")
            logger.info(f"Cloud-init configuration has been applied to VM {vmid}. Please check VM status and restart manually if needed.")
            return True
        
    except Exception as e:
        logger.error(f"Failed to trigger cloud-init reconfiguration for VM {vmid}: {e}")
        raise ProvisionError(f"Failed to trigger cloud-init reconfiguration: {e}", e)


def provision_vm_basic_setup(
    vmid: int,
    username: str,
    proxmox_config: Dict[str, Any],
    config: Dict[str, Any],
    ssh_public_key: Optional[str] = None,
    snippet_storage: Optional[str] = None,
    cloud_init_settings: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Orchestrate complete VM provisioning with basic cloud-init setup.
    
    This is the main entry point for VM provisioning, coordinating all the
    steps required to provision a VM with cloud-init configuration.
    
    Args:
        vmid: VM ID to provision
        username: Username to create on the VM (legacy parameter for Phase 2A)
        proxmox_config: Proxmox connection configuration
        config: Full configuration dictionary containing cloud_init settings
        ssh_public_key: Optional SSH public key for user authentication (legacy)
        snippet_storage: Specific storage name (auto-detected if None)
        cloud_init_settings: Optional pre-merged cloud-init settings (Phase 2B)
        
    Returns:
        True if provisioning completed successfully
        
    Raises:
        ProvisionError: If any step of provisioning fails
        VMOperationError: If VM operations fail
    """
    logger.info(f"Starting basic provisioning for VM {vmid}")
    
    try:
        # Get Proxmox client first
        client = get_proxmox_api_client(proxmox_config)
        
        # Step 1: Find which node hosts the VM
        logger.debug("Finding VM node...")
        node_name = find_vm_node(client, vmid)
        if not node_name:
            raise VMOperationError(f"VM {vmid} not found on any node")
        
        logger.debug(f"VM {vmid} found on node {node_name}")
        
        # Step 2: Generate cloud-init configuration
        logger.debug("Generating cloud-init configuration...")
        
        # Use provided cloud_init_settings or fall back to global config (backward compatibility)
        if cloud_init_settings is not None:
            logger.debug("Using pre-merged cloud-init settings")
            effective_cloud_init = cloud_init_settings
        else:
            logger.debug("Using global cloud-init config (backward compatibility)")
            # Extract global cloud-init config (Phase 2A - no VM-specific merging yet)
            effective_cloud_init = config.get('cloud_init', {})
        
        # For Phase 2A: Add legacy user/SSH key to effective config if provided
        if username and not effective_cloud_init.get('users'):
            # Create a temporary user configuration for legacy parameters
            user_config = {
                'name': username,
                'password': username,  # Using username as password for legacy compatibility
                'sudo': True,
                'shell': '/bin/bash'
            }
            if ssh_public_key:
                user_config['ssh_keys'] = [ssh_public_key]
            
            # Add to a copy of effective config to avoid modifying original
            effective_cloud_init = effective_cloud_init.copy()
            effective_cloud_init['users'] = [user_config]
        
        # Phase 3: Extract network configuration if present
        network_config = extract_network_config(effective_cloud_init)
        has_network_config = network_config is not None
        
        if has_network_config:
            logger.debug("Network configuration found - generating separate user and network config files")
            # Create user config without network section
            user_cloud_init = create_user_config_without_network(effective_cloud_init)
        else:
            logger.debug("No network configuration found - generating user config file only")
            # Still clean the config to remove empty lists and None values
            user_cloud_init = clean_cloud_init_config(effective_cloud_init)
        
        # Generate user cloud-init configuration
        cloud_init_config = create_cloud_init_config(user_cloud_init)
        
        # Clean the configuration to remove empty lists and None values
        cleaned_cloud_init_config = clean_cloud_init_config(cloud_init_config)
        
        # Convert to YAML with cloud-config header
        cloud_init_yaml = "#cloud-config\n" + yaml.dump(
            cleaned_cloud_init_config, 
            default_flow_style=False,
            sort_keys=False
        )
        
        # Step 3: Upload cloud-init files to snippet storage
        logger.debug("Uploading cloud-init configuration...")
        upload_success = upload_cloud_init_to_snippet_storage(
            vmid, node_name, cloud_init_yaml, proxmox_config, snippet_storage
        )
        
        if not upload_success:
            raise ProvisionError("Failed to upload cloud-init configuration")
        
        # Upload network configuration if present
        if has_network_config:
            logger.debug("Uploading network configuration...")
            network_yaml = create_network_config_yaml(network_config)
            network_upload_success = upload_network_config_to_snippet_storage(
                vmid, node_name, network_yaml, proxmox_config, snippet_storage
            )
            
            if not network_upload_success:
                raise ProvisionError("Failed to upload network configuration")
        
        # Step 4: Configure VM to use cloud-init files
        logger.debug("Configuring VM to use cloud-init...")
        # Determine storage name for configuration
        if snippet_storage:
            storage_name = snippet_storage
        else:
            storage_info = get_node_snippet_storage(client, node_name)
            if not storage_info:
                raise ProvisionError(f"No snippet-capable storage found on node {node_name}")
            storage_name = storage_info["storage_name"]
        
        configure_success = configure_vm_cloud_init_files(
            vmid, node_name, storage_name, proxmox_config, has_network_config=has_network_config
        )
        
        if not configure_success:
            raise ProvisionError("Failed to configure VM cloud-init")
        
        # Step 5: Trigger cloud-init reconfiguration
        logger.debug("Triggering cloud-init reconfiguration...")
        reconfig_success = trigger_cloud_init_reconfiguration(
            vmid, node_name, proxmox_config
        )
        
        if not reconfig_success:
            raise ProvisionError("Failed to trigger cloud-init reconfiguration")
        
        logger.info(f"Successfully completed basic provisioning for VM {vmid}")
        return True
        
    except (ProvisionError, VMOperationError):
        # Re-raise our custom exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error during VM {vmid} provisioning: {e}")
        raise ProvisionError(f"Unexpected provisioning error: {e}", e)


def provision_vm(
    config: Dict[str, Any],
    vm_id: Optional[int] = None,
    vm_name: Optional[str] = None,
    force: bool = False,
) -> bool:
    """
    High-level VM provisioning function that handles VM lookup and configuration.
    
    This function serves as the main entry point for VM provisioning from the
    command layer, handling VM identification by ID or name and extracting
    necessary configuration details. SSH key configuration is optional - if not
    provided, the function relies on host OS SSH key management (ssh-agent, ~/.ssh/config).
    
    Args:
        config: Full CLI configuration dictionary
        vm_id: Optional VM ID to provision
        vm_name: Optional VM name to provision (not yet implemented)
        force: Whether to force provisioning (not yet implemented)
        
    Returns:
        True if provisioning succeeded, False otherwise
        
    Raises:
        ProvisionError: If provisioning fails
        VMOperationError: If VM operations fail
    """
    if vm_name:
        # VM name lookup not yet implemented
        raise ProvisionError("VM name lookup not yet implemented. Please use 'vmid'.")
    
    if not vm_id:
        raise ProvisionError("VM ID is required for provisioning")
    
    # Extract required configuration
    proxmox_config = config.get("proxmox", {})
    if not proxmox_config:
        raise ProvisionError("Proxmox configuration not found in config")
    
    # Get SSH key and user configuration (all optional)
    ssh_config = config.get("ssh", {})
    public_key_path = ssh_config.get("public_key_file")
    ssh_public_key = None
    
    # Try to get SSH key from config if specified
    if public_key_path:
        try:
            with open(public_key_path, 'r') as f:
                ssh_public_key = f.read().strip()
            logger.debug(f"Using SSH public key from config: {public_key_path}")
            
            # Validate SSH key if provided
            if not validate_ssh_public_key(ssh_public_key):
                raise ProvisionError("Invalid SSH public key format in configuration")
                
        except FileNotFoundError:
            raise ProvisionError(f"SSH public key file not found: {public_key_path}")
        except Exception as e:
            raise ProvisionError(f"Error reading SSH public key file: {e}")
    else:
        logger.debug("No SSH key specified in config - relying on host OS SSH key management")
    
    # Get username (default to ubuntu)
    username = ssh_config.get("username", "ubuntu")
    
    # Get snippet storage if specified
    snippet_storage = proxmox_config.get("snippet_storage")
    
    # Get merged cloud-init config for this VM (Phase 2B)
    cloud_init_settings = get_merged_cloud_init_for_vm(config, vm_id)
    
    if ssh_public_key:
        logger.info(f"Starting provisioning for VM {vm_id} with user '{username}' and configured SSH key")
    else:
        logger.info(f"Starting provisioning for VM {vm_id} with user '{username}' (no SSH key configured - using host OS SSH management)")
    
    return provision_vm_basic_setup(
        vmid=vm_id,
        username=username,
        proxmox_config=proxmox_config,
        config=config,
        ssh_public_key=ssh_public_key,
        snippet_storage=snippet_storage,
        cloud_init_settings=cloud_init_settings,
    )

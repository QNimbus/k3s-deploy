# filepath: /workspaces/k3s_deploy/src/k3s_deploy_cli/commands/provision_command.py
# file: src/k3s_deploy_cli/commands/provision_command.py
"""Implements the 'provision' command for the K3s Deploy CLI.

This module handles VM provisioning operations for VMs configured in config.json.
The provision command only provisions VMs that exist in the configuration and 
never performs node discovery.
"""

from typing import List, Optional, Set

from loguru import logger

from ..config import K3sDeployCLIConfig
from ..exceptions import ConfigurationError
from ..proxmox_vm_provision import provision_vm


def parse_vmid_string(vmid_string: str) -> List[int]:
    """
    Parse a comma-separated string of VMIDs into a list of integers.
    
    Args:
        vmid_string: Comma-separated VMID string (e.g., "100,101,102")
        
    Returns:
        List of VM IDs as integers
        
    Raises:
        ValueError: If any VMID is not a valid integer
    """
    try:
        vmids = [int(vmid.strip()) for vmid in vmid_string.split(',')]
        return vmids
    except ValueError as e:
        raise ValueError(f"Invalid VMID format: {e}")


def get_configured_vmids(config: K3sDeployCLIConfig) -> Set[int]:
    """
    Extract all VMIDs from the configuration nodes array.
    
    Args:
        config: The K3s Deploy CLI configuration
        
    Returns:
        Set of configured VM IDs
    """
    nodes = config.get("nodes", [])
    return {node["vmid"] for node in nodes if "vmid" in node}


def filter_configured_vmids(requested_vmids: List[int], configured_vmids: Set[int]) -> tuple[List[int], List[int]]:
    """
    Filter requested VMIDs into configured and unconfigured lists.
    
    Args:
        requested_vmids: List of VMIDs requested for provisioning
        configured_vmids: Set of VMIDs that exist in configuration
        
    Returns:
        Tuple of (configured_vmids, unconfigured_vmids) as lists
    """
    configured = [vmid for vmid in requested_vmids if vmid in configured_vmids]
    unconfigured = [vmid for vmid in requested_vmids if vmid not in configured_vmids]
    return configured, unconfigured


def handle_provision_command(
    config: K3sDeployCLIConfig,
    vmids: Optional[List[int]] = None,
) -> bool:
    """
    Handle the provision command for VM cloud-init configuration.
    
    This function provisions VMs with cloud-init configuration by:
    1. Determining which VMs to provision (from VMIDs or all configured)
    2. Filtering to only VMs that exist in config.json
    3. Provisioning each configured VM
    4. Reporting any unconfigured VMIDs
    
    Args:
        config: The K3s Deploy CLI configuration
        vmids: Optional list of VM IDs to provision. If None, provision all configured VMs.
        
    Returns:
        True if all requested provisioning succeeded, False if any failures occurred
        
    Raises:
        ConfigurationError: If configuration is invalid
    """
    logger.info("Starting VM provisioning process")
    
    # Validate configuration
    if "proxmox" not in config:
        raise ConfigurationError("Proxmox configuration not found in config")
    
    # Get configured VMIDs
    configured_vmids = get_configured_vmids(config)
    
    if not configured_vmids:
        if vmids:
            # Report that requested VMIDs are not configured
            for vmid in vmids:
                logger.warning(f"VMID {vmid} is not configured in config.json and will be skipped")
            return True
        else:
            logger.info("No nodes configured in config.json - nothing to provision")
            return True
    
    # Determine which VMs to provision
    if vmids is None:
        # Provision all configured VMs
        vms_to_provision = list(configured_vmids)
        logger.info(f"No specific VMIDs provided - provisioning all {len(vms_to_provision)} configured VMs")
    else:
        # Filter requested VMIDs to only those that are configured
        vms_to_provision, unconfigured_vmids = filter_configured_vmids(vmids, configured_vmids)
        
        # Report unconfigured VMIDs
        for vmid in unconfigured_vmids:
            logger.warning(f"VMID {vmid} is not configured in config.json and will be skipped")
        
        if not vms_to_provision:
            logger.info("No configured VMs found in the requested VMIDs")
            return True
        
        logger.info(f"Provisioning {len(vms_to_provision)} configured VMs: {vms_to_provision}")
    
    # Provision each configured VM
    success_count = 0
    failure_count = 0
    
    for vmid in vms_to_provision:
        try:
            logger.info(f"Provisioning VM {vmid}...")
            result = provision_vm(config=config, vm_id=vmid)
            
            if result:
                logger.info(f"Successfully provisioned VM {vmid}")
                success_count += 1
            else:
                logger.error(f"Failed to provision VM {vmid}")
                failure_count += 1
                
        except Exception as e:
            # If we're only provisioning a single VM, re-raise the exception
            # If we're provisioning multiple VMs, log and continue
            if len(vms_to_provision) == 1:
                raise
            else:
                logger.error(f"Failed to provision VM {vmid}: {e}")
                failure_count += 1
    
    # Report summary
    total_requested = len(vms_to_provision)
    logger.info(f"Provisioning complete: {success_count}/{total_requested} successful, {failure_count} failed")
    
    return failure_count == 0
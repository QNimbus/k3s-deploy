# file: src/k3s_deploy_cli/proxmox_vm_operations.py
"""Manages Proxmox virtual machine (VM) operations.

This module provides functions to interact with Proxmox VMs,
allowing for actions such as retrieving current status, starting, stopping,
and restarting VMs. It also includes a utility to locate a VM across cluster nodes.
"""
import warnings
from typing import Any, Dict, Optional

from loguru import logger
from proxmoxer import ProxmoxAPI
from proxmoxer.core import (
    ResourceException,  # Changed ProxmoxResourceException to ResourceException
)
from urllib3.exceptions import InsecureRequestWarning

from .exceptions import ProxmoxInteractionError

# Suppress InsecureRequestWarning when verify_ssl is False
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

def get_vm_status(proxmox_client: ProxmoxAPI, node_name: str, vmid: int) -> Dict[str, Any]:
    """
    Retrieves the current status of a VM.
    
    Args:
        proxmox_client: An initialized ProxmoxAPI client.
        node_name: The name of the Proxmox node.
        vmid: The VM ID.
    
    Returns:
        Dict containing VM status information including 'status' field.
    
    Raises:
        ProxmoxInteractionError: If fetching VM status fails.
    """
    try:
        logger.debug(f"Fetching status for VM {vmid} on node '{node_name}'")
        vm_status = proxmox_client.nodes(node_name).qemu(vmid).status.current.get()
        logger.debug(f"Successfully fetched status for VM {vmid}: {vm_status.get('status', 'unknown')}")
        return vm_status
    except ResourceException as e:
        logger.error(f"Error fetching status for VM {vmid}: {e.status_code} - {e.content}")
        raise ProxmoxInteractionError(
            f"Error fetching status for VM {vmid}: {e.status_code} - {e.content}"
        ) from e
    except Exception as e:
        logger.error(f"Error fetching status for VM {vmid}: {e}")
        raise ProxmoxInteractionError(
            f"Error fetching status for VM {vmid}: {e}"
        ) from e

def start_vm(proxmox_client: ProxmoxAPI, node_name: str, vmid: int) -> Dict[str, Any]:
    """
    Starts a VM.
    
    Args:
        proxmox_client: An initialized ProxmoxAPI client.
        node_name: The name of the Proxmox node.
        vmid: The VM ID.
    
    Returns:
        Dict containing the operation result.
    
    Raises:
        ProxmoxInteractionError: If starting the VM fails.
    """
    try:
        logger.debug(f"Starting VM {vmid} on node '{node_name}'")
        result = proxmox_client.nodes(node_name).qemu(vmid).status.start.post()
        logger.info(f"Successfully started VM {vmid}")
        return result
    except ResourceException as e:
        logger.error(f"Error starting VM {vmid}: {e.status_code} - {e.content}")
        raise ProxmoxInteractionError(
            f"Error starting VM {vmid}: {e.status_code} - {e.content}"
        ) from e
    except Exception as e:
        logger.error(f"Error starting VM {vmid}: {e}")
        raise ProxmoxInteractionError(
            f"Error starting VM {vmid}: {e}"
        ) from e

def stop_vm(proxmox_client: ProxmoxAPI, node_name: str, vmid: int, force: bool = False) -> Dict[str, Any]:
    """
    Stops a VM using either graceful shutdown or force stop.
    
    Args:
        proxmox_client: An initialized ProxmoxAPI client.
        node_name: The name of the Proxmox node.
        vmid: The VM ID.
        force: If True, use force stop. If False, use graceful shutdown.
    
    Returns:
        Dict containing the operation result.
    
    Raises:
        ProxmoxInteractionError: If stopping the VM fails.
    """
    try:
        if force:
            logger.debug(f"Force stopping VM {vmid} on node '{node_name}'")
            result = proxmox_client.nodes(node_name).qemu(vmid).status.stop.post()
            logger.info(f"Successfully force stopped VM {vmid}")
        else:
            logger.debug(f"Gracefully shutting down VM {vmid} on node '{node_name}'")
            result = proxmox_client.nodes(node_name).qemu(vmid).status.shutdown.post()
            logger.info(f"Successfully initiated shutdown for VM {vmid}")
        return result
    except ResourceException as e:
        action = "force stopping" if force else "shutting down"
        logger.error(f"Error {action} VM {vmid}: {e.status_code} - {e.content}")
        raise ProxmoxInteractionError(
            f"Error {action} VM {vmid}: {e.status_code} - {e.content}"
        ) from e
    except Exception as e:
        action = "force stopping" if force else "shutting down"
        logger.error(f"Error {action} VM {vmid}: {e}")
        raise ProxmoxInteractionError(
            f"Error {action} VM {vmid}: {e}"
        ) from e

def restart_vm(proxmox_client: ProxmoxAPI, node_name: str, vmid: int) -> Dict[str, Any]:
    """
    Restarts a VM.
    
    Args:
        proxmox_client: An initialized ProxmoxAPI client.
        node_name: The name of the Proxmox node.
        vmid: The VM ID.
    
    Returns:
        Dict containing the operation result.
    
    Raises:
        ProxmoxInteractionError: If restarting the VM fails.
    """
    try:
        logger.debug(f"Restarting VM {vmid} on node '{node_name}'")
        result = proxmox_client.nodes(node_name).qemu(vmid).status.reboot.post()
        logger.info(f"Successfully restarted VM {vmid}")
        return result
    except ResourceException as e:
        raise ProxmoxInteractionError(f"Error restarting VM {vmid}: {e.status_code} - {e.content}")
    except Exception as e:
        raise ProxmoxInteractionError(f"Error restarting VM {vmid}: {e}")

def find_vm_node(proxmox_client: ProxmoxAPI, vmid: int) -> Optional[str]:
    """
    Finds which node a VM resides on by searching all nodes.
    
    Args:
        proxmox_client: An initialized ProxmoxAPI client.
        vmid: The VM ID to find.
    
    Returns:
        The node name where the VM is found, or None if not found.
    
    Raises:
        ProxmoxInteractionError: If there's an error querying nodes.
    """
    try:
        logger.debug(f"Searching for VM {vmid} across all nodes")
        
        # Get list of all nodes
        nodes = proxmox_client.nodes.get()
        
        for node in nodes:
            node_name = node.get("node")
            if not node_name:
                continue
                
            try:
                # Check if VM exists on this node
                vms = proxmox_client.nodes(node_name).qemu.get()
                for vm in vms:
                    if vm.get("vmid") == vmid:
                        logger.debug(f"Found VM {vmid} on node '{node_name}'")
                        return node_name
            except ResourceException:
                # Node might be offline or inaccessible, continue to next node
                logger.debug(f"Could not access node '{node_name}', skipping")
                continue
        
        logger.debug(f"VM {vmid} not found on any accessible node")
        return None
        
    except ResourceException as e:
        logger.error(f"Error searching for VM {vmid}: {e.status_code} - {e.content}")
        raise ProxmoxInteractionError(
            f"Error searching for VM {vmid}: {e.status_code} - {e.content}"
        ) from e
    except Exception as e:
        logger.error(f"Error searching for VM {vmid}: {e}")
        raise ProxmoxInteractionError(
            f"Error searching for VM {vmid}: {e}"
        ) from e
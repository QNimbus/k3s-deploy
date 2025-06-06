# file: src/k3s_deploy_cli/proxmox_vm_discovery.py
"""Handles discovery and detailed information retrieval for Proxmox VMs.

This module specializes in finding K3s-tagged virtual machines across Proxmox nodes
and gathering comprehensive data about them, including configuration, QEMU Guest Agent status,
and associated storage. It also includes utilities for testing SFTP connectivity.
"""
import os
import tempfile
import uuid  # Added for more unique temp filenames
import warnings
from typing import Any, Dict, List, Optional

import paramiko
from loguru import logger
from proxmoxer.core import (
    ResourceException,
)
from urllib3.exceptions import InsecureRequestWarning

from .constants import K3S_TAGS
from .exceptions import ProxmoxInteractionError
from .proxmox_core import ProxmoxAPI, get_cluster_status

# Suppress InsecureRequestWarning when verify_ssl is False
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

def get_vms_with_k3s_tags(proxmox_client: ProxmoxAPI, node_name: str) -> List[Dict[str, Any]]:
    """
    Retrieves a list of VMs on a given Proxmox node that have exactly one K3s tag.

    Args:
        proxmox_client: An initialized ProxmoxAPI client.
        node_name: The name of the Proxmox node to query.

    Returns:
        A list of dictionaries, where each dictionary contains information
        about a tagged VM (vmid, name, status, k3s_tag, qga details).

    Raises:
        ProxmoxInteractionError: If there's an issue communicating with the Proxmox API.
    """
    tagged_vms: List[Dict[str, Any]] = []
    try:
        logger.debug(f"Fetching VMs from node '{node_name}' for K3s tag check.")
        vms_on_node = proxmox_client.nodes(node_name).qemu.get()
        
        for vm in vms_on_node:
            vm_tags_str = vm.get("tags", "")
            if not vm_tags_str:
                continue

            vm_tags_list = [tag.strip() for tag in vm_tags_str.split(';')]
            
            found_k3s_tags = []
            for k3s_tag in K3S_TAGS:
                if k3s_tag in vm_tags_list:
                    found_k3s_tags.append(k3s_tag)
            
            if len(found_k3s_tags) == 1:
                logger.trace(f"VMID {vm.get('vmid')} on node '{node_name}' matched with tag: {found_k3s_tags[0]}")
                
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
        
        tagged_vms.sort(key=lambda vm_item: vm_item.get("vmid", 0))
        
        logger.debug(f"Found {len(tagged_vms)} K3s-tagged VMs on node '{node_name}'.")
        return tagged_vms
    except ResourceException as e:
        err_msg = (
            f"Failed to retrieve K3s-tagged VMs from node '{node_name}' "
            f"(API Error: {e.status_code} - {e.content}): {e}"
        )
        logger.error(err_msg)
        raise ProxmoxInteractionError(err_msg) from e
    except Exception as e:
        err_msg = f"Failed to retrieve K3s-tagged VMs from node '{node_name}': {e}"
        logger.error(err_msg)
        raise ProxmoxInteractionError(err_msg) from e
        
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
        - qga_enabled: bool
        - qga_running: bool
        - qga_version: str|None

    Raises:
        ProxmoxInteractionError: If there's an issue communicating with the Proxmox API.
    """
    discovered_nodes: List[Dict[str, Any]] = []
    
    try:
        logger.debug("Getting cluster status for node discovery...")
        cluster_status = get_cluster_status(proxmox_client)
        online_nodes = [
            node for node in cluster_status 
            if node.get("type") == "node" and node.get("online") == 1
        ]
        
        if not online_nodes:
            logger.warning("No online Proxmox nodes found for K3s discovery")
            return discovered_nodes
        
        logger.info(f"Scanning {len(online_nodes)} online Proxmox nodes for K3s VMs...")
        
        for node_info in online_nodes: # Renamed 'node' to 'node_info' to avoid conflict
            node_name = node_info.get("name")
            if not node_name:
                logger.warning(f"Node found without name, skipping: {node_info}")
                continue
                
            logger.debug(f"Discovering K3s VMs on node '{node_name}'...")
            
            try:
                tagged_vms = get_vms_with_k3s_tags(proxmox_client, node_name)
                for vm in tagged_vms:
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
                    
                    discovered_node_info = { # Renamed 'discovered_node'
                        "vmid": vm.get("vmid"),
                        "role": role,
                        "node": node_name,
                        "name": vm.get("name", "N/A"),
                        "status": vm.get("status", "N/A"),
                        "qga_enabled": vm.get("qga_enabled", False),
                        "qga_running": vm.get("qga_running", False),
                        "qga_version": vm.get("qga_version")
                    }
                    discovered_nodes.append(discovered_node_info)
                    logger.debug(f"Discovered K3s node: VMID {discovered_node_info['vmid']}, role '{role}' on '{node_name}'")
                    
            except ProxmoxInteractionError as e:
                logger.error(f"Failed to get K3s VMs from node '{node_name}': {e}")
                continue
        
        discovered_nodes.sort(key=lambda n: n.get("vmid", 0))
        
        logger.info(f"Discovery complete: found {len(discovered_nodes)} K3s VMs across {len(online_nodes)} nodes")
        return discovered_nodes
        
    except Exception as e:
        err_msg = f"Failed to discover K3s nodes: {e}"
        logger.error(err_msg)
        raise ProxmoxInteractionError(err_msg) from e

def get_vm_config(proxmox_client: ProxmoxAPI, node_name: str, vmid: int) -> Dict[str, Any]:
    """
    Retrieves VM configuration.
    
    Args:
        proxmox_client: An initialized ProxmoxAPI client.
        node_name: The name of the Proxmox node.
        vmid: The VM ID.
    
    Returns:
        VM configuration dictionary.
        
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
        # The 'get' method with a path is specific to Proxmoxer for sub-resources
        agent_info = proxmox_client.nodes(node_name).qemu(vmid).agent.get('info')
        logger.debug(f"Successfully fetched QGA info for VM {vmid}")
        return agent_info
    except ResourceException as e:
        logger.debug(f"QGA not available or not responding for VM {vmid}: {e.status_code} - {e.content}")
        return None
    except Exception as e: # Catch any other exception
        logger.debug(f"QGA check failed for VM {vmid} (other exception): {e}")
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
        vm_config = get_vm_config(proxmox_client, node_name, vmid)
        raw_agent_setting = vm_config.get("agent")

        if raw_agent_setting is None:
            qga_status["enabled"] = False
        elif isinstance(raw_agent_setting, int):
            qga_status["enabled"] = bool(raw_agent_setting) # Handles 0 or 1
        elif isinstance(raw_agent_setting, str):
            agent_str = raw_agent_setting.strip().lower()
            if agent_str == "0" or agent_str == "false" or \
               "enabled=0" in agent_str or "enabled=false" in agent_str:
                qga_status["enabled"] = False
            elif agent_str == "": # Explicitly empty string implies disabled
                qga_status["enabled"] = False
            # "enabled=1", "enabled=true", "1", "true", or any other option string implies enabled
            elif agent_str == "1" or agent_str == "true" or \
                 "enabled=1" in agent_str or "enabled=true" in agent_str:
                qga_status["enabled"] = True
            else:
                # If it's a non-empty string not matching false/0 conditions,
                # and it doesn't explicitly state enabled=1/true,
                # the presence of options implies enabled.
                qga_status["enabled"] = True if agent_str else False
        else:
            logger.warning(
                f"VM {vmid} on node '{node_name}' has unexpected agent config type: "
                f"{type(raw_agent_setting)} (value: '{raw_agent_setting}'). Assuming QGA disabled."
            )
            qga_status["enabled"] = False
                
    except ProxmoxInteractionError as e:
        qga_status["error"] = f"Config check failed: {str(e)}"
        logger.warning(f"Failed to check QGA config for VM {vmid}: {e}")
        # If we can't get config, we can't determine if it's enabled.
        # We also can't reliably check runtime status without knowing if it should be enabled.
        return qga_status # Return early as further checks are unreliable
        
    if qga_status["enabled"]:
        try:
            agent_info = get_vm_agent_info(proxmox_client, node_name, vmid)
            if agent_info and isinstance(agent_info, dict): # Ensure agent_info is a dict
                qga_status["running"] = True
                qga_status["version"] = agent_info.get("version", "Unknown")
            else:
                qga_status["running"] = False
                # If agent_info is None, it means QGA is not running or not responsive.
                # If it's not a dict, it's an unexpected response.
                if agent_info is not None:
                    logger.warning(f"Unexpected QGA info format for VM {vmid}: {agent_info}")
        except Exception as e: # Catch any exception during runtime check
            logger.debug(f"QGA runtime check failed for VM {vmid} (enabled in config): {e}")
            qga_status["running"] = False
            if not qga_status["error"]: # Don't overwrite a config check error
                 qga_status["error"] = f"Runtime check failed: {str(e)}"
        
    logger.trace(
        f"QGA status for VM {vmid}: enabled={qga_status['enabled']}, "
        f"running={qga_status['running']}, version={qga_status['version']}"
    )
    return qga_status
        

def get_storage_info(proxmox_client: ProxmoxAPI, storage_name: str) -> Dict[str, Any]:
    """
    Retrieve detailed storage information including filesystem path.
    
    Args:
        proxmox_client: An initialized ProxmoxAPI client
        storage_name: Name of the storage to query
        
    Returns:
        Dict containing storage information:
        {
            "storage": "local",
            "type": "dir", 
            "path": "/var/lib/vz",
            "content": "snippets,iso,vztmpl",
            "enabled": True,
            "shared": False
        }
        Empty dict {} if storage not found.
        
    Raises:
        ProxmoxInteractionError: If API call fails
    """
    try:
        logger.debug(f"Fetching detailed info for storage '{storage_name}'...")
        storage_info_item = proxmox_client.storage(storage_name).get()
        logger.debug(f"Retrieved storage info for '{storage_name}': type={storage_info_item.get('type')}")
        
        return storage_info_item
        
    except ResourceException as e:
        if e.status_code == 404:
            logger.warning(f"Storage '{storage_name}' not found via /storage/{storage_name} endpoint.")
            return {}
        logger.error(f"Error fetching storage info for '{storage_name}': {e.status_code} - {e.content}")
        raise ProxmoxInteractionError(
            f"Error fetching storage info for '{storage_name}': {e.status_code} - {e.content}"
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error fetching storage info for '{storage_name}': {e}")
        raise ProxmoxInteractionError(
            f"Unexpected error fetching storage info for '{storage_name}': {e}"
        ) from e


def test_sftp_write_access(ssh_client: paramiko.SSHClient, remote_path: str) -> Dict[str, Any]:
    """
    Test SFTP write access to a remote directory by creating and removing a test file.
    
    Args:
        ssh_client: An established paramiko SSH client connection
        remote_path: Remote directory path to test write access
        
    Returns:
        Dict containing test results:
        {
            "writable": True/False,
            "error": None or error message,
            "test_file": "test filename used"
        }
    """
    result = {
        "writable": False,
        "error": None,
        "test_file": None
    }
    
    # Generate a unique test filename
    test_filename = f".k3s_deploy_write_test_{os.getpid()}_{uuid.uuid4().hex[:8]}.tmp"
    result["test_file"] = test_filename # Store the base filename

    # Ensure remote_path does not end with a slash for os.path.join
    # and then ensure the path is POSIX-style for SFTP
    clean_remote_path = remote_path.rstrip('/')
    test_file_path = f"{clean_remote_path}/{test_filename}" # Use f-string for POSIX path
    
    logger.debug(f"Testing SFTP write access to '{remote_path}' using test file '{test_file_path}'")
    
    sftp = None
    temp_local_path = None
    try:
        sftp = ssh_client.open_sftp()
        
        # Create a temporary local test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("k3s_deploy SFTP write access test")
            temp_local_path = temp_file.name
        
        # Upload the test file
        sftp.put(temp_local_path, test_file_path)
        logger.debug(f"Successfully uploaded test file to '{test_file_path}'")
        
        # Verify the file exists (optional, but good practice)
        sftp.stat(test_file_path)
        logger.debug(f"Verified test file exists at '{test_file_path}'")
        
        result["writable"] = True
        logger.debug(f"SFTP write test successful for '{remote_path}'")
            
    except Exception as e:
        logger.debug(f"SFTP write test failed for '{remote_path}': {e}")
        result["error"] = str(e)
    finally:
        # Cleanup
        if sftp:
            try:
                if result["writable"]: # Only attempt removal if upload was thought successful
                    sftp.remove(test_file_path)
                    logger.debug(f"Successfully removed remote test file '{test_file_path}'")
            except Exception as cleanup_error:
                logger.warning(f"Failed to remove remote test file '{test_file_path}': {cleanup_error}")
                if not result["error"]: # Add cleanup error if no primary error occurred
                    result["error"] = f"Remote cleanup failed: {str(cleanup_error)}"
            finally:
                sftp.close()
        
        if temp_local_path:
            try:
                os.unlink(temp_local_path)
            except Exception as local_cleanup_error:
                logger.warning(f"Failed to remove local temp file '{temp_local_path}': {local_cleanup_error}")
    
    return result
# file: src/k3s_deploy_cli/commands/info_command.py
"""Implements the 'info' command for the K3s Deploy CLI.

This module is responsible for gathering and displaying detailed information
about the Proxmox cluster, its nodes, and K3s virtual machines.
It can present data based on existing configuration or perform
on-the-fly discovery of K3s VMs.
"""

from typing import Any, Dict, List, Optional

from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.text import Text

from ..config import K3sDeployCLIConfig
from ..exceptions import ConfigurationError, ProxmoxInteractionError
from ..logging_config import VERBOSE_LOG_LEVEL
from ..proxmox_core import (
    get_cluster_status,
    get_node_dns_info,
    get_node_snippet_storage,
    get_proxmox_api_client,
    get_proxmox_version_info,
)
from ..proxmox_vm_discovery import get_vms_with_k3s_tags, test_sftp_write_access
from ..ssh_operations import check_proxmox_ssh_connectivity


def handle_info_command(
    config: K3sDeployCLIConfig, console: Console, discover: bool = False
) -> None:
    """
    Handles the 'info' command to display Proxmox cluster status using rich tables.

    Args:
        config: The loaded application configuration.
        console: The Rich Console object for output.
        discover: If True, always perform tag-based discovery regardless of configured nodes.
    """
    logger.info("Attempting to retrieve Proxmox cluster information...")

    proxmox_cfg = config.get("proxmox")
    if not proxmox_cfg:
        logger.error(
            "Proxmox configuration ('proxmox') is missing from the config file."
        )
        raise ConfigurationError(
            "Proxmox configuration is missing. Ensure the 'proxmox' section exists in your config file."
        )

    try:
        proxmox_client = get_proxmox_api_client(proxmox_cfg)
        logger.info("Successfully connected to Proxmox VE API.")

        # Fetch version and status information
        proxmox_version_info = get_proxmox_version_info(proxmox_client)
        logger.log(
            VERBOSE_LOG_LEVEL,
            f"Retrieved Proxmox version info: {proxmox_version_info}",
        )

        # get_cluster_status() returns a list of node status dictionaries
        all_nodes_status = get_cluster_status(proxmox_client)
        logger.log(
            VERBOSE_LOG_LEVEL,
            f"Retrieved cluster status (list of nodes): {all_nodes_status}",
        )

        if not all_nodes_status:
            console.print(
                "Could not retrieve cluster status or cluster status is empty (no nodes found)."
            )
            return

        # Extract cluster information from /cluster/status response
        cluster_info = None
        for item in all_nodes_status:
            if item.get("type") == "cluster":
                cluster_info = item
                break

        # Display Cluster Overview
        _display_cluster_overview(console, cluster_info, proxmox_version_info, proxmox_cfg)

        # Filter for actual Proxmox VE nodes from the status list and sort alphabetically
        nodes_data = [
            node for node in all_nodes_status if node.get("type") == "node"
        ]
        nodes_data.sort(key=lambda node: node.get("name", ""))

        if not nodes_data:
            console.print(
                Text(
                    "\nNo Proxmox VE nodes found in the cluster status.",
                    style="yellow",
                )
            )
        else:
            _display_nodes_table(console, nodes_data, proxmox_client, config)
            _display_k3s_vm_information(
                console, config, proxmox_client, nodes_data, discover
            )

    except ProxmoxInteractionError as e:
        logger.error(f"Proxmox API interaction failed: {e}")
        raise  # Re-raise to be caught by main()
    except ConfigurationError as e:
        logger.error(f"Configuration error for Proxmox connection: {e}")
        raise  # Re-raise to be caught by main()


def _display_cluster_overview(
    console: Console, cluster_info: Optional[Dict[str, Any]], 
    proxmox_version_info: Dict[str, Any], proxmox_cfg: Dict[str, Any]
) -> None:
    """Display the cluster overview table."""
    cluster_overview_table = Table(
        title="Cluster Overview", show_header=True, header_style="bold magenta"
    )
    cluster_overview_table.add_column("Property", width=20)
    cluster_overview_table.add_column("Value", style="bold")

    cluster_name = cluster_info.get("name", "N/A") if cluster_info else "N/A"
    
    # Parse version information
    pve_full_version_str = proxmox_version_info.get("version", "N/A")
    pve_release_str = proxmox_version_info.get("release", "N/A")
    pve_repo_id_str = proxmox_version_info.get("repid", "N/A")
    
    displayed_version = pve_full_version_str
    if pve_full_version_str != "N/A" and "/" in pve_full_version_str:
        try:
            main_version_part = pve_full_version_str.split("/")[1]
            displayed_version = (
                f"{main_version_part} (OS: {pve_repo_id_str}, Release: {pve_release_str})"
            )
        except IndexError:
            pass  # Stick with the full version string

    # Determine quorate status from cluster info in /cluster/status
    is_quorate = cluster_info.get("quorate") == 1 if cluster_info else False

    # Check SSH connectivity to configured Proxmox host
    ssh_status = "N/A"
    proxmox_host = proxmox_cfg.get("host", "N/A")
    if proxmox_host != "N/A":
        try:
            # Pass the full proxmox config for SSH authentication
            ssh_result = check_proxmox_ssh_connectivity(proxmox_cfg, timeout=5)
            
            if ssh_result["success"]:
                ssh_status = Text("Connected", style="green")
            elif ssh_result.get("warning"):
                ssh_status = Text("Auth Issue", style="yellow")
            else:
                ssh_status = Text("Failed", style="red")
        except Exception as e:
            logger.debug(f"SSH connectivity check failed for host '{proxmox_host}': {e}")
            ssh_status = Text("Error", style="red")
    else:
        ssh_status = Text("Not Configured", style="dim")

    cluster_overview_table.add_row("Name", cluster_name)
    cluster_overview_table.add_row("Proxmox VE Version", displayed_version)
    cluster_overview_table.add_row("Quorate", "Yes" if is_quorate else "No")
    cluster_overview_table.add_row("SSH Connectivity", ssh_status)
    console.print(cluster_overview_table)


def _test_storage_sftp_access(config: K3sDeployCLIConfig, node_name: str, storage_path: str) -> Text:
    """
    Test SFTP write access to storage path on a Proxmox node.
    
    Args:
        config: Application configuration
        node_name: Name of the Proxmox node
        storage_path: Filesystem path to test
        
    Returns:
        Rich Text object indicating write access status
    """
    try:
        import re

        import paramiko
        
        # Get Proxmox configuration for SSH connection
        proxmox_config = config.get("proxmox", {})
        configured_host = proxmox_config.get("host")  # e.g., 'pve1.lan.home.vwn.io'
        
        # Construct hostname by replacing the first part with the node name
        if "." in configured_host:
            domain_parts = configured_host.split(".", 1)
            host = f"{node_name}.{domain_parts[1]}"  # e.g., 'pve2.lan.home.vwn.io'
        else:
            host = node_name  # Fallback to just the node name
        
        # Validate hostname format (basic check for valid hostname characters)
        hostname_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-\.]*[a-zA-Z0-9])?$'
        if not re.match(hostname_pattern, host):
            logger.debug(f"Invalid hostname constructed: {host}")
            return Text("Bad Host", style="red")
        
        # Extract username from Proxmox user config (handle user@realm format)
        user_config = proxmox_config.get("user", "root")
        username = user_config.split("@")[0] if "@" in user_config else user_config
        password = proxmox_config.get("password")
        
        # Create SSH client for SFTP test
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            # Try to connect with available authentication methods
            logger.debug(f"Attempting SSH connection to {host} for SFTP test")
            
            # First try public key authentication
            try:
                ssh_client.connect(
                    hostname=host,
                    port=22,
                    username=username,
                    timeout=10,
                    allow_agent=True,
                    look_for_keys=True
                )
            except Exception:
                # Fall back to password authentication if available
                if password:
                    ssh_client.connect(
                        hostname=host,
                        port=22,
                        username=username,
                        password=password,
                        timeout=10,
                        allow_agent=False,
                        look_for_keys=False
                    )
                else:
                    return Text("Auth Failed", style="red")
            
            # Perform SFTP write test
            sftp_result = test_sftp_write_access(ssh_client, storage_path)
            
            if sftp_result["writable"]:
                return Text("Yes", style="green")
            else:
                error_msg = sftp_result.get("error", "Unknown")
                logger.debug(f"SFTP write test failed for {node_name}: {error_msg}")
                return Text("No", style="red")
                
        finally:
            try:
                ssh_client.close()
            except Exception:
                pass
                
    except Exception as e:
        logger.debug(f"SFTP write test failed for node '{node_name}': {e}")
        return Text("Error", style="red")


def _display_nodes_table(
    console: Console, nodes_data: List[Dict[str, Any]], proxmox_client: Any, config: K3sDeployCLIConfig
) -> None:
    """Display the Proxmox VE nodes table."""
    nodes_table = Table(
        title="Proxmox VE Nodes", show_header=True, header_style="bold blue"
    )
    nodes_table.add_column("Node", width=20)
    nodes_table.add_column("Domain", width=20)
    nodes_table.add_column("Local", width=10)
    nodes_table.add_column("Online", width=10)
    nodes_table.add_column("IP Address", width=20)
    nodes_table.add_column("Snippet Storage", width=18)
    nodes_table.add_column("Storage Path", width=25)
    nodes_table.add_column("SFTP Writable", width=15)
    
    for node in nodes_data:
        node_name = node.get("name", "N/A")

        # Retrieve domain information for the node
        domain = "N/A"
        if node_name != "N/A":
            try:
                domain_info = get_node_dns_info(proxmox_client, node_name)
                domain = domain_info if domain_info else "N/A"
            except Exception as e:
                logger.debug(f"Failed to get DNS info for node '{node_name}': {e}")
                domain = "N/A"

        # Retrieve snippet storage information for the node
        snippet_storage = "N/A"
        storage_path = "N/A" 
        sftp_writable = "N/A"
        
        if node_name != "N/A":
            try:
                storage_info = get_node_snippet_storage(proxmox_client, node_name)
                if storage_info:
                    snippet_storage = Text(storage_info["storage_name"], style="green")
                    storage_path = storage_info.get("path", None)
                    
                    # Test SFTP write access if we have storage path and it's not shared storage
                    if storage_path and not storage_info.get("shared", False):
                        sftp_writable = _test_storage_sftp_access(config, node_name, storage_path)
                    elif storage_info.get("shared", False):
                        sftp_writable = Text("Shared", style="dim")
                    else:
                        sftp_writable = Text("Unknown", style="dim")
                else:
                    snippet_storage = Text("None", style="red")
                    sftp_writable = Text("N/A", style="dim")
            except Exception as e:
                logger.debug(f"Failed to get snippet storage info for node '{node_name}': {e}")
                snippet_storage = Text("Error", style="red")
                sftp_writable = Text("Error", style="red")

        # Create colored text for Yes/No values
        local_text = Text("Yes", style="green") if node.get("local") == 1 else Text("No", style="red")
        online_text = Text("Yes", style="green") if node.get("online") == 1 else Text("No", style="red")

        nodes_table.add_row(
            node_name,
            domain,
            local_text,
            online_text,
            node.get("ip", "N/A"),
            snippet_storage,
            storage_path,
            sftp_writable,
        )
    console.print(nodes_table)


def _display_k3s_vm_information(
    console: Console,
    config: K3sDeployCLIConfig,
    proxmox_client: Any,
    nodes_data: List[Dict[str, Any]],
    discover: bool,
) -> None:
    """Display K3s VM information based on discovery mode or configured nodes."""
    configured_nodes = config.get("nodes", [])

    if discover or not configured_nodes:
        _display_tag_based_k3s_vms(
            console, proxmox_client, nodes_data, discover, configured_nodes
        )
    else:
        _display_configured_nodes(config, proxmox_client, console)


def _display_tag_based_k3s_vms(console: Console, proxmox_client, nodes_data: List[Dict], discover: bool, configured_nodes: List[Dict]) -> None:
    """Display K3s VMs found using tag-based discovery.
    
    Args:
        console: Rich console instance for output
        proxmox_client: Proxmox API client
        nodes_data: List of Proxmox nodes
        discover: Whether this is discovery mode
        configured_nodes: List of configured nodes from config
    """
    mode_text = "discovery" if discover else "fallback discovery"
    console.print(f"\n[bold cyan]K3s VMs (tag-based {mode_text}):[/bold cyan]")
    
    if discover and configured_nodes:
        console.print("[dim]Note: Using discovery mode - configured nodes in config file will be ignored.[/dim]")
    
    try:
        # Collect VMs from all online nodes
        all_vms = []
        
        for node_info in nodes_data:
            if node_info.get("online") == 1:  # Only check online nodes
                node_name = node_info["name"]
                
                try:
                    vms = get_vms_with_k3s_tags(proxmox_client, node_name)
                    if vms:
                        all_vms.extend(vms)
                        
                except ProxmoxInteractionError as e:
                    console.print(f"[red]Error retrieving VMs from node '{node_name}': {e}[/red]")
        
        # Display all VMs in a single table
        if all_vms:
            _display_k3s_vms_table(console, all_vms)
        else:
            console.print("[dim]No K3s VMs found on any online nodes[/dim]")
                    
    except Exception as e:
        console.print(f"[red]Unexpected error during VM discovery: {e}[/red]")


def _display_k3s_vms_table(console: Console, tagged_vms: List[Dict[str, Any]]) -> None:
    """Display a table of K3s VMs for a specific node."""
    k3s_vms_table = Table(show_header=True, header_style="bold blue")
    k3s_vms_table.add_column("VMID", style="dim", width=10)
    k3s_vms_table.add_column("Name", width=30)
    k3s_vms_table.add_column("Status", width=15)
    k3s_vms_table.add_column("K3s Role Tag", width=20)
    k3s_vms_table.add_column("QGA Enabled", width=12)
    k3s_vms_table.add_column("QGA Running", width=12)
    k3s_vms_table.add_column("QGA Version", width=12)

    for vm in tagged_vms:
        # Format QGA status indicators
        qga_enabled = vm.get("qga_enabled", False)
        qga_running = vm.get("qga_running", False)
        qga_version = vm.get("qga_version")
        qga_error = vm.get("qga_error")
        
        # Handle QGA enabled status
        if qga_error:
            enabled_display = "Unknown"
            enabled_style = "yellow"
        else:
            enabled_display = "Yes" if qga_enabled else "No"
            enabled_style = "green" if qga_enabled else "red"
        
        # Handle QGA running status
        if qga_error or not qga_enabled:
            running_display = "N/A"
            running_style = "dim"
        else:
            running_display = "Yes" if qga_running else "No"
            running_style = "green" if qga_running else "red"
        
        # Handle QGA version
        if qga_error or not qga_enabled or not qga_running:
            version_display = "N/A"
            version_style = "dim"
        else:
            version_display = qga_version or "Unknown"
            version_style = "cyan"

        k3s_vms_table.add_row(
            str(vm.get("vmid", "N/A")),
            vm.get("name", "N/A"),
            vm.get("status", "N/A"),
            vm.get("k3s_tag", "N/A"),  # Added by get_vms_with_k3s_tags
            Text(enabled_display, style=enabled_style),
            Text(running_display, style=running_style),
            Text(version_display, style=version_style),
        )
    console.print(k3s_vms_table)


def _display_configured_nodes(
    config: K3sDeployCLIConfig, proxmox_client: Any, console: Console
) -> None:
    """
    Display information about explicitly configured K3s nodes.

    Args:
        config: The loaded application configuration.
        proxmox_client: An initialized ProxmoxAPI client.
        console: The Rich Console object for output.
    """
    configured_nodes = config.get("nodes", [])

    if not configured_nodes:
        return

    console.print(
        Text(
            f"\nConfigured K3s Nodes ({len(configured_nodes)} configured):",
            style="bold green",
        )
    )

    # Create table for configured nodes
    config_table = Table(show_header=True, header_style="bold blue")
    config_table.add_column("VMID", style="dim", width=8)
    config_table.add_column("Name", width=20)
    config_table.add_column("Role", width=12)
    config_table.add_column("Proxmox Node", width=15)
    config_table.add_column("Status", width=12)
    config_table.add_column("IP Address", width=15)

    # Get information for each configured node
    for node_config in configured_nodes:
        vmid = node_config.get("vmid")
        role = node_config.get("role", "N/A")

        if not vmid:
            logger.warning(f"Configured node missing VMID: {node_config}")
            continue

        # Find VM information across all Proxmox nodes
        vm_info = _get_vm_info_by_vmid(proxmox_client, vmid)

        if vm_info:
            config_table.add_row(
                str(vmid),
                vm_info.get("name", "N/A"),
                role,
                vm_info.get("node", "N/A"),
                vm_info.get("status", "N/A"),
                vm_info.get("ip", "N/A"),  # Will be N/A for now, can be enhanced later
            )
        else:
            # VM not found - show as configured but missing
            config_table.add_row(
                str(vmid),
                "VM Not Found",
                role,
                "N/A",
                "N/A",
                "N/A",
            )
            logger.warning(f"Configured VMID {vmid} not found in Proxmox cluster")

    console.print(config_table)
    console.print(
        Text(
            "Use 'k3s-deploy info --discover' to force tag-based discovery instead.",
            style="dim",
        )
    )


def _get_vm_info_by_vmid(
    proxmox_client: Any, vmid: int
) -> Optional[Dict[str, Any]]:
    """
    Get VM information by VMID by searching across all Proxmox nodes.

    Args:
        proxmox_client: An initialized ProxmoxAPI client.
        vmid: The VM ID to search for.

    Returns:
        Dictionary with VM information if found, None otherwise.
    """
    try:
        # Get cluster status to find all nodes
        cluster_status = get_cluster_status(proxmox_client)

        # Search each node for the VM
        for node in cluster_status:
            if node.get("type") != "node" or node.get("online") != 1:
                continue

            node_name = node.get("name")
            if not node_name:
                continue

            try:
                # Get VMs on this node
                vms_on_node = proxmox_client.nodes(node_name).qemu.get()

                # Look for our VMID
                for vm in vms_on_node:
                    if vm.get("vmid") == vmid:
                        # Found the VM, return enhanced info
                        return {
                            "vmid": vm.get("vmid"),
                            "name": vm.get("name"),
                            "status": vm.get("status"),
                            "node": node_name,
                            "ip": "N/A",  # Placeholder for future network discovery
                        }

            except Exception as e:
                logger.debug(
                    f"Error checking node '{node_name}' for VMID {vmid}: {e}"
                )
                continue

        return None

    except ProxmoxInteractionError:
        # Re-raise Proxmox API errors to allow callers to handle them
        raise
    except Exception as e:
        logger.error(f"Error searching for VMID {vmid}: {e}")
        return None


class InfoCommand:
    """Command class for displaying Proxmox cluster status and K3s VMs."""
    
    def __init__(self, config: K3sDeployCLIConfig, console: Console):
        """Initialize the InfoCommand with configuration and console.
        
        Args:
            config: The loaded application configuration
            console: Rich Console instance for output
        """
        self.config = config
        self.console = console
    
    def execute(self, discover: bool = False) -> None:
        """Execute the info command.
        
        Args:
            discover: Whether to force tag-based discovery mode
        """
        handle_info_command(self.config, self.console, discover)

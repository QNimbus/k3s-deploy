# file: src/k3s_deploy_cli/commands/info_command.py
"""
Info command implementation for displaying Proxmox cluster status.

This module handles the 'info' command which displays comprehensive 
information about the Proxmox cluster, nodes, and K3s VMs.
"""

from typing import Any, Dict, List, Optional

from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.text import Text

from ..config import K3sDeployCLIConfig
from ..exceptions import ConfigurationError, ProxmoxInteractionError
from ..logging_config import VERBOSE_LOG_LEVEL
from ..proxmox_client import (
    K3S_TAGS,
    get_cluster_status,
    get_node_dns_info,
    get_proxmox_api_client,
    get_proxmox_version_info,
    get_vms_with_k3s_tags,
)


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
        _display_cluster_overview(console, cluster_info, proxmox_version_info)

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
            _display_nodes_table(console, nodes_data, proxmox_client)
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
    proxmox_version_info: Dict[str, Any]
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

    cluster_overview_table.add_row("Name", cluster_name)
    cluster_overview_table.add_row("Proxmox VE Version", displayed_version)
    cluster_overview_table.add_row("Quorate", "Yes" if is_quorate else "No")
    console.print(cluster_overview_table)


def _display_nodes_table(
    console: Console, nodes_data: List[Dict[str, Any]], proxmox_client: Any
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

        nodes_table.add_row(
            node_name,
            domain,
            "Yes" if node.get("local") == 1 else "No",
            "Yes" if node.get("online") == 1 else "No",
            node.get("ip", "N/A"),
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


def _display_tag_based_k3s_vms(
    console: Console,
    proxmox_client: Any,
    nodes_data: List[Dict[str, Any]],
    discover: bool,
    configured_nodes: List[Dict[str, Any]],
) -> None:
    """Display K3s VMs discovered via tag-based discovery."""
    console.print(Text("\nK3s Tagged VMs per Proxmox Node:", style="bold green"))
    
    if discover and configured_nodes:
        console.print(
            Text(
                "(Using tag-based discovery - configured nodes ignored due to --discover flag)",
                style="dim",
            )
        )
    elif not configured_nodes:
        console.print(
            Text("(Using tag-based discovery - no nodes configured)", style="dim")
        )

    any_k3s_vms_found_overall = False
    online_node_names_for_vm_check = []

    for node in nodes_data:
        node_name = node.get("name")
        if not node_name:
            logger.warning(
                f"Node found without a name, skipping K3s VM check for it: {node}"
            )
            continue

        if node.get("online") != 1:
            logger.info(f"Node '{node_name}' is offline, skipping K3s VM check.")
            console.print(
                Text(
                    f"  Node '{node_name}': Offline, K3s VM check skipped.",
                    style="yellow",
                )
            )
            continue

        online_node_names_for_vm_check.append(node_name)
        console.print(Text(f"  Node: '{node_name}'", style="bold cyan"))
        
        try:
            tagged_vms = get_vms_with_k3s_tags(proxmox_client, node_name)
            if tagged_vms:
                any_k3s_vms_found_overall = True
                _display_k3s_vms_table(console, tagged_vms)
            else:
                console.print(
                    Text(
                        f"    No VMs found with exactly one of the K3s tags ({', '.join(K3S_TAGS)}).",
                        style="italic",
                    )
                )
        except ProxmoxInteractionError as e:
            logger.error(
                f"Could not retrieve K3s tagged VMs for node '{node_name}': {e}"
            )
            console.print(Text(f"    Error retrieving K3s VMs: {e}", style="red"))

    # Print summary messages
    if not any_k3s_vms_found_overall and online_node_names_for_vm_check:
        console.print(
            Text(
                f"  No VMs found with exactly one of the K3s tags ({', '.join(K3S_TAGS)}) on any checked online Proxmox node.",
                style="yellow",
            )
        )
    elif not online_node_names_for_vm_check and nodes_data:
        console.print(
            Text(
                "  All Proxmox nodes are offline. Cannot check for K3s VMs.",
                style="yellow",
            )
        )


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
            enabled_display = "✅ Yes" if qga_enabled else "❌ No"
            enabled_style = "green" if qga_enabled else "red"
        
        # Handle QGA running status
        if qga_error or not qga_enabled:
            running_display = "N/A"
            running_style = "dim"
        else:
            running_display = "✅ Yes" if qga_running else "❌ No"
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

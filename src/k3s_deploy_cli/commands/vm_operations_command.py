# file: src/k3s_deploy_cli/commands/vm_operations_command.py
"""Handles VM power operations for the K3s Deploy CLI.

This module provides the logic for 'start', 'stop', and 'restart'
commands, targeting specific K3s virtual machines or all discovered K3s VMs.
It interacts with the Proxmox API to perform these power state changes.
"""
from typing import Any

from loguru import logger
from rich.console import Console
from rich.table import Table

from ..config import K3sDeployCLIConfig
from ..exceptions import ProxmoxInteractionError
from ..proxmox_core import get_proxmox_api_client
from ..proxmox_vm_discovery import discover_k3s_nodes
from ..proxmox_vm_operations import (
    find_vm_node,
    get_vm_status,
    restart_vm,
    start_vm,
    stop_vm,
)

console = Console()


def handle_start_command(args: Any, config: K3sDeployCLIConfig) -> None:
    """
    Handle the 'start' command for VM power operations.
    
    Args:
        args: Parsed command-line arguments.
        config: The application configuration.
    """
    try:
        proxmox_client = get_proxmox_api_client(config["proxmox"])
        
        if hasattr(args, 'vmid') and args.vmid:
            # Start specific VM
            _start_single_vm(proxmox_client, args.vmid)
        else:
            # Start all K3s VMs
            _start_all_k3s_vms(proxmox_client, config)
            
    except ProxmoxInteractionError as e:
        logger.error(f"Proxmox API error: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in start command: {e}")
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise


def handle_stop_command(args: Any, config: K3sDeployCLIConfig) -> None:
    """
    Handle the 'stop' command for VM power operations.
    
    Args:
        args: Parsed command-line arguments.
        config: The application configuration.
    """
    try:
        proxmox_client = get_proxmox_api_client(config["proxmox"])
        force = getattr(args, 'force', False)
        
        if hasattr(args, 'vmid') and args.vmid:
            # Stop specific VM
            _stop_single_vm(proxmox_client, args.vmid, force)
        else:
            # Stop all K3s VMs
            _stop_all_k3s_vms(proxmox_client, config, force)
            
    except ProxmoxInteractionError as e:
        logger.error(f"Proxmox API error: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in stop command: {e}")
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise


def handle_restart_command(args: Any, config: K3sDeployCLIConfig) -> None:
    """
    Handle the 'restart' command for VM power operations.
    
    Args:
        args: Parsed command-line arguments.
        config: The application configuration.
    """
    try:
        proxmox_client = get_proxmox_api_client(config["proxmox"])
        
        if hasattr(args, 'vmid') and args.vmid:
            # Restart specific VM
            _restart_single_vm(proxmox_client, args.vmid)
        else:
            # Restart all K3s VMs
            _restart_all_k3s_vms(proxmox_client, config)
            
    except ProxmoxInteractionError as e:
        logger.error(f"Proxmox API error: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in restart command: {e}")
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise


def _start_single_vm(proxmox_client: Any, vmid: int) -> None:
    """
    Start a single VM by VMID.
    
    Args:
        proxmox_client: Initialized ProxmoxAPI client.
        vmid: The VM ID to start.
    """
    logger.debug(f"Starting single VM: {vmid}")
    
    # Find which node the VM is on
    node_name = find_vm_node(proxmox_client, vmid)
    if not node_name:
        console.print(f"[red]VM {vmid} not found on any accessible node[/red]")
        return
    
    # Check current status
    try:
        vm_status = get_vm_status(proxmox_client, node_name, vmid)
        current_status = vm_status.get("status", "unknown").lower()
        
        if current_status == "running":
            console.print(f"[yellow]VM {vmid} is already running[/yellow]")
            return
        
        # Start the VM
        start_vm(proxmox_client, node_name, vmid)
        console.print(f"[green]Successfully started VM {vmid}[/green]")
        
    except ProxmoxInteractionError as e:
        console.print(f"[red]Failed to start VM {vmid}: {e}[/red]")
        raise


def _stop_single_vm(proxmox_client: Any, vmid: int, force: bool = False) -> None:
    """
    Stop a single VM by VMID.
    
    Args:
        proxmox_client: Initialized ProxmoxAPI client.
        vmid: The VM ID to stop.
        force: Whether to force stop the VM.
    """
    logger.debug(f"Stopping single VM: {vmid} (force: {force})")
    
    # Find which node the VM is on
    node_name = find_vm_node(proxmox_client, vmid)
    if not node_name:
        console.print(f"[red]VM {vmid} not found on any accessible node[/red]")
        return
    
    # Check current status
    try:
        vm_status = get_vm_status(proxmox_client, node_name, vmid)
        current_status = vm_status.get("status", "unknown").lower()
        
        if current_status == "stopped":
            console.print(f"ℹ️  [yellow]VM {vmid} is already stopped[/yellow]")
            return
        
        # Stop the VM
        stop_vm(proxmox_client, node_name, vmid, force)
        action = "force stopped" if force else "shutdown initiated for"
        console.print(f"[green]Successfully {action} VM {vmid}[/green]")
        
    except ProxmoxInteractionError as e:
        console.print(f"[red]Failed to stop VM {vmid}: {e}[/red]")
        raise


def _restart_single_vm(proxmox_client: Any, vmid: int) -> None:
    """
    Restart a single VM by VMID.
    
    Args:
        proxmox_client: Initialized ProxmoxAPI client.
        vmid: The VM ID to restart.
    """
    logger.debug(f"Restarting single VM: {vmid}")
    
    # Find which node the VM is on
    node_name = find_vm_node(proxmox_client, vmid)
    if not node_name:
        console.print(f"[red]VM {vmid} not found on any accessible node[/red]")
        return
    
    # Check current status
    try:
        vm_status = get_vm_status(proxmox_client, node_name, vmid)
        current_status = vm_status.get("status", "unknown").lower()
        
        if current_status == "stopped":
            console.print(f"[red]Cannot restart VM {vmid}: VM is currently stopped[/red]")
            return
        
        # Restart the VM
        restart_vm(proxmox_client, node_name, vmid)
        console.print(f"[green]Successfully restarted VM {vmid}[/green]")
        
    except ProxmoxInteractionError as e:
        console.print(f"[red]Failed to restart VM {vmid}: {e}[/red]")
        raise


def _start_all_k3s_vms(proxmox_client: Any, config: K3sDeployCLIConfig) -> None:
    """
    Start all discovered K3s VMs.
    
    Args:
        proxmox_client: Initialized ProxmoxAPI client.
        config: The application configuration.
    """
    logger.debug("Starting all K3s VMs")
    console.print("[blue]Starting all K3s VMs...[/blue]")
    
    # Discover all K3s VMs
    k3s_vms = discover_k3s_nodes(proxmox_client)
    if not k3s_vms:
        console.print("[yellow]No K3s VMs found[/yellow]")
        return
    
    # Create results table
    table = Table(title="K3s VM Start Operations")
    table.add_column("VMID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Role", style="blue")
    table.add_column("Node", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Result", style="white")
    
    for vm in k3s_vms:
        vmid = vm["vmid"]
        name = vm["name"]
        role = vm["role"]
        node = vm["node"]
        current_status = vm["status"].lower()
        
        if current_status == "running":
            result = "Already running"
            result_style = "[yellow]Already running[/yellow]"
        else:
            try:
                start_vm(proxmox_client, node, vmid)
                result = "Started"
                result_style = "[green] Started[/green]"
            except ProxmoxInteractionError as e:
                result = f"Failed: {e}"
                result_style = f"[red] Failed[/red]"
        
        table.add_row(
            str(vmid),
            name,
            role,
            node,
            current_status,
            result_style
        )
    
    console.print(table)


def _stop_all_k3s_vms(proxmox_client: Any, config: K3sDeployCLIConfig, force: bool = False) -> None:
    """
    Stop all discovered K3s VMs.
    
    Args:
        proxmox_client: Initialized ProxmoxAPI client.
        config: The application configuration.
        force: Whether to force stop the VMs.
    """
    action = "force stopping" if force else "stopping"
    logger.debug(f"Bulk {action} all K3s VMs")
    console.print(f"[blue]{action.title()} all K3s VMs...[/blue]")
    
    # Discover all K3s VMs
    k3s_vms = discover_k3s_nodes(proxmox_client)
    if not k3s_vms:
        console.print("[yellow]No K3s VMs found[/yellow]")
        return
    
    # Create results table
    table = Table(title=f"K3s VM {'Force Stop' if force else 'Stop'} Operations")
    table.add_column("VMID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Role", style="blue")
    table.add_column("Node", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Result", style="white")
    
    for vm in k3s_vms:
        vmid = vm["vmid"]
        name = vm["name"]
        role = vm["role"]
        node = vm["node"]
        current_status = vm["status"].lower()
        
        if current_status == "stopped":
            result = "Already stopped"
            result_style = "[yellow]Already stopped[/yellow]"
        else:
            try:
                stop_vm(proxmox_client, node, vmid, force)
                result = "Force stopped" if force else "Shutdown initiated"
                result_style = f"[green]{result}[/green]"
            except ProxmoxInteractionError as e:
                result = f"Failed: {e}"
                result_style = f"[red]Failed[/red]"
        
        table.add_row(
            str(vmid),
            name,
            role,
            node,
            current_status,
            result_style
        )
    
    console.print(table)


def _restart_all_k3s_vms(proxmox_client: Any, config: K3sDeployCLIConfig) -> None:
    """
    Restart all discovered K3s VMs.
    
    Args:
        proxmox_client: Initialized ProxmoxAPI client.
        config: The application configuration.
    """
    logger.debug("Restarting all K3s VMs")
    console.print("[blue]Restarting all K3s VMs...[/blue]")
    
    # Discover all K3s VMs
    k3s_vms = discover_k3s_nodes(proxmox_client)
    if not k3s_vms:
        console.print("[yellow]No K3s VMs found[/yellow]")
        return
    
    # Create results table
    table = Table(title="K3s VM Restart Operations")
    table.add_column("VMID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Role", style="blue")
    table.add_column("Node", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Result", style="white")
    
    for vm in k3s_vms:
        vmid = vm["vmid"]
        name = vm["name"]
        role = vm["role"]
        node = vm["node"]
        current_status = vm["status"].lower()
        
        if current_status == "stopped":
            result_style = "[red]Cannot restart (stopped)[/red]"
        else:
            try:
                restart_vm(proxmox_client, node, vmid)
                result_style = "[green]Restarted[/green]"
            except ProxmoxInteractionError as e:
                result_style = f"[red]Failed[/red]"
        
        table.add_row(
            str(vmid),
            name,
            role,
            node,
            current_status,
            result_style
        )
    
    console.print(table)

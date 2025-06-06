# file: src/k3s_deploy_cli/commands/discover_command.py
"""Implements the 'discover' command for the K3s Deploy CLI.

This module provides functionality to find K3s-tagged Virtual Machines
within a Proxmox environment. It supports various output formats
and can update the application's configuration with the discovered nodes.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.text import Text

from ..config import K3sDeployCLIConfig
from ..constants import K3S_TAGS
from ..exceptions import ConfigurationError, ProxmoxInteractionError
from ..proxmox_core import get_proxmox_api_client
from ..proxmox_vm_discovery import discover_k3s_nodes


def handle_discover_command(
    config: K3sDeployCLIConfig,
    console: Console,
    output_format: str = "table",
    output_target: str = "stdout",
) -> None:
    """
    Handles the 'discover' command to find K3s-tagged VMs and output configuration information.

    Args:
        config: The loaded application configuration.
        console: The Rich Console object for output.
        output_format: Output format - 'table' (default) or 'json'.
        output_target: Output target - 'stdout' (default) or 'file'.
    """
    logger.info("Discovering K3s-tagged VMs across Proxmox cluster...")

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

        # Discover K3s nodes
        discovered_nodes = discover_k3s_nodes(proxmox_client)

        if not discovered_nodes:
            console.print(
                Text(
                    "\nNo K3s-tagged VMs found in the Proxmox cluster.",
                    style="yellow",
                )
            )
            console.print(
                Text(f"Expected tags: {', '.join(K3S_TAGS)}", style="dim")
            )
            logger.info("No K3s VMs discovered")
            return

        # Handle different output formats and targets
        if output_format == "json":
            _handle_json_output(discovered_nodes, console, output_target)
        else:  # table format
            _handle_table_output(discovered_nodes, console, output_target)

    except ProxmoxInteractionError as e:
        logger.error(f"Proxmox API interaction failed: {e}")
        raise  # Re-raise to be caught by main()
    except ConfigurationError as e:
        logger.error(f"Configuration error for Proxmox connection: {e}")
        raise  # Re-raise to be caught by main()


def _handle_json_output(
    discovered_nodes: List[Dict[str, Any]], console: Console, output_target: str
) -> None:
    """Handle JSON format output for discovered nodes."""
    # Prepare JSON output with only the required fields for config.json
    config_nodes = []
    for node in discovered_nodes:
        config_node = {"vmid": node["vmid"], "role": node["role"]}
        config_nodes.append(config_node)

    json_output = json.dumps(config_nodes, indent=2)

    if output_target == "file":
        _update_config_file_with_nodes(config_nodes, console)
    else:
        console.print(
            Text(
                "\nDiscovered K3s Nodes Configuration (JSON):",
                style="bold green",
            )
        )
        console.print(json_output)
        console.print(
            Text(
                f"\nFound {len(config_nodes)} K3s nodes ready for configuration.",
                style="dim",
            )
        )
        console.print(
            Text(
                "Copy the JSON above to the 'nodes' array in your config.json file.",
                style="dim",
            )
        )


def _handle_table_output(
    discovered_nodes: List[Dict[str, Any]], console: Console, output_target: str
) -> None:
    """Handle table format output for discovered nodes."""
    if output_target == "file":
        logger.error("File output is only supported with --format=json")
        raise ConfigurationError(
            "File output requires JSON format. Use --format=json --output=file"
        )

    # Display table format
    console.print(
        Text(
            f"\nDiscovered K3s Nodes ({len(discovered_nodes)} found):",
            style="bold green",
        )
    )

    discover_table = Table(show_header=True, header_style="bold blue")
    discover_table.add_column("VMID", width=8)
    discover_table.add_column("Name", width=20)
    discover_table.add_column("Role", width=12)
    discover_table.add_column("Proxmox Node", width=15)
    discover_table.add_column("Status", width=12)
    discover_table.add_column("QGA Enabled", width=12)
    discover_table.add_column("QGA Running", width=12)

    for node in discovered_nodes:
        # Format QGA status for display
        qga_enabled = node.get("qga_enabled", False)
        qga_running = node.get("qga_running", False)

        status = node.get("status", "Unknown")
        if status == "running":
            status_display = Text("Running", style="green")
        elif status == "stopped":
            status_display = Text("Stopped", style="red")
        else:
            status_display = Text(status.capitalize(), style="yellow")
        
        enabled_display = Text("Yes", style="green") if qga_enabled else Text("No", style="red")
        if qga_enabled:
            running_display = Text("Yes", style="green") if qga_running else Text("No", style="red")
        else:
            running_display = Text("N/A", style="dim")
        
        discover_table.add_row(
            str(node["vmid"]),
            node["name"],
            node["role"],
            node["node"],
            status_display,
            enabled_display,
            running_display,
        )

    console.print(discover_table)
    console.print(
        Text(
            "Use 'k3s-deploy discover --format=json' to see the configuration JSON.",
            style="dim",
        )
    )
    console.print(
        Text(
            "Use 'k3s-deploy discover --format=json --output=file' to update config.json automatically.",
            style="dim",
        )
    )


def _update_config_file_with_nodes(
    discovered_nodes: List[Dict[str, Any]], console: Console
) -> None:
    """
    Updates the config.json file with discovered nodes, preserving existing configuration.

    Args:
        discovered_nodes: List of node configurations to add to config.json.
        console: Rich console for user feedback.
    """
    config_path = Path("config.json")

    try:
        # Read existing config
        if config_path.exists():
            with open(config_path, "r") as f:
                existing_config = json.load(f)

            # Create backup by writing JSON
            backup_path = config_path.with_suffix(".json.backup")
            with open(backup_path, "w") as f:
                json.dump(existing_config, f, indent=2)
            logger.info(f"Created backup: {backup_path}")
            console.print(Text(f"✓ Created backup: {backup_path}", style="dim"))
        else:
            logger.warning("config.json does not exist, creating new file")
            existing_config = {}

        # Update nodes array
        existing_config["nodes"] = discovered_nodes

        # Write updated config
        with open(config_path, "w") as f:
            json.dump(existing_config, f, indent=2)

        console.print(
            Text(
                f"✓ Updated {config_path} with {len(discovered_nodes)} discovered nodes",
                style="bold green",
            )
        )
        logger.info(f"Successfully updated {config_path} with {len(discovered_nodes)} nodes")

    except Exception as e:
        err_msg = f"Failed to update config.json: {e}"
        logger.error(err_msg)
        raise ConfigurationError(err_msg) from e


class DiscoverCommand:
    """Command class for discovering K3s-tagged VMs."""
    
    def __init__(self, config: K3sDeployCLIConfig, console: Console):
        """Initialize the DiscoverCommand with configuration and console.
        
        Args:
            config: The loaded application configuration
            console: Rich Console instance for output
        """
        self.config = config
        self.console = console
    
    def execute(self, output_format: str = "table", output_target: str = "stdout") -> None:
        """Execute the discover command.
        
        Args:
            output_format: Output format (table or json)
            output_target: Output target (stdout or file)
        """
        handle_discover_command(self.config, self.console, output_format, output_target)

# file: src/k3s_deploy_cli/cli_parser.py
"""Handles command-line argument parsing for the K3s Deploy CLI.

This module defines the structure of the CLI, including global options
and subcommands, using the `argparse` library. It provides functions
to create, configure, and execute the argument parsing process.
"""

import argparse
import sys
from pathlib import Path

from . import __version__


def create_parser() -> argparse.ArgumentParser:
    """
    Create and configure the main argument parser with all subcommands.

    Returns:
        Configured ArgumentParser instance.
    """
    # Create a parent parser with common flags shared across subcommands
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output.",
    )
    common_parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable debug logging (DEBUG level with detailed tracebacks).",
    )
    common_parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config.json"),
        help="Path to the configuration file (default: config.json).",
    )

    # Main parser - DO NOT include common_parser to avoid conflicts
    parser = argparse.ArgumentParser(
        description="A CLI tool to deploy and manage K3s clusters on Proxmox VE.",
        prog="k3s-deploy",
    )

    # Add only global-specific arguments to main parser
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program's version number and exit.",
    )

    # Add subcommands
    _add_subcommands(parser, common_parser)

    return parser


def create_global_parser() -> argparse.ArgumentParser:
    """
    Create a parser for global flags only (used in two-phase parsing).
    
    Returns:
        ArgumentParser configured with global flags.
    """
    global_parser = argparse.ArgumentParser(add_help=False)
    global_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output.",
    )
    global_parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable debug logging (DEBUG level with detailed tracebacks).",
    )
    global_parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config.json"),
        help="Path to the configuration file (default: config.json).",
    )
    global_parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program's version number and exit.",
    )
    return global_parser


def _add_subcommands(
    parser: argparse.ArgumentParser, common_parser: argparse.ArgumentParser
) -> None:
    """
    Add all subcommands to the main parser.

    Args:
        parser: The main ArgumentParser instance.
        common_parser: The common parser with shared flags.
    """
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Info command
    info_parser = subparsers.add_parser(
        "info",
        help="Display Proxmox cluster status and information.",
        parents=[common_parser],
    )
    info_parser.add_argument(
        "--discover",
        action="store_true",
        help="Force tag-based discovery instead of using configured nodes",
    )

    # Discover command
    discover_parser = subparsers.add_parser(
        "discover",
        help="Discover K3s-tagged VMs and generate configuration.",
        parents=[common_parser],
    )
    discover_parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format: table (default) or json",
    )
    discover_parser.add_argument(
        "--output",
        choices=["stdout", "file"],
        default="stdout",
        help="Output target: stdout (default) or file (updates config.json)",
    )

    # Start command
    start_parser = subparsers.add_parser(
        "start",
        help="Start VM(s). Specify VMID for individual VM or omit for all K3s VMs.",
        parents=[common_parser],
    )
    start_parser.add_argument(
        "vmid",
        type=int,
        nargs="?",
        help="VM ID to start (optional - if omitted, starts all K3s VMs)",
    )

    # Stop command
    stop_parser = subparsers.add_parser(
        "stop",
        help="Stop VM(s). Specify VMID for individual VM or omit for all K3s VMs.",
        parents=[common_parser],
    )
    stop_parser.add_argument(
        "vmid",
        type=int,
        nargs="?",
        help="VM ID to stop (optional - if omitted, stops all K3s VMs)",
    )
    stop_parser.add_argument(
        "--force",
        action="store_true",
        help="Force stop the VM instead of graceful shutdown",
    )

    # Restart command
    restart_parser = subparsers.add_parser(
        "restart",
        help="Restart VM(s). Specify VMID for individual VM or omit for all K3s VMs.",
        parents=[common_parser],
    )
    restart_parser.add_argument(
        "vmid",
        type=int,
        nargs="?",
        help="VM ID to restart (optional - if omitted, restarts all K3s VMs)",
    )

    # Provision command
    provision_parser = subparsers.add_parser(
        "provision",
        help="Provision VMs with cloud-init configuration using config.json settings.",
        parents=[common_parser],
    )
    provision_parser.add_argument(
        "--vmid",
        type=str,
        help="VM ID(s) to provision (comma-separated). If omitted, all VMs from config.json will be provisioned.",
    )

    # Future commands can be added here following the same pattern
    # ssh_parser = subparsers.add_parser(
    #     "ssh-test",
    #     help="Test SSH connectivity to Proxmox nodes.",
    #     parents=[common_parser],
    # )


def parse_args(args=None) -> argparse.Namespace:
    """
    Parse command-line arguments using two-phase parsing for flexible flag placement.
    
    This enables flags to work both before and after subcommands:
    - k3s-deploy -v info (flags before subcommand)
    - k3s-deploy info -v (flags after subcommand)

    Args:
        args: Optional list of arguments to parse (defaults to sys.argv).

    Returns:
        Parsed arguments namespace with properly merged global and subcommand flags.
    """
    # Custom handling for "no arguments at all"
    if args is None and len(sys.argv) == 1:
        from loguru import logger
        logger.warning("No command provided.")
        parser = create_parser()
        parser.print_help(sys.stdout)
        sys.exit(1)

    # Two-phase parsing for flexible flag placement
    # Phase 1: Parse global args and extract them from the argument list
    global_parser = create_global_parser()
    global_args, remaining_args = global_parser.parse_known_args(args)
    
    # Phase 2: Parse the remaining args with the command parser
    command_parser = create_parser()
    command_args = command_parser.parse_args(remaining_args)
    
    # Merge results: prioritize global args for common flags
    final_namespace = argparse.Namespace()
    final_namespace.__dict__.update(command_args.__dict__)
    
    # Override with global values for common flags if they were explicitly set
    for attr in ['verbose', 'debug', 'config']:
        global_value = getattr(global_args, attr, None)
        default_value = None
        
        # Determine if global value was explicitly set (not default)
        if attr == 'verbose' or attr == 'debug':
            default_value = False
        elif attr == 'config':
            default_value = Path("config.json")
        
        # If global value differs from default, use it
        if global_value != default_value:
            final_namespace.__dict__[attr] = global_value

    return final_namespace
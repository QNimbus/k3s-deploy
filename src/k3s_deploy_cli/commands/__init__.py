# file: src/k3s_deploy_cli/commands/__init__.py
"""
Command handlers for the K3s Deploy CLI.

This package contains individual command implementations following the
Command Pattern for clean separation of concerns.
"""

from .discover_command import DiscoverCommand, handle_discover_command
from .info_command import InfoCommand, handle_info_command
from .provision_command import handle_provision_command
from .vm_operations_command import (
    handle_restart_command,
    handle_start_command,
    handle_stop_command,
)

__all__ = [
    "DiscoverCommand",
    "InfoCommand",
    "handle_discover_command",
    "handle_info_command",
    "handle_provision_command",
    "handle_restart_command",
    "handle_start_command",
    "handle_stop_command",
]

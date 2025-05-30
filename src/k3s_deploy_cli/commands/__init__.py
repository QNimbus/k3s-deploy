# file: src/k3s_deploy_cli/commands/__init__.py
"""
Command handlers for the K3s Deploy CLI.

This package contains individual command implementations following the
Command Pattern for clean separation of concerns.
"""

from .discover_command import handle_discover_command
from .info_command import handle_info_command

__all__ = [
    "handle_discover_command",
    "handle_info_command",
]

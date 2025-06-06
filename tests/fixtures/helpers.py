"""Test helper utilities and shared functions."""

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock
from rich.console import Console


def create_temp_json_file(tmp_path: Path, filename: str, content: Dict[str, Any]) -> Path:
    """Creates a temporary JSON file with the given content."""
    file_path = tmp_path / filename
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(content, f)
    return file_path


def create_mock_console() -> MagicMock:
    """Creates a properly mocked Console instance."""
    return MagicMock(spec=Console)


def create_mock_proxmox_client() -> MagicMock:
    """Creates a mocked Proxmox API client with common methods."""
    mock_client = MagicMock()
    # Setup common method chains
    mock_client.nodes.return_value.qemu.return_value.status.return_value = {}
    mock_client.cluster.status.get.return_value = []
    mock_client.version.get.return_value = {'version': '7.4', 'release': '1'}
    return mock_client


class LogCapture:
    """Helper class for capturing log messages in tests."""
    
    def __init__(self):
        self.logs = []

    def write(self, message):
        self.logs.append(message)

    def flush(self):
        pass
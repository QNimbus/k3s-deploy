"""Common test helper functions and utilities."""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock


def create_mock_vm_response(vmid: int, name: str, status: str = 'running', node: str = 'test-node', **kwargs) -> Dict[str, Any]:
    """Create a mock VM response with default values and optional overrides."""
    vm_data = {
        'vmid': vmid,
        'name': name,
        'status': status,
        'node': node,
        'uptime': 3600,
        'maxmem': 2147483648,
        'maxdisk': 34359738368,
        'cpu': 0.01
    }
    vm_data.update(kwargs)
    return vm_data


def create_mock_proxmox_api_client() -> MagicMock:
    """Create a properly configured mock Proxmox API client."""
    mock_client = MagicMock()
    
    # Set up common method chains
    mock_client.version.get.return_value = {'version': '7.4', 'release': '1'}
    mock_client.cluster.status.get.return_value = [
        {'type': 'cluster', 'name': 'test-cluster', 'quorate': 1}
    ]
    
    return mock_client


def create_temp_config_file(config_data: Dict[str, Any], suffix: str = '.json') -> Path:
    """Create a temporary configuration file with the given data."""
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
        json.dump(config_data, f, indent=2)
        return Path(f.name)


def setup_mock_vm_operations(mock_client: MagicMock, node: str = 'test-node', vmid: int = 100) -> None:
    """Set up mock responses for VM operations (start, stop, restart)."""
    # Mock VM start operation
    mock_client.nodes.return_value.qemu.return_value.status.start.post.return_value = {
        'data': f'UPID:{node}:00001234:00000001:start:{vmid}:user@pve:'
    }
    
    # Mock VM stop operations
    mock_client.nodes.return_value.qemu.return_value.status.stop.post.return_value = {
        'data': f'UPID:{node}:00001234:00000001:stop:{vmid}:user@pve:'
    }
    mock_client.nodes.return_value.qemu.return_value.status.shutdown.post.return_value = {
        'data': f'UPID:{node}:00001234:00000001:shutdown:{vmid}:user@pve:'
    }
    
    # Mock VM restart operation
    mock_client.nodes.return_value.qemu.return_value.status.reboot.post.return_value = {
        'data': f'UPID:{node}:00001234:00000001:reboot:{vmid}:user@pve:'
    }


def create_resource_exception_mock(status_code: int = 400, content: str = 'Bad Request', reason: str = 'Error'):
    """Create a ResourceException mock with the given parameters."""
    from proxmoxer.core import ResourceException
    return ResourceException(status_code, reason, content)


def assert_proxmox_api_call(mock_client: MagicMock, node: str, vmid: int, operation: str = None) -> None:
    """Assert that the proxmox API was called correctly for VM operations."""
    mock_client.nodes.assert_called_with(node)
    mock_client.nodes.return_value.qemu.assert_called_with(vmid)
    
    if operation:
        operation_mock = getattr(mock_client.nodes.return_value.qemu.return_value.status, operation)
        operation_mock.post.assert_called_once()


def create_sample_k3s_vms(count: int = 3) -> list:
    """Create a list of sample K3s VMs for testing."""
    vms = []
    roles = ['k3s-server', 'k3s-agent', 'k3s-storage']
    
    for i in range(count):
        vm = {
            'vmid': 100 + i,
            'name': f'k3s-{roles[i % len(roles)]}-{i + 1}',
            'status': 'running',
            'node': f'node{(i % 3) + 1}',
            'k3s_tag': roles[i % len(roles)],
            'role': roles[i % len(roles)].replace('k3s-', ''),
            'qga_enabled': True,
            'qga_running': i % 2 == 0,  # Alternate between running/not running
            'qga_version': '5.2.0' if i % 2 == 0 else 'N/A'
        }
        vms.append(vm)
    
    return vms
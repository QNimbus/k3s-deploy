"""Shared pytest fixtures for the test suite."""

from unittest.mock import MagicMock

import pytest
from loguru import logger
from rich.console import Console


class LogCapture:
    """Helper class for capturing log messages in tests."""
    
    def __init__(self):
        self.logs = []

    def write(self, message):
        self.logs.append(message)

    def flush(self):
        pass


@pytest.fixture
def capture_logs():
    """Fixture for capturing log messages during tests."""
    log_capture = LogCapture()
    logger.add(log_capture, format="{message}", level="DEBUG")
    return log_capture


@pytest.fixture
def basic_proxmox_config():
    """Provides a basic valid Proxmox configuration."""
    return {
        'proxmox': {
            'host': 'pve.example.com',
            'user': 'root@pam',
            'password': 'testpass'
        }
    }


@pytest.fixture
def full_config():
    """Provides a complete configuration with nodes."""
    return {
        'proxmox': {
            'host': 'pve.example.com',
            'user': 'root@pam',
            'password': 'testpass'
        },
        'nodes': [
            {'vmid': 100, 'role': 'server'},
            {'vmid': 101, 'role': 'agent'}
        ]
    }


@pytest.fixture
def mock_console():
    """Provides a mocked Rich Console instance."""
    return MagicMock(spec=Console)


@pytest.fixture
def mock_proxmox_client():
    """Provides a mocked Proxmox API client."""
    return MagicMock()


@pytest.fixture
def sample_cluster_status():
    """Provides sample cluster status data."""
    return [
        {'type': 'cluster', 'name': 'test-cluster', 'quorate': 1},
        {'type': 'node', 'name': 'node1', 'online': 1, 'local': 1},
        {'type': 'node', 'name': 'node2', 'online': 1, 'local': 0}
    ]


@pytest.fixture
def sample_version_info():
    """Provides sample Proxmox version information."""
    return {'version': '7.4', 'release': '1'}


@pytest.fixture
def sample_vm_list():
    """Provides a sample list of VMs with K3s tags."""
    return [
        {
            'vmid': 100, 'name': 'k3s-server-1', 'status': 'running', 
            'node': 'node1', 'k3s_tag': 'k3s-server', 'role': 'server',
            'qga_enabled': True, 'qga_running': True, 'qga_version': '5.2.0'
        },
        {
            'vmid': 101, 'name': 'k3s-agent-1', 'status': 'running',
            'node': 'node2', 'k3s_tag': 'k3s-agent', 'role': 'agent', 
            'qga_enabled': True, 'qga_running': False, 'qga_version': 'N/A'
        }
    ]


@pytest.fixture
def proxmox_config_with_ssl():
    """Provides a Proxmox configuration with SSL verification disabled."""
    return {
        'host': 'proxmox.example.com',
        'user': 'testuser',
        'password': 'testpass',
        'verify_ssl': False
    }


@pytest.fixture
def proxmox_config_with_tokens():
    """Provides a Proxmox configuration using API tokens."""
    return {
        'host': 'proxmox.example.com',
        'user': 'testuser',
        'api_token_id': 'testuser@pam!mytoken',
        'api_token_secret': 'secret-token-value'
    }


@pytest.fixture
def sample_dns_info():
    """Provides sample DNS information."""
    return {
        'search': 'example.com',
        'dns1': '8.8.8.8',
        'dns2': '8.8.4.4'
    }


@pytest.fixture
def sample_vm_status():
    """Provides sample VM status data."""
    return {
        'status': 'running',
        'name': 'test-vm',
        'vmid': 100,
        'node': 'test-node',
        'uptime': 3600
    }


@pytest.fixture
def sample_node_list():
    """Provides a sample list of cluster nodes."""
    return [
        {'node': 'node1', 'status': 'online', 'local': 1},
        {'node': 'node2', 'status': 'online', 'local': 0},
        {'node': 'node3', 'status': 'offline', 'local': 0}
    ]
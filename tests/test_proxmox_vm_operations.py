"""
Unit tests for VM power operations and location discovery functionality in proxmox_client.py.

This module contains tests for:
- VM power operations (start, stop, restart)
- VM location discovery (find_vm_node)

Extracted from test_proxmox_client.py as part of code organization improvement to follow
the 500-line guideline and Single Responsibility Principle.
"""

from unittest.mock import MagicMock

import pytest
from proxmoxer.core import ResourceException

from k3s_deploy_cli.exceptions import ProxmoxInteractionError
from k3s_deploy_cli.proxmox_vm_operations import (
    find_vm_node,
    restart_vm,
    start_vm,
    stop_vm,
)


class TestStartVm:
    """Test cases for start_vm function."""
    
    def test_start_vm_success(self):
        """Test successful VM start."""
        # Arrange
        mock_client = MagicMock()
        expected_result = {"data": "UPID:test-node:00001234:00000001:start:100:user@pve:"}
        mock_client.nodes.return_value.qemu.return_value.status.start.post.return_value = expected_result
        
        # Act
        result = start_vm(mock_client, "test-node", 100)
        
        # Assert
        assert result == expected_result
        mock_client.nodes.assert_called_once_with("test-node")
        mock_client.nodes.return_value.qemu.assert_called_once_with(100)
        mock_client.nodes.return_value.qemu.return_value.status.start.post.assert_called_once()
    
    def test_start_vm_resource_exception(self):
        """Test start_vm with ResourceException."""
        # Arrange
        mock_client = MagicMock()
        mock_client.nodes.return_value.qemu.return_value.status.start.post.side_effect = ResourceException(
            400, "Bad Request", "VM already running"
        )
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError) as exc_info:
            start_vm(mock_client, "test-node", 100)
        
        assert "Error starting VM 100: 400 - VM already running" in str(exc_info.value)
    
    def test_start_vm_generic_exception(self):
        """Test start_vm with generic exception."""
        # Arrange
        mock_client = MagicMock()
        mock_client.nodes.return_value.qemu.return_value.status.start.post.side_effect = Exception("Network timeout")
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError) as exc_info:
            start_vm(mock_client, "test-node", 100)
        
        assert "Error starting VM 100: Network timeout" in str(exc_info.value)


class TestStopVm:
    """Test cases for stop_vm function."""
    
    def test_stop_vm_graceful_success(self):
        """Test successful graceful VM shutdown."""
        # Arrange
        mock_client = MagicMock()
        expected_result = {"data": "UPID:test-node:00001234:00000001:shutdown:100:user@pve:"}
        mock_client.nodes.return_value.qemu.return_value.status.shutdown.post.return_value = expected_result
        
        # Act
        result = stop_vm(mock_client, "test-node", 100, force=False)
        
        # Assert
        assert result == expected_result
        mock_client.nodes.assert_called_once_with("test-node")
        mock_client.nodes.return_value.qemu.assert_called_once_with(100)
        mock_client.nodes.return_value.qemu.return_value.status.shutdown.post.assert_called_once()
        # Ensure stop was not called
        mock_client.nodes.return_value.qemu.return_value.status.stop.post.assert_not_called()
    
    def test_stop_vm_force_success(self):
        """Test successful force VM stop."""
        # Arrange
        mock_client = MagicMock()
        expected_result = {"data": "UPID:test-node:00001234:00000001:stop:100:user@pve:"}
        mock_client.nodes.return_value.qemu.return_value.status.stop.post.return_value = expected_result
        
        # Act
        result = stop_vm(mock_client, "test-node", 100, force=True)
        
        # Assert
        assert result == expected_result
        mock_client.nodes.assert_called_once_with("test-node")
        mock_client.nodes.return_value.qemu.assert_called_once_with(100)
        mock_client.nodes.return_value.qemu.return_value.status.stop.post.assert_called_once()
        # Ensure shutdown was not called
        mock_client.nodes.return_value.qemu.return_value.status.shutdown.post.assert_not_called()
    
    def test_stop_vm_graceful_resource_exception(self):
        """Test stop_vm graceful with ResourceException."""
        # Arrange
        mock_client = MagicMock()
        mock_client.nodes.return_value.qemu.return_value.status.shutdown.post.side_effect = ResourceException(
            400, "Bad Request", "VM already stopped"
        )
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError) as exc_info:
            stop_vm(mock_client, "test-node", 100, force=False)
        
        assert "Error shutting down VM 100: 400 - VM already stopped" in str(exc_info.value)
    
    def test_stop_vm_force_resource_exception(self):
        """Test stop_vm force with ResourceException."""
        # Arrange
        mock_client = MagicMock()
        mock_client.nodes.return_value.qemu.return_value.status.stop.post.side_effect = ResourceException(
            400, "Bad Request", "VM already stopped"
        )
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError) as exc_info:
            stop_vm(mock_client, "test-node", 100, force=True)
        
        assert "Error force stopping VM 100: 400 - VM already stopped" in str(exc_info.value)
    
    def test_stop_vm_generic_exception(self):
        """Test stop_vm with generic exception."""
        # Arrange
        mock_client = MagicMock()
        mock_client.nodes.return_value.qemu.return_value.status.shutdown.post.side_effect = Exception("Connection lost")
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError) as exc_info:
            stop_vm(mock_client, "test-node", 100, force=False)
        
        assert "Error shutting down VM 100: Connection lost" in str(exc_info.value)


class TestRestartVm:
    """Test cases for restart_vm function."""
    
    def test_restart_vm_success(self):
        """Test successful VM restart."""
        # Arrange
        mock_client = MagicMock()
        expected_result = {"data": "UPID:test-node:00001234:00000001:reboot:100:user@pve:"}
        mock_client.nodes.return_value.qemu.return_value.status.reboot.post.return_value = expected_result
        
        # Act
        result = restart_vm(mock_client, "test-node", 100)
        
        # Assert
        assert result == expected_result
        mock_client.nodes.assert_called_once_with("test-node")
        mock_client.nodes.return_value.qemu.assert_called_once_with(100)
        mock_client.nodes.return_value.qemu.return_value.status.reboot.post.assert_called_once()
    
    def test_restart_vm_resource_exception(self):
        """Test restart_vm with ResourceException."""
        # Arrange
        mock_client = MagicMock()
        mock_client.nodes.return_value.qemu.return_value.status.reboot.post.side_effect = ResourceException(
            400, "Bad Request", "VM not running"
        )
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError) as exc_info:
            restart_vm(mock_client, "test-node", 100)
        
        assert "Error restarting VM 100: 400 - VM not running" in str(exc_info.value)
    
    def test_restart_vm_generic_exception(self):
        """Test restart_vm with generic exception."""
        # Arrange
        mock_client = MagicMock()
        mock_client.nodes.return_value.qemu.return_value.status.reboot.post.side_effect = Exception("Hardware error")
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError) as exc_info:
            restart_vm(mock_client, "test-node", 100)
        
        assert "Error restarting VM 100: Hardware error" in str(exc_info.value)


class TestFindVmNode:
    """Test cases for find_vm_node function."""
    
    def test_find_vm_node_success_first_node(self):
        """Test successful VM discovery on first node."""
        # Arrange
        mock_client = MagicMock()
        mock_client.nodes.get.return_value = [
            {"node": "node1", "status": "online"},
            {"node": "node2", "status": "online"}
        ]
        mock_client.nodes.return_value.qemu.get.return_value = [
            {"vmid": 100, "name": "test-vm"},
            {"vmid": 101, "name": "other-vm"}
        ]
        
        # Act
        result = find_vm_node(mock_client, 100)
        
        # Assert
        assert result == "node1"
        mock_client.nodes.get.assert_called_once()
        mock_client.nodes.assert_called_once_with("node1")
        mock_client.nodes.return_value.qemu.get.assert_called_once()
    
    def test_find_vm_node_success_second_node(self):
        """Test successful VM discovery on second node."""
        # Arrange
        mock_client = MagicMock()
        mock_client.nodes.get.return_value = [
            {"node": "node1", "status": "online"},
            {"node": "node2", "status": "online"}
        ]
        
        # First node doesn't have the VM, second node does
        node1_mock = MagicMock()
        node1_mock.qemu.get.return_value = [{"vmid": 101, "name": "other-vm"}]
        
        node2_mock = MagicMock()
        node2_mock.qemu.get.return_value = [{"vmid": 100, "name": "test-vm"}]
        
        mock_client.nodes.side_effect = lambda node: node1_mock if node == "node1" else node2_mock
        
        # Act
        result = find_vm_node(mock_client, 100)
        
        # Assert
        assert result == "node2"
        mock_client.nodes.get.assert_called_once()
        assert mock_client.nodes.call_count == 2
        mock_client.nodes.assert_any_call("node1")
        mock_client.nodes.assert_any_call("node2")
    
    def test_find_vm_node_not_found(self):
        """Test VM not found on any node."""
        # Arrange
        mock_client = MagicMock()
        mock_client.nodes.get.return_value = [
            {"node": "node1", "status": "online"},
            {"node": "node2", "status": "online"}
        ]
        mock_client.nodes.return_value.qemu.get.return_value = [
            {"vmid": 101, "name": "other-vm"},
            {"vmid": 102, "name": "another-vm"}
        ]
        
        # Act
        result = find_vm_node(mock_client, 100)
        
        # Assert
        assert result is None
        mock_client.nodes.get.assert_called_once()
        assert mock_client.nodes.call_count == 2  # Called for both nodes
    
    def test_find_vm_node_skip_inaccessible_node(self):
        """Test skipping inaccessible nodes and finding VM on accessible node."""
        # Arrange
        mock_client = MagicMock()
        mock_client.nodes.get.return_value = [
            {"node": "node1", "status": "offline"},
            {"node": "node2", "status": "online"}
        ]
        
        # First node raises ResourceException, second node has the VM
        node1_mock = MagicMock()
        node1_mock.qemu.get.side_effect = ResourceException(503, "Service Unavailable", "Node offline")
        
        node2_mock = MagicMock()
        node2_mock.qemu.get.return_value = [{"vmid": 100, "name": "test-vm"}]
        
        mock_client.nodes.side_effect = lambda node: node1_mock if node == "node1" else node2_mock
        
        # Act
        result = find_vm_node(mock_client, 100)
        
        # Assert
        assert result == "node2"
        mock_client.nodes.get.assert_called_once()
        assert mock_client.nodes.call_count == 2
    
    def test_find_vm_node_no_node_name(self):
        """Test handling nodes without name field."""
        # Arrange
        mock_client = MagicMock()
        mock_client.nodes.get.return_value = [
            {"status": "online"},  # Missing 'node' field
            {"node": "node2", "status": "online"}
        ]
        mock_client.nodes.return_value.qemu.get.return_value = [
            {"vmid": 100, "name": "test-vm"}
        ]
        
        # Act
        result = find_vm_node(mock_client, 100)
        
        # Assert
        assert result == "node2"
        mock_client.nodes.get.assert_called_once()
        # Should only call nodes() for node2, not the node without name
        mock_client.nodes.assert_called_once_with("node2")
    
    def test_find_vm_node_cluster_error(self):
        """Test find_vm_node with cluster ResourceException."""
        # Arrange
        mock_client = MagicMock()
        mock_client.nodes.get.side_effect = ResourceException(500, "Internal Error", "Cluster unreachable")
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError) as exc_info:
            find_vm_node(mock_client, 100)
        
        assert "Error searching for VM 100: 500 - Cluster unreachable" in str(exc_info.value)
    
    def test_find_vm_node_generic_exception(self):
        """Test find_vm_node with generic exception."""
        # Arrange
        mock_client = MagicMock()
        mock_client.nodes.get.side_effect = Exception("Network failure")
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError) as exc_info:
            find_vm_node(mock_client, 100)
        
        assert "Error searching for VM 100: Network failure" in str(exc_info.value)

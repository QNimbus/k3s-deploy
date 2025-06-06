"""
Unit tests for proxmox_client VM discovery functionality.

This module provides comprehensive test coverage for VM discovery, tagging, 
QGA status, and K3s node discovery functions.
"""

from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from proxmoxer import ResourceException

from k3s_deploy_cli.exceptions import ProxmoxInteractionError
from k3s_deploy_cli.proxmox_core import get_proxmox_api_client
from k3s_deploy_cli.proxmox_vm_discovery import (
    discover_k3s_nodes,
    get_cluster_status,
    get_vms_with_k3s_tags,
)
from k3s_deploy_cli.proxmox_vm_operations import get_vm_status


class TestGetVmsWithK3sTags:
    """Test cases for get_vms_with_k3s_tags function."""
    
    def test_get_vms_with_k3s_tags_success(self, mock_proxmox_client):
        """Test successful VM retrieval with K3s tags."""
        # Arrange
        node_name = "proxmox-node1"
        mock_vms = [
            {"vmid": 100, "name": "master-vm", "tags": "k3s-server;production"},
            {"vmid": 101, "name": "worker-vm", "tags": "k3s-agent;production"},
            {"vmid": 102, "name": "other-vm", "tags": "web;database"}
        ]
        mock_proxmox_client.nodes(node_name).qemu.get.return_value = mock_vms
        
        # Mock QGA status calls for each K3s VM
        mock_config_response = {"agent": "1"}
        mock_agent_response = {"version": "5.2.0"}
        mock_proxmox_client.nodes(node_name).qemu().config.get.return_value = mock_config_response
        mock_proxmox_client.nodes(node_name).qemu().agent.get.return_value = mock_agent_response
    
        # Act
        result = get_vms_with_k3s_tags(mock_proxmox_client, node_name)
    
        # Assert
        expected = [
            {
                "vmid": 100, "name": "master-vm", "status": None, "k3s_tag": "k3s-server",
                "qga_enabled": True, "qga_running": True, "qga_version": "5.2.0", "qga_error": None
            },
            {
                "vmid": 101, "name": "worker-vm", "status": None, "k3s_tag": "k3s-agent",
                "qga_enabled": True, "qga_running": True, "qga_version": "5.2.0", "qga_error": None
            }
        ]
        assert result == expected
    
    def test_get_vms_with_k3s_tags_no_k3s_vms(self, mock_proxmox_client):
        """Test VM retrieval when no K3s VMs exist."""
        # Arrange
        node_name = "proxmox-node1"
        mock_vms = [
            {"vmid": 100, "name": "web-vm", "tags": "web;database"},
            {"vmid": 101, "name": "mail-vm", "tags": "mail;service"}
        ]
        mock_proxmox_client.nodes(node_name).qemu.get.return_value = mock_vms
    
        # Act
        result = get_vms_with_k3s_tags(mock_proxmox_client, node_name)
    
        # Assert
        assert result == []
    
    def test_get_vms_with_k3s_tags_empty_tags(self, mock_proxmox_client):
        """Test VM retrieval with VMs having empty or no tags."""
        # Arrange
        node_name = "proxmox-node1"
        mock_vms = [
            {"vmid": 100, "name": "vm1", "tags": ""},
            {"vmid": 101, "name": "vm2"},  # No tags field
            {"vmid": 102, "name": "vm3", "tags": "k3s-server"}
        ]
        mock_proxmox_client.nodes(node_name).qemu.get.return_value = mock_vms
        
        # Mock QGA status calls for K3s VM
        mock_config_response = {"agent": "1"}
        mock_agent_response = {"version": "5.2.0"}
        mock_proxmox_client.nodes(node_name).qemu().config.get.return_value = mock_config_response
        mock_proxmox_client.nodes(node_name).qemu().agent.get.return_value = mock_agent_response
    
        # Act
        result = get_vms_with_k3s_tags(mock_proxmox_client, node_name)
    
        # Assert
        expected = [{
            "vmid": 102, "name": "vm3", "status": None, "k3s_tag": "k3s-server",
            "qga_enabled": True, "qga_running": True, "qga_version": "5.2.0", "qga_error": None
        }]
        assert result == expected
    
    def test_get_vms_with_k3s_tags_case_sensitivity(self, mock_proxmox_client):
        """Test K3s tag detection is case-sensitive."""
        # Arrange
        node_name = "proxmox-node1"
        mock_vms = [
            {"vmid": 100, "name": "vm1", "tags": "K3S-SERVER"},  # Wrong case
            {"vmid": 101, "name": "vm2", "tags": "k3s-server"},  # Correct case
            {"vmid": 102, "name": "vm3", "tags": "k3s-Agent"}   # Mixed case
        ]
        mock_proxmox_client.nodes(node_name).qemu.get.return_value = mock_vms
        
        # Mock QGA status calls for K3s VM
        mock_config_response = {"agent": "1"}
        mock_agent_response = {"version": "5.2.0"}
        mock_proxmox_client.nodes(node_name).qemu().config.get.return_value = mock_config_response
        mock_proxmox_client.nodes(node_name).qemu().agent.get.return_value = mock_agent_response
    
        # Act
        result = get_vms_with_k3s_tags(mock_proxmox_client, node_name)
    
        # Assert
        expected = [{
            "vmid": 101, "name": "vm2", "status": None, "k3s_tag": "k3s-server",
            "qga_enabled": True, "qga_running": True, "qga_version": "5.2.0", "qga_error": None
        }]
        assert result == expected
    
    def test_get_vms_with_k3s_tags_resource_exception(self, mock_proxmox_client):
        """Test ResourceException handling in VM retrieval."""
        # Arrange
        node_name = "proxmox-node1"
        mock_proxmox_client.nodes(node_name).qemu.get.side_effect = ResourceException(404, "Node not found", "Node offline")
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError):
            get_vms_with_k3s_tags(mock_proxmox_client, node_name)
    
    def test_get_vms_with_k3s_tags_generic_exception(self, mock_proxmox_client):
        """Test generic exception handling in VM retrieval."""
        # Arrange
        node_name = "proxmox-node1"
        mock_proxmox_client.nodes(node_name).qemu.get.side_effect = Exception("Connection error")
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError):
            get_vms_with_k3s_tags(mock_proxmox_client, node_name)


class TestDiscoverK3sNodes:
    """Test cases for discover_k3s_nodes function."""
    
    @patch('k3s_deploy_cli.proxmox_vm_discovery.get_vms_with_k3s_tags')
    @patch('k3s_deploy_cli.proxmox_vm_discovery.get_cluster_status')
    def test_discover_k3s_nodes_success(self, mock_get_cluster_status, mock_get_vms_with_k3s_tags, mock_proxmox_client):
        """Test successful K3s node discovery."""
        # Arrange
        mock_get_cluster_status.return_value = [
            {"name": "node1", "type": "node", "online": 1},
            {"name": "node2", "type": "node", "online": 1}
        ]
    
        # Mock VM responses for each node
        node1_vms = [
            {"vmid": 100, "name": "master-vm", "k3s_tag": "k3s-server", "status": "running",
             "qga_enabled": True, "qga_running": True, "qga_version": "5.2.0", "qga_error": None},
            {"vmid": 101, "name": "worker-vm1", "k3s_tag": "k3s-agent", "status": "running",
             "qga_enabled": False, "qga_running": False, "qga_version": None, "qga_error": None}
        ]
        node2_vms = [
            {"vmid": 102, "name": "worker-vm2", "k3s_tag": "k3s-agent", "status": "running",
             "qga_enabled": True, "qga_running": False, "qga_version": None, "qga_error": None}
        ]
        mock_get_vms_with_k3s_tags.side_effect = [node1_vms, node2_vms]
    
        # Act
        result = discover_k3s_nodes(mock_proxmox_client)
    
        # Assert
        expected = [
            {"vmid": 100, "role": "server", "node": "node1", "name": "master-vm", "status": "running",
             "qga_enabled": True, "qga_running": True, "qga_version": "5.2.0"},
            {"vmid": 101, "role": "agent", "node": "node1", "name": "worker-vm1", "status": "running",
             "qga_enabled": False, "qga_running": False, "qga_version": None},
            {"vmid": 102, "role": "agent", "node": "node2", "name": "worker-vm2", "status": "running",
             "qga_enabled": True, "qga_running": False, "qga_version": None}
        ]
        assert result == expected
    
    @patch('k3s_deploy_cli.proxmox_vm_discovery.get_vms_with_k3s_tags')
    @patch('k3s_deploy_cli.proxmox_vm_discovery.get_cluster_status')
    def test_discover_k3s_nodes_no_nodes(self, mock_get_cluster_status, mock_get_vms_with_k3s_tags, mock_proxmox_client):
        """Test K3s discovery with no cluster nodes."""
        # Arrange
        mock_get_cluster_status.return_value = []

        # Act
        result = discover_k3s_nodes(mock_proxmox_client)

        # Assert
        assert result == []

    @patch('k3s_deploy_cli.proxmox_vm_discovery.get_vms_with_k3s_tags')
    @patch('k3s_deploy_cli.proxmox_vm_discovery.get_cluster_status')
    def test_discover_k3s_nodes_no_k3s_vms(self, mock_get_cluster_status, mock_get_vms_with_k3s_tags, mock_proxmox_client):
        """Test K3s discovery when no K3s VMs exist."""
        # Arrange
        mock_get_cluster_status.return_value = [
            {"name": "node1", "type": "node", "online": 1}
        ]
        mock_get_vms_with_k3s_tags.return_value = []
    
        # Act
        result = discover_k3s_nodes(mock_proxmox_client)
    
        # Assert
        assert result == []

    @patch('k3s_deploy_cli.proxmox_vm_discovery.get_vms_with_k3s_tags')
    @patch('k3s_deploy_cli.proxmox_vm_discovery.get_cluster_status')
    def test_discover_k3s_nodes_mixed_node_types(self, mock_get_cluster_status, mock_get_vms_with_k3s_tags, mock_proxmox_client):
        """Test K3s discovery filtering only node types."""
        # Arrange
        mock_get_cluster_status.return_value = [
            {"name": "node1", "type": "node", "online": 1},
            {"name": "cluster", "type": "cluster", "online": 1},
            {"name": "node2", "type": "node", "online": 0}  # offline
        ]
        mock_get_vms_with_k3s_tags.return_value = []
    
        # Act
        result = discover_k3s_nodes(mock_proxmox_client)
    
        # Assert - Only node1 should be checked (online nodes only)
        assert result == []
        # Should only call get_vms_with_k3s_tags once for node1
        assert mock_get_vms_with_k3s_tags.call_count == 1

    @patch('k3s_deploy_cli.proxmox_vm_discovery.get_vms_with_k3s_tags')
    @patch('k3s_deploy_cli.proxmox_vm_discovery.get_cluster_status')
    def test_discover_k3s_nodes_sorted_results(self, mock_get_cluster_status, mock_get_vms_with_k3s_tags, mock_proxmox_client):
        """Test K3s discovery returns sorted node names."""
        # Arrange
        mock_get_cluster_status.return_value = [
            {"name": "node3", "type": "node", "online": 1},
            {"name": "node1", "type": "node", "online": 1},
            {"name": "node2", "type": "node", "online": 1}
        ]
        mock_vms = [
            {"vmid": 103, "name": "vm3", "k3s_tag": "k3s-server", "status": "running",
             "qga_enabled": True, "qga_running": True, "qga_version": "5.2.0", "qga_error": None},
            {"vmid": 101, "name": "vm1", "k3s_tag": "k3s-agent", "status": "running",
             "qga_enabled": False, "qga_running": False, "qga_version": None, "qga_error": None},
            {"vmid": 102, "name": "vm2", "k3s_tag": "k3s-storage", "status": "running",
             "qga_enabled": True, "qga_running": False, "qga_version": None, "qga_error": None}
        ]
        mock_get_vms_with_k3s_tags.side_effect = [
            [mock_vms[0]],  # node3 
            [mock_vms[1]],  # node1
            [mock_vms[2]]   # node2
        ]
    
        # Act
        result = discover_k3s_nodes(mock_proxmox_client)
    
        # Assert - Results should be sorted by vmid
        assert len(result) == 3
        vmids = [node["vmid"] for node in result]
        assert vmids == [101, 102, 103]

    @patch('k3s_deploy_cli.proxmox_vm_discovery.get_vms_with_k3s_tags')
    @patch('k3s_deploy_cli.proxmox_vm_discovery.get_cluster_status')
    def test_discover_k3s_nodes_vm_error_continues(self, mock_get_cluster_status, mock_get_vms_with_k3s_tags, mock_proxmox_client):
        """Test K3s discovery continues when VM retrieval fails for one node."""
        # Arrange
        # Using shared mock_proxmox_client fixture
        mock_get_cluster_status.return_value = [
            {"name": "node1", "type": "node", "online": 1},
            {"name": "node2", "type": "node", "online": 1}
        ]
    
        # First call fails, second succeeds
        mock_get_vms_with_k3s_tags.side_effect = [
            ProxmoxInteractionError("Node offline"),
            [{"vmid": 100, "name": "vm", "k3s_tag": "k3s-server", "status": "running",
              "qga_enabled": True, "qga_running": False, "qga_version": None, "qga_error": None}]
        ]
    
        # Act
        result = discover_k3s_nodes(mock_proxmox_client)
    
        # Assert
        expected = [{"vmid": 100, "role": "server", "node": "node2", "name": "vm", "status": "running",
                     "qga_enabled": True, "qga_running": False, "qga_version": None}]
        assert result == expected

    @patch('k3s_deploy_cli.proxmox_vm_discovery.get_vms_with_k3s_tags')
    @patch('k3s_deploy_cli.proxmox_vm_discovery.get_cluster_status')
    def test_discover_k3s_nodes_cluster_status_error(self, mock_get_cluster_status, mock_get_vms_with_k3s_tags, mock_proxmox_client):
        """Test K3s discovery when cluster status retrieval fails."""
        # Arrange
        # Using shared mock_proxmox_client fixture
        mock_get_cluster_status.side_effect = ProxmoxInteractionError("Auth failed")
    
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError):
            discover_k3s_nodes(mock_proxmox_client)


class TestGetVmStatus:
    """Test cases for get_vm_status function."""
    
    def test_get_vm_status_success(self, mock_proxmox_client):
        """Test successful VM status retrieval."""
        # Arrange
        expected_status = {
            'status': 'running',
            'cpu': 0.02,
            'mem': 1073741824,
            'uptime': 3600
        }
        mock_proxmox_client.nodes.return_value.qemu.return_value.status.current.get.return_value = expected_status
        
        # Act
        result = get_vm_status(mock_proxmox_client, "test-node", 100)
        
        # Assert
        assert result == expected_status
        mock_proxmox_client.nodes.assert_called_once_with("test-node")
        mock_proxmox_client.nodes.return_value.qemu.assert_called_once_with(100)
        mock_proxmox_client.nodes.return_value.qemu.return_value.status.current.get.assert_called_once()
    
    def test_get_vm_status_resource_exception(self, mock_proxmox_client):
        """Test get_vm_status with ResourceException."""
        # Arrange
        # Using shared mock_proxmox_client fixture
        mock_proxmox_client.nodes.return_value.qemu.return_value.status.current.get.side_effect = ResourceException(
            404, "Not Found", "VM not found"
        )
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError) as exc_info:
            get_vm_status(mock_proxmox_client, "test-node", 100)
        
        assert "Error fetching status for VM 100: 404 - VM not found" in str(exc_info.value)
    
    def test_get_vm_status_generic_exception(self, mock_proxmox_client):
        """Test get_vm_status with generic exception."""
        # Arrange
        # Using shared mock_proxmox_client fixture
        mock_proxmox_client.nodes.return_value.qemu.return_value.status.current.get.side_effect = Exception("Connection error")
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError) as exc_info:
            get_vm_status(mock_proxmox_client, "test-node", 100)
        
        assert "Error fetching status for VM 100: Connection error" in str(exc_info.value)


class TestIntegrationScenarios:
    """Integration test scenarios testing multiple functions together."""

    @patch('k3s_deploy_cli.proxmox_core.ProxmoxAPI')
    def test_full_workflow_integration(self, mock_proxmox_api, mock_proxmox_client):
        """Test complete workflow from connection to discovery."""
        # Arrange
        # Using shared mock_proxmox_client fixture
        mock_proxmox_api.return_value = mock_proxmox_client
        config = {"host": "proxmox.test", "user": "user", "password": "pass"}
    
        # Mock cluster status
        mock_proxmox_client.cluster.status.get.return_value = [
            {"name": "node1", "type": "node", "online": 1}
        ]
    
        # Mock VMs with K3s tags
        mock_proxmox_client.nodes("node1").qemu.get.return_value = [
            {"vmid": 100, "name": "master", "tags": "k3s-server"},
            {"vmid": 101, "name": "worker", "tags": "k3s-agent"}
        ]
    
        # Act
        client = get_proxmox_api_client(config)
        cluster_status = get_cluster_status(client)
        vms = get_vms_with_k3s_tags(client, "node1")
        discovered = discover_k3s_nodes(client)
    
        # Assert
        assert client == mock_proxmox_client
        assert len(cluster_status) == 1
        assert len(vms) == 2
        assert len(discovered) == 2
    
    def test_error_propagation_chain(self, mock_proxmox_client):
        """Test error propagation through function call chain."""
        # Arrange
        # Using shared mock_proxmox_client fixture
        mock_proxmox_client.cluster.status.get.side_effect = ResourceException(500, "Network error", "Server error")
    
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError):
            get_cluster_status(mock_proxmox_client)

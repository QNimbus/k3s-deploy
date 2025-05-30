"""
Unit tests for proxmox_client module.

This module provides comprehensive test coverage for all functions in the
proxmox_client module, including success scenarios, error handling, and edge cases.
"""

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, call, patch

import pytest
from proxmoxer import ResourceException

from k3s_deploy_cli.exceptions import (
    ConfigurationError,
    ProxmoxInteractionError,
)
from k3s_deploy_cli.proxmox_client import (
    K3S_TAGS,
    discover_k3s_nodes,
    get_cluster_status,
    get_node_dns_info,
    get_proxmox_api_client,
    get_proxmox_version_info,
    get_vms_with_k3s_tags,
)


class TestConstants:
    """Test module constants are properly defined."""
    
    def test_k3s_tags(self):
        """Test K3S_TAGS constant."""
        assert K3S_TAGS == ['k3s-server', 'k3s-agent', 'k3s-storage']
        assert isinstance(K3S_TAGS, list)
        assert len(K3S_TAGS) == 3


class TestGetProxmoxApiClient:
    """Test cases for get_proxmox_api_client function."""
    
    @patch('k3s_deploy_cli.proxmox_client.ProxmoxAPI')
    def test_get_proxmox_api_client_success(self, mock_proxmox_api):
        """Test successful Proxmox API client creation."""
        # Arrange
        mock_client = MagicMock()
        mock_proxmox_api.return_value = mock_client
        config = {
            "host": "proxmox.example.com",
            "user": "testuser",
            "password": "testpass"
        }
        
        # Act
        result = get_proxmox_api_client(config)
        
        # Assert
        assert result == mock_client
        mock_proxmox_api.assert_called_once_with(
            "proxmox.example.com",
            user="testuser",
            password="testpass",
            verify_ssl=True,
            timeout=10
        )
        mock_client.version.get.assert_called_once()
    
    @patch('k3s_deploy_cli.proxmox_client.ProxmoxAPI')
    def test_get_proxmox_api_client_with_ssl_verification(self, mock_proxmox_api):
        """Test API client creation with SSL verification disabled."""
        # Arrange
        mock_client = MagicMock()
        mock_proxmox_api.return_value = mock_client
        config = {
            "host": "proxmox.example.com",
            "user": "testuser",
            "password": "testpass",
            "verify_ssl": False
        }
        
        # Act
        result = get_proxmox_api_client(config)
        
        # Assert
        assert result == mock_client
        mock_proxmox_api.assert_called_once_with(
            "proxmox.example.com",
            user="testuser",
            password="testpass",
            verify_ssl=False,
            timeout=10
        )
        mock_client.version.get.assert_called_once()
    
    @patch('k3s_deploy_cli.proxmox_client.ProxmoxAPI')
    def test_get_proxmox_api_client_connection_error(self, mock_proxmox_api):
        """Test ProxmoxInteractionError when connection fails."""
        # Arrange
        mock_proxmox_api.side_effect = Exception("Connection failed")
        config = {
            "host": "proxmox.example.com", 
            "user": "testuser",
            "password": "testpass"
        }
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError) as exc_info:
            get_proxmox_api_client(config)
        
        assert "Failed to connect to Proxmox API" in str(exc_info.value)
        assert "Connection failed" in str(exc_info.value)
    
    @patch('k3s_deploy_cli.proxmox_client.ProxmoxAPI')
    def test_get_proxmox_api_client_resource_exception(self, mock_proxmox_api):
        """Test ProxmoxInteractionError when ResourceException occurs."""
        # Arrange
        mock_proxmox_api.side_effect = ResourceException(401, "Auth failed", "Authentication failed")
        config = {
            "host": "proxmox.example.com",
            "user": "testuser", 
            "password": "testpass"
        }
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError) as exc_info:
            get_proxmox_api_client(config)
        
        assert "Proxmox API error" in str(exc_info.value)
        assert "401" in str(exc_info.value)


class TestGetClusterStatus:
    """Test cases for get_cluster_status function."""
    
    def test_get_cluster_status_success(self):
        """Test successful cluster status retrieval."""
        # Arrange
        mock_client = MagicMock()
        expected_status = [
            {"name": "node1", "status": "online", "type": "node"},
            {"name": "node2", "status": "online", "type": "node"}
        ]
        mock_client.cluster.status.get.return_value = expected_status
        
        # Act
        result = get_cluster_status(mock_client)
        
        # Assert
        assert result == expected_status
        mock_client.cluster.status.get.assert_called_once()
    
    def test_get_cluster_status_empty_response(self):
        """Test cluster status with empty response."""
        # Arrange
        mock_client = MagicMock()
        mock_client.cluster.status.get.return_value = []
        
        # Act
        result = get_cluster_status(mock_client)
        
        # Assert
        assert result == []
        mock_client.cluster.status.get.assert_called_once()
    
    def test_get_cluster_status_resource_exception(self):
        """Test ResourceException handling in cluster status."""
        # Arrange
        mock_client = MagicMock()
        mock_client.cluster.status.get.side_effect = ResourceException(403, "Access denied", "Permission denied")
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError):
            get_cluster_status(mock_client)
    
    def test_get_cluster_status_generic_exception(self):
        """Test generic exception handling in cluster status."""
        # Arrange
        mock_client = MagicMock()
        mock_client.cluster.status.get.side_effect = Exception("Network error")
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError):
            get_cluster_status(mock_client)


class TestGetProxmoxVersionInfo:
    """Test cases for get_proxmox_version_info function."""
    
    def test_get_proxmox_version_info_success(self):
        """Test successful version info retrieval."""
        # Arrange
        mock_client = MagicMock()
        expected_version = {
            "version": "7.0",
            "release": "12",
            "repoversion": "version-7.0-12"
        }
        mock_client.version.get.return_value = expected_version
        
        # Act
        result = get_proxmox_version_info(mock_client)
        
        # Assert
        assert result == expected_version
        mock_client.version.get.assert_called_once()
    
    def test_get_proxmox_version_info_minimal_response(self):
        """Test version info with minimal response data."""
        # Arrange
        mock_client = MagicMock()
        minimal_version = {"version": "6.4"}
        mock_client.version.get.return_value = minimal_version
        
        # Act
        result = get_proxmox_version_info(mock_client)
        
        # Assert
        assert result == minimal_version
        mock_client.version.get.assert_called_once()
    
    def test_get_proxmox_version_info_resource_exception(self):
        """Test ResourceException handling in version info."""
        # Arrange
        mock_client = MagicMock()
        mock_client.version.get.side_effect = ResourceException(403, "Forbidden", "Access forbidden")
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError):
            get_proxmox_version_info(mock_client)
    
    def test_get_proxmox_version_info_generic_exception(self):
        """Test generic exception handling in version info."""
        # Arrange
        mock_client = MagicMock()
        mock_client.version.get.side_effect = Exception("Connection timeout")
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError):
            get_proxmox_version_info(mock_client)


class TestGetVmsWithK3sTags:
    """Test cases for get_vms_with_k3s_tags function."""
    
    def test_get_vms_with_k3s_tags_success(self):
        """Test successful VM retrieval with K3s tags."""
        # Arrange
        mock_client = MagicMock()
        node_name = "proxmox-node1"
        mock_vms = [
            {"vmid": 100, "name": "master-vm", "tags": "k3s-server;production"},
            {"vmid": 101, "name": "worker-vm", "tags": "k3s-agent;production"},
            {"vmid": 102, "name": "other-vm", "tags": "web;database"}
        ]
        mock_client.nodes(node_name).qemu.get.return_value = mock_vms
        
        # Mock QGA status calls for each K3s VM
        mock_config_response = {"agent": "1"}
        mock_agent_response = {"version": "5.2.0"}
        mock_client.nodes(node_name).qemu().config.get.return_value = mock_config_response
        mock_client.nodes(node_name).qemu().agent.get.return_value = mock_agent_response
    
        # Act
        result = get_vms_with_k3s_tags(mock_client, node_name)
    
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
    
    def test_get_vms_with_k3s_tags_no_k3s_vms(self):
        """Test VM retrieval when no K3s VMs exist."""
        # Arrange
        mock_client = MagicMock()
        node_name = "proxmox-node1"
        mock_vms = [
            {"vmid": 100, "name": "web-vm", "tags": "web;database"},
            {"vmid": 101, "name": "mail-vm", "tags": "mail;service"}
        ]
        mock_client.nodes(node_name).qemu.get.return_value = mock_vms
    
        # Act
        result = get_vms_with_k3s_tags(mock_client, node_name)
    
        # Assert
        assert result == []
    
    def test_get_vms_with_k3s_tags_empty_tags(self):
        """Test VM retrieval with VMs having empty or no tags."""
        # Arrange
        mock_client = MagicMock()
        node_name = "proxmox-node1"
        mock_vms = [
            {"vmid": 100, "name": "vm1", "tags": ""},
            {"vmid": 101, "name": "vm2"},  # No tags field
            {"vmid": 102, "name": "vm3", "tags": "k3s-server"}
        ]
        mock_client.nodes(node_name).qemu.get.return_value = mock_vms
        
        # Mock QGA status calls for K3s VM
        mock_config_response = {"agent": "1"}
        mock_agent_response = {"version": "5.2.0"}
        mock_client.nodes(node_name).qemu().config.get.return_value = mock_config_response
        mock_client.nodes(node_name).qemu().agent.get.return_value = mock_agent_response
    
        # Act
        result = get_vms_with_k3s_tags(mock_client, node_name)
    
        # Assert
        expected = [{
            "vmid": 102, "name": "vm3", "status": None, "k3s_tag": "k3s-server",
            "qga_enabled": True, "qga_running": True, "qga_version": "5.2.0", "qga_error": None
        }]
        assert result == expected
    
    def test_get_vms_with_k3s_tags_case_sensitivity(self):
        """Test K3s tag detection is case-sensitive."""
        # Arrange
        mock_client = MagicMock()
        node_name = "proxmox-node1"
        mock_vms = [
            {"vmid": 100, "name": "vm1", "tags": "K3S-SERVER"},  # Wrong case
            {"vmid": 101, "name": "vm2", "tags": "k3s-server"},  # Correct case
            {"vmid": 102, "name": "vm3", "tags": "k3s-Agent"}   # Mixed case
        ]
        mock_client.nodes(node_name).qemu.get.return_value = mock_vms
        
        # Mock QGA status calls for K3s VM
        mock_config_response = {"agent": "1"}
        mock_agent_response = {"version": "5.2.0"}
        mock_client.nodes(node_name).qemu().config.get.return_value = mock_config_response
        mock_client.nodes(node_name).qemu().agent.get.return_value = mock_agent_response
    
        # Act
        result = get_vms_with_k3s_tags(mock_client, node_name)
    
        # Assert
        expected = [{
            "vmid": 101, "name": "vm2", "status": None, "k3s_tag": "k3s-server",
            "qga_enabled": True, "qga_running": True, "qga_version": "5.2.0", "qga_error": None
        }]
        assert result == expected
    
    def test_get_vms_with_k3s_tags_resource_exception(self):
        """Test ResourceException handling in VM retrieval."""
        # Arrange
        mock_client = MagicMock()
        node_name = "proxmox-node1"
        mock_client.nodes(node_name).qemu.get.side_effect = ResourceException(404, "Node not found", "Node offline")
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError):
            get_vms_with_k3s_tags(mock_client, node_name)
    
    def test_get_vms_with_k3s_tags_generic_exception(self):
        """Test generic exception handling in VM retrieval."""
        # Arrange
        mock_client = MagicMock()
        node_name = "proxmox-node1"
        mock_client.nodes(node_name).qemu.get.side_effect = Exception("Connection error")
        
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError):
            get_vms_with_k3s_tags(mock_client, node_name)


class TestGetNodeDnsInfo:
    """Test cases for get_node_dns_info function."""
    
    def test_get_node_dns_info_success(self):
        """Test successful DNS info retrieval."""
        # Arrange
        mock_client = MagicMock()
        node_name = "proxmox-node1"
        expected_dns = {
            "search": "example.com",
            "dns1": "8.8.8.8",
            "dns2": "8.8.4.4"
        }
        mock_client.nodes(node_name).dns.get.return_value = expected_dns
    
        # Act
        result = get_node_dns_info(mock_client, node_name)
    
        # Assert - Function returns the search domain, not the full dict
        assert result == "example.com"
    
    def test_get_node_dns_info_minimal_response(self):
        """Test DNS info with minimal response data."""
        # Arrange
        mock_client = MagicMock()
        node_name = "proxmox-node1"
        minimal_dns = {"search": "local"}
        mock_client.nodes(node_name).dns.get.return_value = minimal_dns
    
        # Act
        result = get_node_dns_info(mock_client, node_name)
    
        # Assert
        assert result == "local"
    
    def test_get_node_dns_info_empty_response(self):
        """Test DNS info with empty response."""
        # Arrange
        mock_client = MagicMock()
        node_name = "proxmox-node1"
        mock_client.nodes(node_name).dns.get.return_value = {}
    
        # Act
        result = get_node_dns_info(mock_client, node_name)
    
        # Assert
        assert result is None
    
    def test_get_node_dns_info_resource_exception(self):
        """Test ResourceException handling in DNS info retrieval."""
        # Arrange
        mock_client = MagicMock()
        node_name = "proxmox-node1"
        mock_client.nodes(node_name).dns.get.side_effect = ResourceException(403, "Access denied", "Permission denied")
    
        # Act
        result = get_node_dns_info(mock_client, node_name)
    
        # Assert - Function handles errors gracefully and returns None
        assert result is None
    
    def test_get_node_dns_info_generic_exception(self):
        """Test generic exception handling in DNS info retrieval."""
        # Arrange
        mock_client = MagicMock()
        node_name = "proxmox-node1"
        mock_client.nodes(node_name).dns.get.side_effect = Exception("Connection error")
    
        # Act
        result = get_node_dns_info(mock_client, node_name)
    
        # Assert - Function handles errors gracefully and returns None
        assert result is None


class TestDiscoverK3sNodes:
    """Test cases for discover_k3s_nodes function."""
    
    @patch('k3s_deploy_cli.proxmox_client.get_vms_with_k3s_tags')
    @patch('k3s_deploy_cli.proxmox_client.get_cluster_status')
    def test_discover_k3s_nodes_success(self, mock_get_cluster_status, mock_get_vms_with_k3s_tags):
        """Test successful K3s node discovery."""
        # Arrange
        mock_client = MagicMock()
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
        result = discover_k3s_nodes(mock_client)
    
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
    
    @patch('k3s_deploy_cli.proxmox_client.get_vms_with_k3s_tags')
    @patch('k3s_deploy_cli.proxmox_client.get_cluster_status')
    def test_discover_k3s_nodes_no_nodes(self, mock_get_cluster_status, mock_get_vms_with_k3s_tags):
        """Test K3s discovery with no cluster nodes."""
        # Arrange
        mock_client = MagicMock()
        mock_get_cluster_status.return_value = []
    
        # Act
        result = discover_k3s_nodes(mock_client)
    
        # Assert
        assert result == []
    
    @patch('k3s_deploy_cli.proxmox_client.get_vms_with_k3s_tags')
    @patch('k3s_deploy_cli.proxmox_client.get_cluster_status')
    def test_discover_k3s_nodes_no_k3s_vms(self, mock_get_cluster_status, mock_get_vms_with_k3s_tags):
        """Test K3s discovery when no K3s VMs exist."""
        # Arrange
        mock_client = MagicMock()
        mock_get_cluster_status.return_value = [
            {"name": "node1", "type": "node", "online": 1}
        ]
        mock_get_vms_with_k3s_tags.return_value = []
    
        # Act
        result = discover_k3s_nodes(mock_client)
    
        # Assert
        assert result == []
    
    @patch('k3s_deploy_cli.proxmox_client.get_vms_with_k3s_tags')
    @patch('k3s_deploy_cli.proxmox_client.get_cluster_status')
    def test_discover_k3s_nodes_mixed_node_types(self, mock_get_cluster_status, mock_get_vms_with_k3s_tags):
        """Test K3s discovery filtering only node types."""
        # Arrange
        mock_client = MagicMock()
        mock_get_cluster_status.return_value = [
            {"name": "node1", "type": "node", "online": 1},
            {"name": "cluster", "type": "cluster", "online": 1},
            {"name": "node2", "type": "node", "online": 0}  # offline
        ]
        mock_get_vms_with_k3s_tags.return_value = []
    
        # Act
        result = discover_k3s_nodes(mock_client)
    
        # Assert - Only node1 should be checked (online nodes only)
        assert result == []
        # Should only call get_vms_with_k3s_tags once for node1
        assert mock_get_vms_with_k3s_tags.call_count == 1
    
    @patch('k3s_deploy_cli.proxmox_client.get_vms_with_k3s_tags')
    @patch('k3s_deploy_cli.proxmox_client.get_cluster_status')
    def test_discover_k3s_nodes_sorted_results(self, mock_get_cluster_status, mock_get_vms_with_k3s_tags):
        """Test K3s discovery returns sorted node names."""
        # Arrange
        mock_client = MagicMock()
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
        result = discover_k3s_nodes(mock_client)
    
        # Assert - Results should be sorted by vmid
        assert len(result) == 3
        vmids = [node["vmid"] for node in result]
        assert vmids == [101, 102, 103]
    
    @patch('k3s_deploy_cli.proxmox_client.get_vms_with_k3s_tags')
    @patch('k3s_deploy_cli.proxmox_client.get_cluster_status')
    def test_discover_k3s_nodes_vm_error_continues(self, mock_get_cluster_status, mock_get_vms_with_k3s_tags):
        """Test K3s discovery continues when VM retrieval fails for one node."""
        # Arrange
        mock_client = MagicMock()
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
        result = discover_k3s_nodes(mock_client)
    
        # Assert
        expected = [{"vmid": 100, "role": "server", "node": "node2", "name": "vm", "status": "running",
                     "qga_enabled": True, "qga_running": False, "qga_version": None}]
        assert result == expected
    
    @patch('k3s_deploy_cli.proxmox_client.get_vms_with_k3s_tags')
    @patch('k3s_deploy_cli.proxmox_client.get_cluster_status')
    def test_discover_k3s_nodes_cluster_status_error(self, mock_get_cluster_status, mock_get_vms_with_k3s_tags):
        """Test K3s discovery when cluster status retrieval fails."""
        # Arrange
        mock_client = MagicMock()
        mock_get_cluster_status.side_effect = ProxmoxInteractionError("Auth failed")
    
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError):
            discover_k3s_nodes(mock_client)


class TestIntegrationScenarios:
    """Integration test scenarios testing multiple functions together."""
    
    @patch('k3s_deploy_cli.proxmox_client.ProxmoxAPI')
    def test_full_workflow_integration(self, mock_proxmox_api):
        """Test complete workflow from connection to discovery."""
        # Arrange
        mock_client = MagicMock()
        mock_proxmox_api.return_value = mock_client
        config = {"host": "proxmox.test", "user": "user", "password": "pass"}
    
        # Mock cluster status
        mock_client.cluster.status.get.return_value = [
            {"name": "node1", "type": "node", "online": 1}
        ]
    
        # Mock VMs with K3s tags
        mock_client.nodes("node1").qemu.get.return_value = [
            {"vmid": 100, "name": "master", "tags": "k3s-server"},
            {"vmid": 101, "name": "worker", "tags": "k3s-agent"}
        ]
    
        # Act
        client = get_proxmox_api_client(config)
        cluster_status = get_cluster_status(client)
        vms = get_vms_with_k3s_tags(client, "node1")
        discovered = discover_k3s_nodes(client)
    
        # Assert
        assert client == mock_client
        assert len(cluster_status) == 1
        assert len(vms) == 2
        assert len(discovered) == 2
    
    def test_error_propagation_chain(self):
        """Test error propagation through function call chain."""
        # Arrange
        mock_client = MagicMock()
        mock_client.cluster.status.get.side_effect = ResourceException(500, "Network error", "Server error")
    
        # Act & Assert
        with pytest.raises(ProxmoxInteractionError):
            get_cluster_status(mock_client)

"""
Unit tests for proxmox_client core functionality.

This module provides comprehensive test coverage for core Proxmox API functions
including client creation, cluster management, version info, and DNS configuration.
"""
import socket
from unittest.mock import MagicMock, patch

import paramiko
import pytest
from proxmoxer import ResourceException

from k3s_deploy_cli.constants import (
    K3S_TAGS,
)
from k3s_deploy_cli.exceptions import ConfigurationError, ProxmoxInteractionError
from k3s_deploy_cli.proxmox_core import (
    _clear_client_cache,
    get_cluster_status,
    get_node_dns_info,
    get_node_snippet_storage,
    get_proxmox_api_client,
    get_proxmox_version_info,
)
from k3s_deploy_cli.ssh_operations import check_proxmox_ssh_connectivity


@pytest.fixture(autouse=True)
def clear_proxmox_cache():
    """Clear the Proxmox client cache before each test to ensure test isolation."""
    _clear_client_cache()
    yield
    _clear_client_cache()


class TestConstants:
    """Test module constants are properly defined."""
    
    def test_k3s_tags(self):
        """Test K3S_TAGS constant."""
        assert K3S_TAGS == ['k3s-server', 'k3s-agent', 'k3s-storage']
        assert isinstance(K3S_TAGS, list)
        assert len(K3S_TAGS) == 3


class TestGetProxmoxApiClient:
    """Test cases for get_proxmox_api_client function."""
    
    @patch('k3s_deploy_cli.proxmox_core.ProxmoxAPI')
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
    
    @patch('k3s_deploy_cli.proxmox_core.ProxmoxAPI')
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
    
    @patch('k3s_deploy_cli.proxmox_core.ProxmoxAPI')
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
    
    @patch('k3s_deploy_cli.proxmox_core.ProxmoxAPI')
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
        mock_client.nodes.assert_called_with(node_name)
        mock_client.nodes(node_name).dns.get.assert_called_once()
    
    def test_get_node_dns_info_no_search_domain(self):
        """Test DNS info retrieval when no search domain is configured."""
        # Arrange
        mock_client = MagicMock()
        node_name = "proxmox-node1"
        dns_without_search = {
            "dns1": "8.8.8.8",
            "dns2": "8.8.4.4"
        }
        mock_client.nodes(node_name).dns.get.return_value = dns_without_search

        # Act
        result = get_node_dns_info(mock_client, node_name)

        # Assert - Should return None when no search domain
        assert result is None
        mock_client.nodes.assert_called_with(node_name)
        mock_client.nodes(node_name).dns.get.assert_called_once()

    def test_get_node_dns_info_empty_search_domain(self):        
        """Test DNS info retrieval when search domain is empty."""
        # Arrange
        mock_client = MagicMock()
        node_name = "proxmox-node1"
        dns_empty_search = {
            "search": "",
            "dns1": "8.8.8.8"
        }
        mock_client.nodes(node_name).dns.get.return_value = dns_empty_search

        # Act
        result = get_node_dns_info(mock_client, node_name)

        # Assert - Should return None for empty search domain
        assert result is None
    
    def test_get_node_dns_info_resource_exception(self):
        """Test ResourceException handling in DNS info retrieval."""
        # Arrange
        mock_client = MagicMock()
        node_name = "proxmox-node1"
        mock_client.nodes(node_name).dns.get.side_effect = ResourceException(404, "Not found", "Node not found")

        # Act & Assert
        with pytest.raises(ProxmoxInteractionError):
            get_node_dns_info(mock_client, node_name)
    
    def test_get_node_dns_info_generic_exception(self):
        """Test generic exception handling in DNS info retrieval."""
        # Arrange
        mock_client = MagicMock()
        node_name = "proxmox-node1"
        mock_client.nodes(node_name).dns.get.side_effect = Exception("Connection error")

        # Act & Assert
        with pytest.raises(ProxmoxInteractionError):
            get_node_dns_info(mock_client, node_name)


class TestGetNodeSnippetStorage:
    """Test cases for get_node_snippet_storage function."""

    def test_get_node_snippet_storage_success_with_snippets(self):
        """Test successful retrieval when node has snippet-capable storage."""
        # Arrange
        mock_client = MagicMock()
        node_name = "pve-node1"

        # Mock API response with snippet-capable storage (path and shared NOT included in first call)
        mock_storage_response = [
            {
                "storage": "local",
                "content": "images,iso,backup,rootdir,vztmpl,snippets",
                "enabled": 1,
                "active": 1,
                "type": "dir"
                # path and shared are NOT included - requires second API call
            },
            {
                "storage": "shared-storage",
                "content": "images,iso,backup",
                "enabled": 1,
                "active": 1,
                "type": "nfs"
            }
        ]
        mock_client.nodes(node_name).storage.get.return_value = mock_storage_response

        # Mock the second API call to get detailed storage info
        mock_storage_details = {
            "type": "dir",
            "path": "/var/lib/vz",
            "shared": 0
        }
        mock_client.storage("local").get.return_value = mock_storage_details

        # Act
        result = get_node_snippet_storage(mock_client, node_name)

        # Assert
        expected = {
            "storage_name": "local",
            "enabled": True,
            "active": True,
            "type": "dir",
            "path": "/var/lib/vz",
            "shared": False
        }
        assert result == expected
        mock_client.nodes(node_name).storage.get.assert_called_once()
        mock_client.storage("local").get.assert_called_once()

    def test_get_node_snippet_storage_success_no_snippets(self):
        """Test when node has no snippet-capable storage."""
        # Arrange
        mock_client = MagicMock()
        node_name = "pve-node2"

        # Mock API response with no snippet storage
        mock_storage_response = [
            {
                "storage": "shared-storage",
                "content": "images,iso,backup",
                "enabled": 1,
                "active": 1,
                "type": "nfs"
            }
        ]
        mock_client.nodes(node_name).storage.get.return_value = mock_storage_response

        # Act
        # from k3s_deploy_cli.proxmox_core import get_node_snippet_storage
        result = get_node_snippet_storage(mock_client, node_name)

        # Assert
        assert result == {}
        mock_client.nodes(node_name).storage.get.assert_called_once()

    def test_get_node_snippet_storage_disabled_storage(self):
        """Test when snippet storage exists but is disabled."""
        # Arrange
        mock_client = MagicMock()
        node_name = "pve-node3"

        # Mock API response with disabled snippet storage
        mock_storage_response = [
            {
                "storage": "local",
                "content": "images,iso,backup,rootdir,vztmpl,snippets",
                "enabled": 0,  # Disabled
                "active": 1,
                "type": "dir"
            }
        ]
        mock_client.nodes(node_name).storage.get.return_value = mock_storage_response

        # Act
        # from k3s_deploy_cli.proxmox_core import get_node_snippet_storage
        result = get_node_snippet_storage(mock_client, node_name)

        # Assert
        assert result == {}
        mock_client.nodes(node_name).storage.get.assert_called_once()

    def test_get_node_snippet_storage_inactive_storage(self):
        """Test when snippet storage exists but is inactive."""
        # Arrange
        mock_client = MagicMock()
        node_name = "pve-node4"

        # Mock API response with inactive snippet storage
        mock_storage_response = [
            {
                "storage": "local",
                "content": "images,iso,backup,rootdir,vztmpl,snippets",
                "enabled": 1,
                "active": 0,  # Inactive
                "type": "dir"
            }
        ]
        mock_client.nodes(node_name).storage.get.return_value = mock_storage_response

        # Act
        # from k3s_deploy_cli.proxmox_core import get_node_snippet_storage
        result = get_node_snippet_storage(mock_client, node_name)

        # Assert
        assert result == {}
        mock_client.nodes(node_name).storage.get.assert_called_once()

    def test_get_node_snippet_storage_multiple_snippet_storages(self):
        """Test when node has multiple snippet-capable storages (return first active)."""
        # Arrange
        mock_client = MagicMock()
        node_name = "pve-node5"

        # Mock API response with multiple snippet storages (path and shared NOT included)
        mock_storage_response = [
            {
                "storage": "local", # This one should be picked
                "content": "images,iso,backup,rootdir,vztmpl,snippets",
                "enabled": 1,
                "active": 1,
                "type": "dir"
                # path and shared are NOT included - requires second API call
            },
            {
                "storage": "snippets-nfs",
                "content": "snippets",
                "enabled": 1,
                "active": 1,
                "type": "nfs"
            }
        ]
        mock_client.nodes(node_name).storage.get.return_value = mock_storage_response

        # Mock the second API call to get detailed storage info for first storage
        mock_storage_details = {
            "type": "dir",
            "path": "/var/lib/vz",
            "shared": 0
        }
        mock_client.storage("local").get.return_value = mock_storage_details

        # Act
        result = get_node_snippet_storage(mock_client, node_name)

        # Assert - Should return first valid snippet storage
        expected = {
            "storage_name": "local",
            "enabled": True,
            "active": True,
            "type": "dir",
            "path": "/var/lib/vz",
            "shared": False
        }
        assert result == expected
        mock_client.nodes(node_name).storage.get.assert_called_once()
        mock_client.storage("local").get.assert_called_once()

    def test_get_node_snippet_storage_empty_response(self):
        """Test when API returns empty storage list."""
        # Arrange
        mock_client = MagicMock()
        node_name = "pve-node6"

        # Mock empty API response
        mock_client.nodes(node_name).storage.get.return_value = []

        # Act
        # from k3s_deploy_cli.proxmox_core import get_node_snippet_storage
        result = get_node_snippet_storage(mock_client, node_name)

        # Assert
        assert result == {}
        mock_client.nodes(node_name).storage.get.assert_called_once()

    def test_get_node_snippet_storage_resource_exception(self):
        """Test handling of Proxmox API ResourceException."""
        # Arrange
        mock_client = MagicMock()
        node_name = "pve-node7"

        # Mock ResourceException
        mock_client.nodes(node_name).storage.get.side_effect = ResourceException(
            404, 'Not Found', 'node not found'
        )

        # Act & Assert
        # from k3s_deploy_cli.proxmox_core import get_node_snippet_storage
        with pytest.raises(ProxmoxInteractionError,
                         match="Error fetching storage info for node pve-node7: 404 - node not found"):
            get_node_snippet_storage(mock_client, node_name)

    def test_get_node_snippet_storage_generic_exception(self):
        """Test handling of generic exceptions."""
        # Arrange
        mock_client = MagicMock()
        node_name = "pve-node8"

        # Mock generic exception
        mock_client.nodes(node_name).storage.get.side_effect = Exception("Connection timeout")

        # Act & Assert
        # from k3s_deploy_cli.proxmox_core import get_node_snippet_storage
        with pytest.raises(ProxmoxInteractionError,
                         match="Failed to get storage info for node pve-node8: Connection timeout"):
            get_node_snippet_storage(mock_client, node_name)

    def test_get_node_snippet_storage_path_not_available(self):
        """Test when snippet storage has no 'path' or 'shared' keys."""
        # Arrange
        mock_client = MagicMock()
        node_name = "pve-node9"

        # Mock API response with snippet-capable storage but missing path/shared
        mock_storage_response = [
            {
                "storage": "local-no-path",
                "content": "snippets",
                "enabled": 1,
                "active": 1,
                "type": "dir"
                # "path" key is missing
                # "shared" key is missing
            }
        ]
        mock_client.nodes(node_name).storage.get.return_value = mock_storage_response

        # Mock the second API call that also doesn't have path/shared
        mock_storage_details = {
            "type": "dir"
            # path and shared missing from second call too
        }
        mock_client.storage("local-no-path").get.return_value = mock_storage_details

        # Act
        result = get_node_snippet_storage(mock_client, node_name)

        # Assert
        expected = {
            "storage_name": "local-no-path",
            "enabled": True,
            "active": True,
            "type": "dir",
            "path": None, # Should default to None (from missing key)
            "shared": False # Should default to False (from bool(0))
        }
        assert result == expected
        mock_client.nodes(node_name).storage.get.assert_called_once()
        mock_client.storage("local-no-path").get.assert_called_once()

class TestCheckProxmoxSSHConnectivity:
    """Test cases for check_proxmox_ssh_connectivity function."""

    @patch('paramiko.SSHClient')
    def test_ssh_connectivity_success_with_public_key(self, mock_ssh_client_constructor):
        """Test successful SSH connection with public key authentication."""
        # Arrange
        mock_client_instance = MagicMock()
        mock_ssh_client_constructor.return_value = mock_client_instance
        mock_client_instance.connect.return_value = None # Simulates successful connect

        config = {"host": "proxmox.example.com", "user": "testuser@pve"}

        # Act
        result = check_proxmox_ssh_connectivity(config, timeout=15)

        # Assert
        assert result["success"] is True
        assert result["host"] == "proxmox.example.com"
        assert result["port"] == 22
        assert result["username_for_ssh"] == "testuser"
        assert result["connection_established"] is True
        assert result["server_allows_publickey_auth"] is True
        assert result["server_allows_password_auth"] is False # Not attempted or indicated
        assert result["auth_method_used"] == "publickey"
        assert result["error"] is None
        assert result["warning"] is None

        mock_ssh_client_constructor.assert_called_once() # Only one client needed for PK success
        mock_client_instance.set_missing_host_key_policy.assert_called_once()
        mock_client_instance.connect.assert_called_once_with(
            hostname="proxmox.example.com",
            port=22,
            username="testuser",
            allow_agent=True,
            look_for_keys=True,
            timeout=15,
            auth_timeout=15
        )
        mock_client_instance.close.assert_called_once()

    @patch('paramiko.SSHClient')
    def test_ssh_connectivity_public_key_auth_failed_password_success(self, mock_ssh_client_constructor):
        """Test successful password authentication when public key auth fails."""
        # Arrange
        mock_pk_client_instance = MagicMock(name="PKClient")
        mock_pwd_client_instance = MagicMock(name="PWDClient")
        # Return different mock instances for each SSHClient() call
        mock_ssh_client_constructor.side_effect = [mock_pk_client_instance, mock_pwd_client_instance]

        pk_auth_exception = paramiko.AuthenticationException("Public key auth failed")
        mock_pk_client_instance.connect.side_effect = pk_auth_exception
        mock_pwd_client_instance.connect.return_value = None # Password auth succeeds

        config = {"host": "proxmox.example.com", "user": "root", "password": "testpass"}

        # Act
        result = check_proxmox_ssh_connectivity(config, timeout=5)

        # Assert
        assert result["success"] is True
        assert result["username_for_ssh"] == "root"
        assert result["connection_established"] is True
        assert result["server_allows_publickey_auth"] is True # PK Auth failed, so server offered it
        assert result["server_allows_password_auth"] is True # PWD Auth succeeded
        assert result["auth_method_used"] == "password"
        assert result["error"] is None
        assert result["warning"] is None

        assert mock_ssh_client_constructor.call_count == 2
        mock_pk_client_instance.set_missing_host_key_policy.assert_called_once()
        mock_pk_client_instance.connect.assert_called_once_with(
            hostname="proxmox.example.com", port=22, username="root",
            allow_agent=True, look_for_keys=True, timeout=5, auth_timeout=5
        )
        mock_pk_client_instance.close.assert_called_once()

        mock_pwd_client_instance.set_missing_host_key_policy.assert_called_once()
        mock_pwd_client_instance.connect.assert_called_once_with(
            hostname="proxmox.example.com", port=22, username="root",
            password="testpass", allow_agent=False, look_for_keys=False, timeout=5, auth_timeout=5
        )
        mock_pwd_client_instance.close.assert_called_once()


    @patch('paramiko.SSHClient')
    def test_ssh_connectivity_both_auth_methods_failed(self, mock_ssh_client_constructor):
        """Test error when both public key and password authentication fail."""
        # Arrange
        mock_pk_client_instance = MagicMock(name="PKClient")
        mock_pwd_client_instance = MagicMock(name="PWDClient")
        mock_ssh_client_constructor.side_effect = [mock_pk_client_instance, mock_pwd_client_instance]

        auth_exception = paramiko.AuthenticationException("Auth failed")
        mock_pk_client_instance.connect.side_effect = auth_exception
        mock_pwd_client_instance.connect.side_effect = auth_exception

        config = {"host": "proxmox.example.com", "user": "user", "password": "wrongpass"}

        # Act
        result = check_proxmox_ssh_connectivity(config)

        # Assert
        assert result["success"] is False
        assert result["connection_established"] is False # No connection truly established
        assert result["server_allows_publickey_auth"] is True # PK Auth failed, so offered
        assert result["server_allows_password_auth"] is True # PWD Auth failed, so offered
        assert result["auth_method_used"] is None
        assert "Both public key and password SSH authentication failed" in result["error"]
        assert result["warning"] is None

        assert mock_ssh_client_constructor.call_count == 2
        mock_pk_client_instance.close.assert_called_once()
        mock_pwd_client_instance.close.assert_called_once()

    @patch('paramiko.SSHClient')
    def test_ssh_connectivity_pk_failed_no_password_configured(self, mock_ssh_client_constructor):
        """Test error when public key auth fails and no password is configured."""
        # Arrange
        mock_client_instance = MagicMock()
        mock_ssh_client_constructor.return_value = mock_client_instance

        auth_exception = paramiko.AuthenticationException("Public key auth failed")
        mock_client_instance.connect.side_effect = auth_exception

        config = {"host": "proxmox.example.com", "user": "test"}  # No password

        # Act
        result = check_proxmox_ssh_connectivity(config)

        # Assert
        assert result["success"] is False
        assert result["connection_established"] is False
        assert result["server_allows_publickey_auth"] is True # PK Auth failed, so offered
        assert result["server_allows_password_auth"] is False # Not attempted
        assert result["auth_method_used"] is None
        assert "SSH public key authentication failed" in result["error"]
        assert "No password was configured" in result["error"]
        assert result["warning"] is None

        mock_ssh_client_constructor.assert_called_once()
        mock_client_instance.close.assert_called_once()

    @patch('paramiko.SSHClient')
    def test_ssh_connectivity_connection_socket_error_on_pk_attempt(self, mock_ssh_client_constructor):
        """Test SSH connection failure (e.g., socket error) during PK attempt."""
        # Arrange
        mock_client_instance = MagicMock()
        mock_ssh_client_constructor.return_value = mock_client_instance

        connection_error = socket.error("Connection refused") # More specific
        mock_client_instance.connect.side_effect = connection_error

        config = {"host": "nonexistent.example.com", "password": "somepassword"} # Password won't be tried

        # Act
        result = check_proxmox_ssh_connectivity(config)

        # Assert
        assert result["success"] is False
        assert result["connection_established"] is False
        assert result["server_allows_publickey_auth"] is False # Connection failed before auth protocol
        assert result["server_allows_password_auth"] is False # Not attempted
        assert result["auth_method_used"] is None
        assert "SSH connection to root@nonexistent.example.com:22 failed: Connection refused" in result["error"]
        assert result["warning"] is None

        mock_ssh_client_constructor.assert_called_once() # Only one attempt for PK
        mock_client_instance.close.assert_called_once() # Should still be closed

    @patch('paramiko.SSHClient')
    def test_ssh_connectivity_connection_ssh_exception_on_pk_attempt(self, mock_ssh_client_constructor):
        """Test SSH connection failure (e.g., SSHException) during PK attempt."""
        # Arrange
        mock_client_instance = MagicMock()
        mock_ssh_client_constructor.return_value = mock_client_instance

        # Example: NoValidConnectionsError is a subclass of SSHException
        connection_error = paramiko.ssh_exception.NoValidConnectionsError({('host', 22): socket.error("Network is unreachable")})
        mock_client_instance.connect.side_effect = connection_error

        config = {"host": "unreachable.example.com", "password": "somepassword"} # Password won't be tried

        # Act
        result = check_proxmox_ssh_connectivity(config)

        # Assert
        assert result["success"] is False
        assert result["connection_established"] is False
        assert result["server_allows_publickey_auth"] is False
        assert result["server_allows_password_auth"] is False
        assert result["auth_method_used"] is None
        assert "SSH connection to root@unreachable.example.com:22 failed" in result["error"]
        assert "Unable to connect to port 22" in result["error"]

        mock_ssh_client_constructor.assert_called_once()
        mock_client_instance.close.assert_called_once()


    def test_ssh_connectivity_missing_host_config(self):
        """Test ConfigurationError when host is missing from config."""
        # Arrange
        config = {}  # Missing host

        # Act & Assert
        with pytest.raises(ConfigurationError, match="Proxmox host must be configured"):
            check_proxmox_ssh_connectivity(config)

    @patch('paramiko.SSHClient')
    def test_ssh_connectivity_custom_port_and_timeout_pk_success(self, mock_ssh_client_constructor):
        """Test SSH connectivity with custom port and timeout, PK success."""
        # Arrange
        mock_client_instance = MagicMock()
        mock_ssh_client_constructor.return_value = mock_client_instance
        mock_client_instance.connect.return_value = None

        config = {"host": "proxmox.example.com"}

        # Act
        result = check_proxmox_ssh_connectivity(config, port=2222, timeout=30)

        # Assert
        assert result["port"] == 2222
        assert result["success"] is True
        assert result["auth_method_used"] == "publickey"

        mock_client_instance.connect.assert_called_once_with(
            hostname="proxmox.example.com",
            port=2222,
            username="root", # Default user
            allow_agent=True,
            look_for_keys=True,
            timeout=30,
            auth_timeout=30
        )

    @patch('paramiko.SSHClient')
    def test_ssh_connectivity_client_close_on_exception_pk_attempt(self, mock_ssh_client_constructor):
        """Test that SSH client is properly closed even when exceptions occur during PK attempt."""
        # Arrange
        mock_client_instance = MagicMock()
        mock_ssh_client_constructor.return_value = mock_client_instance
        mock_client_instance.connect.side_effect = paramiko.AuthenticationException("PK Failed")

        config = {"host": "proxmox.example.com"} # No password, so only PK attempt

        # Act
        result = check_proxmox_ssh_connectivity(config)

        # Assert
        assert result["success"] is False
        assert "SSH public key authentication failed" in result["error"]
        mock_client_instance.close.assert_called_once() # Crucial: close should be called

    @patch('paramiko.SSHClient')
    def test_ssh_connectivity_client_close_on_exception_pwd_attempt(self, mock_ssh_client_constructor):
        """Test that SSH clients are closed when exceptions occur during PWD attempt."""
        # Arrange
        mock_pk_client_instance = MagicMock(name="PKClient")
        mock_pwd_client_instance = MagicMock(name="PWDClient")
        mock_ssh_client_constructor.side_effect = [mock_pk_client_instance, mock_pwd_client_instance]

        mock_pk_client_instance.connect.side_effect = paramiko.AuthenticationException("PK Auth Failed")
        mock_pwd_client_instance.connect.side_effect = paramiko.AuthenticationException("PWD Auth Failed")

        config = {"host": "proxmox.example.com", "password": "pwd"}

        # Act
        result = check_proxmox_ssh_connectivity(config)

        # Assert
        assert result["success"] is False
        assert "Both public key and password SSH authentication failed" in result["error"]
        mock_pk_client_instance.close.assert_called_once()
        mock_pwd_client_instance.close.assert_called_once()
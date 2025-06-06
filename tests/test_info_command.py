# file: tests/test_info_command.py
"""Unit tests for the info command implementation."""

from unittest.mock import MagicMock, patch

import pytest

from k3s_deploy_cli.commands.info_command import (
    _display_cluster_overview,
    _display_configured_nodes,
    _display_k3s_vm_information,
    _display_k3s_vms_table,
    _display_nodes_table,
    _display_tag_based_k3s_vms,
    _get_vm_info_by_vmid,
    handle_info_command,
)
from k3s_deploy_cli.exceptions import ConfigurationError, ProxmoxInteractionError


class TestHandleInfoCommand:
    """Tests for the main handle_info_command function."""

    @patch('k3s_deploy_cli.commands.info_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.info_command.get_proxmox_version_info')
    @patch('k3s_deploy_cli.commands.info_command.get_cluster_status')
    @patch('k3s_deploy_cli.commands.info_command._display_cluster_overview')
    @patch('k3s_deploy_cli.commands.info_command._display_nodes_table')
    @patch('k3s_deploy_cli.commands.info_command._display_k3s_vm_information')
    def test_handle_info_command_happy_path(self, mock_display_k3s, mock_display_nodes, 
                                          mock_display_cluster, mock_get_cluster_status,
                                          mock_get_version_info, mock_get_api_client,
                                          basic_proxmox_config, mock_console, mock_proxmox_client):
        """Test successful info command execution."""
        # Arrange - Use shared fixtures
        mock_get_api_client.return_value = mock_proxmox_client
        
        mock_version_info = {'version': '7.4', 'release': '1'}
        mock_get_version_info.return_value = mock_version_info
        
        mock_cluster_status = [
            {'type': 'cluster', 'name': 'test-cluster', 'quorate': 1},
            {'type': 'node', 'name': 'node1', 'online': 1},
            {'type': 'node', 'name': 'node2', 'online': 1}
        ]
        mock_get_cluster_status.return_value = mock_cluster_status

        # Act
        handle_info_command(basic_proxmox_config, mock_console, discover=False)

        # Assert
        mock_get_api_client.assert_called_once_with(basic_proxmox_config['proxmox'])
        mock_get_version_info.assert_called_once_with(mock_proxmox_client)
        mock_get_cluster_status.assert_called_once_with(mock_proxmox_client)
        mock_display_cluster.assert_called_once()
        mock_display_nodes.assert_called_once()
        mock_display_k3s.assert_called_once()

    def test_handle_info_command_missing_proxmox_config(self, mock_console):
        """Test info command with missing Proxmox configuration."""
        # Arrange - Use empty config
        config = {}  # Missing proxmox section

        # Act & Assert
        with pytest.raises(ConfigurationError) as exc_info:
            handle_info_command(config, mock_console)
        
        assert "Proxmox configuration is missing" in str(exc_info.value)

    @patch('k3s_deploy_cli.commands.info_command.get_proxmox_api_client')
    def test_handle_info_command_proxmox_connection_failure(self, mock_get_api_client, basic_proxmox_config, mock_console):
        """Test info command with Proxmox connection failure."""
        # Arrange - Use basic config and mock connection failure
        mock_get_api_client.side_effect = ProxmoxInteractionError("Connection failed")

        # Act & Assert
        with pytest.raises(ProxmoxInteractionError):
            handle_info_command(basic_proxmox_config, mock_console)

    @patch('k3s_deploy_cli.commands.info_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.info_command.get_cluster_status')
    def test_handle_info_command_empty_cluster_status(self, mock_get_cluster_status, mock_get_api_client, 
                                                     basic_proxmox_config, mock_console, mock_proxmox_client):
        """Test info command with empty cluster status."""
        # Arrange - Use shared fixtures
        mock_get_api_client.return_value = mock_proxmox_client
        mock_get_cluster_status.return_value = []

        # Act
        handle_info_command(basic_proxmox_config, mock_console)

        # Assert
        mock_console.print.assert_called_with(
            "Could not retrieve cluster status or cluster status is empty (no nodes found)."
        )

    @patch('k3s_deploy_cli.commands.info_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.info_command.get_proxmox_version_info')
    @patch('k3s_deploy_cli.commands.info_command.get_cluster_status')
    @patch('k3s_deploy_cli.commands.info_command.get_node_dns_info')
    @patch('k3s_deploy_cli.commands.info_command._display_k3s_vm_information')
    def test_handle_info_command_discover_flag(self, mock_display_k3s, mock_get_dns_info, mock_get_cluster_status,
                                             mock_get_version_info, mock_get_api_client,
                                             basic_proxmox_config, mock_console, mock_proxmox_client, sample_version_info):
        """Test info command with discover flag."""
        # Arrange - Use shared fixtures
        mock_get_api_client.return_value = mock_proxmox_client
        mock_get_version_info.return_value = sample_version_info
        mock_get_cluster_status.return_value = [
            {'type': 'cluster', 'name': 'test'},
            {'type': 'node', 'name': 'node1'}
        ]
        mock_get_dns_info.return_value = 'example.com'

        # Act
        handle_info_command(basic_proxmox_config, mock_console, discover=True)

        # Assert - Verify discover=True is passed through
        mock_display_k3s.assert_called_once()
        args, kwargs = mock_display_k3s.call_args
        assert len(args) >= 5  # Check we have enough arguments
        assert args[4] is True  # discover parameter


class TestDisplayClusterOverview:
    """Tests for the _display_cluster_overview function."""

    @patch('k3s_deploy_cli.commands.info_command.check_proxmox_ssh_connectivity')
    def test_display_cluster_overview_with_cluster_info(self, mock_ssh_check, mock_console, sample_version_info):
        """Test cluster overview display with cluster information."""
        # Arrange - Use shared fixtures
        cluster_info = {'name': 'test-cluster', 'quorate': 1, 'nodes': 3}
        proxmox_cfg = {'host': 'proxmox.example.com'}
        mock_ssh_check.return_value = {'success': True, 'connection_established': True}

        # Act
        _display_cluster_overview(mock_console, cluster_info, sample_version_info, proxmox_cfg)

        # Assert
        assert mock_console.print.call_count >= 1

    @patch('k3s_deploy_cli.commands.info_command.check_proxmox_ssh_connectivity')
    def test_display_cluster_overview_without_cluster_info(self, mock_ssh_check, mock_console, sample_version_info):
        """Test cluster overview display without cluster information."""
        # Arrange - Use shared fixtures
        cluster_info = None
        proxmox_cfg = {'host': 'proxmox.example.com'}
        mock_ssh_check.return_value = {'success': False, 'connection_established': False}

        # Act
        _display_cluster_overview(mock_console, cluster_info, sample_version_info, proxmox_cfg)

        # Assert
        mock_console.print.assert_called()


class TestDisplayNodesTable:
    """Tests for the _display_nodes_table function."""

    @patch('k3s_deploy_cli.commands.info_command.get_node_dns_info')
    def test_display_nodes_table_successful(self, mock_get_dns_info, mock_console, mock_proxmox_client, basic_proxmox_config):
        """Test successful nodes table display."""
        # Arrange - Use shared fixtures
        nodes_data = [
            {'name': 'node1', 'status': 'online', 'local': 1, 'online': 1, 'ip': '192.168.1.10'},
            {'name': 'node2', 'status': 'online', 'local': 0, 'online': 1, 'ip': '192.168.1.11'}
        ]
        mock_get_dns_info.return_value = 'example.com'

        # Act
        _display_nodes_table(mock_console, nodes_data, mock_proxmox_client, basic_proxmox_config)

        # Assert
        mock_console.print.assert_called()
        assert mock_get_dns_info.call_count == 2  # Called for each node

    @patch('k3s_deploy_cli.commands.info_command.get_node_dns_info')
    def test_display_nodes_table_dns_failure(self, mock_get_dns_info, mock_console, mock_proxmox_client, basic_proxmox_config):
        """Test nodes table display with DNS lookup failure."""
        # Arrange - Use shared fixtures
        nodes_data = [{'name': 'node1', 'status': 'online', 'local': 1, 'online': 1, 'ip': '192.168.1.10'}]
        mock_get_dns_info.side_effect = Exception("DNS lookup failed")

        # Act - Should not raise exception, should handle gracefully
        _display_nodes_table(mock_console, nodes_data, mock_proxmox_client, basic_proxmox_config)

        # Assert
        mock_console.print.assert_called()  # Should still display table with "N/A"
        mock_get_dns_info.assert_called_once_with(mock_proxmox_client, 'node1')

    def test_display_nodes_table_empty_nodes(self, mock_console, mock_proxmox_client, basic_proxmox_config):
        """Test nodes table display with empty nodes list."""
        # Arrange - Use shared fixtures
        nodes_data = []

        # Act
        _display_nodes_table(mock_console, nodes_data, mock_proxmox_client, basic_proxmox_config)

        # Assert
        mock_console.print.assert_called()


class TestDisplayK3sVmInformation:
    """Tests for the _display_k3s_vm_information function."""

    @patch('k3s_deploy_cli.commands.info_command._display_tag_based_k3s_vms')
    def test_display_k3s_vm_information_discover_mode(self, mock_display_tag_based, mock_console, mock_proxmox_client):
        """Test K3s VM information display in discover mode."""
        # Arrange - Use shared fixtures
        config = {'nodes': [{'vmid': 100}]}
        nodes_data = [{'name': 'node1'}]

        # Act
        _display_k3s_vm_information(mock_console, config, mock_proxmox_client, nodes_data, discover=True)

        # Assert
        mock_display_tag_based.assert_called_once_with(mock_console, mock_proxmox_client, nodes_data, True, [{'vmid': 100}])

    @patch('k3s_deploy_cli.commands.info_command._display_configured_nodes')
    def test_display_k3s_vm_information_configured_nodes(self, mock_display_configured, mock_console, mock_proxmox_client):
        """Test K3s VM information display with configured nodes."""
        # Arrange - Use shared fixtures
        config = {'nodes': [{'vmid': 100, 'role': 'server'}]}
        nodes_data = [{'name': 'node1'}]

        # Act
        _display_k3s_vm_information(mock_console, config, mock_proxmox_client, nodes_data, discover=False)

        # Assert
        mock_display_configured.assert_called_once()

    @patch('k3s_deploy_cli.commands.info_command._display_tag_based_k3s_vms')
    def test_display_k3s_vm_information_fallback_to_discovery(self, mock_display_tag_based, mock_console, mock_proxmox_client):
        """Test K3s VM information display fallback to discovery mode."""
        # Arrange - Use shared fixtures
        config = {}  # No nodes configured
        nodes_data = [{'name': 'node1'}]

        # Act
        _display_k3s_vm_information(mock_console, config, mock_proxmox_client, nodes_data, discover=False)

        # Assert
        mock_display_tag_based.assert_called_once_with(mock_console, mock_proxmox_client, nodes_data, False, [])


class TestDisplayTagBasedK3sVms:
    """Tests for the _display_tag_based_k3s_vms function."""

    @patch('k3s_deploy_cli.commands.info_command.get_vms_with_k3s_tags')
    @patch('k3s_deploy_cli.commands.info_command._display_k3s_vms_table')
    def test_display_tag_based_k3s_vms_with_vms(self, mock_display_table, mock_get_vms, mock_console, mock_proxmox_client, sample_vm_list):
        """Test tag-based K3s VMs display with VMs found."""
        # Arrange - Use shared fixtures
        nodes_data = [{"name": "node1", "online": 1}]
        discover = True
        configured_nodes = []
        mock_get_vms.return_value = sample_vm_list

        # Act
        _display_tag_based_k3s_vms(mock_console, mock_proxmox_client, nodes_data, discover, configured_nodes)

        # Assert
        mock_get_vms.assert_called_once_with(mock_proxmox_client, "node1")
        mock_display_table.assert_called_once_with(mock_console, sample_vm_list)

    @patch('k3s_deploy_cli.commands.info_command.get_vms_with_k3s_tags')
    def test_display_tag_based_k3s_vms_no_vms_found(self, mock_get_vms, mock_console, mock_proxmox_client):
        """Test tag-based K3s VMs display with no VMs found."""
        # Arrange - Use shared fixtures
        nodes_data = [{"name": "node1", "online": 1}]
        discover = True
        configured_nodes = []
        mock_get_vms.return_value = []

        # Act
        _display_tag_based_k3s_vms(mock_console, mock_proxmox_client, nodes_data, discover, configured_nodes)

        # Assert
        mock_get_vms.assert_called_once_with(mock_proxmox_client, "node1")
        mock_console.print.assert_called()  # Should print "no VMs found" message

    @patch('k3s_deploy_cli.commands.info_command.get_vms_with_k3s_tags')
    def test_display_tag_based_k3s_vms_api_error(self, mock_get_vms, mock_console, mock_proxmox_client):
        """Test tag-based K3s VMs display with API error."""
        # Arrange - Use shared fixtures
        nodes_data = [{"name": "node1", "online": 1}]
        discover = True
        configured_nodes = []
        mock_get_vms.side_effect = ProxmoxInteractionError("API error")

        # Act
        _display_tag_based_k3s_vms(mock_console, mock_proxmox_client, nodes_data, discover, configured_nodes)

        # Assert - Should not raise but handle error gracefully
        mock_console.print.assert_called()


class TestDisplayConfiguredNodes:
    """Tests for the _display_configured_nodes function."""

    @patch('k3s_deploy_cli.commands.info_command._get_vm_info_by_vmid')
    def test_display_configured_nodes_successful(self, mock_get_vm_info, mock_console, mock_proxmox_client):
        """Test successful display of configured nodes."""
        # Arrange - Use shared fixtures
        config = {
            'nodes': [
                {'vmid': 100, 'role': 'server'},
                {'vmid': 101, 'role': 'agent'}
            ]
        }
        
        mock_vm_info_1 = {'vmid': 100, 'name': 'k3s-server-1', 'status': 'running', 'node': 'node1'}
        mock_vm_info_2 = {'vmid': 101, 'name': 'k3s-agent-1', 'status': 'running', 'node': 'node2'}
        mock_get_vm_info.side_effect = [mock_vm_info_1, mock_vm_info_2]

        # Act
        _display_configured_nodes(config, mock_proxmox_client, mock_console)

        # Assert
        assert mock_get_vm_info.call_count == 2
        mock_console.print.assert_called()  # Should print the configuration table

    @patch('k3s_deploy_cli.commands.info_command._get_vm_info_by_vmid')
    def test_display_configured_nodes_vm_not_found(self, mock_get_vm_info, mock_console, mock_proxmox_client):
        """Test display of configured nodes when VM is not found."""
        # Arrange - Use shared fixtures
        config = {'nodes': [{'vmid': 999, 'role': 'server'}]}
        mock_get_vm_info.return_value = None

        # Act
        _display_configured_nodes(config, mock_proxmox_client, mock_console)

        # Assert
        mock_get_vm_info.assert_called_once()
        # Should still attempt to display table with available data


class TestDisplayK3sVmsTable:
    """Tests for the _display_k3s_vms_table function."""

    def test_display_k3s_vms_table_with_vms(self, mock_console):
        """Test K3s VMs table display with VMs."""
        # Arrange - Use shared fixtures
        vms_data = [
            {'vmid': 100, 'name': 'k3s-server-1', 'status': 'running', 'node': 'node1', 'role': 'server'},
            {'vmid': 101, 'name': 'k3s-agent-1', 'status': 'stopped', 'node': 'node2', 'role': 'agent'}
        ]

        # Act
        _display_k3s_vms_table(mock_console, vms_data)

        # Assert
        mock_console.print.assert_called()

    def test_display_k3s_vms_table_empty_list(self, mock_console):
        """Test K3s VMs table display with empty list."""
        # Arrange - Use shared fixtures
        vms_data = []

        # Act
        _display_k3s_vms_table(mock_console, vms_data)

        # Assert
        mock_console.print.assert_called()


class TestGetVmInfoByVmid:
    """Tests for the _get_vm_info_by_vmid function."""

    @patch('k3s_deploy_cli.commands.info_command.get_cluster_status')
    def test_get_vm_info_by_vmid_found(self, mock_get_cluster_status):
        """Test getting VM info when VM is found."""
        # Arrange
        proxmox_client = MagicMock()
        vmid = 100
        
        # Mock cluster status response
        mock_get_cluster_status.return_value = [
            {'type': 'cluster', 'name': 'test-cluster'},
            {'type': 'node', 'name': 'node1', 'online': 1},
            {'type': 'node', 'name': 'node2', 'online': 1}
        ]
        
        # Mock VM found on node2
        node1_mock = MagicMock()
        node1_mock.qemu.get.return_value = []  # No VMs on node1
        
        node2_mock = MagicMock()
        node2_mock.qemu.get.return_value = [
            {'vmid': 100, 'name': 'test-vm', 'status': 'running'}
        ]
        
        proxmox_client.nodes.side_effect = lambda name: node1_mock if name == 'node1' else node2_mock

        # Act
        result = _get_vm_info_by_vmid(proxmox_client, vmid)

        # Assert
        assert result is not None
        assert result['vmid'] == 100
        assert result['name'] == 'test-vm'
        assert result['node'] == 'node2'

    @patch('k3s_deploy_cli.commands.info_command.get_cluster_status')
    def test_get_vm_info_by_vmid_not_found(self, mock_get_cluster_status):
        """Test getting VM info when VM is not found."""
        # Arrange
        proxmox_client = MagicMock()
        vmid = 999
        
        # Mock cluster status response
        mock_get_cluster_status.return_value = [
            {'type': 'node', 'name': 'node1', 'online': 1}
        ]
        
        # Mock VM not found
        node_mock = MagicMock()
        node_mock.qemu.get.return_value = []  # No VMs found
        proxmox_client.nodes.return_value = node_mock

        # Act
        result = _get_vm_info_by_vmid(proxmox_client, vmid)

        # Assert
        assert result is None

    @patch('k3s_deploy_cli.commands.info_command.get_cluster_status')
    def test_get_vm_info_by_vmid_api_error(self, mock_get_cluster_status):
        """Test getting VM info with API error."""
        # Arrange
        proxmox_client = MagicMock()
        vmid = 100
        
        # Mock API error at cluster level
        mock_get_cluster_status.side_effect = ProxmoxInteractionError("API error")

        # Act & Assert
        with pytest.raises(ProxmoxInteractionError):
            _get_vm_info_by_vmid(proxmox_client, vmid)


class TestInfoCommandIntegration:
    """Integration-style tests for the info command."""

    @patch('k3s_deploy_cli.commands.info_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.info_command.get_proxmox_version_info')
    @patch('k3s_deploy_cli.commands.info_command.get_cluster_status')
    @patch('k3s_deploy_cli.commands.info_command.get_node_dns_info')
    @patch('k3s_deploy_cli.commands.info_command.get_vms_with_k3s_tags')
    def test_info_command_full_flow_tag_discovery(self, mock_get_vms, mock_get_dns_info, mock_get_cluster_status,
                                                 mock_get_version_info, mock_get_api_client,
                                                 basic_proxmox_config, mock_console, mock_proxmox_client, 
                                                 sample_version_info, sample_cluster_status, sample_vm_list):
        """Test complete info command flow with tag-based discovery."""
        # Arrange - Use shared fixtures
        mock_get_api_client.return_value = mock_proxmox_client
        mock_get_version_info.return_value = sample_version_info
        mock_get_cluster_status.return_value = sample_cluster_status
        mock_get_dns_info.return_value = 'example.com'  # Return string instead of MagicMock
        mock_get_vms.return_value = sample_vm_list

        # Act
        handle_info_command(basic_proxmox_config, mock_console, discover=True)

        # Assert - Verify all major components were called
        mock_get_api_client.assert_called_once()
        mock_get_version_info.assert_called_once()
        mock_get_cluster_status.assert_called_once()
        # get_vms_with_k3s_tags should be called once per online node (node1 and node2)
        assert mock_get_vms.call_count == 2
        mock_get_vms.assert_any_call(mock_proxmox_client, 'node1')
        mock_get_vms.assert_any_call(mock_proxmox_client, 'node2')
        
        # Verify console output was generated
        assert mock_console.print.call_count > 0

    @patch('k3s_deploy_cli.commands.info_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.info_command.get_proxmox_version_info')
    @patch('k3s_deploy_cli.commands.info_command.get_cluster_status')
    @patch('k3s_deploy_cli.commands.info_command.get_node_dns_info')
    def test_info_command_full_flow_configured_nodes(self, mock_get_dns_info, mock_get_cluster_status,
                                                   mock_get_version_info, mock_get_api_client,
                                                   full_config, mock_console, mock_proxmox_client, sample_version_info):
        """Test complete info command flow with configured nodes."""
        # Arrange - Use shared fixtures
        mock_get_api_client.return_value = mock_proxmox_client
        mock_get_version_info.return_value = sample_version_info
        mock_get_cluster_status.return_value = [
            {'type': 'cluster', 'name': 'test-cluster'},
            {'type': 'node', 'name': 'node1', 'online': 1, 'local': 1}  # Added online: 1
        ]
        mock_get_dns_info.return_value = 'example.com'  # Return string instead of MagicMock
        
        # Mock VM lookup for configured node
        mock_proxmox_client.nodes.get.return_value.qemu.get.return_value = [
            {'vmid': 100, 'name': 'k3s-server-1', 'status': 'running'}
        ]

        # Act
        handle_info_command(full_config, mock_console, discover=False)

        # Assert
        mock_get_api_client.assert_called_once()
        mock_get_version_info.assert_called_once()
        # Don't assert call count for get_cluster_status since it's called by multiple functions
        assert mock_console.print.call_count > 0


class TestNodesTableWithSnippetStorage:
    """Tests for the nodes table with snippet storage information."""
    
    @patch('k3s_deploy_cli.commands.info_command.get_node_dns_info')
    @patch('k3s_deploy_cli.commands.info_command.get_node_snippet_storage')
    def test_display_nodes_table_with_snippet_storage(self, mock_get_snippet_storage, 
                                                     mock_get_dns_info, mock_console, 
                                                     mock_proxmox_client, basic_proxmox_config):
        """Test nodes table displays snippet storage information correctly."""
        # Arrange
        nodes_data = [
            {
                "name": "pve-node1",
                "local": 1,
                "online": 1,
                "ip": "192.168.1.10"
            },
            {
                "name": "pve-node2", 
                "local": 0,
                "online": 1,
                "ip": "192.168.1.11"
            }
        ]
        
        # Mock DNS info
        mock_get_dns_info.side_effect = ["example.local", "N/A"]
        
        # Mock snippet storage info - node1 has snippets, node2 doesn't
        mock_get_snippet_storage.side_effect = [
            {
                "storage_name": "local",
                "enabled": True,
                "active": True,
                "type": "dir"
            },
            {}  # No snippet storage
        ]
        
        # Act
        _display_nodes_table(mock_console, nodes_data, mock_proxmox_client, basic_proxmox_config)
        
        # Assert
        mock_console.print.assert_called_once()
        
        # Verify snippet storage function was called for each node
        assert mock_get_snippet_storage.call_count == 2
        mock_get_snippet_storage.assert_any_call(mock_proxmox_client, "pve-node1")
        mock_get_snippet_storage.assert_any_call(mock_proxmox_client, "pve-node2")
        
        # Check that table was created with snippet storage column
        # Note: We can't easily test the exact table content without more complex mocking
        # but we can verify the function was called and no exceptions were raised
    
    @patch('k3s_deploy_cli.commands.info_command.get_node_dns_info')
    @patch('k3s_deploy_cli.commands.info_command.get_node_snippet_storage')
    def test_display_nodes_table_snippet_storage_error_handling(self, mock_get_snippet_storage,
                                                               mock_get_dns_info, mock_console,
                                                               mock_proxmox_client, basic_proxmox_config):
        """Test nodes table handles snippet storage errors gracefully."""
        # Arrange
        nodes_data = [
            {
                "name": "pve-node1",
                "local": 1,
                "online": 1,
                "ip": "192.168.1.10"
            }
        ]
        
        # Mock DNS info success
        mock_get_dns_info.return_value = "example.local"
        
        # Mock snippet storage error
        mock_get_snippet_storage.side_effect = ProxmoxInteractionError("API error")
        
        # Act - Should not raise exception
        _display_nodes_table(mock_console, nodes_data, mock_proxmox_client, basic_proxmox_config)
        
        # Assert
        mock_console.print.assert_called_once()
        mock_get_snippet_storage.assert_called_once_with(mock_proxmox_client, "pve-node1")
        
        # Verify error was logged but execution continued
        # (The actual implementation should show "Error" or "N/A" in the snippet storage column)
    
    @patch('k3s_deploy_cli.commands.info_command.get_node_dns_info')
    @patch('k3s_deploy_cli.commands.info_command.get_node_snippet_storage')
    def test_display_nodes_table_multiple_snippet_storages(self, mock_get_snippet_storage,
                                                          mock_get_dns_info,
                                                          mock_console, mock_proxmox_client, basic_proxmox_config):
        """Test nodes table handles multiple snippet storages correctly."""
        # Arrange
        nodes_data = [
            {
                "name": "pve-node1",
                "local": 1,
                "online": 1,
                "ip": "192.168.1.10"
            },
            {
                "name": "pve-node2",
                "local": 0,
                "online": 1,
                "ip": "192.168.1.11"
            }
        ]
        
        # Mock DNS info
        mock_get_dns_info.side_effect = ["example.local", "other.local"]
        
        # Mock different snippet storage scenarios
        mock_get_snippet_storage.side_effect = [
            {
                "storage_name": "local",
                "enabled": True,
                "active": True,
                "type": "dir"
            },
            {
                "storage_name": "snippets-nfs",
                "enabled": True,
                "active": True,
                "type": "nfs"
            }
        ]
        
        # Act
        _display_nodes_table(mock_console, nodes_data, mock_proxmox_client, basic_proxmox_config)
        
        # Assert
        mock_console.print.assert_called_once()
        assert mock_get_snippet_storage.call_count == 2
        
        # Verify both nodes were checked for snippet storage
        mock_get_snippet_storage.assert_any_call(mock_proxmox_client, "pve-node1")
        mock_get_snippet_storage.assert_any_call(mock_proxmox_client, "pve-node2")

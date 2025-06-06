# file: tests/test_discover_command.py
"""Unit tests for the discover command implementation."""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest
from rich.console import Console

from k3s_deploy_cli.commands.discover_command import (
    _handle_json_output,
    _handle_table_output,
    _update_config_file_with_nodes,
    handle_discover_command,
)
from k3s_deploy_cli.exceptions import ConfigurationError, ProxmoxInteractionError


class TestHandleDiscoverCommand:
    """Tests for the main handle_discover_command function."""

    @patch('k3s_deploy_cli.commands.discover_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.discover_command.discover_k3s_nodes')
    @patch('k3s_deploy_cli.commands.discover_command._handle_table_output')
    def test_handle_discover_command_table_output_happy_path(self, mock_handle_table, 
                                                           mock_discover_nodes, mock_get_api_client,
                                                           basic_proxmox_config, mock_console, mock_proxmox_client):
        """Test successful discover command with table output."""
        # Arrange - Use shared fixtures
        mock_get_api_client.return_value = mock_proxmox_client
        
        mock_discovered_nodes = [
            {'vmid': 100, 'name': 'k3s-server-1', 'role': 'server', 'node': 'node1', 'status': 'running'},
            {'vmid': 101, 'name': 'k3s-agent-1', 'role': 'agent', 'node': 'node2', 'status': 'running'}
        ]
        mock_discover_nodes.return_value = mock_discovered_nodes

        # Act
        handle_discover_command(basic_proxmox_config, mock_console, output_format="table", output_target="stdout")

        # Assert
        mock_get_api_client.assert_called_once_with(basic_proxmox_config['proxmox'])
        mock_discover_nodes.assert_called_once_with(mock_proxmox_client)
        mock_handle_table.assert_called_once_with(mock_discovered_nodes, mock_console, "stdout")

    @patch('k3s_deploy_cli.commands.discover_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.discover_command.discover_k3s_nodes')
    @patch('k3s_deploy_cli.commands.discover_command._handle_json_output')
    def test_handle_discover_command_json_output_happy_path(self, mock_handle_json,
                                                          mock_discover_nodes, mock_get_api_client,
                                                          basic_proxmox_config, mock_console, mock_proxmox_client):
        """Test successful discover command with JSON output."""
        # Arrange - Use shared fixtures
        mock_get_api_client.return_value = mock_proxmox_client
        mock_discovered_nodes = [{'vmid': 100, 'name': 'test-vm'}]
        mock_discover_nodes.return_value = mock_discovered_nodes

        # Act
        handle_discover_command(basic_proxmox_config, mock_console, output_format="json", output_target="file")

        # Assert
        mock_handle_json.assert_called_once_with(mock_discovered_nodes, mock_console, "file")

    def test_handle_discover_command_missing_proxmox_config(self, mock_console):
        """Test discover command with missing Proxmox configuration."""
        # Arrange - Use shared fixtures
        config = {}  # Missing proxmox section

        # Act & Assert
        with pytest.raises(ConfigurationError) as exc_info:
            handle_discover_command(config, mock_console)
        
        assert "Proxmox configuration is missing" in str(exc_info.value)

    @patch('k3s_deploy_cli.commands.discover_command.get_proxmox_api_client')
    def test_handle_discover_command_proxmox_connection_failure(self, mock_get_api_client, basic_proxmox_config, mock_console):
        """Test discover command with Proxmox connection failure."""
        # Arrange - Use shared fixtures
        mock_get_api_client.side_effect = ProxmoxInteractionError("Connection failed")

        # Act & Assert
        with pytest.raises(ProxmoxInteractionError):
            handle_discover_command(basic_proxmox_config, mock_console)

    @patch('k3s_deploy_cli.commands.discover_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.discover_command.discover_k3s_nodes')
    def test_handle_discover_command_no_nodes_found(self, mock_discover_nodes, mock_get_api_client, 
                                                   basic_proxmox_config, mock_console, mock_proxmox_client):
        """Test discover command when no K3s nodes are found."""
        # Arrange - Use shared fixtures
        mock_get_api_client.return_value = mock_proxmox_client
        mock_discover_nodes.return_value = []  # No nodes found

        # Act
        handle_discover_command(basic_proxmox_config, mock_console)

        # Assert
        mock_console.print.assert_called()  # Should print "no VMs found" message

    @patch('k3s_deploy_cli.commands.discover_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.discover_command.discover_k3s_nodes')
    def test_handle_discover_command_api_error_during_discovery(self, mock_discover_nodes, mock_get_api_client,
                                                              basic_proxmox_config, mock_console, mock_proxmox_client):
        """Test discover command with API error during node discovery."""
        # Arrange - Use shared fixtures
        mock_get_api_client.return_value = mock_proxmox_client
        mock_discover_nodes.side_effect = ProxmoxInteractionError("API error during discovery")

        # Act & Assert
        with pytest.raises(ProxmoxInteractionError):
            handle_discover_command(basic_proxmox_config, mock_console)


class TestHandleJsonOutput:
    """Tests for the _handle_json_output function."""

    def test_handle_json_output_stdout(self, mock_console):
        """Test JSON output to stdout."""
        # Arrange - Use shared fixtures
        discovered_nodes = [
            {'vmid': 100, 'name': 'k3s-server-1', 'role': 'server'},
            {'vmid': 101, 'name': 'k3s-agent-1', 'role': 'agent'}
        ]

        # Act
        _handle_json_output(discovered_nodes, mock_console, "stdout")

        # Assert
        mock_console.print.assert_called()
        # Verify JSON content was printed (check call arguments)
        print_calls = mock_console.print.call_args_list
        assert len(print_calls) > 0

    @patch('k3s_deploy_cli.commands.discover_command._update_config_file_with_nodes')
    def test_handle_json_output_file(self, mock_update_config, mock_console):
        """Test JSON output to file."""
        # Arrange - Use shared fixtures
        discovered_nodes = [{'vmid': 100, 'name': 'test-vm', 'role': 'server'}]

        # Act
        _handle_json_output(discovered_nodes, mock_console, "file")

        # Assert
        expected_config_nodes = [{'vmid': 100, 'role': 'server'}]
        mock_update_config.assert_called_once_with(expected_config_nodes, mock_console)

    def test_handle_json_output_empty_nodes(self, mock_console):
        """Test JSON output with empty nodes list."""
        # Arrange - Use shared fixtures
        discovered_nodes = []

        # Act
        _handle_json_output(discovered_nodes, mock_console, "stdout")

        # Assert
        mock_console.print.assert_called()


class TestHandleTableOutput:
    """Tests for the _handle_table_output function."""

    def test_handle_table_output_with_nodes(self, mock_console):
        """Test table output with discovered nodes."""
        # Arrange - Use shared fixtures
        discovered_nodes = [
            {'vmid': 100, 'name': 'k3s-server-1', 'role': 'server', 'node': 'node1', 'status': 'running'},
            {'vmid': 101, 'name': 'k3s-agent-1', 'role': 'agent', 'node': 'node2', 'status': 'stopped'}
        ]

        # Act
        _handle_table_output(discovered_nodes, mock_console, "stdout")

        # Assert
        assert mock_console.print.call_count >= 3  # Table + 2 info messages

    def test_handle_table_output_empty_nodes(self, mock_console):
        """Test table output with empty nodes list."""
        # Arrange - Use shared fixtures
        discovered_nodes = []

        # Act
        _handle_table_output(discovered_nodes, mock_console, "stdout")

        # Assert
        mock_console.print.assert_called()  # Should still print empty table

    def test_handle_table_output_different_target(self, mock_console):
        """Test table output with file target raises error."""
        # Arrange - Use shared fixtures
        discovered_nodes = [{'vmid': 100, 'name': 'test-vm', 'role': 'server', 'node': 'node1', 'status': 'running'}]

        # Act & Assert
        with pytest.raises(ConfigurationError) as exc_info:
            _handle_table_output(discovered_nodes, mock_console, "file")
        
        assert "File output requires JSON format" in str(exc_info.value)


class TestUpdateConfigFileWithNodes:
    """Tests for the _update_config_file_with_nodes function."""

    @patch('builtins.open', new_callable=mock_open, read_data='{"proxmox": {"host": "test.com"}}')
    @patch('k3s_deploy_cli.commands.discover_command.Path.exists')
    def test_update_config_file_with_nodes_successful(self, mock_exists, mock_file, mock_console):
        """Test successful config file update with discovered nodes."""
        # Arrange - Use shared fixtures
        discovered_nodes = [
            {
                'vmid': 100,
                'name': 'k3s-server-1',
                'role': 'server',
                'ip_config': {'address': '192.168.1.100/24', 'gateway': '192.168.1.1'}
            }
        ]
        mock_exists.return_value = True

        # Act
        _update_config_file_with_nodes(discovered_nodes, mock_console)

        # Assert
        assert mock_file.call_count >= 3  # Read original, write backup, write updated
        mock_console.print.assert_called()  # Success message displayed

    @patch('builtins.open', new_callable=mock_open)
    @patch('k3s_deploy_cli.commands.discover_command.Path.exists')
    def test_update_config_file_missing_config(self, mock_exists, mock_file, mock_console):
        """Test config file update when config.json doesn't exist."""
        # Arrange - Use shared fixtures
        discovered_nodes = [{'vmid': 100, 'name': 'test-vm'}]
        mock_exists.return_value = False

        # Act
        _update_config_file_with_nodes(discovered_nodes, mock_console)

        # Assert
        mock_console.print.assert_called()  # Should display error message

    @patch('builtins.open', new_callable=mock_open, read_data='invalid json')
    @patch('k3s_deploy_cli.commands.discover_command.Path.exists')
    def test_update_config_file_invalid_json(self, mock_exists, mock_file, mock_console):
        """Test config file update with invalid JSON in existing file."""
        # Arrange - Use shared fixtures
        discovered_nodes = [{'vmid': 100, 'name': 'test-vm'}]
        mock_exists.return_value = True

        # Act & Assert
        with pytest.raises(ConfigurationError) as exc_info:
            _update_config_file_with_nodes(discovered_nodes, mock_console)
        
        assert "Failed to update config.json" in str(exc_info.value)

    @patch('builtins.open', new_callable=mock_open)
    @patch('k3s_deploy_cli.commands.discover_command.Path.exists')
    def test_update_config_file_backup_failure(self, mock_exists, mock_file, mock_console):
        """Test config file update when backup creation fails."""
        # Arrange - Use shared fixtures
        discovered_nodes = [{'vmid': 100, 'name': 'test-vm'}]
        mock_exists.return_value = True
        
        # Make backup write operation fail
        mock_file.side_effect = [
            mock_open(read_data='{"proxmox": {"host": "test.com"}}').return_value,  # Read config
            OSError("Permission denied")  # Backup write fails
        ]

        # Act & Assert
        with pytest.raises(ConfigurationError) as exc_info:
            _update_config_file_with_nodes(discovered_nodes, mock_console)
        
        assert "Failed to update config.json" in str(exc_info.value)

    @patch('builtins.open', new_callable=mock_open, read_data='{"proxmox": {"host": "test.com"}}')
    @patch('k3s_deploy_cli.commands.discover_command.Path.exists')
    def test_update_config_file_write_failure(self, mock_exists, mock_file, mock_console):
        """Test config file update when writing fails."""
        # Arrange - Use shared fixtures
        discovered_nodes = [{'vmid': 100, 'name': 'test-vm'}]
        mock_exists.return_value = True
        
        # Make final write operation fail (after successful read and backup)
        mock_file.side_effect = [
            mock_open(read_data='{"proxmox": {"host": "test.com"}}').return_value,  # Read config
            mock_open().return_value,  # Write backup (succeeds)
            OSError("Disk full")  # Final write fails
        ]

        # Act & Assert
        with pytest.raises(ConfigurationError) as exc_info:
            _update_config_file_with_nodes(discovered_nodes, mock_console)
        
        assert "Failed to update config.json" in str(exc_info.value)

    @patch('builtins.open', new_callable=mock_open, read_data='{"proxmox": {"host": "test.com"}, "nodes": [{"vmid": 999}]}')
    @patch('k3s_deploy_cli.commands.discover_command.Path.exists')
    def test_update_config_file_overwrites_existing_nodes(self, mock_exists, mock_file, mock_console):
        """Test that config file update overwrites existing nodes section."""
        # Arrange - Use shared fixtures
        discovered_nodes = [{'vmid': 100, 'name': 'new-vm'}]
        mock_exists.return_value = True

        # Act
        _update_config_file_with_nodes(discovered_nodes, mock_console)

        # Assert
        assert mock_file.call_count >= 3  # Read, backup write, updated write
        mock_console.print.assert_called()  # Success message displayed

    @patch('builtins.open', new_callable=mock_open, read_data='{"proxmox": {"host": "test.com"}}')
    @patch('k3s_deploy_cli.commands.discover_command.Path.exists')
    def test_update_config_file_empty_nodes_list(self, mock_exists, mock_file, mock_console):
        """Test config file update with empty nodes list."""
        # Arrange - Use shared fixtures
        discovered_nodes = []
        mock_exists.return_value = True
        
        # Set up mock_open to handle both read and write operations
        mock_file.return_value.__enter__.return_value.read.return_value = '{"proxmox": {"host": "test.com"}}'

        # Act
        _update_config_file_with_nodes(discovered_nodes, mock_console)

        # Assert
        mock_console.print.assert_called()  # Should still attempt update
        # Verify that file operations were attempted (read original, write backup, write updated)
        assert mock_file.call_count >= 2  # At least backup and updated config writes


class TestDiscoverCommandIntegration:
    """Integration-style tests for the discover command."""

    @patch('k3s_deploy_cli.commands.discover_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.discover_command.discover_k3s_nodes')
    def test_discover_command_full_flow_table_format(self, mock_discover_nodes, mock_get_api_client, 
                                                    basic_proxmox_config, mock_console, mock_proxmox_client):
        """Test complete discover command flow with table format."""
        # Arrange - Use shared fixtures
        mock_get_api_client.return_value = mock_proxmox_client
        mock_discovered_nodes = [
            {'vmid': 100, 'name': 'k3s-server-1', 'role': 'server', 'node': 'node1', 'status': 'running'},
            {'vmid': 101, 'name': 'k3s-agent-1', 'role': 'agent', 'node': 'node2', 'status': 'running'}
        ]
        mock_discover_nodes.return_value = mock_discovered_nodes

        # Act
        handle_discover_command(basic_proxmox_config, mock_console, output_format="table", output_target="stdout")

        # Assert
        mock_get_api_client.assert_called_once()
        mock_discover_nodes.assert_called_once()
        assert mock_console.print.call_count > 0  # Table and info messages displayed

    @patch('k3s_deploy_cli.commands.discover_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.discover_command.discover_k3s_nodes')
    @patch('builtins.open', new_callable=mock_open, read_data='{"proxmox": {"host": "test.com"}}')
    @patch('k3s_deploy_cli.commands.discover_command.Path.exists')
    def test_discover_command_full_flow_json_to_file(self, mock_exists, mock_file,
                                                   mock_discover_nodes, mock_get_api_client,
                                                   basic_proxmox_config, mock_console, mock_proxmox_client):
        """Test complete discover command flow with JSON output to file."""
        # Arrange - Use shared fixtures
        mock_get_api_client.return_value = mock_proxmox_client
        mock_discovered_nodes = [
            {
                'vmid': 100,
                'name': 'k3s-server-1',
                'role': 'server',
                'ip_config': {'address': '192.168.1.100/24', 'gateway': '192.168.1.1'}
            }
        ]
        mock_discover_nodes.return_value = mock_discovered_nodes
        mock_exists.return_value = True

        # Act
        handle_discover_command(basic_proxmox_config, mock_console, output_format="json", output_target="file")

        # Assert
        mock_get_api_client.assert_called_once()
        mock_discover_nodes.assert_called_once()
        assert mock_file.call_count >= 3  # Read, backup write, updated write
        mock_console.print.assert_called()  # Success message displayed

    @patch('k3s_deploy_cli.commands.discover_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.discover_command.discover_k3s_nodes')
    def test_discover_command_realistic_large_cluster(self, mock_discover_nodes, mock_get_api_client,
                                                     basic_proxmox_config, mock_console, mock_proxmox_client):
        """Test discover command with realistic large cluster scenario."""
        # Arrange - Use shared fixtures
        mock_get_api_client.return_value = mock_proxmox_client
        # Simulate larger cluster with multiple node types
        mock_discovered_nodes = [
            {'vmid': 100, 'name': 'k3s-server-1', 'role': 'server', 'node': 'node1', 'status': 'running'},
            {'vmid': 101, 'name': 'k3s-server-2', 'role': 'server', 'node': 'node2', 'status': 'running'},
            {'vmid': 110, 'name': 'k3s-agent-1', 'role': 'agent', 'node': 'node3', 'status': 'running'},
            {'vmid': 111, 'name': 'k3s-agent-2', 'role': 'agent', 'node': 'node4', 'status': 'stopped'},
            {'vmid': 120, 'name': 'k3s-storage-1', 'role': 'storage', 'node': 'node1', 'status': 'running'}
        ]
        mock_discover_nodes.return_value = mock_discovered_nodes

        # Act
        handle_discover_command(basic_proxmox_config, mock_console, output_format="table", output_target="stdout")

        # Assert
        mock_get_api_client.assert_called_once()
        mock_discover_nodes.assert_called_once()
        assert mock_console.print.call_count > 0

    def test_discover_command_parameter_validation(self, basic_proxmox_config, mock_console):
        """Test discover command parameter validation."""
        # Arrange - Use shared fixtures
        # Test valid parameter combinations
        valid_combinations = [
            ("table", "stdout"),
            ("table", "file"),
            ("json", "stdout"),
            ("json", "file")
        ]

        for output_format, output_target in valid_combinations:
            with patch('k3s_deploy_cli.commands.discover_command.get_proxmox_api_client') as mock_client:
                with patch('k3s_deploy_cli.commands.discover_command.discover_k3s_nodes') as mock_discover:
                    mock_client.return_value = MagicMock()
                    mock_discover.return_value = []
                    
                    # Should not raise any exceptions
                    handle_discover_command(basic_proxmox_config, mock_console, output_format, output_target)


class TestDiscoverCommandErrorScenarios:
    """Tests for error scenarios and edge cases in discover command."""

    @patch('k3s_deploy_cli.commands.discover_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.discover_command.discover_k3s_nodes')
    def test_discover_command_network_timeout(self, mock_discover_nodes, mock_get_api_client,
                                             basic_proxmox_config, mock_console, mock_proxmox_client):
        """Test discover command with network timeout."""
        # Arrange
        mock_get_api_client.return_value = mock_proxmox_client
        mock_discover_nodes.side_effect = ProxmoxInteractionError("Connection timeout")

        # Act & Assert
        with pytest.raises(ProxmoxInteractionError) as exc_info:
            handle_discover_command(basic_proxmox_config, mock_console)
        
        assert "Connection timeout" in str(exc_info.value)

    @patch('k3s_deploy_cli.commands.discover_command.get_proxmox_api_client')
    def test_discover_command_authentication_failure(self, mock_get_api_client, 
                                                    basic_proxmox_config, mock_console):
        """Test discover command with authentication failure."""
        # Arrange
        mock_get_api_client.side_effect = ProxmoxInteractionError("Authentication failed")

        # Act & Assert
        with pytest.raises(ProxmoxInteractionError) as exc_info:
            handle_discover_command(basic_proxmox_config, mock_console)
        
        assert "Authentication failed" in str(exc_info.value)

    def test_discover_command_malformed_config(self, mock_console):
        """Test discover command with malformed Proxmox configuration."""
        # Arrange
        config = {'proxmox': {}}  # Missing required fields

        # Act & Assert
        with pytest.raises(ConfigurationError):
            handle_discover_command(config, mock_console)

    @patch('k3s_deploy_cli.commands.discover_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.discover_command.discover_k3s_nodes')
    def test_discover_command_unicode_vm_names(self, mock_discover_nodes, mock_get_api_client,
                                             basic_proxmox_config, mock_console, mock_proxmox_client):
        """Test discover command with Unicode characters in VM names."""
        # Arrange
        mock_get_api_client.return_value = mock_proxmox_client
        mock_discovered_nodes = [
            {'vmid': 100, 'name': 'k3s-服务器-1', 'role': 'server', 'node': 'node1', 'status': 'running'},
            {'vmid': 101, 'name': 'k3s-агент-1', 'role': 'agent', 'node': 'node2', 'status': 'running'}
        ]
        mock_discover_nodes.return_value = mock_discovered_nodes

        # Act - Should handle Unicode characters gracefully
        handle_discover_command(basic_proxmox_config, mock_console, output_format="table", output_target="stdout")

        # Assert
        mock_get_api_client.assert_called_once()
        mock_discover_nodes.assert_called_once()
        mock_console.print.assert_called()  # Should display table with Unicode names

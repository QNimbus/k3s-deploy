# file: tests/test_provision_command.py
"""Unit tests for the provision command implementation."""

from unittest.mock import patch

import pytest

from k3s_deploy_cli.commands.provision_command import handle_provision_command
from k3s_deploy_cli.exceptions import ConfigurationError, ProvisionError


class TestHandleProvisionCommand:
    """Tests for the main handle_provision_command function."""

    def test_provision_single_vmid_in_config(self, basic_config_with_nodes):
        """Test provisioning a single VMID that exists in config."""
        # Arrange
        config = basic_config_with_nodes
        config["nodes"] = [
            {"vmid": 100, "role": "k3s-server"},
            {"vmid": 101, "role": "k3s-agent"}
        ]
        
        with patch('k3s_deploy_cli.commands.provision_command.provision_vm') as mock_provision:
            mock_provision.return_value = True
            
            # Act
            result = handle_provision_command(config, vmids=[100])
            
            # Assert
            assert result is True
            mock_provision.assert_called_once_with(
                config=config,
                vm_id=100
            )

    def test_provision_single_vmid_not_in_config(self, basic_config_with_nodes):
        """Test attempting to provision a VMID that doesn't exist in config."""
        # Arrange
        config = basic_config_with_nodes
        config["nodes"] = [
            {"vmid": 100, "role": "k3s-server"},
            {"vmid": 101, "role": "k3s-agent"}
        ]
        
        with patch('k3s_deploy_cli.commands.provision_command.provision_vm') as mock_provision:
            with patch('k3s_deploy_cli.commands.provision_command.logger') as mock_logger:
                
                # Act
                result = handle_provision_command(config, vmids=[999])
                
                # Assert
                assert result is True  # Command succeeds but reports the issue
                mock_provision.assert_not_called()  # No provisioning attempted
                mock_logger.warning.assert_called_with(
                    "VMID 999 is not configured in config.json and will be skipped"
                )

    def test_provision_mixed_vmids_some_in_config(self, basic_config_with_nodes):
        """Test provisioning multiple VMIDs where some are in config and some are not."""
        # Arrange
        config = basic_config_with_nodes
        config["nodes"] = [
            {"vmid": 100, "role": "k3s-server"},
            {"vmid": 101, "role": "k3s-agent"}
        ]
        
        with patch('k3s_deploy_cli.commands.provision_command.provision_vm') as mock_provision:
            with patch('k3s_deploy_cli.commands.provision_command.logger') as mock_logger:
                mock_provision.return_value = True
                
                # Act
                result = handle_provision_command(config, vmids=[100, 999, 101, 888])
                
                # Assert
                assert result is True
                # Should provision only the configured VMs
                assert mock_provision.call_count == 2
                mock_provision.assert_any_call(config=config, vm_id=100)
                mock_provision.assert_any_call(config=config, vm_id=101)
                
                # Should warn about unconfigured VMs
                mock_logger.warning.assert_any_call(
                    "VMID 999 is not configured in config.json and will be skipped"
                )
                mock_logger.warning.assert_any_call(
                    "VMID 888 is not configured in config.json and will be skipped"
                )

    def test_provision_all_when_no_vmids_specified(self, basic_config_with_nodes):
        """Test provisioning all configured VMs when no VMIDs are specified."""
        # Arrange
        config = basic_config_with_nodes
        config["nodes"] = [
            {"vmid": 100, "role": "k3s-server"},
            {"vmid": 101, "role": "k3s-agent"},
            {"vmid": 102, "role": "k3s-storage"}
        ]
        
        with patch('k3s_deploy_cli.commands.provision_command.provision_vm') as mock_provision:
            mock_provision.return_value = True
            
            # Act
            result = handle_provision_command(config, vmids=None)
            
            # Assert
            assert result is True
            assert mock_provision.call_count == 3
            mock_provision.assert_any_call(config=config, vm_id=100)
            mock_provision.assert_any_call(config=config, vm_id=101)
            mock_provision.assert_any_call(config=config, vm_id=102)

    def test_provision_empty_nodes_array_no_vmids(self, basic_config_with_nodes):
        """Test that no provisioning occurs when nodes array is empty and no VMIDs specified."""
        # Arrange
        config = basic_config_with_nodes
        config["nodes"] = []
        
        with patch('k3s_deploy_cli.commands.provision_command.provision_vm') as mock_provision:
            with patch('k3s_deploy_cli.commands.provision_command.logger') as mock_logger:
                
                # Act
                result = handle_provision_command(config, vmids=None)
                
                # Assert
                assert result is True
                mock_provision.assert_not_called()
                mock_logger.info.assert_called_with(
                    "No nodes configured in config.json - nothing to provision"
                )

    def test_provision_empty_nodes_array_with_vmids(self, basic_config_with_nodes):
        """Test that no provisioning occurs when nodes array is empty even with VMIDs specified."""
        # Arrange
        config = basic_config_with_nodes
        config["nodes"] = []
        
        with patch('k3s_deploy_cli.commands.provision_command.provision_vm') as mock_provision:
            with patch('k3s_deploy_cli.commands.provision_command.logger') as mock_logger:
                
                # Act
                result = handle_provision_command(config, vmids=[100, 101])
                
                # Assert
                assert result is True
                mock_provision.assert_not_called()
                mock_logger.warning.assert_any_call(
                    "VMID 100 is not configured in config.json and will be skipped"
                )
                mock_logger.warning.assert_any_call(
                    "VMID 101 is not configured in config.json and will be skipped"
                )

    def test_provision_invalid_vmid_format_handled_by_parser(self):
        """Test that invalid VMID formats are handled by the CLI parser (not the command)."""
        # This test documents that VMID validation happens at the parser level
        # The command function should only receive valid integer VMIDs
        pass

    def test_provision_failure_handling(self, basic_config_with_nodes):
        """Test proper error handling when provisioning fails."""
        # Arrange
        config = basic_config_with_nodes
        config["nodes"] = [{"vmid": 100, "role": "k3s-server"}]
        
        with patch('k3s_deploy_cli.commands.provision_command.provision_vm') as mock_provision:
            mock_provision.side_effect = ProvisionError("Provisioning failed")
            
            # Act & Assert
            with pytest.raises(ProvisionError, match="Provisioning failed"):
                handle_provision_command(config, vmids=[100])

    def test_provision_partial_success_continues(self, basic_config_with_nodes):
        """Test that provisioning continues even if some VMs fail."""
        # Arrange
        config = basic_config_with_nodes
        config["nodes"] = [
            {"vmid": 100, "role": "k3s-server"},
            {"vmid": 101, "role": "k3s-agent"},
            {"vmid": 102, "role": "k3s-storage"}
        ]
        
        def provision_side_effect(config, vm_id):
            if vm_id == 101:
                raise ProvisionError("VM 101 failed")
            return True
        
        with patch('k3s_deploy_cli.commands.provision_command.provision_vm') as mock_provision:
            with patch('k3s_deploy_cli.commands.provision_command.logger') as mock_logger:
                mock_provision.side_effect = provision_side_effect
                
                # Act
                result = handle_provision_command(config, vmids=[100, 101, 102])
                
                # Assert
                assert result is False  # Overall failure due to one VM failing
                assert mock_provision.call_count == 3
                mock_logger.error.assert_called_with(
                    "Failed to provision VM 101: VM 101 failed"
                )

    def test_provision_configuration_validation(self):
        """Test that missing required configuration is handled properly."""
        # Arrange
        config = {}  # Missing proxmox config
        
        # Act & Assert
        with pytest.raises(ConfigurationError, match="Proxmox configuration not found"):
            handle_provision_command(config, vmids=[100])


class TestProvisionCommandHelpers:
    """Tests for helper functions in the provision command module."""

    def test_parse_vmid_list_single_vmid(self):
        """Test parsing a single VMID string."""
        # This will be implemented when we add the helper function
        pass

    def test_parse_vmid_list_comma_separated(self):
        """Test parsing comma-separated VMID string."""
        # This will be implemented when we add the helper function
        pass

    def test_filter_configured_vmids(self, basic_config_with_nodes):
        """Test filtering VMIDs to only those in config."""
        # This will be implemented when we add the helper function
        pass


@pytest.fixture
def basic_config_with_nodes():
    """Fixture providing a basic config structure with nodes array."""
    return {
        "proxmox": {
            "host": "proxmox.example.com",
            "user": "root@pam",
            "password": "test_password"
        },
        "nodes": []  # Will be overridden in tests
    }
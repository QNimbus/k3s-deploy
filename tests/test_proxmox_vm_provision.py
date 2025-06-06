"""
Tests for provisioning functionality with cloud-init configuration (Phase 2A).

This module tests the updated provision_vm_basic_setup function that now
supports global cloud-init configuration from config.json.
"""

from unittest.mock import MagicMock, patch

import pytest

from k3s_deploy_cli.exceptions import ProvisionError, VMOperationError
from k3s_deploy_cli.proxmox_vm_provision import provision_vm_basic_setup


class TestProvisionVMBasicSetupWithConfig:
    """Test the updated provision_vm_basic_setup function with config support."""

    @pytest.fixture
    def mock_dependencies(self):
        """Setup common mocks for provisioning tests."""
        with patch('k3s_deploy_cli.proxmox_vm_provision.get_proxmox_api_client') as mock_client, \
             patch('k3s_deploy_cli.proxmox_vm_provision.find_vm_node') as mock_find_node, \
             patch('k3s_deploy_cli.proxmox_vm_provision.create_cloud_init_config') as mock_create_config, \
             patch('k3s_deploy_cli.proxmox_vm_provision.upload_cloud_init_to_snippet_storage') as mock_upload, \
             patch('k3s_deploy_cli.proxmox_vm_provision.get_node_snippet_storage') as mock_storage, \
             patch('k3s_deploy_cli.proxmox_vm_provision.configure_vm_cloud_init_files') as mock_configure, \
             patch('k3s_deploy_cli.proxmox_vm_provision.trigger_cloud_init_reconfiguration') as mock_reconfig:
            
            # Setup default return values
            mock_find_node.return_value = "test-node"
            mock_create_config.return_value = {'packages': ['qemu-guest-agent'], 'users': []}
            mock_upload.return_value = True
            mock_storage.return_value = {"storage_name": "local"}
            mock_configure.return_value = True
            mock_reconfig.return_value = True
            
            yield {
                'client': mock_client,
                'find_node': mock_find_node,
                'create_config': mock_create_config,
                'upload': mock_upload,
                'storage': mock_storage,
                'configure': mock_configure,
                'reconfig': mock_reconfig
            }

    def test_provision_vm_basic_setup_with_global_config(self, mock_dependencies):
        """Test provisioning with global cloud-init configuration."""
        vmid = 101
        username = "testuser"
        proxmox_config = {"host": "proxmox.example.com"}
        config = {
            "cloud_init": {
                "packages": ["htop", "git"],
                "package_update": True,
                "users": [
                    {
                        "name": "configuser",
                        "password": "configpass",
                        "sudo": True
                    }
                ]
            }
        }
        
        result = provision_vm_basic_setup(
            vmid=vmid,
            username=username,
            proxmox_config=proxmox_config,
            config=config
        )
        
        assert result is True
        
        # Verify cloud-init config was created with global settings
        mock_dependencies['create_config'].assert_called_once_with(config["cloud_init"])

    def test_provision_vm_basic_setup_with_empty_global_config(self, mock_dependencies):
        """Test provisioning with empty global cloud-init configuration."""
        vmid = 102
        username = "testuser"
        proxmox_config = {"host": "proxmox.example.com"}
        config = {}  # No cloud_init section
        
        result = provision_vm_basic_setup(
            vmid=vmid,
            username=username,
            proxmox_config=proxmox_config,
            config=config
        )
        
        assert result is True
        
        # Should call create_cloud_init_config with empty dict (falls back to defaults)
        expected_config = {
            'users': [{
                'name': 'testuser',
                'password': 'testuser',
                'sudo': True,
                'shell': '/bin/bash'
            }]
        }
        mock_dependencies['create_config'].assert_called_once()
        called_config = mock_dependencies['create_config'].call_args[0][0]
        assert called_config['users'] == expected_config['users']

    def test_provision_vm_basic_setup_with_legacy_ssh_key(self, mock_dependencies):
        """Test provisioning with legacy SSH key parameter."""
        vmid = 103
        username = "testuser"
        proxmox_config = {"host": "proxmox.example.com"}
        config = {"cloud_init": {}}  # Empty cloud_init
        ssh_public_key = "ssh-rsa AAAAB3NzaC1..."
        
        result = provision_vm_basic_setup(
            vmid=vmid,
            username=username,
            proxmox_config=proxmox_config,
            config=config,
            ssh_public_key=ssh_public_key
        )
        
        assert result is True
        
        # Verify SSH key was added to user config
        called_config = mock_dependencies['create_config'].call_args[0][0]
        assert called_config['users'][0]['ssh_keys'] == [ssh_public_key]

    def test_provision_vm_basic_setup_config_priority(self, mock_dependencies):
        """Test that existing global config users take priority over legacy parameters."""
        vmid = 104
        username = "legacyuser"  # This should be ignored
        proxmox_config = {"host": "proxmox.example.com"}
        config = {
            "cloud_init": {
                "users": [
                    {
                        "name": "configuser",
                        "password": "configpass"
                    }
                ]
            }
        }
        ssh_public_key = "ssh-rsa AAAAB3NzaC1..."
        
        result = provision_vm_basic_setup(
            vmid=vmid,
            username=username,
            proxmox_config=proxmox_config,
            config=config,
            ssh_public_key=ssh_public_key
        )
        
        assert result is True
        
        # Should use existing global config, not create legacy user
        mock_dependencies['create_config'].assert_called_once_with(config["cloud_init"])

    def test_provision_vm_basic_setup_vm_not_found(self, mock_dependencies):
        """Test error handling when VM is not found."""
        mock_dependencies['find_node'].return_value = None
        
        vmid = 999
        username = "testuser"
        proxmox_config = {"host": "proxmox.example.com"}
        config = {}
        
        with pytest.raises(VMOperationError, match="VM 999 not found on any node"):
            provision_vm_basic_setup(
                vmid=vmid,
                username=username,
                proxmox_config=proxmox_config,
                config=config
            )

    def test_provision_vm_basic_setup_upload_failure(self, mock_dependencies):
        """Test error handling when cloud-init upload fails."""
        mock_dependencies['upload'].return_value = False
        
        vmid = 105
        username = "testuser"
        proxmox_config = {"host": "proxmox.example.com"}
        config = {}
        
        with pytest.raises(ProvisionError, match="Failed to upload cloud-init configuration"):
            provision_vm_basic_setup(
                vmid=vmid,
                username=username,
                proxmox_config=proxmox_config,
                config=config
            )

    def test_provision_vm_basic_setup_configure_failure(self, mock_dependencies):
        """Test error handling when VM configuration fails."""
        mock_dependencies['configure'].return_value = False
        
        vmid = 106
        username = "testuser"
        proxmox_config = {"host": "proxmox.example.com"}
        config = {}
        
        with pytest.raises(ProvisionError, match="Failed to configure VM cloud-init"):
            provision_vm_basic_setup(
                vmid=vmid,
                username=username,
                proxmox_config=proxmox_config,
                config=config
            )

    def test_provision_vm_basic_setup_reconfig_failure(self, mock_dependencies):
        """Test error handling when cloud-init reconfiguration fails."""
        mock_dependencies['reconfig'].return_value = False
        
        vmid = 107
        username = "testuser"
        proxmox_config = {"host": "proxmox.example.com"}
        config = {}
        
        with pytest.raises(ProvisionError, match="Failed to trigger cloud-init reconfiguration"):
            provision_vm_basic_setup(
                vmid=vmid,
                username=username,
                proxmox_config=proxmox_config,
                config=config
            )

    @patch('k3s_deploy_cli.proxmox_vm_provision.logger')
    def test_provision_vm_basic_setup_logging(self, mock_logger, mock_dependencies):
        """Test proper logging during provisioning."""
        vmid = 108
        username = "testuser"
        proxmox_config = {"host": "proxmox.example.com"}
        config = {}
        
        provision_vm_basic_setup(
            vmid=vmid,
            username=username,
            proxmox_config=proxmox_config,
            config=config
        )
        
        # Verify key logging messages
        mock_logger.info.assert_any_call(f"Starting basic provisioning for VM {vmid}")
        mock_logger.info.assert_any_call(f"Successfully completed basic provisioning for VM {vmid}")
        mock_logger.debug.assert_any_call("Finding VM node...")
        mock_logger.debug.assert_any_call("Generating cloud-init configuration...")


class TestProvisionVMWithMergedConfig:
    """Test cases for VM provisioning with merged cloud-init configurations (Phase 2B)."""

    @patch('k3s_deploy_cli.proxmox_vm_provision.trigger_cloud_init_reconfiguration')
    @patch('k3s_deploy_cli.proxmox_vm_provision.configure_vm_cloud_init')
    @patch('k3s_deploy_cli.proxmox_vm_provision.upload_cloud_init_to_snippet_storage')
    @patch('k3s_deploy_cli.proxmox_vm_provision.get_node_snippet_storage')
    @patch('k3s_deploy_cli.proxmox_vm_provision.find_vm_node')
    @patch('k3s_deploy_cli.proxmox_vm_provision.get_proxmox_api_client')
    @patch('k3s_deploy_cli.proxmox_vm_provision.create_cloud_init_config')
    def test_provision_vm_with_merged_config_vm_override(
        self, mock_create_config, mock_client, mock_find_node, mock_snippet_storage,
        mock_upload, mock_configure, mock_reconfig
    ):
        """Test provision_vm with VM-specific cloud-init overrides."""
        # Setup
        vmid = 100
        config = {
            'cloud_init': {
                'packages': ['git', 'curl'],
                'package_update': True
            },
            'nodes': [
                {
                    'vmid': 100,
                    'name': 'test-vm',
                    'cloud_init': {
                        'packages': ['docker', 'kubectl'],  # Override global packages
                        'package_upgrade': True  # Additional setting
                    }
                }
            ],
            'proxmox': {'host': 'test-host', 'username': 'test-user'},
            'ssh': {'username': 'testuser'}
        }
        
        # Mock dependencies
        mock_client.return_value = MagicMock()
        mock_find_node.return_value = 'test-node'
        mock_snippet_storage.return_value = {'storage_name': 'local'}
        mock_upload.return_value = True
        mock_configure.return_value = True
        mock_reconfig.return_value = True
        mock_create_config.return_value = {'test': 'config'}
        
        # Execute
        from k3s_deploy_cli.proxmox_vm_provision import provision_vm
        result = provision_vm(config, vm_id=vmid)
        
        # Verify successful execution
        assert result is True
        
        # Verify create_cloud_init_config was called with merged settings
        mock_create_config.assert_called_once()
        call_args = mock_create_config.call_args[0][0]
        
        # VM packages should override global packages
        assert call_args['packages'] == ['docker', 'kubectl']
        # Global package_update should be preserved
        assert call_args['package_update'] is True
        # VM package_upgrade should be added
        assert call_args['package_upgrade'] is True

    @patch('k3s_deploy_cli.proxmox_vm_provision.trigger_cloud_init_reconfiguration')
    @patch('k3s_deploy_cli.proxmox_vm_provision.configure_vm_cloud_init')
    @patch('k3s_deploy_cli.proxmox_vm_provision.upload_cloud_init_to_snippet_storage')
    @patch('k3s_deploy_cli.proxmox_vm_provision.get_node_snippet_storage')
    @patch('k3s_deploy_cli.proxmox_vm_provision.find_vm_node')
    @patch('k3s_deploy_cli.proxmox_vm_provision.get_proxmox_api_client')
    @patch('k3s_deploy_cli.proxmox_vm_provision.create_cloud_init_config')
    def test_provision_vm_with_merged_config_no_vm_override(
        self, mock_create_config, mock_client, mock_find_node, mock_snippet_storage,
        mock_upload, mock_configure, mock_reconfig
    ):
        """Test provision_vm with no VM-specific overrides uses global config."""
        # Setup
        vmid = 100
        config = {
            'cloud_init': {
                'packages': ['git', 'curl'],
                'package_update': True,
                'package_upgrade': False
            },
            'nodes': [
                {
                    'vmid': 100,
                    'name': 'test-vm'
                    # No cloud_init section - should use global config
                }
            ],
            'proxmox': {'host': 'test-host', 'username': 'test-user'},
            'ssh': {'username': 'testuser'}
        }
        
        # Mock dependencies
        mock_client.return_value = MagicMock()
        mock_find_node.return_value = 'test-node'
        mock_snippet_storage.return_value = {'storage_name': 'local'}
        mock_upload.return_value = True
        mock_configure.return_value = True
        mock_reconfig.return_value = True
        mock_create_config.return_value = {'test': 'config'}
        
        # Execute
        from k3s_deploy_cli.proxmox_vm_provision import provision_vm
        result = provision_vm(config, vm_id=vmid)
        
        # Verify successful execution
        assert result is True
        
        # Verify create_cloud_init_config was called with global settings
        mock_create_config.assert_called_once()
        call_args = mock_create_config.call_args[0][0]
        
        # Should use global config as-is
        assert call_args['packages'] == ['git', 'curl']
        assert call_args['package_update'] is True
        assert call_args['package_upgrade'] is False

    @patch('k3s_deploy_cli.proxmox_vm_provision.trigger_cloud_init_reconfiguration')
    @patch('k3s_deploy_cli.proxmox_vm_provision.configure_vm_cloud_init')
    @patch('k3s_deploy_cli.proxmox_vm_provision.upload_cloud_init_to_snippet_storage')
    @patch('k3s_deploy_cli.proxmox_vm_provision.get_node_snippet_storage')
    @patch('k3s_deploy_cli.proxmox_vm_provision.find_vm_node')
    @patch('k3s_deploy_cli.proxmox_vm_provision.get_proxmox_api_client')
    @patch('k3s_deploy_cli.proxmox_vm_provision.create_cloud_init_config')
    def test_provision_vm_with_merged_config_vm_not_found(
        self, mock_create_config, mock_client, mock_find_node, mock_snippet_storage,
        mock_upload, mock_configure, mock_reconfig
    ):
        """Test provision_vm when VM not found in nodes list uses global config."""
        # Setup
        vmid = 999  # VM not in nodes list
        config = {
            'cloud_init': {
                'packages': ['git'],
                'package_update': True
            },
            'nodes': [
                {
                    'vmid': 100,
                    'name': 'other-vm',
                    'cloud_init': {'packages': ['docker']}
                }
            ],
            'proxmox': {'host': 'test-host', 'username': 'test-user'},
            'ssh': {'username': 'testuser'}
        }
        
        # Mock dependencies
        mock_client.return_value = MagicMock()
        mock_find_node.return_value = 'test-node'
        mock_snippet_storage.return_value = {'storage_name': 'local'}
        mock_upload.return_value = True
        mock_configure.return_value = True
        mock_reconfig.return_value = True
        mock_create_config.return_value = {'test': 'config'}
        
        # Execute
        from k3s_deploy_cli.proxmox_vm_provision import provision_vm
        result = provision_vm(config, vm_id=vmid)
        
        # Verify successful execution
        assert result is True
        
        # Verify create_cloud_init_config was called with global settings only
        mock_create_config.assert_called_once()
        call_args = mock_create_config.call_args[0][0]
        
        # Should use global config since VM not found
        assert call_args['packages'] == ['git']
        assert call_args['package_update'] is True

    @patch('k3s_deploy_cli.proxmox_vm_provision.trigger_cloud_init_reconfiguration')
    @patch('k3s_deploy_cli.proxmox_vm_provision.configure_vm_cloud_init')
    @patch('k3s_deploy_cli.proxmox_vm_provision.upload_cloud_init_to_snippet_storage')
    @patch('k3s_deploy_cli.proxmox_vm_provision.get_node_snippet_storage')
    @patch('k3s_deploy_cli.proxmox_vm_provision.find_vm_node')
    @patch('k3s_deploy_cli.proxmox_vm_provision.get_proxmox_api_client')
    @patch('k3s_deploy_cli.proxmox_vm_provision.create_cloud_init_config')
    def test_provision_vm_basic_setup_with_cloud_init_settings_parameter(
        self, mock_create_config, mock_client, mock_find_node, mock_snippet_storage,
        mock_upload, mock_configure, mock_reconfig
    ):
        """Test provision_vm_basic_setup with explicit cloud_init_settings parameter."""
        # Setup
        vmid = 100
        config = {
            'cloud_init': {
                'packages': ['git']  # This should be ignored
            },
            'proxmox': {'host': 'test-host', 'username': 'test-user'}
        }
        
        # Pre-merged cloud-init settings
        cloud_init_settings = {
            'packages': ['docker', 'kubectl'],
            'package_update': True,
            'package_upgrade': True
        }
        
        # Mock dependencies
        mock_client.return_value = MagicMock()
        mock_find_node.return_value = 'test-node'
        mock_snippet_storage.return_value = {'storage_name': 'local'}
        mock_upload.return_value = True
        mock_configure.return_value = True
        mock_reconfig.return_value = True
        mock_create_config.return_value = {'test': 'config'}
        
        # Execute
        from k3s_deploy_cli.proxmox_vm_provision import provision_vm_basic_setup
        result = provision_vm_basic_setup(
            vmid=vmid,
            username='testuser',
            proxmox_config=config['proxmox'],
            config=config,
            cloud_init_settings=cloud_init_settings
        )
        
        # Verify successful execution
        assert result is True
        
        # Verify create_cloud_init_config was called with provided cloud_init_settings
        mock_create_config.assert_called_once()
        call_args = mock_create_config.call_args[0][0]
        
        # Should use provided cloud_init_settings, not config['cloud_init']
        assert call_args['packages'] == ['docker', 'kubectl']
        assert call_args['package_update'] is True
        assert call_args['package_upgrade'] is True


class TestNetworkConfigProvisioning:
    """Test cases for network configuration provisioning (Phase 3)."""

    @pytest.fixture
    def mock_dependencies_with_network(self):
        """Setup common mocks for network provisioning tests."""
        with patch('k3s_deploy_cli.proxmox_vm_provision.get_proxmox_api_client') as mock_client, \
             patch('k3s_deploy_cli.proxmox_vm_provision.find_vm_node') as mock_find_node, \
             patch('k3s_deploy_cli.proxmox_vm_provision.create_cloud_init_config') as mock_create_config, \
             patch('k3s_deploy_cli.proxmox_vm_provision.extract_network_config') as mock_extract_network, \
             patch('k3s_deploy_cli.proxmox_vm_provision.create_user_config_without_network') as mock_user_config, \
             patch('k3s_deploy_cli.proxmox_vm_provision.create_network_config_yaml') as mock_network_yaml, \
             patch('k3s_deploy_cli.proxmox_vm_provision.upload_cloud_init_to_snippet_storage') as mock_upload, \
             patch('k3s_deploy_cli.proxmox_vm_provision.upload_network_config_to_snippet_storage') as mock_upload_network, \
             patch('k3s_deploy_cli.proxmox_vm_provision.get_node_snippet_storage') as mock_storage, \
             patch('k3s_deploy_cli.proxmox_vm_provision.configure_vm_cloud_init_files') as mock_configure, \
             patch('k3s_deploy_cli.proxmox_vm_provision.trigger_cloud_init_reconfiguration') as mock_reconfig:
            
            # Setup default return values
            mock_find_node.return_value = "test-node"
            mock_create_config.return_value = {'packages': ['qemu-guest-agent'], 'users': []}
            mock_upload.return_value = True
            mock_upload_network.return_value = True
            mock_storage.return_value = {"storage_name": "local"}
            mock_configure.return_value = True
            mock_reconfig.return_value = True
            
            yield {
                'client': mock_client,
                'find_node': mock_find_node,
                'create_config': mock_create_config,
                'extract_network': mock_extract_network,
                'user_config': mock_user_config,
                'network_yaml': mock_network_yaml,
                'upload': mock_upload,
                'upload_network': mock_upload_network,
                'storage': mock_storage,
                'configure': mock_configure,
                'reconfig': mock_reconfig
            }

    def test_provision_vm_with_network_config(self, mock_dependencies_with_network):
        """Test provisioning VM with network configuration."""
        vmid = 1211
        network_config = {
            'version': 2,
            'ethernets': {'eth0': {'dhcp4': True}}
        }
        cloud_init_settings = {
            'users': [{'name': 'ubuntu'}],
            'packages': ['git'],
            'network': network_config
        }
        
        # Setup network config extraction
        mock_dependencies_with_network['extract_network'].return_value = network_config
        mock_dependencies_with_network['user_config'].return_value = {
            'users': [{'name': 'ubuntu'}],
            'packages': ['git']
        }
        mock_dependencies_with_network['network_yaml'].return_value = "network:\n  version: 2\n"
        
        config = {
            'proxmox': {'host': 'test-host', 'username': 'test-user'},
            'cloud_init': {}
        }
        
        result = provision_vm_basic_setup(
            vmid=vmid,
            username='ubuntu',
            proxmox_config=config['proxmox'],
            config=config,
            cloud_init_settings=cloud_init_settings
        )
        
        # Verify successful execution
        assert result is True
        
        # Verify network config extraction was called
        mock_dependencies_with_network['extract_network'].assert_called_once_with(cloud_init_settings)
        
        # Verify user config without network was created
        mock_dependencies_with_network['user_config'].assert_called_once_with(cloud_init_settings)
        
        # Verify network YAML was generated
        mock_dependencies_with_network['network_yaml'].assert_called_once_with(network_config)
        
        # Verify both user and network configs were uploaded
        mock_dependencies_with_network['upload'].assert_called_once()
        mock_dependencies_with_network['upload_network'].assert_called_once()
        
        # Verify VM was configured with network config
        mock_dependencies_with_network['configure'].assert_called_once()
        configure_call = mock_dependencies_with_network['configure'].call_args
        assert configure_call[1]['has_network_config'] is True

    def test_provision_vm_without_network_config(self, mock_dependencies_with_network):
        """Test provisioning VM without network configuration."""
        vmid = 1221
        cloud_init_settings = {
            'users': [{'name': 'ubuntu'}],
            'packages': ['git']
        }
        
        # Setup no network config
        mock_dependencies_with_network['extract_network'].return_value = None
        
        config = {
            'proxmox': {'host': 'test-host', 'username': 'test-user'},
            'cloud_init': {}
        }
        
        result = provision_vm_basic_setup(
            vmid=vmid,
            username='ubuntu',
            proxmox_config=config['proxmox'],
            config=config,
            cloud_init_settings=cloud_init_settings
        )
        
        # Verify successful execution
        assert result is True
        
        # Verify network config extraction was called
        mock_dependencies_with_network['extract_network'].assert_called_once_with(cloud_init_settings)
        
        # Verify user config without network was NOT called (no network to remove)
        mock_dependencies_with_network['user_config'].assert_not_called()
        
        # Verify network YAML was NOT generated
        mock_dependencies_with_network['network_yaml'].assert_not_called()
        
        # Verify only user config was uploaded
        mock_dependencies_with_network['upload'].assert_called_once()
        mock_dependencies_with_network['upload_network'].assert_not_called()
        
        # Verify VM was configured without network config
        mock_dependencies_with_network['configure'].assert_called_once()
        configure_call = mock_dependencies_with_network['configure'].call_args
        assert configure_call[1]['has_network_config'] is False


class TestUploadNetworkConfig:
    """Test cases for upload_network_config_to_snippet_storage function."""

    @patch('k3s_deploy_cli.proxmox_vm_provision.establish_node_ssh_connection')
    @patch('k3s_deploy_cli.proxmox_vm_provision.is_storage_shared')
    @patch('k3s_deploy_cli.proxmox_vm_provision.get_proxmox_api_client')
    @patch('k3s_deploy_cli.proxmox_vm_provision.establish_ssh_connection')
    @patch('k3s_deploy_cli.proxmox_vm_provision.get_node_snippet_storage')
    def test_upload_network_config_success(self, mock_storage, mock_ssh, mock_client, mock_shared, mock_node_ssh):
        """Test successful network config upload."""
        from k3s_deploy_cli.proxmox_vm_provision import (
            upload_network_config_to_snippet_storage,
        )
        
        # Setup mocks
        mock_storage.return_value = {"storage_name": "local", "shared": False}
        mock_shared.return_value = False  # Local storage
        mock_client.return_value = MagicMock()
        mock_ssh_client = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_client.open_sftp.return_value = mock_sftp
        mock_node_ssh.return_value = mock_ssh_client  # Use node-specific SSH for local storage
        
        vmid = 1211
        node_name = "test-node"
        network_content = "network:\n  version: 2\n"
        proxmox_config = {'host': 'test-host', 'user': 'root@pam'}
        
        result = upload_network_config_to_snippet_storage(
            vmid, node_name, network_content, proxmox_config
        )
        
        assert result is True
        mock_node_ssh.assert_called_once_with(proxmox_config, node_name)
        mock_sftp.open.assert_called_once()

    @patch('k3s_deploy_cli.proxmox_vm_provision.establish_node_ssh_connection')
    @patch('k3s_deploy_cli.proxmox_vm_provision.is_storage_shared')
    @patch('k3s_deploy_cli.proxmox_vm_provision.get_proxmox_api_client')
    @patch('k3s_deploy_cli.proxmox_vm_provision.establish_ssh_connection')
    @patch('k3s_deploy_cli.proxmox_vm_provision.get_node_snippet_storage')
    def test_upload_network_config_with_specified_storage(self, mock_storage, mock_ssh, mock_client, mock_shared, mock_node_ssh):
        """Test network config upload with specified storage."""
        from k3s_deploy_cli.proxmox_vm_provision import (
            upload_network_config_to_snippet_storage,
        )
        
        # Setup mocks
        mock_shared.return_value = True  # Shared storage
        mock_client.return_value = MagicMock()
        mock_ssh_client = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_client.open_sftp.return_value = mock_sftp
        mock_ssh.return_value = mock_ssh_client  # Use primary SSH for shared storage
        
        vmid = 1211
        node_name = "test-node"
        network_content = "network:\n  version: 2\n"
        proxmox_config = {'host': 'test-host', 'user': 'root@pam'}
        snippet_storage = "custom-storage"
        
        result = upload_network_config_to_snippet_storage(
            vmid, node_name, network_content, proxmox_config, snippet_storage
        )
        
        assert result is True
        # Should not call get_node_snippet_storage when storage is specified
        mock_storage.assert_not_called()
        mock_ssh.assert_called_once_with(proxmox_config)


class TestConfigureVMCloudInitFiles:
    """Test cases for configure_vm_cloud_init_files function."""

    @patch('k3s_deploy_cli.proxmox_vm_provision.get_proxmox_api_client')
    def test_configure_vm_with_network_config(self, mock_client):
        """Test VM configuration with both user and network config files."""
        from k3s_deploy_cli.proxmox_vm_provision import configure_vm_cloud_init_files
        
        # Setup mocks
        mock_api_client = MagicMock()
        mock_client.return_value = mock_api_client
        mock_vm_config = MagicMock()
        mock_api_client.nodes.return_value.qemu.return_value.config = mock_vm_config
        
        vmid = 1211
        node_name = "test-node"
        storage_name = "local"
        proxmox_config = {'host': 'test-host', 'user': 'root@pam'}
        
        result = configure_vm_cloud_init_files(
            vmid, node_name, storage_name, proxmox_config, has_network_config=True
        )
        
        assert result is True
        
        # Verify correct cicustom parameter was set
        mock_vm_config.post.assert_called_once()
        call_args = mock_vm_config.post.call_args[1]
        expected_cicustom = f"user={storage_name}:snippets/userconfig-{vmid}.yaml,network={storage_name}:snippets/networkconfig-{vmid}.yaml"
        assert call_args['cicustom'] == expected_cicustom

    @patch('k3s_deploy_cli.proxmox_vm_provision.get_proxmox_api_client')
    def test_configure_vm_without_network_config(self, mock_client):
        """Test VM configuration with user config file only."""
        from k3s_deploy_cli.proxmox_vm_provision import configure_vm_cloud_init_files
        
        # Setup mocks
        mock_api_client = MagicMock()
        mock_client.return_value = mock_api_client
        mock_vm_config = MagicMock()
        mock_api_client.nodes.return_value.qemu.return_value.config = mock_vm_config
        
        vmid = 1221
        node_name = "test-node"
        storage_name = "local"
        proxmox_config = {'host': 'test-host', 'user': 'root@pam'}
        
        result = configure_vm_cloud_init_files(
            vmid, node_name, storage_name, proxmox_config, has_network_config=False
        )
        
        assert result is True
        
        # Verify correct cicustom parameter was set (user only)
        mock_vm_config.post.assert_called_once()
        call_args = mock_vm_config.post.call_args[1]
        expected_cicustom = f"user={storage_name}:snippets/userconfig-{vmid}.yaml"
        assert call_args['cicustom'] == expected_cicustom
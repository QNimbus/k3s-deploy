"""
Tests for cloud-init configuration functionality (Phase 2A).

This module tests the new create_cloud_init_config function that supports
global configuration from config.json with fallback to sensible defaults.
"""

from unittest.mock import Mock, patch

import pytest

from k3s_deploy_cli.cloud_init import CloudInitConfig, create_cloud_init_config
from k3s_deploy_cli.exceptions import ProvisionError


class TestCreateCloudInitConfig:
    """Test the new create_cloud_init_config function."""

    def test_create_cloud_init_config_with_defaults(self):
        """Test function with no settings provided (uses defaults)."""
        with patch('k3s_deploy_cli.cloud_init.logger') as mock_logger:
            config = create_cloud_init_config()
            
            # Verify defaults are applied
            assert config['packages'] == ['qemu-guest-agent', 'ansible']
            assert config['package_update'] is True
            assert config['package_upgrade'] is True
            assert config['package_reboot_if_required'] is True
            assert 'systemctl enable qemu-guest-agent' in config['runcmd']
            assert 'systemctl start qemu-guest-agent' in config['runcmd']
            # No users configured, so 'users' key should NOT exist in output
            assert 'users' not in config
            
            # Verify logging - updated to match actual implementation behavior
            mock_logger.debug.assert_any_call("Generated cloud-init config with 2 packages, 0 users, 2 run commands")

    def test_create_cloud_init_config_with_empty_settings(self):
        """Test function with empty settings dict (uses defaults)."""
        config = create_cloud_init_config({})
        
        # Should behave same as None
        assert config['packages'] == ['qemu-guest-agent', 'ansible']
        assert config['package_update'] is True
        # No users configured, so 'users' key should NOT exist
        assert 'users' not in config

    def test_create_cloud_init_config_with_custom_packages(self):
        """Test function with custom package configuration."""
        cloud_init_settings = {
            'packages': ['custom-package', 'another-package'],
            'package_update': False,
            'package_upgrade': True
        }
        
        config = create_cloud_init_config(cloud_init_settings)
        
        assert config['packages'] == ['custom-package', 'another-package']
        assert config['package_update'] is False
        assert config['package_upgrade'] is True
        # Should still have default for unspecified settings
        assert config['package_reboot_if_required'] is True
        # No users configured, so 'users' key should NOT exist
        assert 'users' not in config

    def test_create_cloud_init_config_with_custom_commands(self):
        """Test function with custom run commands."""
        cloud_init_settings = {
            'runcmd': [
                'echo "Custom command 1"',
                'systemctl enable custom-service',
                'custom-setup-script.sh'
            ]
        }
        
        config = create_cloud_init_config(cloud_init_settings)
        
        assert config['runcmd'] == [
            'echo "Custom command 1"',
            'systemctl enable custom-service',
            'custom-setup-script.sh'
        ]
        # No users configured, so 'users' key should NOT exist
        assert 'users' not in config

    def test_create_cloud_init_config_with_users(self):
        """Test function with user configuration."""
        cloud_init_settings = {
            'users': [
                {
                    'username': 'testuser',
                    'plain_text_passwd': 'testpass',
                    'sudo': True,
                    'shell': '/bin/bash',
                    'ssh_keys': ['ssh-rsa AAAAB3NzaC1...']
                },
                {
                    'username': 'nopassuser',
                    'ssh_keys': ['ssh-rsa AAAAB3NzaC1...'],
                    'sudo': False
                }
            ]
        }
        
        with patch('k3s_deploy_cli.cloud_init.logger') as mock_logger:
            config = create_cloud_init_config(cloud_init_settings)
            
            # Verify users were added
            assert len(config['users']) == 2
            
            # Verify logging for user addition
            mock_logger.debug.assert_any_call("Added user 'testuser' from global configuration")
            mock_logger.debug.assert_any_call("Added user 'nopassuser' from global configuration")

    def test_create_cloud_init_config_with_invalid_user(self):
        """Test function handling of user missing required 'username' field.
        
        While JSON schema validation would normally prevent this in production,
        this test ensures the function itself has proper defense-in-depth validation.
        """
        cloud_init_settings = {
            'users': [
                {
                    'plain_text_passwd': 'testpass',
                    'sudo': True
                    # Missing required 'username' field
                }
            ]
        }
        
        with patch('k3s_deploy_cli.cloud_init.logger') as mock_logger:
            config = create_cloud_init_config(cloud_init_settings)
            
            # Should skip invalid user
            assert len(config.get('users', [])) == 0
            mock_logger.warning.assert_called_with("Skipping user configuration without 'username' field")

    def test_create_cloud_init_config_user_with_password(self):
        """Test user configuration with password."""
        cloud_init_settings = {
            'users': [
                {
                    'username': 'pwuser',
                    'plain_text_passwd': 'secret123',
                    'sudo': True,
                    'groups': ['docker', 'admin'],
                    'shell': '/bin/zsh'
                }
            ]
        }
        
        config = create_cloud_init_config(cloud_init_settings)
        user = config['users'][0]
        # Verify user was added
        assert 'users' in config
        assert len(config['users']) == 1
        assert 'hashed_passwd' in user
        assert user['name'] == 'pwuser'
        assert user['shell'] == '/bin/zsh'
        assert user['sudo'] == "ALL=(ALL) NOPASSWD:ALL"
        assert user['groups'] == ['docker', 'admin']

    def test_create_cloud_init_config_user_without_password(self):
        """Test user configuration without password (SSH keys only)."""
        cloud_init_settings = {
            'users': [
                {
                    'username': 'sshuser',
                    'ssh_keys': ['ssh-rsa AAAAB3NzaC1...'],
                    'sudo': False
                }
            ]
        }
        
        config = create_cloud_init_config(cloud_init_settings)
        user = config['users'][0]
        # Verify user was added
        assert 'users' in config
        assert len(config['users']) == 1
        assert user['name'] == 'sshuser'
        assert user['ssh_authorized_keys'] == ['ssh-rsa AAAAB3NzaC1...']
        # sudo=False should result in no sudo key
        assert 'sudo' not in user

    def test_create_cloud_init_config_complete_configuration(self):
        """Test function with complete custom configuration."""
        cloud_init_settings = {
            'packages': ['htop', 'git', 'docker.io'],
            'package_update': True,
            'package_upgrade': False,
            'package_reboot_if_required': False,
            'runcmd': [
                'systemctl enable docker',
                'usermod -aG docker ubuntu'
            ],
            'users': [
                {
                    'username': 'admin',
                    'hashed_passwd': 'hashed-password',
                    'sudo': True,
                    'ssh_keys': ['ssh-rsa AAAAB3NzaC1...']
                }
            ]
        }
        
        config = create_cloud_init_config(cloud_init_settings)
        # Verify all custom settings are applied
        assert config['packages'] == ['htop', 'git', 'docker.io']
        assert config['package_update'] is True
        assert config['package_upgrade'] is False
        assert config['package_reboot_if_required'] is False
        assert config['runcmd'] == [
            'systemctl enable docker',
            'usermod -aG docker ubuntu'
        ]
        assert len(config['users']) == 1
        user = config['users'][0]
        assert 'hashed_passwd' in user
        assert user['hashed_passwd'] == 'hashed-password'
        assert user['name'] == 'admin'
        assert user['sudo'] == "ALL=(ALL) NOPASSWD:ALL"
        assert user['ssh_authorized_keys'] == ['ssh-rsa AAAAB3NzaC1...']

    @patch('k3s_deploy_cli.cloud_init.logger')
    def test_create_cloud_init_config_logging(self, mock_logger):
        """Test proper logging messages."""
        # Test with global config
        cloud_init_settings = {'packages': ['test']}
        create_cloud_init_config(cloud_init_settings)
        mock_logger.debug.assert_any_call("Creating cloud-init config from global settings")
        mock_logger.debug.assert_any_call("Using global cloud-init configuration from config.json")
        # Test package/user counts in final log
        expected_log_calls = [call for call in mock_logger.debug.call_args_list 
                            if "Generated cloud-init config with" in str(call)]
        assert len(expected_log_calls) > 0

    def test_create_cloud_init_config_user_with_username_field(self):
        """Test function properly handles 'username' field as an alias for 'name'."""
        cloud_init_settings = {
            'users': [
                {
                    'username': 'testuser',
                    'plain_text_passwd': 'testpass',
                    'sudo': True,
                    'shell': '/bin/bash',
                    'ssh_keys': ['ssh-rsa AAAAB3NzaC1...']
                }
            ]
        }
        
        with patch('k3s_deploy_cli.cloud_init.logger') as mock_logger:
            config = create_cloud_init_config(cloud_init_settings)
            user = config['users'][0]
            # Verify user was added
            assert 'users' in config
            assert 'hashed_passwd' in user
            assert len(config['users']) == 1
            assert user['name'] == 'testuser'
            
            # Verify logging - updated to match actual implementation behavior
            mock_logger.debug.assert_any_call("Generated cloud-init config with 2 packages, 1 users, 2 run commands")

"""
Unit tests for configuration utilities module.

Tests the configuration merging functionality for combining global and 
VM-specific cloud-init settings, ensuring proper merge behavior and
edge case handling.
"""

from unittest.mock import MagicMock, patch

import pytest

from k3s_deploy_cli.config_utils import (
    clean_cloud_init_config,
    create_network_config_yaml,
    create_user_config_without_network,
    extract_network_config,
    find_node_by_vmid,
    get_merged_cloud_init_for_vm,
    merge_cloud_init_config,
)


class TestCleanCloudInitConfig:
    """Test cases for clean_cloud_init_config function."""
    
    def test_clean_config_removes_empty_groups(self):
        """Test that empty groups lists are removed."""
        config = {
            "users": [
                {"name": "ubuntu", "groups": []},
                {"name": "admin", "groups": ["wheel", "docker"]}
            ]
        }
        
        result = clean_cloud_init_config(config)
        
        # First user should have groups removed, second should keep groups
        assert result == {
            "users": [
                {"name": "ubuntu"},
                {"name": "admin", "groups": ["wheel", "docker"]}
            ]
        }
    
    def test_clean_config_removes_none_values(self):
        """Test that None values are removed."""
        config = {
            "users": [{"name": "ubuntu", "shell": None, "sudo": True}],
            "packages": None,
            "network": {"version": 2}
        }
        
        result = clean_cloud_init_config(config)
        
        assert result == {
            "users": [{"name": "ubuntu", "sudo": True}],
            "network": {"version": 2}
        }
    
    def test_clean_config_removes_empty_lists(self):
        """Test that empty lists are removed."""
        config = {
            "packages": [],
            "runcmd": ["echo hello"],
            "users": []
        }
        
        result = clean_cloud_init_config(config)
        
        assert result == {
            "runcmd": ["echo hello"]
        }
    
    def test_clean_config_nested_cleaning(self):
        """Test that nested structures are cleaned recursively."""
        config = {
            "users": [
                {
                    "name": "ubuntu",
                    "groups": [],
                    "ssh_keys": ["ssh-rsa AAAA..."],
                    "metadata": {
                        "tags": [],
                        "description": None,
                        "active": True
                    }
                }
            ],
            "network": {
                "version": 2,
                "ethernets": {
                    "eth0": {
                        "dhcp4": True,
                        "routes": []
                    }
                }
            }
        }
        
        result = clean_cloud_init_config(config)
        
        expected = {
            "users": [
                {
                    "name": "ubuntu",
                    "ssh_keys": ["ssh-rsa AAAA..."],
                    "metadata": {
                        "active": True
                    }
                }
            ],
            "network": {
                "version": 2,
                "ethernets": {
                    "eth0": {
                        "dhcp4": True
                    }
                }
            }
        }
        
        assert result == expected
    
    def test_clean_config_preserves_valid_data(self):
        """Test that valid data is preserved."""
        config = {
            "users": [
                {
                    "name": "ubuntu",
                    "groups": ["sudo"],
                    "shell": "/bin/bash",
                    "sudo": True
                }
            ],
            "packages": ["git", "vim"],
            "package_update": True,
            "network": {
                "version": 2,
                "ethernets": {
                    "eth0": {"dhcp4": True}
                }
            }
        }
        
        result = clean_cloud_init_config(config)
        
        # Should be identical since no empty lists or None values
        assert result == config
    
    def test_clean_config_empty_dict_input(self):
        """Test cleaning empty dictionary."""
        result = clean_cloud_init_config({})
        assert result == {}
    
    def test_clean_config_non_dict_input(self):
        """Test that non-dict input is returned as-is."""
        assert clean_cloud_init_config("string") == "string"
        assert clean_cloud_init_config(123) == 123
        assert clean_cloud_init_config(["list"]) == ["list"]


class TestFindNodeByVmid:
    """Test cases for find_node_by_vmid function."""

    def test_find_existing_node(self):
        """Test finding a node that exists in the list."""
        nodes = [
            {'vmid': 100, 'name': 'test-vm-1'},
            {'vmid': 101, 'name': 'test-vm-2'},
            {'vmid': 102, 'name': 'test-vm-3'}
        ]
        
        result = find_node_by_vmid(nodes, 101)
        
        assert result is not None
        assert result['vmid'] == 101
        assert result['name'] == 'test-vm-2'

    def test_find_nonexistent_node(self):
        """Test searching for a node that doesn't exist."""
        nodes = [
            {'vmid': 100, 'name': 'test-vm-1'},
            {'vmid': 101, 'name': 'test-vm-2'}
        ]
        
        result = find_node_by_vmid(nodes, 999)
        
        assert result is None

    def test_empty_nodes_list(self):
        """Test searching in an empty nodes list."""
        nodes = []
        
        result = find_node_by_vmid(nodes, 100)
        
        assert result is None

    def test_invalid_node_format(self):
        """Test handling nodes with invalid format."""
        nodes = [
            {'vmid': 100, 'name': 'valid-node'},
            'invalid-node',  # String instead of dict
            {'name': 'missing-vmid'},  # Missing vmid field
            {'vmid': '101', 'name': 'string-vmid'}  # String vmid instead of int
        ]
        
        # Should find the valid node
        result = find_node_by_vmid(nodes, 100)
        assert result is not None
        assert result['vmid'] == 100
        
        # Should not find invalid nodes
        result = find_node_by_vmid(nodes, 101)
        assert result is None


class TestMergeCloudInitConfig:
    """Test cases for merge_cloud_init_config function."""

    def test_vm_boolean_overrides_global(self):
        """Test VM boolean setting overrides global boolean."""
        global_config = {'package_update': True}
        vm_config = {'package_update': False}
        
        result = merge_cloud_init_config(global_config, vm_config)
        
        assert result['package_update'] is False

    def test_vm_packages_replace_global_packages(self):
        """Test VM packages completely replace global packages."""
        global_config = {'packages': ['git', 'curl', 'vim']}
        vm_config = {'packages': ['docker', 'kubectl']}
        
        result = merge_cloud_init_config(global_config, vm_config)
        
        assert result['packages'] == ['docker', 'kubectl']

    def test_vm_users_replace_global_users(self):
        """Test VM users completely replace global users."""
        global_config = {
            'users': [
                {'name': 'admin', 'sudo': True},
                {'name': 'user1', 'sudo': False}
            ]
        }
        vm_config = {
            'users': [
                {'name': 'vm-admin', 'sudo': True}
            ]
        }
        
        result = merge_cloud_init_config(global_config, vm_config)
        
        assert len(result['users']) == 1
        assert result['users'][0]['name'] == 'vm-admin'

    def test_vm_runcmd_replace_global_runcmd(self):
        """Test VM runcmd completely replaces global runcmd."""
        global_config = {
            'runcmd': [
                'apt update',
                'apt upgrade -y'
            ]
        }
        vm_config = {
            'runcmd': [
                'docker --version'
            ]
        }
        
        result = merge_cloud_init_config(global_config, vm_config)
        
        assert result['runcmd'] == ['docker --version']

    def test_missing_vm_config_uses_global(self):
        """Test missing VM config uses global config as-is."""
        global_config = {
            'packages': ['git', 'curl'],
            'package_update': True,
            'users': [{'name': 'admin'}]
        }
        vm_config = {}
        
        result = merge_cloud_init_config(global_config, vm_config)
        
        assert result == global_config

    def test_missing_global_config_uses_vm(self):
        """Test missing global config uses VM config as-is."""
        global_config = {}
        vm_config = {
            'packages': ['docker'],
            'package_upgrade': True
        }
        
        result = merge_cloud_init_config(global_config, vm_config)
        
        assert result == vm_config

    def test_both_configs_missing_returns_empty(self):
        """Test both configs missing returns empty dict."""
        global_config = {}
        vm_config = {}
        
        result = merge_cloud_init_config(global_config, vm_config)
        
        assert result == {}

    def test_partial_vm_override(self):
        """Test VM config only overrides specified settings."""
        global_config = {
            'packages': ['git', 'curl'],
            'package_update': True,
            'package_upgrade': False,
            'users': [{'name': 'admin'}]
        }
        vm_config = {
            'packages': ['docker'],
            'package_upgrade': True
            # package_update and users not specified, should keep global values
        }
        
        result = merge_cloud_init_config(global_config, vm_config)
        
        assert result['packages'] == ['docker']
        assert result['package_update'] is True  # From global
        assert result['package_upgrade'] is True  # From VM
        assert result['users'] == [{'name': 'admin'}]  # From global

    def test_none_values_not_overridden(self):
        """Test VM config with None values don't override global config."""
        global_config = {
            'packages': ['git'],
            'package_update': True
        }
        vm_config = {
            'packages': None,  # Should not override
            'package_upgrade': False  # Should override
        }
        
        result = merge_cloud_init_config(global_config, vm_config)
        
        assert result['packages'] == ['git']  # Global preserved
        assert result['package_update'] is True  # Global preserved
        assert result['package_upgrade'] is False  # VM override


class TestGetMergedCloudInitForVm:
    """Test cases for get_merged_cloud_init_for_vm function."""

    def test_vm_with_overrides(self):
        """Test VM with cloud-init overrides."""
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
                        'packages': ['docker'],
                        'package_upgrade': True
                    }
                }
            ]
        }
        
        result = get_merged_cloud_init_for_vm(config, 100)
        
        assert result['packages'] == ['docker']  # VM override
        assert result['package_update'] is True  # Global preserved
        assert result['package_upgrade'] is True  # VM addition

    def test_vm_without_overrides(self):
        """Test VM without cloud-init overrides uses global config."""
        config = {
            'cloud_init': {
                'packages': ['git', 'curl'],
                'package_update': True
            },
            'nodes': [
                {
                    'vmid': 100,
                    'name': 'test-vm'
                    # No cloud_init section
                }
            ]
        }
        
        result = get_merged_cloud_init_for_vm(config, 100)
        
        assert result['packages'] == ['git', 'curl']
        assert result['package_update'] is True

    def test_vm_not_found_uses_global(self):
        """Test VM not found in nodes uses global config."""
        config = {
            'cloud_init': {
                'packages': ['git'],
                'package_update': True
            },
            'nodes': [
                {'vmid': 101, 'name': 'other-vm'}
            ]
        }
        
        result = get_merged_cloud_init_for_vm(config, 999)
        
        assert result['packages'] == ['git']
        assert result['package_update'] is True

    def test_no_global_config_vm_found(self):
        """Test no global config but VM has cloud-init config."""
        config = {
            # No cloud_init section
            'nodes': [
                {
                    'vmid': 100,
                    'cloud_init': {
                        'packages': ['docker'],
                        'package_upgrade': True
                    }
                }
            ]
        }
        
        result = get_merged_cloud_init_for_vm(config, 100)
        
        assert result['packages'] == ['docker']
        assert result['package_upgrade'] is True

    def test_no_global_config_no_vm_config(self):
        """Test no global config and no VM config returns empty."""
        config = {
            # No cloud_init section
            'nodes': [
                {
                    'vmid': 100,
                    'name': 'test-vm'
                    # No cloud_init section
                }
            ]
        }
        
        result = get_merged_cloud_init_for_vm(config, 100)
        
        assert result == {}

    def test_no_nodes_section(self):
        """Test config without nodes section uses global config."""
        config = {
            'cloud_init': {
                'packages': ['git'],
                'package_update': True
            }
            # No nodes section
        }
        
        result = get_merged_cloud_init_for_vm(config, 100)
        
        assert result['packages'] == ['git']
        assert result['package_update'] is True

    def test_empty_nodes_list(self):
        """Test empty nodes list uses global config."""
        config = {
            'cloud_init': {
                'packages': ['git']
            },
            'nodes': []
        }
        
        result = get_merged_cloud_init_for_vm(config, 100)
        
        assert result['packages'] == ['git']

    @patch('k3s_deploy_cli.config_utils.logger')
    def test_logging_behavior(self, mock_logger):
        """Test proper logging behavior during merge process."""
        config = {
            'cloud_init': {'packages': ['git']},
            'nodes': [
                {
                    'vmid': 100,
                    'cloud_init': {'packages': ['docker']}
                }
            ]
        }
        
        get_merged_cloud_init_for_vm(config, 100)
        
        # Verify logging calls were made
        mock_logger.debug.assert_called()
        mock_logger.info.assert_called()


class TestCleanCloudInitConfig:
    """Test cases for clean_cloud_init_config function."""
    
    def test_clean_config_removes_empty_groups(self):
        """Test that empty groups lists are removed."""
        from k3s_deploy_cli.config_utils import clean_cloud_init_config
        
        config = {
            "users": [
                {"name": "ubuntu", "groups": []},
                {"name": "admin", "groups": ["wheel", "docker"]}
            ]
        }
        
        result = clean_cloud_init_config(config)
        
        # First user should have groups removed, second should keep groups
        assert result == {
            "users": [
                {"name": "ubuntu"},
                {"name": "admin", "groups": ["wheel", "docker"]}
            ]
        }
    
    def test_clean_config_removes_none_values(self):
        """Test that None values are removed."""
        from k3s_deploy_cli.config_utils import clean_cloud_init_config
        
        config = {
            "users": [{"name": "ubuntu", "shell": None, "sudo": True}],
            "packages": None,
            "network": {"version": 2}
        }
        
        result = clean_cloud_init_config(config)
        
        assert result == {
            "users": [{"name": "ubuntu", "sudo": True}],
            "network": {"version": 2}
        }
    
    def test_clean_config_removes_empty_lists(self):
        """Test that empty lists are removed."""
        from k3s_deploy_cli.config_utils import clean_cloud_init_config
        
        config = {
            "packages": [],
            "runcmd": ["echo hello"],
            "users": []
        }
        
        result = clean_cloud_init_config(config)
        
        assert result == {
            "runcmd": ["echo hello"]
        }
    
    def test_clean_config_nested_cleaning(self):
        """Test that nested structures are cleaned recursively."""
        from k3s_deploy_cli.config_utils import clean_cloud_init_config
        
        config = {
            "users": [
                {
                    "name": "ubuntu",
                    "groups": [],
                    "ssh_keys": ["ssh-rsa AAAA..."],
                    "metadata": {
                        "tags": [],
                        "description": None,
                        "active": True
                    }
                }
            ],
            "network": {
                "version": 2,
                "ethernets": {
                    "eth0": {
                        "dhcp4": True,
                        "routes": []
                    }
                }
            }
        }
        
        result = clean_cloud_init_config(config)
        
        expected = {
            "users": [
                {
                    "name": "ubuntu",
                    "ssh_keys": ["ssh-rsa AAAA..."],
                    "metadata": {
                        "active": True
                    }
                }
            ],
            "network": {
                "version": 2,
                "ethernets": {
                    "eth0": {
                        "dhcp4": True
                    }
                }
            }
        }
        
        assert result == expected
    
    def test_clean_config_preserves_valid_data(self):
        """Test that valid data is preserved."""
        from k3s_deploy_cli.config_utils import clean_cloud_init_config
        
        config = {
            "users": [
                {
                    "name": "ubuntu",
                    "groups": ["sudo"],
                    "shell": "/bin/bash",
                    "sudo": True
                }
            ],
            "packages": ["git", "vim"],
            "package_update": True,
            "network": {
                "version": 2,
                "ethernets": {
                    "eth0": {"dhcp4": True}
                }
            }
        }
        
        result = clean_cloud_init_config(config)
        
        # Should be identical since no empty lists or None values
        assert result == config
    
    def test_clean_config_empty_dict_input(self):
        """Test cleaning empty dictionary."""
        from k3s_deploy_cli.config_utils import clean_cloud_init_config
        
        result = clean_cloud_init_config({})
        assert result == {}
    
    def test_clean_config_non_dict_input(self):
        """Test that non-dict input is returned as-is."""
        from k3s_deploy_cli.config_utils import clean_cloud_init_config
        
        assert clean_cloud_init_config("string") == "string"
        assert clean_cloud_init_config(123) == 123
        assert clean_cloud_init_config(["list"]) == ["list"]


class TestNetworkConfigExtraction:
    """Test cases for network configuration extraction functions."""

    def test_extract_network_config_exists(self):
        """Test extracting network configuration when it exists."""
        from k3s_deploy_cli.config_utils import extract_network_config
        
        cloud_init_config = {
            'users': [{'name': 'ubuntu'}],
            'packages': ['git'],
            'network': {
                'version': 2,
                'ethernets': {
                    'eth0': {'dhcp4': True}
                }
            }
        }
        
        result = extract_network_config(cloud_init_config)
        
        assert result is not None
        assert result['version'] == 2
        assert 'ethernets' in result
        assert result['ethernets']['eth0']['dhcp4'] is True

    def test_extract_network_config_missing(self):
        """Test extracting network configuration when it doesn't exist."""
        from k3s_deploy_cli.config_utils import extract_network_config
        
        cloud_init_config = {
            'users': [{'name': 'ubuntu'}],
            'packages': ['git']
        }
        
        result = extract_network_config(cloud_init_config)
        
        assert result is None

    def test_extract_network_config_empty(self):
        """Test extracting empty network configuration."""
        from k3s_deploy_cli.config_utils import extract_network_config
        
        cloud_init_config = {
            'users': [{'name': 'ubuntu'}],
            'network': {}
        }
        
        result = extract_network_config(cloud_init_config)
        
        assert result is None

    def test_extract_network_config_invalid_type(self):
        """Test extracting network configuration with invalid type."""
        from k3s_deploy_cli.config_utils import extract_network_config
        
        cloud_init_config = {
            'users': [{'name': 'ubuntu'}],
            'network': "invalid_string"
        }
        
        result = extract_network_config(cloud_init_config)
        
        assert result is None

    def test_create_network_config_yaml(self):
        """Test creating network configuration YAML."""
        from k3s_deploy_cli.config_utils import create_network_config_yaml
        
        network_config = {
            'version': 2,
            'ethernets': {
                'eth0': {'dhcp4': True}
            }
        }
        
        result = create_network_config_yaml(network_config)
        
        assert isinstance(result, str)
        assert 'network:' in result
        assert 'version: 2' in result
        assert 'ethernets:' in result
        assert 'eth0:' in result
        assert 'dhcp4: true' in result

    def test_create_network_config_yaml_empty(self):
        """Test creating network configuration YAML with empty config."""
        from k3s_deploy_cli.config_utils import create_network_config_yaml
        
        with pytest.raises(ValueError, match="Network configuration cannot be empty"):
            create_network_config_yaml({})

    def test_create_network_config_yaml_invalid_type(self):
        """Test creating network configuration YAML with invalid type."""
        from k3s_deploy_cli.config_utils import create_network_config_yaml
        
        with pytest.raises(ValueError, match="Network configuration must be a dictionary"):
            create_network_config_yaml("invalid_string")

    def test_create_user_config_without_network(self):
        """Test creating user config with network section removed."""
        from k3s_deploy_cli.config_utils import create_user_config_without_network
        
        cloud_init_config = {
            'users': [{'name': 'ubuntu'}],
            'packages': ['git', 'curl'],
            'runcmd': ['echo "test"'],
            'network': {
                'version': 2,
                'ethernets': {'eth0': {'dhcp4': True}}
            }
        }
        
        result = create_user_config_without_network(cloud_init_config)
        
        assert 'users' in result
        assert 'packages' in result
        assert 'runcmd' in result
        assert 'network' not in result
        assert result['users'] == [{'name': 'ubuntu'}]
        assert result['packages'] == ['git', 'curl']

    def test_create_user_config_without_network_no_network_section(self):
        """Test creating user config when no network section exists."""
        from k3s_deploy_cli.config_utils import create_user_config_without_network
        
        cloud_init_config = {
            'users': [{'name': 'ubuntu'}],
            'packages': ['git']
        }
        
        result = create_user_config_without_network(cloud_init_config)
        
        assert result == cloud_init_config
        assert 'users' in result
        assert 'packages' in result
        assert 'network' not in result

    @patch('k3s_deploy_cli.config_utils.logger')
    def test_extract_network_config_logging(self, mock_logger):
        """Test that network config extraction includes proper logging."""
        from k3s_deploy_cli.config_utils import extract_network_config
        
        cloud_init_config = {
            'network': {'version': 2, 'ethernets': {'eth0': {'dhcp4': True}}}
        }
        
        extract_network_config(cloud_init_config)
        
        # Verify logging calls were made
        mock_logger.debug.assert_called()

    @patch('k3s_deploy_cli.config_utils.logger')
    def test_create_user_config_without_network_logging(self, mock_logger):
        """Test that user config creation includes proper logging."""
        from k3s_deploy_cli.config_utils import create_user_config_without_network
        
        cloud_init_config = {
            'users': [{'name': 'ubuntu'}],
            'network': {'version': 2}
        }
        
        create_user_config_without_network(cloud_init_config)
        
        # Verify logging calls were made
        mock_logger.debug.assert_called()

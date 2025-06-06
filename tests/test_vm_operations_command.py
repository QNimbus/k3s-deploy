"""
Unit tests for VM operations command handlers.

This module contains tests for the command layer that handles start, stop, and restart
operations for individual VMs and bulk K3s VM operations.
"""

from argparse import Namespace
from unittest.mock import patch

import pytest

from k3s_deploy_cli.commands.vm_operations_command import (
    _restart_all_k3s_vms,
    _restart_single_vm,
    _start_all_k3s_vms,
    _start_single_vm,
    _stop_all_k3s_vms,
    _stop_single_vm,
    handle_restart_command,
    handle_start_command,
    handle_stop_command,
)
from k3s_deploy_cli.exceptions import ProxmoxInteractionError
from tests.helpers import create_sample_k3s_vms, setup_mock_vm_operations


def create_args(vmid: int = None, force: bool = None) -> Namespace:
    """Create argument namespace with optional parameters."""
    args = Namespace()
    if vmid is not None:
        args.vmid = vmid
    if force is not None:
        args.force = force
    return args


class TestHandleStartCommand:
    """Test cases for handle_start_command function."""
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.vm_operations_command._start_single_vm')
    def test_handle_start_command_single_vm(self, mock_start_single, mock_get_client, basic_proxmox_config, mock_proxmox_client):
        """Test handle_start_command for single VM."""
        mock_get_client.return_value = mock_proxmox_client
        args = create_args(vmid=100)
        
        handle_start_command(args, basic_proxmox_config)
        
        mock_get_client.assert_called_once_with(basic_proxmox_config["proxmox"])
        mock_start_single.assert_called_once_with(mock_proxmox_client, 100)
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.vm_operations_command._start_all_k3s_vms')
    def test_handle_start_command_all_vms(self, mock_start_all, mock_get_client, basic_proxmox_config, mock_proxmox_client):
        """Test handle_start_command for all K3s VMs."""
        mock_get_client.return_value = mock_proxmox_client
        args = create_args()
        
        handle_start_command(args, basic_proxmox_config)
        
        mock_get_client.assert_called_once_with(basic_proxmox_config["proxmox"])
        mock_start_all.assert_called_once_with(mock_proxmox_client, basic_proxmox_config)
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.get_proxmox_api_client')
    def test_handle_start_command_proxmox_error(self, mock_get_client, basic_proxmox_config):
        """Test handle_start_command with ProxmoxInteractionError."""
        mock_get_client.side_effect = ProxmoxInteractionError("Connection failed")
        args = create_args(vmid=100)
        
        with pytest.raises(ProxmoxInteractionError):
            handle_start_command(args, basic_proxmox_config)
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.get_proxmox_api_client')
    def test_handle_start_command_generic_error(self, mock_get_client, basic_proxmox_config):
        """Test handle_start_command with generic exception."""
        mock_get_client.side_effect = Exception("Unexpected error")
        args = create_args(vmid=100)
        
        with pytest.raises(Exception):
            handle_start_command(args, basic_proxmox_config)


class TestHandleStopCommand:
    """Test cases for handle_stop_command function."""
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.vm_operations_command._stop_single_vm')
    def test_handle_stop_command_single_vm_graceful(self, mock_stop_single, mock_get_client, basic_proxmox_config, mock_proxmox_client):
        """Test handle_stop_command for single VM graceful shutdown."""
        mock_get_client.return_value = mock_proxmox_client
        args = create_args(vmid=100, force=False)
        
        handle_stop_command(args, basic_proxmox_config)
        
        mock_get_client.assert_called_once_with(basic_proxmox_config["proxmox"])
        mock_stop_single.assert_called_once_with(mock_proxmox_client, 100, False)
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.vm_operations_command._stop_single_vm')
    def test_handle_stop_command_single_vm_force(self, mock_stop_single, mock_get_client, basic_proxmox_config, mock_proxmox_client):
        """Test handle_stop_command for single VM force stop."""
        mock_get_client.return_value = mock_proxmox_client
        args = create_args(vmid=100, force=True)
        
        handle_stop_command(args, basic_proxmox_config)
        
        mock_get_client.assert_called_once_with(basic_proxmox_config["proxmox"])
        mock_stop_single.assert_called_once_with(mock_proxmox_client, 100, True)
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.vm_operations_command._stop_all_k3s_vms')
    def test_handle_stop_command_all_vms(self, mock_stop_all, mock_get_client, basic_proxmox_config, mock_proxmox_client):
        """Test handle_stop_command for all K3s VMs."""
        mock_get_client.return_value = mock_proxmox_client
        args = create_args()
        args.force = False  # Add force attribute
        
        handle_stop_command(args, basic_proxmox_config)
        
        mock_get_client.assert_called_once_with(basic_proxmox_config["proxmox"])
        mock_stop_all.assert_called_once_with(mock_proxmox_client, basic_proxmox_config, False)


class TestHandleRestartCommand:
    """Test cases for handle_restart_command function."""
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.vm_operations_command._restart_single_vm')
    def test_handle_restart_command_single_vm(self, mock_restart_single, mock_get_client, basic_proxmox_config, mock_proxmox_client):
        """Test handle_restart_command for single VM."""
        mock_get_client.return_value = mock_proxmox_client
        args = create_args(vmid=100)
        
        handle_restart_command(args, basic_proxmox_config)
        
        mock_get_client.assert_called_once_with(basic_proxmox_config["proxmox"])
        mock_restart_single.assert_called_once_with(mock_proxmox_client, 100)
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.get_proxmox_api_client')
    @patch('k3s_deploy_cli.commands.vm_operations_command._restart_all_k3s_vms')
    def test_handle_restart_command_all_vms(self, mock_restart_all, mock_get_client, basic_proxmox_config, mock_proxmox_client):
        """Test handle_restart_command for all K3s VMs."""
        mock_get_client.return_value = mock_proxmox_client
        args = create_args()
        
        handle_restart_command(args, basic_proxmox_config)
        
        mock_get_client.assert_called_once_with(basic_proxmox_config["proxmox"])
        mock_restart_all.assert_called_once_with(mock_proxmox_client, basic_proxmox_config)


class TestStartSingleVm:
    """Test cases for _start_single_vm function."""
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.console')
    @patch('k3s_deploy_cli.commands.vm_operations_command.find_vm_node')
    @patch('k3s_deploy_cli.commands.vm_operations_command.get_vm_status')
    @patch('k3s_deploy_cli.commands.vm_operations_command.start_vm')
    def test_start_single_vm_success(self, mock_start_vm, mock_get_status, mock_find_node, mock_console, mock_proxmox_client):
        """Test successful single VM start."""
        mock_find_node.return_value = "node1"
        mock_get_status.return_value = {"status": "stopped"}
        setup_mock_vm_operations(mock_proxmox_client, "node1", 100)
        
        _start_single_vm(mock_proxmox_client, 100)
        
        mock_find_node.assert_called_once_with(mock_proxmox_client, 100)
        mock_get_status.assert_called_once_with(mock_proxmox_client, "node1", 100)
        mock_start_vm.assert_called_once_with(mock_proxmox_client, "node1", 100)
        mock_console.print.assert_called_with("[green]Successfully started VM 100[/green]")
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.console')
    @patch('k3s_deploy_cli.commands.vm_operations_command.find_vm_node')
    def test_start_single_vm_not_found(self, mock_find_node, mock_console, mock_proxmox_client):
        """Test single VM start when VM not found."""
        mock_find_node.return_value = None
        
        _start_single_vm(mock_proxmox_client, 100)
        
        mock_find_node.assert_called_once_with(mock_proxmox_client, 100)
        mock_console.print.assert_called_with("[red]VM 100 not found on any accessible node[/red]")
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.console')
    @patch('k3s_deploy_cli.commands.vm_operations_command.find_vm_node')
    @patch('k3s_deploy_cli.commands.vm_operations_command.get_vm_status')
    def test_start_single_vm_already_running(self, mock_get_status, mock_find_node, mock_console, mock_proxmox_client):
        """Test single VM start when already running."""
        mock_find_node.return_value = "node1"
        mock_get_status.return_value = {"status": "running"}
        
        _start_single_vm(mock_proxmox_client, 100)
        
        mock_console.print.assert_called_with("[yellow]VM 100 is already running[/yellow]")
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.console')
    @patch('k3s_deploy_cli.commands.vm_operations_command.find_vm_node')
    @patch('k3s_deploy_cli.commands.vm_operations_command.get_vm_status')
    @patch('k3s_deploy_cli.commands.vm_operations_command.start_vm')
    def test_start_single_vm_error(self, mock_start_vm, mock_get_status, mock_find_node, mock_console, mock_proxmox_client):
        """Test single VM start with error."""
        mock_find_node.return_value = "node1"
        mock_get_status.return_value = {"status": "stopped"}
        mock_start_vm.side_effect = ProxmoxInteractionError("Start failed")
        
        with pytest.raises(ProxmoxInteractionError):
            _start_single_vm(mock_proxmox_client, 100)
        
        mock_console.print.assert_called_with("[red]Failed to start VM 100: Start failed[/red]")


class TestStopSingleVm:
    """Test cases for _stop_single_vm function."""
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.console')
    @patch('k3s_deploy_cli.commands.vm_operations_command.find_vm_node')
    @patch('k3s_deploy_cli.commands.vm_operations_command.get_vm_status')
    @patch('k3s_deploy_cli.commands.vm_operations_command.stop_vm')
    def test_stop_single_vm_graceful_success(self, mock_stop_vm, mock_get_status, mock_find_node, mock_console, mock_proxmox_client):
        """Test successful graceful single VM stop."""
        mock_find_node.return_value = "node1"
        mock_get_status.return_value = {"status": "running"}
        setup_mock_vm_operations(mock_proxmox_client, "node1", 100)
        
        _stop_single_vm(mock_proxmox_client, 100, force=False)
        
        mock_find_node.assert_called_once_with(mock_proxmox_client, 100)
        mock_get_status.assert_called_once_with(mock_proxmox_client, "node1", 100)
        mock_stop_vm.assert_called_once_with(mock_proxmox_client, "node1", 100, False)
        mock_console.print.assert_called_with("[green]Successfully shutdown initiated for VM 100[/green]")
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.console')
    @patch('k3s_deploy_cli.commands.vm_operations_command.find_vm_node')
    @patch('k3s_deploy_cli.commands.vm_operations_command.get_vm_status')
    @patch('k3s_deploy_cli.commands.vm_operations_command.stop_vm')
    def test_stop_single_vm_force_success(self, mock_stop_vm, mock_get_status, mock_find_node, mock_console, mock_proxmox_client):
        """Test successful force single VM stop."""
        mock_find_node.return_value = "node1"
        mock_get_status.return_value = {"status": "running"}
        setup_mock_vm_operations(mock_proxmox_client, "node1", 100)
        
        _stop_single_vm(mock_proxmox_client, 100, force=True)
        
        mock_stop_vm.assert_called_once_with(mock_proxmox_client, "node1", 100, True)
        mock_console.print.assert_called_with("[green]Successfully force stopped VM 100[/green]")
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.console')
    @patch('k3s_deploy_cli.commands.vm_operations_command.find_vm_node')
    @patch('k3s_deploy_cli.commands.vm_operations_command.get_vm_status')
    def test_stop_single_vm_already_stopped(self, mock_get_status, mock_find_node, mock_console, mock_proxmox_client):
        """Test single VM stop when already stopped."""
        mock_find_node.return_value = "node1"
        mock_get_status.return_value = {"status": "stopped"}
        
        _stop_single_vm(mock_proxmox_client, 100, force=False)
        
        mock_console.print.assert_called_with("ℹ️  [yellow]VM 100 is already stopped[/yellow]")


class TestRestartSingleVm:
    """Test cases for _restart_single_vm function."""
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.console')
    @patch('k3s_deploy_cli.commands.vm_operations_command.find_vm_node')
    @patch('k3s_deploy_cli.commands.vm_operations_command.get_vm_status')
    @patch('k3s_deploy_cli.commands.vm_operations_command.restart_vm')
    def test_restart_single_vm_success(self, mock_restart_vm, mock_get_status, mock_find_node, mock_console, mock_proxmox_client):
        """Test successful single VM restart."""
        mock_find_node.return_value = "node1"
        mock_get_status.return_value = {"status": "running"}
        setup_mock_vm_operations(mock_proxmox_client, "node1", 100)
        
        _restart_single_vm(mock_proxmox_client, 100)
        
        mock_find_node.assert_called_once_with(mock_proxmox_client, 100)
        mock_get_status.assert_called_once_with(mock_proxmox_client, "node1", 100)
        mock_restart_vm.assert_called_once_with(mock_proxmox_client, "node1", 100)
        mock_console.print.assert_called_with("[green]Successfully restarted VM 100[/green]")
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.console')
    @patch('k3s_deploy_cli.commands.vm_operations_command.find_vm_node')
    @patch('k3s_deploy_cli.commands.vm_operations_command.get_vm_status')
    def test_restart_single_vm_stopped(self, mock_get_status, mock_find_node, mock_console, mock_proxmox_client):
        """Test single VM restart when VM is stopped."""
        mock_find_node.return_value = "node1"
        mock_get_status.return_value = {"status": "stopped"}
        
        _restart_single_vm(mock_proxmox_client, 100)
        
        mock_console.print.assert_called_with("[red]Cannot restart VM 100: VM is currently stopped[/red]")


class TestStartAllK3sVms:
    """Test cases for _start_all_k3s_vms function."""
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.console')
    @patch('k3s_deploy_cli.commands.vm_operations_command.discover_k3s_nodes')
    @patch('k3s_deploy_cli.commands.vm_operations_command.start_vm')
    def test_start_all_k3s_vms_success(self, mock_start_vm, mock_discover, mock_console, mock_proxmox_client, basic_proxmox_config):
        """Test successful start of all K3s VMs."""
        k3s_vms = create_sample_k3s_vms(2)
        k3s_vms[0]["status"] = "stopped"  # One VM stopped
        k3s_vms[1]["status"] = "running"  # One VM running
        mock_discover.return_value = k3s_vms
        
        _start_all_k3s_vms(mock_proxmox_client, basic_proxmox_config)
        
        mock_discover.assert_called_once_with(mock_proxmox_client)
        mock_start_vm.assert_called_once_with(mock_proxmox_client, k3s_vms[0]["node"], k3s_vms[0]["vmid"])
        assert mock_console.print.call_count >= 2  # Initial message + table
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.console')
    @patch('k3s_deploy_cli.commands.vm_operations_command.discover_k3s_nodes')
    def test_start_all_k3s_vms_no_vms(self, mock_discover, mock_console, mock_proxmox_client, basic_proxmox_config):
        """Test start all K3s VMs when no VMs found."""
        mock_discover.return_value = []
        
        _start_all_k3s_vms(mock_proxmox_client, basic_proxmox_config)
        
        mock_discover.assert_called_once_with(mock_proxmox_client)
        mock_console.print.assert_any_call("[yellow]No K3s VMs found[/yellow]")


class TestStopAllK3sVms:
    """Test cases for _stop_all_k3s_vms function."""
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.console')
    @patch('k3s_deploy_cli.commands.vm_operations_command.discover_k3s_nodes')
    @patch('k3s_deploy_cli.commands.vm_operations_command.stop_vm')
    def test_stop_all_k3s_vms_graceful(self, mock_stop_vm, mock_discover, mock_console, mock_proxmox_client, basic_proxmox_config):
        """Test graceful stop of all K3s VMs."""
        k3s_vms = create_sample_k3s_vms(2)
        k3s_vms[0]["status"] = "running"  # One VM running
        k3s_vms[1]["status"] = "stopped"  # One VM stopped
        mock_discover.return_value = k3s_vms
        
        _stop_all_k3s_vms(mock_proxmox_client, basic_proxmox_config, force=False)
        
        mock_discover.assert_called_once_with(mock_proxmox_client)
        mock_stop_vm.assert_called_once_with(mock_proxmox_client, k3s_vms[0]["node"], k3s_vms[0]["vmid"], False)


class TestRestartAllK3sVms:
    """Test cases for _restart_all_k3s_vms function."""
    
    @patch('k3s_deploy_cli.commands.vm_operations_command.console')
    @patch('k3s_deploy_cli.commands.vm_operations_command.discover_k3s_nodes')
    @patch('k3s_deploy_cli.commands.vm_operations_command.restart_vm')
    def test_restart_all_k3s_vms_success(self, mock_restart_vm, mock_discover, mock_console, mock_proxmox_client, basic_proxmox_config):
        """Test restart of all K3s VMs."""
        k3s_vms = create_sample_k3s_vms(2)
        k3s_vms[0]["status"] = "running"  # One VM running
        k3s_vms[1]["status"] = "stopped"  # One VM stopped
        mock_discover.return_value = k3s_vms
        
        _restart_all_k3s_vms(mock_proxmox_client, basic_proxmox_config)
        
        mock_discover.assert_called_once_with(mock_proxmox_client)
        mock_restart_vm.assert_called_once_with(mock_proxmox_client, k3s_vms[0]["node"], k3s_vms[0]["vmid"])

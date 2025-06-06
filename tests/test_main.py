# file: tests/test_main.py
"""Unit tests for the main entry point and command dispatch logic."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from argparse import Namespace

from k3s_deploy_cli.main import main, _dispatch_command
from k3s_deploy_cli.exceptions import ConfigurationError, K3sDeployCLIError, ProxmoxInteractionError


class TestMainEntryPoint:
    """Tests for the main() function - the primary entry point."""

    @patch('k3s_deploy_cli.main.parse_args')
    @patch('k3s_deploy_cli.main.configure_logging')
    @patch('k3s_deploy_cli.main.load_configuration')
    @patch('k3s_deploy_cli.main._dispatch_command')
    @patch('k3s_deploy_cli.main.Console')
    def test_main_happy_path(self, mock_console, mock_dispatch, mock_load_config, 
                           mock_configure_logging, mock_parse_args):
        """Test successful main execution with valid arguments."""
        # Arrange
        mock_args = Namespace(
            command='info',
            verbose=False,
            debug=False,
            config=Path('config.json')
        )
        mock_parse_args.return_value = mock_args
        mock_config = {'proxmox': {'host': 'test.com'}}
        mock_load_config.return_value = mock_config
        mock_console_instance = MagicMock()
        mock_console.return_value = mock_console_instance

        # Act & Assert - Should not raise any exceptions
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        # Verify successful exit code
        assert exc_info.value.code == 0
        
        # Verify all components were called correctly
        mock_parse_args.assert_called_once()
        mock_configure_logging.assert_called_once_with(verbose=False, debug=False)
        mock_load_config.assert_called_once()
        mock_dispatch.assert_called_once_with(mock_args, mock_config, mock_console_instance)

    @patch('k3s_deploy_cli.main.parse_args')
    @patch('k3s_deploy_cli.main.configure_logging')
    def test_main_no_command_provided(self, mock_configure_logging, mock_parse_args):
        """Test main() when no command is provided."""
        # Arrange
        mock_args = Namespace(
            command=None,
            verbose=False,
            debug=False,
            config=Path('config.json')
        )
        mock_parse_args.return_value = mock_args

        # Act & Assert
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        # Verify error exit code
        assert exc_info.value.code == 1

    @patch('k3s_deploy_cli.main.parse_args')
    @patch('k3s_deploy_cli.main.configure_logging')
    @patch('k3s_deploy_cli.main.load_configuration')
    def test_main_configuration_error(self, mock_load_config, mock_configure_logging, mock_parse_args):
        """Test main() handling of configuration errors."""
        # Arrange
        mock_args = Namespace(
            command='info',
            verbose=False,
            debug=False,
            config=Path('invalid_config.json')
        )
        mock_parse_args.return_value = mock_args
        mock_load_config.side_effect = ConfigurationError("Config file not found")

        # Act & Assert
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 1

    @patch('k3s_deploy_cli.main.parse_args')
    @patch('k3s_deploy_cli.main.configure_logging')
    @patch('k3s_deploy_cli.main.load_configuration')
    @patch('k3s_deploy_cli.main._dispatch_command')
    @patch('k3s_deploy_cli.main.Console')
    def test_main_cli_error(self, mock_console, mock_dispatch, mock_load_config, 
                          mock_configure_logging, mock_parse_args):
        """Test main() handling of CLI errors."""
        # Arrange
        mock_args = Namespace(
            command='info',
            verbose=False,
            debug=False,
            config=Path('config.json')
        )
        mock_parse_args.return_value = mock_args
        mock_config = {'proxmox': {'host': 'test.com'}}
        mock_load_config.return_value = mock_config
        mock_dispatch.side_effect = K3sDeployCLIError("CLI operation failed")

        # Act & Assert
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 1

    @patch('k3s_deploy_cli.main.parse_args')
    @patch('k3s_deploy_cli.main.configure_logging')
    @patch('k3s_deploy_cli.main.load_configuration')
    @patch('k3s_deploy_cli.main._dispatch_command')
    @patch('k3s_deploy_cli.main.Console')
    def test_main_unexpected_error(self, mock_console, mock_dispatch, mock_load_config, 
                                 mock_configure_logging, mock_parse_args):
        """Test main() handling of unexpected errors."""
        # Arrange
        mock_args = Namespace(
            command='info',
            verbose=False,
            debug=True,  # Test debug mode
            config=Path('config.json')
        )
        mock_parse_args.return_value = mock_args
        mock_config = {'proxmox': {'host': 'test.com'}}
        mock_load_config.return_value = mock_config
        mock_dispatch.side_effect = ValueError("Unexpected error")

        # Act & Assert
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 1


class TestCommandDispatch:
    """Tests for the _dispatch_command() function."""

    @patch('k3s_deploy_cli.main.InfoCommand')
    def test_dispatch_info_command(self, mock_info_command_class):
        """Test dispatching to info command."""
        # Arrange
        args = Namespace(command='info', discover=False)
        config = {'proxmox': {'host': 'test.com'}}
        console = MagicMock()
        mock_info_command = MagicMock()
        mock_info_command_class.return_value = mock_info_command

        # Act
        _dispatch_command(args, config, console)

        # Assert
        mock_info_command_class.assert_called_once_with(config, console)
        mock_info_command.execute.assert_called_once_with(discover=False)

    @patch('k3s_deploy_cli.main.InfoCommand')
    def test_dispatch_info_command_with_discover(self, mock_info_command_class):
        """Test dispatching to info command with discover flag."""
        # Arrange
        args = Namespace(command='info', discover=True)
        config = {'proxmox': {'host': 'test.com'}}
        console = MagicMock()
        mock_info_command = MagicMock()
        mock_info_command_class.return_value = mock_info_command

        # Act
        _dispatch_command(args, config, console)

        # Assert
        mock_info_command_class.assert_called_once_with(config, console)
        mock_info_command.execute.assert_called_once_with(discover=True)

    @patch('k3s_deploy_cli.main.DiscoverCommand')
    def test_dispatch_discover_command(self, mock_discover_command_class):
        """Test dispatching to discover command."""
        # Arrange
        args = Namespace(command='discover', format='table', output='stdout')
        config = {'proxmox': {'host': 'test.com'}}
        console = MagicMock()
        mock_discover_command = MagicMock()
        mock_discover_command_class.return_value = mock_discover_command

        # Act
        _dispatch_command(args, config, console)

        # Assert
        mock_discover_command_class.assert_called_once_with(config, console)
        mock_discover_command.execute.assert_called_once_with('table', 'stdout')

    @patch('k3s_deploy_cli.main.DiscoverCommand')
    def test_dispatch_discover_command_json_format(self, mock_discover_command_class):
        """Test dispatching to discover command with JSON format."""
        # Arrange
        args = Namespace(command='discover', format='json', output='file')
        config = {'proxmox': {'host': 'test.com'}}
        console = MagicMock()
        mock_discover_command = MagicMock()
        mock_discover_command_class.return_value = mock_discover_command

        # Act
        _dispatch_command(args, config, console)

        # Assert
        mock_discover_command_class.assert_called_once_with(config, console)
        mock_discover_command.execute.assert_called_once_with('json', 'file')

    def test_dispatch_unknown_command(self):
        """Test dispatching unknown command."""
        # Arrange
        args = Namespace(command='unknown')
        config = {'proxmox': {'host': 'test.com'}}
        console = MagicMock()

        # Act & Assert
        with pytest.raises(SystemExit) as exc_info:
            _dispatch_command(args, config, console)
        
        assert exc_info.value.code == 2

    @patch('k3s_deploy_cli.main.InfoCommand')
    def test_dispatch_command_missing_discover_attr(self, mock_info_command_class):
        """Test dispatching info command when discover attribute is missing."""
        # Arrange
        args = Namespace(command='info')  # Missing discover attribute
        config = {'proxmox': {'host': 'test.com'}}
        console = MagicMock()
        mock_info_command = MagicMock()
        mock_info_command_class.return_value = mock_info_command

        # Act - Should handle missing attribute gracefully
        _dispatch_command(args, config, console)
        
        # Assert
        mock_info_command_class.assert_called_once_with(config, console)
        mock_info_command.execute.assert_called_once_with(discover=False)


class TestMainIntegrationScenarios:
    """Integration-style tests for main() with realistic scenarios."""

    @patch('k3s_deploy_cli.main.sys.argv', ['k3s-deploy'])
    @patch('k3s_deploy_cli.main.parse_args')
    def test_main_no_args_help_displayed(self, mock_parse_args):
        """Test that help is displayed when no arguments provided."""
        # parse_args should handle this scenario and exit
        mock_parse_args.side_effect = SystemExit(1)
        
        with pytest.raises(SystemExit):
            main()

    @patch('k3s_deploy_cli.main.parse_args')
    @patch('k3s_deploy_cli.main.configure_logging')
    @patch('k3s_deploy_cli.main.load_configuration')
    @patch('k3s_deploy_cli.main._dispatch_command')
    @patch('k3s_deploy_cli.main.Console')
    def test_main_verbose_debug_logging(self, mock_console, mock_dispatch, mock_load_config, 
                                      mock_configure_logging, mock_parse_args):
        """Test main() with verbose and debug flags."""
        # Arrange
        mock_args = Namespace(
            command='info',
            verbose=True,
            debug=True,
            config=Path('config.json')
        )
        mock_parse_args.return_value = mock_args
        mock_config = {'proxmox': {'host': 'test.com'}}
        mock_load_config.return_value = mock_config

        # Act
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        # Assert
        assert exc_info.value.code == 0
        mock_configure_logging.assert_called_once_with(verbose=True, debug=True)

    @patch('k3s_deploy_cli.main.parse_args')
    @patch('k3s_deploy_cli.main.configure_logging')
    @patch('k3s_deploy_cli.main.load_configuration')
    @patch('k3s_deploy_cli.main._dispatch_command')
    @patch('k3s_deploy_cli.main.Console')
    def test_main_custom_config_path(self, mock_console, mock_dispatch, mock_load_config, 
                                   mock_configure_logging, mock_parse_args):
        """Test main() with custom configuration file path."""
        # Arrange
        custom_config_path = Path('/custom/path/config.json')
        mock_args = Namespace(
            command='info',
            verbose=False,
            debug=False,
            config=custom_config_path
        )
        mock_parse_args.return_value = mock_args
        mock_config = {'proxmox': {'host': 'test.com'}}
        mock_load_config.return_value = mock_config

        # Act
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        # Assert
        assert exc_info.value.code == 0
        # Verify load_configuration was called with custom path
        args, kwargs = mock_load_config.call_args
        assert args[0] == custom_config_path

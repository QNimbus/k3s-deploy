# file: tests/test_cli_parser.py
"""Unit tests for the CLI argument parser module."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch
from argparse import ArgumentParser, Namespace

from k3s_deploy_cli.cli_parser import create_parser, parse_args, _add_subcommands


class TestCreateParser:
    """Tests for the create_parser() function."""

    def test_create_parser_returns_argument_parser(self):
        """Test that create_parser returns an ArgumentParser instance."""
        parser = create_parser()
        assert isinstance(parser, ArgumentParser)

    def test_create_parser_has_correct_prog_name(self):
        """Test that parser has correct program name."""
        parser = create_parser()
        assert parser.prog == "k3s-deploy"

    def test_create_parser_has_description(self):
        """Test that parser has a description."""
        parser = create_parser()
        assert "CLI tool to deploy and manage K3s clusters" in parser.description

    def test_create_parser_has_version_argument(self):
        """Test that parser includes version argument."""
        parser = create_parser()
        # Test that version argument works
        with pytest.raises(SystemExit):
            parser.parse_args(['--version'])

    def test_create_parser_has_common_arguments(self):
        """Test that parser includes common arguments (-v, -d, -c)."""
        # Note: This test uses parse_args() function which handles two-phase parsing
        # The parser returned by create_parser() alone doesn't handle global flags
        args = parse_args(['-v', '-d', '-c', 'custom.json', 'info'])
        
        assert args.verbose is True
        assert args.debug is True
        assert args.config == Path('custom.json')
        assert args.command == 'info'

    def test_create_parser_has_subcommands(self):
        """Test that parser includes subcommands (info, discover)."""
        parser = create_parser()
        
        # Test info subcommand
        args = parser.parse_args(['info'])
        assert args.command == 'info'
        
        # Test discover subcommand
        args = parser.parse_args(['discover'])
        assert args.command == 'discover'


class TestParseArgs:
    """Tests for the parse_args() function."""

    def test_parse_args_info_command_basic(self):
        """Test parsing basic info command."""
        args = parse_args(['info'])
        
        assert args.command == 'info'
        assert args.verbose is False
        assert args.debug is False
        assert args.config == Path('config.json')
        assert hasattr(args, 'discover')
        assert args.discover is False

    def test_parse_args_info_command_with_discover(self):
        """Test parsing info command with discover flag."""
        args = parse_args(['info', '--discover'])
        
        assert args.command == 'info'
        assert args.discover is True

    def test_parse_args_info_command_with_flags(self):
        """Test parsing info command with verbose and debug flags."""
        args = parse_args(['info', '-v', '-d'])
        
        assert args.command == 'info'
        assert args.verbose is True
        assert args.debug is True

    def test_parse_args_discover_command_basic(self):
        """Test parsing basic discover command."""
        args = parse_args(['discover'])
        
        assert args.command == 'discover'
        assert args.format == 'table'  # default
        assert args.output == 'stdout'  # default

    def test_parse_args_discover_command_json_format(self):
        """Test parsing discover command with JSON format."""
        args = parse_args(['discover', '--format', 'json'])
        
        assert args.command == 'discover'
        assert args.format == 'json'

    def test_parse_args_discover_command_file_output(self):
        """Test parsing discover command with file output."""
        args = parse_args(['discover', '--output', 'file'])
        
        assert args.command == 'discover'
        assert args.output == 'file'

    def test_parse_args_discover_command_all_options(self):
        """Test parsing discover command with all options."""
        args = parse_args(['discover', '--format', 'json', '--output', 'file', '-v'])
        
        assert args.command == 'discover'
        assert args.format == 'json'
        assert args.output == 'file'
        assert args.verbose is True

    def test_parse_args_flexible_flag_placement_before_command(self):
        """Test that flags work when placed before subcommands."""
        args = parse_args(['-v', '-d', 'info'])
        
        assert args.verbose is True
        assert args.debug is True
        assert args.command == 'info'

    def test_parse_args_flexible_flag_placement_after_command(self):
        """Test that flags work when placed after subcommands."""
        args = parse_args(['info', '-v', '-d'])
        
        assert args.verbose is True
        assert args.debug is True
        assert args.command == 'info'

    def test_parse_args_custom_config_path(self):
        """Test parsing with custom configuration file path."""
        custom_path = '/custom/path/config.json'
        args = parse_args(['-c', custom_path, 'info'])
        
        assert args.config == Path(custom_path)
        assert args.command == 'info'

    def test_parse_args_short_and_long_flags(self):
        """Test that both short and long form flags work."""
        # Test short flags
        args = parse_args(['-v', '-d', '-c', 'test.json', 'info'])
        assert args.verbose is True
        assert args.debug is True
        assert args.config == Path('test.json')
        
        # Test long flags
        args = parse_args(['--verbose', '--debug', '--config', 'test.json', 'info'])
        assert args.verbose is True
        assert args.debug is True
        assert args.config == Path('test.json')

    @patch('k3s_deploy_cli.cli_parser.sys.argv', ['k3s-deploy'])
    def test_parse_args_no_arguments_prints_help(self):
        """Test that parse_args prints help and exits when no arguments provided."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args()
        
        assert exc_info.value.code == 1

    def test_parse_args_invalid_command(self):
        """Test parsing with invalid command."""
        with pytest.raises(SystemExit):
            parse_args(['invalid-command'])

    def test_parse_args_invalid_format_option(self):
        """Test parsing discover command with invalid format option."""
        with pytest.raises(SystemExit):
            parse_args(['discover', '--format', 'invalid'])

    def test_parse_args_invalid_output_option(self):
        """Test parsing discover command with invalid output option."""
        with pytest.raises(SystemExit):
            parse_args(['discover', '--output', 'invalid'])

    def test_parse_args_help_flag(self):
        """Test that help flag works."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(['--help'])
        
        # Help should exit with code 0
        assert exc_info.value.code == 0

    def test_parse_args_subcommand_help(self):
        """Test that subcommand help works."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(['info', '--help'])
        
        assert exc_info.value.code == 0

    def test_parse_args_with_explicit_args_list(self):
        """Test parse_args with explicitly provided arguments list."""
        test_args = ['info', '--discover', '-v']
        args = parse_args(test_args)
        
        assert args.command == 'info'
        assert args.discover is True
        assert args.verbose is True


class TestSubcommandAddition:
    """Tests for the _add_subcommands() function."""

    def test_add_subcommands_creates_info_parser(self):
        """Test that _add_subcommands creates info subcommand parser."""
        parser = ArgumentParser()
        common_parser = ArgumentParser(add_help=False)
        
        _add_subcommands(parser, common_parser)
        
        # Test that info subcommand was added
        args = parser.parse_args(['info'])
        assert args.command == 'info'

    def test_add_subcommands_creates_discover_parser(self):
        """Test that _add_subcommands creates discover subcommand parser."""
        parser = ArgumentParser()
        common_parser = ArgumentParser(add_help=False)
        
        _add_subcommands(parser, common_parser)
        
        # Test that discover subcommand was added
        args = parser.parse_args(['discover'])
        assert args.command == 'discover'

    def test_add_subcommands_info_has_discover_flag(self):
        """Test that info subcommand has discover flag."""
        parser = ArgumentParser()
        common_parser = ArgumentParser(add_help=False)
        
        _add_subcommands(parser, common_parser)
        
        args = parser.parse_args(['info', '--discover'])
        assert hasattr(args, 'discover')
        assert args.discover is True

    def test_add_subcommands_discover_has_format_and_output(self):
        """Test that discover subcommand has format and output options."""
        parser = ArgumentParser()
        common_parser = ArgumentParser(add_help=False)
        
        _add_subcommands(parser, common_parser)
        
        args = parser.parse_args(['discover', '--format', 'json', '--output', 'file'])
        assert args.format == 'json'
        assert args.output == 'file'


class TestArgumentValidation:
    """Tests for argument validation and edge cases."""

    def test_boolean_flags_default_values(self):
        """Test that boolean flags have correct default values."""
        args = parse_args(['info'])
        
        assert args.verbose is False
        assert args.debug is False
        assert args.discover is False

    def test_path_argument_conversion(self):
        """Test that config argument is converted to Path object."""
        args = parse_args(['-c', 'test.json', 'info'])
        
        assert isinstance(args.config, Path)
        assert str(args.config) == 'test.json'

    def test_default_config_path(self):
        """Test that default config path is correct."""
        args = parse_args(['info'])
        
        assert args.config == Path('config.json')

    def test_multiple_flags_combination(self):
        """Test various combinations of flags."""
        # Test all flags together
        args = parse_args(['-v', '-d', 'info', '--discover'])
        assert args.verbose is True
        assert args.debug is True
        assert args.discover is True
        
        # Test partial combinations
        args = parse_args(['-v', 'discover', '--format', 'json'])
        assert args.verbose is True
        assert args.debug is False
        assert args.format == 'json'

    def test_conflicting_flags_behavior(self):
        """Test behavior with flags that could conflict."""
        # debug=True should work with verbose=True 
        args = parse_args(['-v', '-d', 'info'])
        assert args.verbose is True
        assert args.debug is True

    def test_case_sensitivity(self):
        """Test that command and option values are case sensitive."""
        # Commands should be case sensitive
        with pytest.raises(SystemExit):
            parse_args(['INFO'])  # uppercase should fail
        
        # Format values should be case sensitive  
        with pytest.raises(SystemExit):
            parse_args(['discover', '--format', 'JSON'])  # uppercase should fail


class TestComplexArgumentCombinations:
    """Tests for complex real-world argument combinations."""

    def test_full_info_command_with_all_flags(self):
        """Test info command with all possible flags."""
        args = parse_args([
            '--verbose', '--debug', '--config', '/path/to/config.json',
            'info', '--discover'
        ])
        
        assert args.command == 'info'
        assert args.verbose is True
        assert args.debug is True
        assert args.config == Path('/path/to/config.json')
        assert args.discover is True

    def test_full_discover_command_with_all_options(self):
        """Test discover command with all possible options."""
        args = parse_args([
            '-v', '-d', '-c', 'custom.json',
            'discover', '--format', 'json', '--output', 'file'
        ])
        
        assert args.command == 'discover'
        assert args.verbose is True
        assert args.debug is True
        assert args.config == Path('custom.json')
        assert args.format == 'json'
        assert args.output == 'file'

    def test_minimal_valid_commands(self):
        """Test minimal valid command invocations."""
        # Minimal info command
        args = parse_args(['info'])
        assert args.command == 'info'
        
        # Minimal discover command
        args = parse_args(['discover'])
        assert args.command == 'discover'

    def test_realistic_user_scenarios(self):
        """Test realistic command-line scenarios users might type."""
        # User wants verbose info with discovery
        args = parse_args(['k3s-deploy', '-v', 'info', '--discover'][1:])  # Skip program name
        assert args.verbose is True
        assert args.command == 'info'
        assert args.discover is True
        
        # User wants to discover and save to file
        args = parse_args(['discover', '--format', 'json', '--output', 'file'])
        assert args.command == 'discover'
        assert args.format == 'json'
        assert args.output == 'file'
        
        # User wants debug output for troubleshooting
        args = parse_args(['-d', 'info'])
        assert args.debug is True
        assert args.command == 'info'
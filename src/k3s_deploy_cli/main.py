# file: src/k3s_deploy_cli/main.py
"""
Main entry point for the K3s Deploy CLI.

This module provides the primary entry point and orchestrates command
execution with centralized configuration loading and error handling.
"""

import sys
from pathlib import Path

from loguru import logger
from rich.console import Console

from . import APP_NAME, __version__
from .cli_parser import parse_args
from .commands import handle_discover_command, handle_info_command
from .config import load_configuration
from .exceptions import ConfigurationError, K3sDeployCLIError
from .logging_config import configure_logging


def main() -> None:
    """Main entry point for the K3s Deploy CLI."""
    # Parse command-line arguments
    args = parse_args()

    # Configure logging based on parsed arguments
    configure_logging(verbose=args.verbose, debug=args.debug)

    logger.debug(f"Parsed arguments: {args}")
    logger.debug(f"Running {APP_NAME} version {__version__}")

    # Validate that a command was provided
    if not args.command:
        logger.info(
            f"No command specified. Use '{APP_NAME} --help' for available commands."
        )
        sys.exit(1)

    # Initialize console for output
    console = Console()
    
    try:
        # Load configuration
        schema_file_path = Path(__file__).parent / "config_schema.json"
        logger.info(f"Loading configuration from: {args.config.resolve()}")
        
        config = load_configuration(args.config, schema_file_path)
        logger.debug(f"Loaded application configuration: {config}")

        # Dispatch to appropriate command handler
        _dispatch_command(args, config, console)

    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        if args.debug:
            logger.opt(exception=True).debug("Configuration error traceback:")
        sys.exit(1)
    except K3sDeployCLIError as e:
        logger.error(f"CLI Error: {e}")
        if args.debug:
            logger.opt(exception=True).debug("CLI error traceback:")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        if args.debug:
            logger.opt(exception=True).debug("Unexpected error traceback:")
        sys.exit(1)

    logger.debug(f"{APP_NAME} finished.")
    sys.exit(0)


def _dispatch_command(args, config, console) -> None:
    """
    Dispatch the parsed command to the appropriate handler.

    Args:
        args: Parsed command-line arguments.
        config: Loaded application configuration.
        console: Rich Console instance for output.
    """
    if args.command == "info":
        handle_info_command(
            config, console, discover=getattr(args, "discover", False)
        )
    elif args.command == "discover":
        handle_discover_command(config, console, args.format, args.output)
    else:
        # This should not be reached if subparsers are defined correctly
        logger.warning(f"Unknown command: {args.command}")
        sys.exit(2)


if __name__ == "__main__":
    main()
# file: src/k3s_deploy_cli/logging_config.py
"""Configures logging for the K3s Deploy CLI application.

This module provides a function to set up the Loguru logger,
allowing for different log levels such as verbose and debug.
It standardizes how log messages are formatted and output.
"""

import sys

from loguru import logger  # type: ignore # Imported via Poetry dependency

LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {module}:{function}:{line} - {message}"
# Add a new log level for VERBOSE output
VERBOSE_LOG_LEVEL = "VERBOSE"
# Define a custom log level "VERBOSE" with a level number of 15.
# This value is chosen to fit between DEBUG (10) and INFO (20), ensuring it does not conflict with standard log levels.
# It provides a distinct level for verbose output, useful for detailed logs without enabling full debug mode.
# Check if the VERBOSE log level already exists before defining it
if not any(level.name == VERBOSE_LOG_LEVEL for level in logger._core.levels.values()):
    logger.level(VERBOSE_LOG_LEVEL, no=15, color="<blue>", icon="📣")

def configure_logging(verbose: bool = False, debug: bool = False) -> None:
    """
    Configures the Loguru logger.

    Args:
        verbose (bool): If True, sets the log level to VERBOSE. Defaults to False.
        debug (bool): If True, sets the log level to DEBUG. Takes precedence over verbose. Defaults to False.
    """
    # Remove existing stderr handlers only, preserve other handlers (like test captures)
    # This includes loguru's default handler and any manually added stderr handlers
    handlers_to_remove = []
    for handler_id, handler in logger._core.handlers.items():
        should_remove = False
        
        # Check if this is a stderr handler by looking at the handler configuration
        # Method 1: Check _sink attribute (for manually added handlers)
        if hasattr(handler, '_sink') and handler._sink is sys.stderr:
            should_remove = True
        
        # Method 2: Check if it's loguru's default handler (usually has handler_id of 0)
        # Default handler typically writes to stderr and has specific characteristics
        elif handler_id == 0:
            # This is likely the default handler, remove it
            should_remove = True
            
        # Method 3: Check sink attribute (alternative structure)
        elif hasattr(handler, 'sink') and handler.sink is sys.stderr:
            should_remove = True
            
        if should_remove:
            handlers_to_remove.append(handler_id)

    for handler_id in handlers_to_remove:
        logger.remove(handler_id)

    level: str
    log_format_to_use: str

    if debug:
        level = "DEBUG"
        log_format_to_use = LOG_FORMAT  # Keep detailed format for DEBUG
    elif verbose:
        level = VERBOSE_LOG_LEVEL
        log_format_to_use = "{time:HH:mm:ss} | {level: <8} | {message}" # Simpler format for VERBOSE
    else:
        level = "INFO"
        log_format_to_use = "{time:HH:mm:ss} | {level: <8} | {message}" # Simpler format for INFO

    # For debug mode, enable backtrace and diagnose for more detailed error reports
    logger.add(
        sys.stderr,
        format=log_format_to_use, # Use the determined format
        level=level,  # Explicitly set the handler level
        backtrace=debug, # Enable backtrace in debug mode
        diagnose=debug   # Enable diagnose in debug mode
    )
    
    # Use a specific logger call that will respect the configured level
    # For example, if level is INFO, a logger.debug() message here won't show.
    # We can use logger.patch to ensure this configuration message is always shown if needed,
    # or simply log at the configured level.
    # For now, let's make sure it's visible if the configured level allows.
    logger.debug("Logger configured with level: {} and format: '{}'", level, log_format_to_use)

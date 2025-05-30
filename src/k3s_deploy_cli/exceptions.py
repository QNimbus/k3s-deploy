# file: src/k3s_deploy_cli/exceptions.py
"""
Custom exception classes for the K3s Deployment CLI.

This module defines a hierarchy of custom exceptions to provide more specific
error information than built-in exceptions. This helps in better error handling
and debugging throughout the application.
"""

from typing import Optional


class K3sDeployCLIError(Exception):
    """
    Base class for all custom exceptions in the K3s Deployment CLI.

    This exception is not meant to be raised directly but serves as a parent
    for more specific error types.
    """
    def __init__(self, message: str, original_exception: Optional[Exception] = None) -> None:
        """
        Initialize the base K3sDeployCLIError.

        Args:
            message: A human-readable error message.
            original_exception: The original exception that caused this error, if any.
        """
        super().__init__(message)
        self.original_exception = original_exception
        self.message = message

    def __str__(self) -> str:
        """Return the string representation of the exception."""
        if self.original_exception:
            return f"{self.message}: {self.original_exception}"
        return self.message

class ProxmoxInteractionError(K3sDeployCLIError):
    """
    Raised when an error occurs while interacting with the Proxmox VE API.

    This could be due to connection issues, authentication failures, API command
    errors, or unexpected responses from the Proxmox server.
    """
    def __init__(self, message: str, original_exception: Optional[Exception] = None) -> None:
        """
        Initialize the ProxmoxInteractionError.

        Args:
            message: A human-readable error message describing the Proxmox API issue.
            original_exception: The original exception from the Proxmox library or HTTP request.
        """
        super().__init__(message, original_exception)

class SSHConnectionError(K3sDeployCLIError):
    """
    Raised when an error occurs during an SSH connection or command execution.

    This can include issues like authentication failures, host key mismatches,
    network timeouts, or errors during remote command execution.
    """
    def __init__(self, message: str, original_exception: Optional[Exception] = None) -> None:
        """
        Initialize the SSHConnectionError.

        Args:
            message: A human-readable error message describing the SSH issue.
            original_exception: The original exception from the SSH library (e.g., Paramiko).
        """
        super().__init__(message, original_exception)

class ConfigurationError(K3sDeployCLIError):
    """
    Raised when there is an issue with the application's configuration.

    This could be due to a missing configuration file, invalid schema,
    or incorrect values for configuration parameters.
    """
    def __init__(self, message: str, original_exception: Optional[Exception] = None) -> None:
        """
        Initialize the ConfigurationError.

        Args:
            message: A human-readable error message describing the configuration issue.
            original_exception: The original exception, if any (e.g., JSONDecodeError).
        """
        super().__init__(message, original_exception)

class VMOperationError(K3sDeployCLIError):
    """
    Raised when an operation on a Proxmox VM fails.

    Examples include failing to start, stop, or configure a VM.
    """
    def __init__(self, message: str, original_exception: Optional[Exception] = None) -> None:
        """
        Initialize the VMOperationError.

        Args:
            message: A human-readable error message describing the VM operation failure.
            original_exception: The original exception, if any.
        """
        super().__init__(message, original_exception)

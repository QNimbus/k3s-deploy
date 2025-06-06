# file: src/k3s_deploy_cli/ssh_operations.py
"""Provides SSH connectivity checks for Proxmox hosts.

This module contains functions to test and verify SSH connections
to Proxmox servers, supporting various authentication methods.
It helps ensure that remote operations can be performed successfully.
"""

import re
import socket
from typing import Any, Dict, Optional

import paramiko
from loguru import logger

from k3s_deploy_cli.exceptions import ConfigurationError, ProvisionError


def check_proxmox_ssh_connectivity(
    config: Dict[str, Any],
    port: int = 22,
    timeout: int = 10
) -> Dict[str, Any]:
    """
    Check SSH connectivity to Proxmox host using available authentication methods.

    This function attempts to establish an SSH connection to the Proxmox host,
    trying public key authentication first, then password authentication if
    public key fails and a password is provided.

    Args:
        config: The 'proxmox' section of the application configuration.
                Must contain 'host'.
                May contain 'user' (defaults to 'root', 'user@realm' is handled).
                May contain 'password'.
        port: SSH port to connect to (default: 22).
        timeout: Connection and authentication timeout in seconds (default: 10).

    Returns:
        Dict containing connection status and authentication information:
        {
            "success": bool,
            "host": str,
            "port": int,
            "username_for_ssh": str,
            "server_allows_publickey_auth": bool, # True if server indicated PK as an option
            "server_allows_password_auth": bool, # True if server indicated PWD as an option
            "auth_method_used": Optional[str],   # 'publickey' or 'password' on success
            "connection_established": bool,    # Whether an SSH connection succeeded
            "warning": Optional[str],
            "error": Optional[str]
        }

    Raises:
        ConfigurationError: If 'host' is missing from config.
        # SSHConnectionError is not raised by this function directly anymore,
        # critical connection issues are reported in the "error" field of the result.
    """
    host: Optional[str] = config.get("host")
    if not host:
        raise ConfigurationError("Proxmox host must be configured for SSH connectivity check.")

    user_config: str = config.get("user", "root")
    # Split on '@' to handle Proxmox format like 'root@pam' - use only username for SSH
    username: str = user_config.split("@")[0] if "@" in user_config else user_config

    result = {
        "success": False,
        "host": host,
        "port": port,
        "username_for_ssh": username,
        "server_allows_publickey_auth": False,
        "server_allows_password_auth": False,
        "auth_method_used": None,
        "connection_established": False,
        "warning": None,
        "error": None
    }

    ssh_client_pk = None
    # Attempt 1: Public Key Authentication
    try:
        logger.debug(f"Attempting SSH public key authentication for {username}@{host}:{port}")
        ssh_client_pk = paramiko.SSHClient()
        ssh_client_pk.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client_pk.connect(
            hostname=host,
            port=port,
            username=username,
            allow_agent=True,
            look_for_keys=True,
            timeout=timeout,
            auth_timeout=timeout # Timeout for the authentication phase itself
        )
        result["success"] = True
        result["connection_established"] = True
        result["auth_method_used"] = "publickey"
        result["server_allows_publickey_auth"] = True # Succeeded, so it's allowed and used
        logger.info(f"SSH public key authentication successful for {username}@{host}:{port}")
        return result  # Successfully connected with public key

    except paramiko.AuthenticationException as e:
        logger.debug(f"Public key authentication failed for {username}@{host}:{port}: {e}")
        result["server_allows_publickey_auth"] = True # Auth failed, so method was likely offered by server
    except (socket.error, paramiko.SSHException) as e:
        # Includes paramiko.ssh_exception.NoValidConnectionsError, socket.timeout, etc.
        error_msg = f"SSH connection to {username}@{host}:{port} failed: {str(e)}"
        logger.error(error_msg)
        result["error"] = error_msg
        # This is a fundamental connection issue, no point in trying password auth.
        return result
    except Exception as e: # Catch-all for other unexpected errors during PK attempt
        error_msg = f"Unexpected error during SSH public key auth for {username}@{host}:{port}: {str(e)}"
        logger.error(error_msg)
        result["error"] = error_msg
        # Proceed to password auth if configured, as this wasn't a clear connection/auth protocol error.
    finally:
        if ssh_client_pk:
            ssh_client_pk.close()

    # If PK auth was successful, we would have returned.
    # Proceed to Password Authentication if configured.
    if config.get("password"):
        ssh_client_pwd = None
        try:
            logger.debug(f"Attempting SSH password authentication for {username}@{host}:{port}")
            ssh_client_pwd = paramiko.SSHClient()
            ssh_client_pwd.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client_pwd.connect(
                hostname=host,
                port=port,
                username=username,
                password=config.get("password"),
                allow_agent=False,
                look_for_keys=False,
                timeout=timeout,
                auth_timeout=timeout
            )
            result["success"] = True
            # If PK attempt failed due to auth, connection_established might be considered true
            # if the socket connection itself was fine. For clarity, set it if password auth succeeds.
            result["connection_established"] = True
            result["auth_method_used"] = "password"
            result["server_allows_password_auth"] = True # Succeeded, so it's allowed and used
            logger.info(f"SSH password authentication successful for {username}@{host}:{port}")
            return result # Successfully connected with password

        except paramiko.AuthenticationException as e:
            logger.debug(f"Password authentication failed for {username}@{host}:{port}: {e}")
            result["server_allows_password_auth"] = True # Auth failed, method likely offered
        except (socket.error, paramiko.SSHException) as e:
            # This would be less common if PK attempt reached AuthenticationException,
            # but could happen (e.g. server becomes unresponsive).
            error_msg = f"SSH connection to {username}@{host}:{port} failed during password auth: {str(e)}"
            logger.error(error_msg)
            if not result["error"]: # Prioritize earlier, possibly more fundamental error
                result["error"] = error_msg
            if ssh_client_pwd:
                ssh_client_pwd.close()
            return result # Fundamental connection issue
        except Exception as e: # Catch-all for other unexpected errors
            error_msg = f"Unexpected error during SSH password auth for {username}@{host}:{port}: {str(e)}"
            logger.error(error_msg)
            if not result["error"]:
                result["error"] = error_msg
        finally:
            if ssh_client_pwd:
                ssh_client_pwd.close()
    else:
        # No password configured, and PK auth did not succeed.
        if result["server_allows_publickey_auth"] and not result["error"]: # PK was offered but failed creds
            result["error"] = (
                f"SSH public key authentication failed for {username}@{host}. "
                "No password was configured to attempt password authentication."
            )
        elif not result["error"]: # PK not offered or some other issue, and no password.
             result["error"] = (
                f"SSH public key authentication was not successful for {username}@{host}, "
                "and no password was configured to attempt password authentication."
            )


    # Final error/warning composition if no method succeeded
    if not result["success"]:
        if result["server_allows_publickey_auth"] and result["server_allows_password_auth"]:
            result["error"] = (f"Both public key and password SSH authentication failed for {username}@{host}. "
                               "Verify keys and password.")
        elif result["server_allows_publickey_auth"] and not config.get("password"):
            # This case is mostly covered by the "No password configured" block above.
            # Consolidate or ensure it's the primary message.
            if not result["error"]: # If not already set by the specific PK failure + no PWD case
                result["error"] = (f"SSH public key authentication failed for {username}@{host}. "
                                   "Password authentication not attempted (no password configured).")
        elif result["server_allows_password_auth"] and not result["server_allows_publickey_auth"]:
            # This implies PK auth failed for a reason other than AuthenticationException (e.g. connection error)
            # OR PK was genuinely not offered.
            if not result["error"]: # If not already set by a PWD auth failure alone.
                result["error"] = (f"SSH password authentication failed for {username}@{host}. "
                                   "Public key authentication was not successful or not offered.")
        # If no auth methods were seemingly allowed or an early connection error occurred,
        # result["error"] should already be set.

        if not result["error"]: # Default fallback error if not set by specific conditions
            result["error"] = f"Unable to establish SSH connection to {username}@{host} with available methods."

    return result


def establish_ssh_connection(config: Dict[str, Any]) -> paramiko.SSHClient:
    """
    Establish an SSH connection to Proxmox host using available authentication methods.

    This function creates and returns an authenticated SSH connection to the Proxmox host,
    trying public key authentication first, then password authentication if available.

    Args:
        config: The 'proxmox' section of the application configuration.
                Must contain 'host' and 'user'.
                May contain 'password'.

    Returns:
        Authenticated paramiko.SSHClient instance

    Raises:
        SSHConnectionError: If SSH connection fails
        ConfigurationError: If required configuration is missing
    """
    from .exceptions import SSHConnectionError
    
    host = config.get("host")
    user = config.get("user")
    password = config.get("password")
    
    if not host or not user:
        raise ConfigurationError("Proxmox host and user must be configured for SSH connection")
    
    # Extract username from user@realm format for SSH
    username = user.split('@')[0] if '@' in user else user
    
    logger.debug(f"Establishing SSH connection to {username}@{host}")
    
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # Try public key authentication first
        try:
            logger.debug("Attempting SSH public key authentication")
            ssh_client.connect(
                hostname=host,
                username=username,
                timeout=10,
                auth_timeout=10,
                look_for_keys=True,
                allow_agent=True
            )
            logger.debug("SSH public key authentication successful")
            return ssh_client
            
        except paramiko.AuthenticationException:
            logger.debug("SSH public key authentication failed, trying password")
            
            if password:
                ssh_client.connect(
                    hostname=host,
                    username=username,
                    password=password,
                    timeout=10,
                    auth_timeout=10,
                    look_for_keys=False,
                    allow_agent=False
                )
                logger.debug("SSH password authentication successful")
                return ssh_client
            else:
                raise SSHConnectionError(
                    f"SSH public key authentication failed for {username}@{host} "
                    "and no password configured"
                )
                
    except paramiko.AuthenticationException as e:
        ssh_client.close()
        raise SSHConnectionError(
            f"SSH authentication failed for {username}@{host}: {e}"
        ) from e
    except Exception as e:
        ssh_client.close()
        raise SSHConnectionError(
            f"Failed to establish SSH connection to {username}@{host}: {e}"
        ) from e


def validate_ssh_public_key(ssh_key: str) -> bool:
    """
    Validate SSH public key format.

    Args:
        ssh_key: SSH public key string to validate

    Returns:
        True if valid SSH public key format

    Raises:
        ProvisionError: If SSH key format is invalid
    """
    # Basic SSH key format validation
    ssh_key_pattern = r'^(ssh-rsa|ssh-dss|ssh-ed25519|ecdsa-sha2-nistp256|ecdsa-sha2-nistp384|ecdsa-sha2-nistp521)[ ]+([A-Za-z0-9+\/]+)(={0,2})(?:[ ]+(.*))?$'

    if not re.match(ssh_key_pattern, ssh_key.strip()):
        raise ProvisionError("Invalid SSH public key format")

    return True


def extract_domain_from_hostname(hostname: str) -> Optional[str]:
    """
    Extract domain portion from a hostname (e.g., 'pve1.lan.home.vwn.io' -> 'lan.home.vwn.io').
    
    Args:
        hostname: The full hostname to extract domain from
        
    Returns:
        Domain portion if hostname contains dots, None otherwise
    """
    if "." in hostname:
        domain_parts = hostname.split(".", 1)
        return domain_parts[1]
    return None


def construct_node_hostname(base_hostname: str, node_name: str) -> str:
    """
    Construct node-specific hostname by replacing the first part with the node name.
    
    Args:
        base_hostname: The base hostname (e.g., 'pve1.lan.home.vwn.io')
        node_name: The target node name (e.g., 'pve2')
        
    Returns:
        Node-specific hostname (e.g., 'pve2.lan.home.vwn.io')
        
    Examples:
        >>> construct_node_hostname('pve1.lan.home.vwn.io', 'pve2')
        'pve2.lan.home.vwn.io'
        >>> construct_node_hostname('proxmox', 'pve2')
        'pve2'
    """
    domain = extract_domain_from_hostname(base_hostname)
    if domain:
        return f"{node_name}.{domain}"
    else:
        return node_name  # Fallback to just the node name


def establish_node_ssh_connection(config: Dict[str, Any], node_name: str) -> paramiko.SSHClient:
    """
    Establish SSH connection to a specific Proxmox node.
    
    This function constructs the node-specific hostname using domain extraction
    and attempts to connect. If the domain-based connection fails, it falls back
    to using just the node name.
    
    Args:
        config: Proxmox configuration dictionary containing connection details
        node_name: Name of the target Proxmox node
        
    Returns:
        Authenticated paramiko.SSHClient instance for the specific node

    Raises:
        SSHConnectionError: If SSH connection fails to both domain-based and fallback hostnames
        ConfigurationError: If required configuration is missing
    """
    from .exceptions import SSHConnectionError
    
    base_host = config.get("host")
    user = config.get("user")
    password = config.get("password")
    
    if not base_host or not user:
        raise ConfigurationError("Proxmox host and user must be configured for SSH connection")
    
    # Extract username from user@realm format for SSH
    username = user.split('@')[0] if '@' in user else user
    
    # Construct node-specific hostname
    node_host = construct_node_hostname(base_host, node_name)
    
    # Validate hostname format (basic check for valid hostname characters)
    hostname_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-\.]*[a-zA-Z0-9])?$'
    if not re.match(hostname_pattern, node_host):
        logger.debug(f"Invalid hostname constructed: {node_host}")
        raise ConfigurationError(f"Invalid hostname constructed for node {node_name}: {node_host}")
    
    logger.debug(f"Establishing SSH connection to {username}@{node_host} for node {node_name}")
    
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # Try public key authentication first
        try:
            logger.debug(f"Attempting SSH public key authentication to {node_host}")
            ssh_client.connect(
                hostname=node_host,
                username=username,
                timeout=10,
                auth_timeout=10,
                look_for_keys=True,
                allow_agent=True
            )
            logger.debug(f"SSH public key authentication successful to {node_host}")
            return ssh_client
            
        except paramiko.AuthenticationException:
            logger.debug(f"SSH public key authentication failed to {node_host}, trying password")
            
            if password:
                ssh_client.connect(
                    hostname=node_host,
                    username=username,
                    password=password,
                    timeout=10,
                    auth_timeout=10,
                    look_for_keys=False,
                    allow_agent=False
                )
                logger.debug(f"SSH password authentication successful to {node_host}")
                return ssh_client
            else:
                raise SSHConnectionError(
                    f"SSH public key authentication failed for {username}@{node_host} "
                    "and no password configured"
                )
                
    except paramiko.AuthenticationException as e:
        logger.debug(f"SSH authentication failed to {node_host}: {e}")
        raise SSHConnectionError(f"SSH authentication failed to {node_host}: {e}") from e
        
    except (socket.timeout, socket.error, paramiko.SSHException) as e:
        logger.debug(f"SSH connection failed to {node_host}: {e}")
        
        # Fallback: Try connecting to just the node name if domain-based connection failed
        if node_host != node_name:
            logger.debug(f"Fallback: Attempting SSH connection to {node_name} directly")
            try:
                ssh_client_fallback = paramiko.SSHClient()
                ssh_client_fallback.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                # Try public key authentication first
                try:
                    ssh_client_fallback.connect(
                        hostname=node_name,
                        username=username,
                        timeout=10,
                        auth_timeout=10,
                        look_for_keys=True,
                        allow_agent=True
                    )
                    logger.debug(f"SSH public key authentication successful to {node_name} (fallback)")
                    return ssh_client_fallback
                    
                except paramiko.AuthenticationException:
                    if password:
                        ssh_client_fallback.connect(
                            hostname=node_name,
                            username=username,
                            password=password,
                            timeout=10,
                            auth_timeout=10,
                            look_for_keys=False,
                            allow_agent=False
                        )
                        logger.debug(f"SSH password authentication successful to {node_name} (fallback)")
                        return ssh_client_fallback
                        
            except Exception as fallback_e:
                logger.debug(f"Fallback SSH connection to {node_name} also failed: {fallback_e}")
        
        raise SSHConnectionError(
            f"SSH connection failed to both {node_host} and {node_name}: {e}"
        ) from e
    
    except Exception as e:
        logger.error(f"Unexpected error during SSH connection to {node_host}: {e}")
        raise SSHConnectionError(f"Unexpected error during SSH connection to {node_host}: {e}") from e
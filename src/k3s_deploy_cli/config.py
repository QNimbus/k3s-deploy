# file: src/k3s_deploy_cli/config.py
"""Manages application configuration loading and validation.

This module provides the `load_configuration` function, which is responsible
for reading the application's configuration from a JSON file. It validates
the loaded configuration against a predefined schema to ensure correctness.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, TypeAlias  # Import TypeAlias

from dotenv import load_dotenv
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from loguru import logger

from .exceptions import ConfigurationError

# Define K3sDeployCLIConfig as a type alias for the configuration dictionary
K3sDeployCLIConfig: TypeAlias = Dict[str, Any]

def load_configuration(
    config_file_path: Path, schema_file_path: Path
) -> K3sDeployCLIConfig: # Use the type alias here
    """Loads, validates, and processes the application configuration.

    Args:
        config_file_path: Path to the configuration JSON file.
        schema_file_path: Path to the configuration schema JSON file.

    Returns:
        A dictionary containing the validated configuration.

    Raises:
        ConfigurationError: If there's an issue with loading or validating
                            the configuration.
    """
    logger.debug(f"Attempting to load configuration from: {config_file_path}")
    logger.debug(f"Using schema for validation: {schema_file_path}")

    # Load .env file from the project root (if it exists)
    # Assumes this script is run from a context where the project root is discoverable
    # or that .env is in the current working directory or its parents.
    project_root_env = Path(os.getcwd()) / ".env"
    if project_root_env.exists():
        logger.debug(f"Loading environment variables from {project_root_env}")
        # Log relevant env vars BEFORE load_dotenv if they might exist
        logger.debug(f"Value of DOTENV_PROXMOX_HOST before load_dotenv: {os.getenv('DOTENV_PROXMOX_HOST')}")
        logger.debug(f"Value of ENV_PREFIX_PASSWORD_FROM_DOTENV before load_dotenv: {os.getenv('ENV_PREFIX_PASSWORD_FROM_DOTENV')}")
        # Add any other specific vars relevant to the failing test here
        logger.debug(f"Value of MY_HOST_VAR before load_dotenv: {os.getenv('MY_HOST_VAR')}")


        loaded_dotenv = load_dotenv(dotenv_path=project_root_env, override=True)
        logger.debug(f"python-dotenv load_dotenv returned: {loaded_dotenv}")
        logger.debug(
            f"Value of DOTENV_PROXMOX_HOST after load_dotenv: {os.getenv('DOTENV_PROXMOX_HOST')}"
        )
        logger.debug(
            f"Value of ENV_PREFIX_PASSWORD_FROM_DOTENV after load_dotenv: {os.getenv('ENV_PREFIX_PASSWORD_FROM_DOTENV')}"
        )
        # Add any other specific vars relevant to the failing test here
        logger.debug(f"Value of MY_HOST_VAR after load_dotenv: {os.getenv('MY_HOST_VAR')}")
    else:
        # Fallback for cases where CWD might not be project root,
        # try loading .env from where the script's package is.
        # This might be more robust depending on execution context.
        package_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        if package_env_path.exists():
            logger.debug(f"Loading environment variables from {package_env_path}")
            loaded_dotenv = load_dotenv(dotenv_path=package_env_path, override=True)
            logger.debug(f"python-dotenv load_dotenv returned: {loaded_dotenv}")
            logger.debug(
                f"Value of DOTENV_PROXMOX_HOST after load_dotenv: {os.getenv('DOTENV_PROXMOX_HOST')}"
            )
            logger.debug(
                f"Value of ENV_PREFIX_PASSWORD_FROM_DOTENV after load_dotenv: {os.getenv('ENV_PREFIX_PASSWORD_FROM_DOTENV')}"
            )
        else:
            logger.debug(
                "No .env file found at project root or package level. "
                "Proceeding without .env overrides."
            )
    
    # Check if config file exists
    if not config_file_path.exists():
        msg = (
            f"Configuration file not found at '{config_file_path}'. "
            "Please create one or use a command to initialize it (e.g., "
            "'k3s-deploy init' - once implemented)."
        )
        logger.error(msg)
        raise ConfigurationError(msg)

    # Check if schema file exists
    if not schema_file_path.exists():
        msg = f"Configuration schema file not found at '{schema_file_path}'."
        logger.error(msg)
        raise ConfigurationError(msg) # This is more of an internal error

    try:
        with open(config_file_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        logger.debug("Successfully loaded configuration file.")
    except json.JSONDecodeError as e:
        msg = f"Error decoding JSON from '{config_file_path}': {e}"
        logger.error(msg)
        raise ConfigurationError(msg) from e
    except OSError as e:
        msg = f"Error reading configuration file '{config_file_path}': {e}"
        logger.error(msg)
        raise ConfigurationError(msg) from e

    try:
        with open(schema_file_path, "r", encoding="utf-8") as f:
            schema_data = json.load(f)
        logger.debug("Successfully loaded schema file.")
    except json.JSONDecodeError as e:
        msg = f"Error decoding JSON from schema '{schema_file_path}': {e}"
        logger.error(msg)
        raise ConfigurationError(msg) from e
    except OSError as e:
        msg = f"Error reading schema file '{schema_file_path}': {e}"
        logger.error(msg)
        raise ConfigurationError(msg) from e

    # --- Environment Variable Substitution ---
    # Specifically target proxmox connection details for substitution
    if "proxmox" in config_data and isinstance(config_data["proxmox"], dict):
        proxmox_config = config_data["proxmox"]
        for key in ["password", "api_token_secret", "api_token_id", "user", "host"]:
            if isinstance(proxmox_config.get(key), str) and proxmox_config[key].startswith("ENV:"):
                env_var_name = proxmox_config[key][4:]
                logger.debug(f"Attempting to get env var '{env_var_name}' for proxmox.{key} (original value: '{proxmox_config[key]}')")
                env_var_value = os.getenv(env_var_name)
                logger.debug(f"Value of '{env_var_name}' from os.getenv: '{env_var_value}'")
                if env_var_value is not None:
                    logger.debug(
                        f"Substituting proxmox.{key} with value from "
                        f"environment variable '{env_var_name}'."
                    )
                    proxmox_config[key] = env_var_value
                else:
                    logger.warning(
                        f"Environment variable '{env_var_name}' for proxmox.{key} not found. "
                        f"Setting proxmox.{key} to None."
                    )
                    # If ENV: var is specified but not found, it might be an issue.
                    # Schema validation will catch it if the field becomes null and is required.
                    # Or, if it's optional, it will just be missing.
                    # For now, we'll let schema validation handle missing required fields.
                    # If it's an optional field, it will become null.
                    proxmox_config[key] = None


    try:
        validate(instance=config_data, schema=schema_data)
        logger.debug("Configuration validated successfully against schema.")
    except ValidationError as e:
        # Provide a more user-friendly error message for validation issues
        error_path = " -> ".join(map(str, e.path))
        msg = (
            f"Configuration validation error at '{error_path}': {e.message}. "
            "Please check your configuration file."
        )
        logger.error(msg)
        # Log the full validation error details at debug level
        logger.debug(f"Full validation error details: {e}")
        raise ConfigurationError(msg) from e

    logger.info("Configuration loaded and validated successfully.")
    return config_data
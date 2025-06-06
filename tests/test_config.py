# file: tests/test_config.py
"""Unit tests for the k3s_deploy_cli.config module."""

import builtins  # Moved to top
import os
from pathlib import Path
from typing import Any, Dict

import pytest

# Import the config module itself to allow mocking its __file__ attribute
from k3s_deploy_cli import (
    config as k3s_deploy_cli_config_module,  # Moved to top and aliased
)
from k3s_deploy_cli.config import load_configuration
from k3s_deploy_cli.exceptions import ConfigurationError
from tests.fixtures.helpers import create_temp_json_file

# --- Fixtures ---

@pytest.fixture
def tmp_path_factory_fixture(tmp_path_factory: Any) -> Any: # Renamed to avoid conflict
    """Fixture to use the built-in tmp_path_factory."""
    return tmp_path_factory

@pytest.fixture
def base_config_schema_content() -> Dict[str, Any]:
    """Provides the base content for the config schema."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "K3s Deploy CLI Configuration",
        "type": "object",
        "properties": {
            "proxmox": {
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "user": {"type": "string"},
                    "password": {"type": "string"},  # Changed: Must be string, not ["string", "null"]
                    "api_token_id": {"type": "string"},  # Changed: Must be string, not ["string", "null"]
                    "api_token_secret": {"type": "string"},  # Changed: Must be string, not ["string", "null"]
                    "verify_ssl": {"type": "boolean", "default": True}
                },
                "required": ["host", "user"],
                "oneOf": [
                    { "required": ["password"] },
                    { "required": ["api_token_id", "api_token_secret"] }
                ]
            },
            "nodes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "vmid": {"type": "integer"},
                        "role": {"type": "string", "enum": ["server", "agent", "storage"]},
                        "ip_config": {
                            "type": "object",
                            "properties": {
                                "address": {"type": "string"},
                                "gateway": {"type": "string"}
                            },
                            "required": ["address", "gateway"]
                        }
                    },
                    "required": ["vmid", "role", "ip_config"]
                }
            }
        },
        "required": ["proxmox", "nodes"]
    }

@pytest.fixture
def temp_schema_file(tmp_path: Path, base_config_schema_content: Dict[str, Any]) -> Path:
    """Creates a temporary schema file for tests."""
    return create_temp_json_file(tmp_path, "test_schema.json", base_config_schema_content)

@pytest.fixture
def minimal_valid_config_content() -> Dict[str, Any]:
    """Provides minimal valid configuration content."""
    return {
        "proxmox": {
            "host": "pve.example.com",
            "user": "root@pam",
            "password": "testpassword"
        },
        "nodes": [{
            "vmid": 100,
            "role": "server",
            "ip_config": {
                "address": "192.168.1.100/24",
                "gateway": "192.168.1.1"
            }
        }]
    }

@pytest.fixture
def temp_config_file_minimal(tmp_path: Path, minimal_valid_config_content: Dict[str, Any]) -> Path:
    """Creates a temporary minimal valid config file."""
    return create_temp_json_file(tmp_path, "config_minimal.json", minimal_valid_config_content)

# --- Test Cases ---

def test_load_minimal_valid_config(
    temp_config_file_minimal: Path, temp_schema_file: Path
) -> None:
    """Tests loading a minimal but valid configuration file."""
    config = load_configuration(temp_config_file_minimal, temp_schema_file)
    assert config is not None
    assert config["proxmox"]["host"] == "pve.example.com"
    assert len(config["nodes"]) == 1
    assert config["nodes"][0]["vmid"] == 100
    assert config["nodes"][0]["ip_config"]["address"] == "192.168.1.100/24"

def test_config_file_not_found(tmp_path: Path, temp_schema_file: Path) -> None:
    """Tests that ConfigurationError is raised if config file is not found."""
    non_existent_config_path = tmp_path / "non_existent_config.json"
    with pytest.raises(ConfigurationError) as excinfo:
        load_configuration(non_existent_config_path, temp_schema_file)
    assert "Configuration file not found" in str(excinfo.value)

def test_schema_file_not_found(tmp_path: Path, temp_config_file_minimal: Path) -> None:
    """Tests that ConfigurationError is raised if schema file is not found."""
    non_existent_schema_path = tmp_path / "non_existent_schema.json"
    with pytest.raises(ConfigurationError) as excinfo:
        load_configuration(temp_config_file_minimal, non_existent_schema_path)
    assert "Configuration schema file not found" in str(excinfo.value)

def test_invalid_json_in_config_file(tmp_path: Path, temp_schema_file: Path) -> None:
    """Tests ConfigurationError for invalid JSON in the config file."""
    invalid_json_path = tmp_path / "invalid_config.json"
    with open(invalid_json_path, "w", encoding="utf-8") as f:
        f.write("this is not valid json")
    
    with pytest.raises(ConfigurationError) as excinfo:
        load_configuration(invalid_json_path, temp_schema_file)
    assert "Error decoding JSON" in str(excinfo.value)

def test_schema_validation_failure_missing_required_field(
    tmp_path: Path, temp_schema_file: Path
) -> None:
    """Tests schema validation failure for a missing required field."""
    invalid_config_data = {
        "proxmox": { 
            "user": "root@pam",
            "password": "testpassword"
        },
        "nodes": [{
            "vmid": 100, 
            "role": "server",
            "ip_config": {
                "address": "192.168.1.101/24",
                "gateway": "192.168.1.1"
            }
        }]
    }
    invalid_config_path = create_temp_json_file(tmp_path, "invalid_config.json", invalid_config_data)
    
    with pytest.raises(ConfigurationError) as excinfo:
        load_configuration(invalid_config_path, temp_schema_file)
    assert "Configuration validation error" in str(excinfo.value)
    assert "'host' is a required property" in str(excinfo.value)

@pytest.fixture
def mock_env_vars(monkeypatch: Any) -> None:
    """Mocks environment variables for testing ENV: prefix."""
    monkeypatch.setenv("TEST_PROXMOX_HOST", "env.proxmox.host")
    monkeypatch.setenv("TEST_PROXMOX_PASSWORD", "env_password")
    monkeypatch.setenv("MY_HOST_VAR", "host.from.direct.env")
    monkeypatch.setenv("MY_PASS_VAR", "pass.from.direct.env")

def test_load_config_with_env_prefix(
    tmp_path: Path, temp_schema_file: Path, mock_env_vars: None 
) -> None:
    """Tests loading configuration with ENV: prefix substitution."""
    config_with_env_data = {
        "proxmox": {
            "host": "ENV:TEST_PROXMOX_HOST",
            "user": "root@pam",
            "password": "ENV:TEST_PROXMOX_PASSWORD"
        },
        "nodes": [{
            "vmid": 200, 
            "role": "agent",
            "ip_config": {
                "address": "192.168.1.200/24",
                "gateway": "192.168.1.1"
            }
        }]
    }
    config_path = create_temp_json_file(tmp_path, "config_env.json", config_with_env_data)
    
    # Create a dummy .env file in the tmp_path (which will be CWD for the test)
    # to ensure load_dotenv() in config.py doesn't fail if it expects one,
    # though monkeypatch should handle the actual env var values.
    # Alternatively, ensure config.py handles .env not found gracefully.
    (tmp_path / ".env").touch()


    original_cwd = Path.cwd()
    os.chdir(tmp_path) # Change CWD to where .env might be sought by load_dotenv

    try:
        config = load_configuration(config_path, temp_schema_file)
        assert config["proxmox"]["host"] == "env.proxmox.host"
        assert config["proxmox"]["password"] == "env_password"
        assert config["nodes"][0]["vmid"] == 200
    finally:
        os.chdir(original_cwd) # Restore CWD

def test_load_config_with_dotenv_override_and_direct_env_vars(
    tmp_path: Path, temp_schema_file: Path, monkeypatch: Any
) -> None:
    """
    Tests .env file overriding, ENV: prefix, and direct env var precedence.
    """
    monkeypatch.setenv("MY_HOST_VAR", "host.from.direct.env.specific.for.this.test")
    monkeypatch.setenv("MY_PASS_VAR", "pass.from.direct.env.specific.for.this.test")
    monkeypatch.setenv("DOTENV_PROXMOX_HOST", "this.should.be.overridden.by.dotenv.file")

    env_file_content = """
DOTENV_PROXMOX_HOST="host.from.dotenv.file"
DOTENV_PROXMOX_PASSWORD="password.from.dotenv.file"
"""
    env_file_path = tmp_path / ".env"
    with open(env_file_path, "w", encoding="utf-8") as f:
        f.write(env_file_content)

    config_data = {
        "proxmox": {
            "host": "ENV:DOTENV_PROXMOX_HOST",
            "user": "user.from.config.json",
            "password": "ENV:MY_PASS_VAR"
        },
        "nodes": [{"vmid": 400, "role": "agent", "ip_config": {"address": "192.168.1.40/24", "gateway": "192.168.1.1"}}]
    }
    config_path = create_temp_json_file(tmp_path, "config_dotenv_direct.json", config_data)

    original_cwd = Path.cwd()
    os.chdir(tmp_path)

    try:
        config = load_configuration(config_path, temp_schema_file)
        assert config["proxmox"]["host"] == "host.from.dotenv.file"
        assert config["proxmox"]["user"] == "user.from.config.json"
        assert config["proxmox"]["password"] == "pass.from.direct.env.specific.for.this.test"
    finally:
        os.chdir(original_cwd)
        monkeypatch.delenv("MY_HOST_VAR", raising=False)
        monkeypatch.delenv("MY_PASS_VAR", raising=False)
        monkeypatch.delenv("DOTENV_PROXMOX_HOST", raising=False)

def test_load_config_with_dotenv_override(
    tmp_path: Path, temp_schema_file: Path, monkeypatch: Any
) -> None:
    """Tests .env file overriding values and ENV: prefix."""
    monkeypatch.delenv("DOTENV_PROXMOX_HOST", raising=False)
    monkeypatch.delenv("ENV_PREFIX_PASSWORD_FROM_DOTENV", raising=False)

    env_content = """
DOTENV_PROXMOX_HOST="host.from.dotenv"
ENV_PREFIX_PASSWORD_FROM_DOTENV="password.from.dotenv"
"""
    env_file_path = tmp_path / ".env"
    with open(env_file_path, "w", encoding="utf-8") as f:
        f.write(env_content)

    config_data = {
        "proxmox": {
            "host": "ENV:DOTENV_PROXMOX_HOST", 
            "user": "test@pam",
            "password": "ENV:ENV_PREFIX_PASSWORD_FROM_DOTENV"
        },
        "nodes": [{"vmid": 300, "role": "server", "ip_config": {"address": "192.168.1.30/24", "gateway": "192.168.1.1"}}]
    }
    config_path = create_temp_json_file(tmp_path, "config_dotenv.json", config_data)

    original_cwd = Path.cwd()
    os.chdir(tmp_path) 

    try:
        config = load_configuration(config_path, temp_schema_file)
        assert config["proxmox"]["host"] == "host.from.dotenv"
        assert config["proxmox"]["password"] == "password.from.dotenv"
    finally:
        os.chdir(original_cwd)

def test_env_prefix_required_field_not_set(
    tmp_path: Path, temp_schema_file: Path, monkeypatch: Any
) -> None:
    """Tests ConfigurationError if ENV: var for a required field is not set."""
    monkeypatch.delenv("MISSING_REQUIRED_PASSWORD", raising=False)

    config_data_missing_env = {
        "proxmox": {
            "host": "pve.example.com",
            "user": "root@pam",
            "password": "ENV:MISSING_REQUIRED_PASSWORD"
        },
        "nodes": [{"vmid": 100, "role": "server", "ip_config": {"address": "192.168.1.100/24", "gateway": "192.168.1.1"}}]
    }
    config_path = create_temp_json_file(tmp_path, "config_missing_env.json", config_data_missing_env)
    
    original_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        with pytest.raises(ConfigurationError) as excinfo:
            load_configuration(config_path, temp_schema_file)
        assert "Configuration validation error" in str(excinfo.value)
        assert "is not valid under any of the given schemas" in str(excinfo.value) or \
               "'password' is a required property" in str(excinfo.value) or \
               "None is not of type 'string'" in str(excinfo.value) # Added possible error messages
    finally:
        os.chdir(original_cwd)

def test_load_configuration_raises_oserror_on_config_read_failure(
    tmp_path: Path, temp_schema_file: Path, monkeypatch: Any
) -> None:
    """Tests ConfigurationError if OSError occurs during config file read."""
    config_file_to_fail = tmp_path / "config_oserror.json"
    config_file_to_fail.write_text("{}", encoding="utf-8")

    original_open = builtins.open

    def selective_mock_open(file_path_arg: Any, *args: Any, **kwargs: Any) -> Any:
        if str(file_path_arg) == str(config_file_to_fail):
            raise OSError("Simulated OSError during config read")
        return original_open(file_path_arg, *args, **kwargs)

    monkeypatch.setattr("builtins.open", selective_mock_open)

    with pytest.raises(ConfigurationError) as excinfo:
        load_configuration(config_file_to_fail, temp_schema_file)
    
    assert "Error reading configuration file" in str(excinfo.value)
    assert "Simulated OSError during config read" in str(excinfo.value)

def test_load_configuration_raises_oserror_on_schema_read_failure(
    tmp_path: Path, temp_config_file_minimal: Path, monkeypatch: Any
) -> None:
    """Tests ConfigurationError if OSError occurs during schema file read."""
    schema_file_to_fail = tmp_path / "schema_oserror.json"
    schema_file_to_fail.touch() # schema_file_path.exists() is checked first

    original_open = builtins.open

    def selective_mock_open(file_path_arg: Any, *args: Any, **kwargs: Any) -> Any:
        if str(file_path_arg) == str(temp_config_file_minimal):
            return original_open(file_path_arg, *args, **kwargs)
        if str(file_path_arg) == str(schema_file_to_fail):
            raise OSError("Simulated OSError during schema read")
        return original_open(file_path_arg, *args, **kwargs)
    monkeypatch.setattr("builtins.open", selective_mock_open)

    with pytest.raises(ConfigurationError) as excinfo:
        load_configuration(temp_config_file_minimal, schema_file_to_fail)
    
    assert "Error reading schema file" in str(excinfo.value)
    assert "Simulated OSError during schema read" in str(excinfo.value)

def test_load_configuration_invalid_json_in_schema_file(
    tmp_path: Path, temp_config_file_minimal: Path
) -> None:
    """Tests ConfigurationError for invalid JSON in the schema file."""
    invalid_schema_path = tmp_path / "invalid_schema.json"
    with open(invalid_schema_path, "w", encoding="utf-8") as f:
        f.write("this is not valid json {{{{")

    with pytest.raises(ConfigurationError) as excinfo:
        load_configuration(temp_config_file_minimal, invalid_schema_path)
    assert "Error decoding JSON from schema" in str(excinfo.value)

def test_load_configuration_dotenv_from_package_path(
    tmp_path: Path, temp_schema_file: Path, minimal_valid_config_content: Dict[str, Any], monkeypatch: Any
) -> None:
    """Tests loading .env from package path when not in CWD."""
    # 1. Setup paths
    test_cwd = tmp_path / "test_app_cwd"
    test_cwd.mkdir()

    fake_package_root = tmp_path / "fake_project_root"
    fake_package_root.mkdir()
    
    package_dotenv_file = fake_package_root / ".env"
    # Corrected string literal for write_text
    package_dotenv_file.write_text('PACKAGE_VAR_HOST="host.from.package.env"\n', encoding="utf-8")

    config_content_uses_package_var = {
        "proxmox": {
            "host": "ENV:PACKAGE_VAR_HOST",
            "user": "testuser",
            "password": "testpassword"
        },
        "nodes": minimal_valid_config_content["nodes"]
    }
    config_file = create_temp_json_file(test_cwd, "config.json", config_content_uses_package_var)
    # 2. Monkeypatch
    monkeypatch.setattr(os, "getcwd", lambda: str(test_cwd))

    mock_config_module_file_path = fake_package_root / "src/k3s_deploy_cli/config.py"
    mock_config_module_file_path.parent.mkdir(parents=True, exist_ok=True) 
    # Use the aliased module name here
    monkeypatch.setattr(k3s_deploy_cli_config_module, "__file__", str(mock_config_module_file_path))
    
    assert not (test_cwd / ".env").exists()
    assert package_dotenv_file.exists()

    # 3. Run and Assert
    loaded_config = load_configuration(config_file, temp_schema_file)
    assert loaded_config["proxmox"]["host"] == "host.from.package.env"
    
    monkeypatch.delenv("PACKAGE_VAR_HOST", raising=False)
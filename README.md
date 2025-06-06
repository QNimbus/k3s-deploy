# K3s Deploy CLI

This project is a CLI tool to deploy and manage K3s clusters on Proxmox VE.

## Prerequisites

*   Python 3.13+ (as defined in `pyproject.toml`)
*   Poetry (for dependency management and running the CLI)

[![asciicast](https://asciinema.org/a/Rc6N9xvp6WvU7JgwEq34UibQG.svg)](https://asciinema.org/a/Rc6N9xvp6WvU7JgwEq34UibQG)

## Getting Started

1.  **Clone the repository (if you haven't already):**
    ```bash
    git clone <repository-url>
    cd k3s_deploy
    ```

2.  **Ensure you have Python 3.13+ available:**
    This project requires Python 3.13 or higher. If you encounter an error like:
    ```
    Current Python version (3.12) is not allowed by the project (>=3.13,<4.0).
    Please change python executable via the "env use" command.
    ```

    **Option A: Using pyenv (recommended)**
    ```bash
    # Install Python 3.13 if not already available
    pyenv install 3.13.0
    
    # Set Python 3.13 as the local version for this project
    pyenv local 3.13.0
    
    # Verify the version
    python --version
    ```

    **Option B: Using nix-shell**
    ```bash
    # Enter a shell with Python 3.13
    nix-shell -p python313
    
    # Verify the version
    python --version
    ```

    **Option C: Using Poetry's environment management**
    ```bash
    # Tell Poetry to use a specific Python version (if available on your system)
    poetry env use python3.13
    
    # Or use the full path to Python 3.13 if needed
    poetry env use /usr/bin/python3.13
    ```

3.  **Install dependencies using Poetry:**
    This will create a virtual environment and install all necessary packages.
    ```bash
    poetry install
    ```

    
## Configuration

The CLI is configured primarily through a `config.json` file and environment variables for sensitive data.

1.  **`config.json`:**
    *   This file should be placed in the root directory where you run the `k3s-deploy` command.
    *   It defines the Proxmox connection details and the list of nodes to be managed.
    *   Refer to `config.example.json` for an example structure.
    *   The structure is validated against `src/k3s_deploy_cli/config_schema.json`. Your editor might provide autocompletion and validation if configured (see `.vscode/settings.json` for an example with VS Code).

2.  **Environment Variables (`.env` file):**
    *   For sensitive information like passwords or API tokens, it is recommended to use environment variables.
    *   You can create a `.env` file in the project root directory.
    *   An example structure is provided in `.env.example`.
        ```env
        # Example .env content
        # PROXMOX_HOST="your-proxmox-host"
        # PROXMOX_USER="your-user@pam"
        # PROXMOX_PASSWORD="your-secret-password"
        # or for API token authentication:
        # PROXMOX_API_TOKEN_ID="your-token-id@pve!mytoken"
        # PROXMOX_API_TOKEN_SECRET="your-token-secret"
        ```
    *   The application will automatically load variables from this `.env` file if it exists.

3.  **Using Environment Variables in `config.json`:**
    *   You can reference environment variables directly within your `config.json` file by prefixing the variable name with `ENV:`.
    *   For example, to use an environment variable named `PROXMOX_PASSWORD` for the password field:
        ```json
        {
          "proxmox": {
            "host": "your-proxmox-host",
            "user": "your-user@pam",
            "password": "ENV:PROXMOX_PASSWORD", // This will be replaced by the value of PROXMOX_PASSWORD
            // ... other proxmox settings
          },
          // ... other configurations
        }
        ```
    *   If an `ENV:`-prefixed variable is specified in `config.json` but the corresponding environment variable is not set, the application will raise a configuration error if that field is required by the schema, or the field will be treated as `null` if optional.
    
## Running the CLI

Once the dependencies are installed, you can run the CLI using `poetry run`:

```bash
poetry run k3s-deploy [COMMAND] [OPTIONS]
```

**Examples**:

Show the help message:

`poetry run k3s-deploy -h`

Show the version:

`poetry run k3s-deploy --version`

Run with verbose output (for more detailed logs):

`poetry run k3s-deploy -v <your-command-here>`

Run with debug output (for extensive diagnostic logs):

`poetry run k3s-deploy -d <your-command-here>`

**Note on Log Output:**
Log output (info, verbose, or debug) is sent to stderr and can be silenced by redirecting stderr to `/dev/null`:

```bash
poetry run k3s-deploy <your-command-here> 2> /dev/null
```

This is useful when you want to capture only the command's primary output without log messages.

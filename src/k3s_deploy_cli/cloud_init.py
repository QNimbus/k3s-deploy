from typing import Any, Dict, Optional

from loguru import logger
from passlib.hash import sha256_crypt, sha512_crypt

from k3s_deploy_cli.exceptions import ProvisionError


def generate_password_hash(password: str, method: str = "sha512") -> str:
    """
    Generate a password hash suitable for cloud-init passwd field.

    This function creates a SHA-256 or SHA-512 hash that
    can be used in the cloud-init passwd field. The hash is generated
    with a random salt for security.

    Args:
        password: Plain text password to hash
        method: Hash method - "sha256" or "sha512" (default: "sha512")

    Returns:
        Password hash string

    Raises:
        ProvisionError: If invalid hash method specified
    """
    if method == "sha512":
        hashed_password = sha512_crypt.hash(password)
    elif method == "sha256":
        hashed_password = sha256_crypt.hash(password)
    else:
        raise ProvisionError(f"Unsupported hash method: {method}. Use 'sha256' or 'sha512'")

    logger.debug(f"Generated {method.upper()} password hash")
    return hashed_password


class CloudInitConfig:
    """
    Builder class for generating cloud-init configurations.

    This class provides a clean interface for building cloud-init YAML
    configurations with support for common setup tasks like package
    installation, user creation, and SSH key deployment.
    """

    def __init__(self) -> None:
        """Initialize empty cloud-init configuration."""
        self.config: Dict[str, Any] = {}

    def package_update(self, enabled: bool = True) -> 'CloudInitConfig':
        """
        Enable or disable package updates during cloud-init.

        Args:
            enabled: Whether to update packages during initialization

        Returns:
            Self for method chaining
        """
        self.config['package_update'] = enabled
        return self

    def package_upgrade(self, enabled: bool = True) -> 'CloudInitConfig':
        """
        Enable or disable package upgrades during cloud-init.

        Args:
            enabled: Whether to upgrade existing packages during initialization

        Returns:
            Self for method chaining
        """
        self.config['package_upgrade'] = enabled
        return self

    def package_reboot_if_required(self, enabled: bool = True) -> 'CloudInitConfig':
        """
        Enable or disable automatic reboot if packages require it.

        Args:
            enabled: Whether to reboot the system if packages require it after installation/upgrade

        Returns:
            Self for method chaining
        """
        self.config['package_reboot_if_required'] = enabled
        return self

    def add_packages(self, packages: list[str]) -> 'CloudInitConfig':
        """
        Add packages to be installed during cloud-init.

        Args:
            packages: List of package names to install

        Returns:
            Self for method chaining
        """
        if 'packages' not in self.config:
            self.config['packages'] = []
        self.config['packages'].extend(packages)
        return self

    def add_user(self, username: str, ssh_keys: Optional[list[str]] = None,
                 sudo: Optional[str] = "ALL=(ALL) NOPASSWD:ALL",
                 shell: Optional[str] = "/bin/bash",
                 password: Optional[str] = None,
                 hashed_passwd: Optional[str] = None,
                 plain_text_passwd: Optional[str] = None,
                 lock_passwd: Optional[bool] = None,
                 gecos: Optional[str] = None,
                 primary_group: Optional[str] = None,
                 groups: Optional[list[str]] = None,
                 selinux_user: Optional[str] = None,
                 expiredate: Optional[str] = None,
                 ssh_import_id: Optional[list[str]] = None,
                 ssh_pwauth: Optional[bool] = None,
                 inactive: Optional[str] = None,
                 system: Optional[bool] = None,
                 snapuser: Optional[str] = None,
                 ssh_redirect_user: Optional[bool] = None,
                 doas: Optional[list[str]] = None) -> 'CloudInitConfig':
        """
        Add a user configuration to cloud-init with comprehensive property support.

        Args:
            username: Username to create
            ssh_keys: List of SSH public keys for the user
            sudo: Sudo privileges string (e.g., "ALL=(ALL) NOPASSWD:ALL")
            shell: Default shell for the user (e.g., "/bin/bash")
            password: Password (plain text - will be hashed by cloud-init - only when user does not already exist)
            hashed_passwd: Pre-hashed password (use instead of plain_text_passwd, will overwrite existing password)
            plain_text_passwd: Explicit plain text password (will be hashed by cloud-init - will overwrite existing password)
            lock_passwd: If True, locks the password (disables password login, default: False)
            gecos: Full name or description for the user (GECOS field)
            primary_group: Primary group name for the user
            groups: List of additional groups to add the user to
            selinux_user: SELinux user context (e.g., "staff_u")
            expiredate: Account expiration date (YYYY-MM-DD format)
            ssh_import_id: List of SSH key import IDs (e.g., ["lp:username", "gh:username"])
            ssh_pwauth: If True, allows password authentication via SSH
            inactive: Number of days after password expires before account is disabled
            system: If True, create as a system user
            snapuser: Snap user configuration (email address)
            ssh_redirect_user: If True, redirect SSH connections with a message
            doas: List of doas/opendoas rules for this user

        Returns:
            Self for method chaining

        Examples:
            # Basic user with SSH key
            config.add_user("myuser", ssh_keys=["ssh-rsa AAAAB..."])

            # User with groups and full name
            config.add_user("admin", groups=["wheel", "docker"], gecos="Admin User")

            # System user
            config.add_user("service", system=True, shell="/bin/false")

            # User with SSH key import from GitHub
            config.add_user("dev", ssh_import_id=["gh:username"])

            # User with doas configuration
            config.add_user("ops", doas=["permit nopass ops", "deny ops as root"])
        """
        if 'users' not in self.config:
            self.config['users'] = []

        user_config = {
            'name': username,
        }

        # Add optional configuration parameters
        if ssh_keys is not None and len(ssh_keys) > 0:
            user_config['ssh_authorized_keys'] = ssh_keys

        if sudo is not None:
            user_config['sudo'] = sudo

        if shell is not None:
            user_config['shell'] = shell

        # Password configuration (mutually exclusive options)
        if password is not None:
            user_config['password'] = password
        elif hashed_passwd is not None:
            user_config['hashed_passwd'] = hashed_passwd
        elif plain_text_passwd is not None:
            user_config['plain_text_passwd'] = plain_text_passwd

        if lock_passwd is not None:
            user_config['lock_passwd'] = lock_passwd
        else:
            user_config['lock_passwd'] = False

        if gecos is not None:
            user_config['gecos'] = gecos

        if primary_group is not None:
            user_config['primary_group'] = primary_group

        if groups is not None:
            user_config['groups'] = groups

        if selinux_user is not None:
            user_config['selinux_user'] = selinux_user

        if expiredate is not None:
            user_config['expiredate'] = expiredate

        if ssh_import_id is not None:
            user_config['ssh_import_id'] = ssh_import_id

        if ssh_pwauth is not None:
            user_config['ssh_pwauth'] = ssh_pwauth

        if inactive is not None:
            user_config['inactive'] = inactive

        if system is not None:
            user_config['system'] = system

        if snapuser is not None:
            user_config['snapuser'] = snapuser

        if ssh_redirect_user is not None:
            user_config['ssh_redirect_user'] = ssh_redirect_user

        if doas is not None:
            user_config['doas'] = doas

        self.config['users'].append(user_config)
        return self

    def add_user_with_password(self, username: str, password: str,
                              hash_method: Optional[str] = "sha512", **kwargs) -> 'CloudInitConfig':
        """
        Convenience method to add a user with a plain text password.

        This method handles the password in two ways:
        - If hash_method is specified ("sha256" or "sha512"), the password is hashed before adding the user
        - If hash_method is None, the password is passed as plain text to cloud-init

        Args:
            username: Username to create
            password: Plain text password
            hash_method: Hash method - "sha256", "sha512", or None to use plain text (default: "sha512")
            **kwargs: All other arguments supported by add_user()

        Returns:
            Self for method chaining

        Example:
            # Add user with automatic password hashing
            config.add_user_with_password("myuser", "mypassword", 
                                        ssh_keys=["ssh-rsa AAAAB..."])
            
            # Add user with plain text password (handled by cloud-init)
            config.add_user_with_password("myuser", "mypassword", hash_method=None,
                                        ssh_keys=["ssh-rsa AAAAB..."])
        """
        if hash_method is None:
            return self.add_user(username, plain_text_passwd=password, **kwargs)
        else:
            hashed_password = generate_password_hash(password, hash_method)
            return self.add_user(username, hashed_passwd=hashed_password, **kwargs)

    def add_group(self, group_name: str, members: Optional[list[str]] = None) -> 'CloudInitConfig':
        """
        Add a group configuration to cloud-init.

        Args:
            group_name: Name of the group to create
            members: Optional list of usernames to add to the group

        Returns:
            Self for method chaining

        Examples:
            # Create empty group
            config.add_group("developers")

            # Create group with members
            config.add_group("admingroup", ["root", "sys"])
        """
        if 'groups' not in self.config:
            self.config['groups'] = []

        if members:
            # Format: "groupname: [member1, member2]"
            group_config = {group_name: members}
        else:
            # Format: just "groupname" for empty group
            group_config = group_name

        self.config['groups'].append(group_config)
        return self

    def add_default_user(self) -> 'CloudInitConfig':
        """
        Add the default user configuration (equivalent to users: [default]).

        Returns:
            Self for method chaining
        """
        if 'users' not in self.config:
            self.config['users'] = []
        self.config['users'].append('default')
        return self

    def disable_default_user(self) -> 'CloudInitConfig':
        """
        Disable default user creation (equivalent to users: []).

        Returns:
            Self for method chaining
        """
        self.config['users'] = []
        return self

    def override_default_user(self, name: Optional[str] = None,
                             sudo: Optional[str] = None,
                             ssh_import_id: Optional[list[str]] = None) -> 'CloudInitConfig':
        """
        Override default user configuration with custom settings.

        Args:
            name: New name for the default user
            sudo: Sudo privileges (use null to remove sudo access)
            ssh_import_id: SSH key import IDs for the default user

        Returns:
            Self for method chaining

        Example:
            # Change default user name and remove sudo
            config.override_default_user(name="mynewdefault", sudo=None)
        """
        user_override = {}

        if name is not None:
            user_override['name'] = name
        if sudo is not None:
            user_override['sudo'] = sudo
        if ssh_import_id is not None:
            user_override['ssh_import_id'] = ssh_import_id

        self.config['user'] = user_override
        return self

    def add_run_commands(self, commands: list[str]) -> 'CloudInitConfig':
        """
        Add commands to run during cloud-init.

        Args:
            commands: List of shell commands to execute

        Returns:
            Self for method chaining
        """
        if 'runcmd' not in self.config:
            self.config['runcmd'] = []
        self.config['runcmd'].extend(commands)
        return self

    def build(self) -> Dict[str, Any]:
        """
        Build and return the final cloud-init configuration.

        Returns:
            Complete cloud-init configuration dictionary
        """
        return self.config.copy()


def create_cloud_init_config(cloud_init_settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create cloud-init configuration from global settings (Phase 2A - Simple Version).
    
    This function generates a cloud-init configuration using global settings from config.json.
    If no settings are provided, falls back to sensible defaults for basic VM provisioning.
    
    Args:
        cloud_init_settings: Global cloud_init configuration from config.json
                           If None/empty, will use hardcoded defaults
    
    Returns:
        Cloud-init configuration dictionary ready for YAML conversion
        
    Raises:
        ProvisionError: If invalid configuration is provided
    """
    logger.debug("Creating cloud-init config from global settings")
    
    # Use provided config or fallback to defaults
    if not cloud_init_settings:
        cloud_init_settings = {
            "packages": ["qemu-guest-agent", "ansible"],
            "package_update": True,
            "package_upgrade": True,
            "package_reboot_if_required": True,
            "runcmd": [
                "systemctl enable qemu-guest-agent",
                "systemctl start qemu-guest-agent"
            ],
            "users": []
        }
        logger.debug("Using default cloud-init configuration")
    else:
        logger.debug("Using global cloud-init configuration from config.json")
    
    # Extract settings with defaults
    packages = cloud_init_settings.get('packages', ['qemu-guest-agent', 'ansible'])
    package_update = cloud_init_settings.get('package_update', True)
    package_upgrade = cloud_init_settings.get('package_upgrade', True)
    package_reboot_if_required = cloud_init_settings.get('package_reboot_if_required', True)
    runcmd = cloud_init_settings.get('runcmd', [
        'systemctl enable qemu-guest-agent',
        'systemctl start qemu-guest-agent'
    ])
    users = cloud_init_settings.get('users', [])
    
    # Build configuration using CloudInitConfig
    config_builder = (CloudInitConfig()
                     .package_update(package_update)
                     .package_upgrade(package_upgrade)
                     .package_reboot_if_required(package_reboot_if_required)
                     .add_packages(packages))
    
    # Add users if configured
    for user_config in users:
        username = user_config.get('username')
        # Check for required username field
        if not username:
            logger.warning("Skipping user configuration without 'username' field")
            continue
            
        plain_text_passwd = user_config.get('plain_text_passwd', None)
        hashed_passwd = user_config.get('hashed_passwd', None)
        ssh_keys = user_config.get('ssh_keys', [])
        sudo = user_config.get('sudo')
        groups = user_config.get('groups', [])
        shell = user_config.get('shell', '/bin/bash')
        
        # Convert boolean sudo to proper string format
        if sudo is True:
            sudo = "ALL=(ALL) NOPASSWD:ALL"
        elif sudo is False:
            sudo = None
        
        if not plain_text_passwd and not hashed_passwd:
            config_builder.add_user(
                username, ssh_keys=ssh_keys, sudo=sudo, groups=groups, shell=shell
            )
        elif plain_text_passwd:
            config_builder.add_user_with_password(
                username, password=plain_text_passwd, ssh_keys=ssh_keys, sudo=sudo, groups=groups, shell=shell
            )
        else:
            config_builder.add_user(
                username, hashed_passwd=hashed_passwd, ssh_keys=ssh_keys, sudo=sudo, groups=groups, shell=shell
            )
        
        logger.debug(f"Added user '{username}' from global configuration")
    
    # Add run commands
    if runcmd:
        config_builder.add_run_commands(runcmd)
    
    config = config_builder.build()
    
    logger.debug(f"Generated cloud-init config with {len(config.get('packages', []))} packages, "
                f"{len(config.get('users', []))} users, {len(config.get('runcmd', []))} run commands")
    
    return config
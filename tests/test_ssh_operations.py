import pytest

from k3s_deploy_cli.ssh_operations import validate_ssh_public_key
from k3s_deploy_cli.exceptions import ProvisionError

class TestValidateSSHPublicKey:
    """Test cases for validate_ssh_public_key function."""

    def test_valid_ssh_rsa_key(self):
        """Test validation of a standard valid SSH RSA key with a comment.
        Format: ssh-rsa <base64_data> <comment>
        """
        valid_rsa_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7vbqajDhA user@example.com"
        assert validate_ssh_public_key(valid_rsa_key) is True

    def test_valid_ssh_rsa_key_without_comment(self):
        """Test validation of a valid SSH RSA key without a comment.
        Format: ssh-rsa <base64_data>
        """
        valid_rsa_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7vbqajDhA"
        assert validate_ssh_public_key(valid_rsa_key) is True

    def test_valid_ssh_ed25519_key(self):
        """Test validation of a standard valid SSH Ed25519 key with a comment.
        Format: ssh-ed25519 <base64_data> <comment>
        """
        valid_ed25519_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl user@example.com"
        assert validate_ssh_public_key(valid_ed25519_key) is True

    def test_valid_ecdsa_nistp256_key(self):
        """Test validation of a standard valid ECDSA NIST P-256 key with a comment.
        Format: ecdsa-sha2-nistp256 <base64_data> <comment>
        """
        valid_ecdsa_key = "ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBEmKSENjQEezOmxkZMy7opKgwFB9nkt5YRrYMjNuG5N87uRgg6CLrbo5wAdT/y6v0mKV0U2w0WZ2YB/++Tpockg= user@example.com"
        assert validate_ssh_public_key(valid_ecdsa_key) is True

    def test_valid_ecdsa_nistp384_key(self):
        """Test validation of a standard valid ECDSA NIST P-384 key with a comment.
        Format: ecdsa-sha2-nistp384 <base64_data> <comment>
        """
        valid_ecdsa_key = "ecdsa-sha2-nistp384 AAAAE2VjZHNhLXNoYTItbmlzdHAzODQAAAAIbmlzdHAzODQAAABhBGp6w4QWo8XZWW+h9DUjAKWVeZoT user@example.com" # Note: Key data might be truncated for example purposes
        assert validate_ssh_public_key(valid_ecdsa_key) is True

    def test_valid_ecdsa_nistp521_key(self):
        """Test validation of a standard valid ECDSA NIST P-521 key with a comment.
        Format: ecdsa-sha2-nistp521 <base64_data> <comment>
        """
        valid_ecdsa_key = "ecdsa-sha2-nistp521 AAAAE2VjZHNhLXNoYTItbmlzdHA1MjEAAAAIbmlzdHA1MjEAAACFBAGp6w4QWo8XZWW user@example.com" # Note: Key data might be truncated for example purposes
        assert validate_ssh_public_key(valid_ecdsa_key) is True

    def test_valid_ssh_dss_key(self):
        """Test validation of a standard valid SSH DSS key with a comment.
        Format: ssh-dss <base64_data> <comment>
        (Note: ssh-dss is often deprecated but may still be format-valid).
        """
        valid_dss_key = "ssh-dss AAAAB3NzaC1kc3MAAACBAM3T2lPT user@example.com" # Note: Key data might be truncated for example purposes
        assert validate_ssh_public_key(valid_dss_key) is True

    def test_key_with_padding_equals(self):
        """Test validation of a key with two base64 padding characters (==) at the end of the data.
        Format: ssh-rsa <base64_data==> <comment>
        This tests handling of common base64 padding.
        """
        valid_key_with_padding = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7vbqajDhA== user@example.com"
        assert validate_ssh_public_key(valid_key_with_padding) is True

    def test_key_with_invalid_triple_padding_equals(self): # Renamed for clarity
        """Test validation fails for a key with invalid triple base64 padding (===).
        Format: ssh-rsa <base64_data===> <comment>
        Strict Base64 only allows 0, 1, or 2 '=' padding characters.
        """
        invalid_key_with_padding = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7vbqajDhA=== user@example.com"
        with pytest.raises(ProvisionError, match="Invalid SSH public key format"): # Or "Invalid Base64 encoding"
            validate_ssh_public_key(invalid_key_with_padding)

    def test_key_with_whitespace_around(self):
        """Test validation of a key with leading and trailing whitespace.
        Format: "  ssh-rsa <base64_data> <comment>  "
        The validator should ideally strip whitespace before processing.
        """
        valid_key_with_whitespace = "  ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7vbqajDhA user@example.com  "
        assert validate_ssh_public_key(valid_key_with_whitespace) is True

    def test_key_with_complex_comment(self):
        """Test validation of a key with a complex comment containing spaces and hyphens.
        Format: ssh-rsa <base64_data> <comment with multiple words and symbols>
        The comment part should allow a wide range of characters.
        """
        valid_key_with_comment = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7vbqajDhA user@example.com generated on 2024-01-01"
        assert validate_ssh_public_key(valid_key_with_comment) is True

    def test_invalid_key_type(self):
        """Test validation fails for a key with an unrecognized key type.
        Format: ssh-invalid <base64_data> <comment>
        """
        invalid_key_type = "ssh-invalid AAAAB3NzaC1yc2EAAAADAQABAAABgQC7vbqajDhA user@example.com"
        with pytest.raises(ProvisionError, match="Invalid SSH public key format"):
            validate_ssh_public_key(invalid_key_type)

    def test_missing_key_type(self):
        """Test validation fails when the key type part is missing.
        Format: <base64_data> <comment> (Key type omitted)
        """
        missing_key_type = "AAAAB3NzaC1yc2EAAAADAQABAAABgQC7vbqajDhA user@example.com"
        with pytest.raises(ProvisionError, match="Invalid SSH public key format"):
            validate_ssh_public_key(missing_key_type)

    def test_missing_key_data(self):
        """Test validation fails when the base64 encoded key data part is missing.
        Format: ssh-rsa <comment> (Key data omitted)
        """
        missing_key_data = "ssh-rsa user@example.com"
        with pytest.raises(ProvisionError, match="Invalid SSH public key format"):
            validate_ssh_public_key(missing_key_data)

    def test_invalid_base64_characters(self):
        """Test validation fails when the key data contains characters not valid in Base64 encoding.
        Format: ssh-rsa <data_with_invalid_chars@#$%> <comment>
        """
        invalid_base64 = "ssh-rsa AAAAB3NzaC1yc2E@#$%^&*()DAQABAAABgQC7vbqajDhA user@example.com"
        with pytest.raises(ProvisionError, match="Invalid SSH public key format"):
            validate_ssh_public_key(invalid_base64)

    def test_empty_string(self):
        """Test validation fails for an empty string input."""
        with pytest.raises(ProvisionError, match="Invalid SSH public key format"):
            validate_ssh_public_key("")

    def test_whitespace_only(self):
        """Test validation fails for a string containing only whitespace."""
        with pytest.raises(ProvisionError, match="Invalid SSH public key format"):
            validate_ssh_public_key("   ")

    def test_only_key_type(self):
        """Test validation fails when only the key type is provided.
        Format: ssh-rsa (Key data and comment omitted)
        """
        only_key_type = "ssh-rsa"
        with pytest.raises(ProvisionError, match="Invalid SSH public key format"):
            validate_ssh_public_key(only_key_type)

    def test_newline_in_key(self):
        """Test validation fails if a newline character is present within the key string,
        particularly within the key data part.
        Format: ssh-rsa <base64_data_part1\nbase64_data_part2> <comment>
        """
        key_with_newline = "ssh-rsa AAAAB3NzaC1yc2E\nAAAADAQABAAABgQC7vbqajDhA user@example.com"
        with pytest.raises(ProvisionError, match="Invalid SSH public key format"):
            validate_ssh_public_key(key_with_newline)

    def test_tab_character_in_key(self):
        """Test validation fails if a tab character is used as a separator instead of a space,
        or is present within unquoted parts of the key.
        Format: ssh-rsa\t<base64_data> <comment>
        """
        key_with_tab = "ssh-rsa\tAAAAB3NzaC1yc2EAAAADAQABAAABgQC7vbqajDhA user@example.com"
        with pytest.raises(ProvisionError, match="Invalid SSH public key format"):
            validate_ssh_public_key(key_with_tab)

    def test_key_with_special_chars_in_comment(self):
        """Test validation passes with various special characters in the comment section.
        Format: ssh-rsa <base64_data> <comment_with_!@#$%^&*()>
        The comment part should be flexible.
        """
        key_with_special_comment = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7vbqajDhA user@example.com!@#$%^&*()"
        assert validate_ssh_public_key(key_with_special_comment) is True

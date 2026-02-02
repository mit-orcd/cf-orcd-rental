"""Module 01: User Management Tests.

This module tests user management functionality via coldfront management commands.
It uses pytest-django for Django test integration.

Note: The conftest.py in the parent directory configures Django and pytest-django,
including automatic database access for all tests. The @pytest.mark.django_db
decorators are added for explicitness but are also applied automatically.
"""

import pytest
import unittest
from pathlib import Path
from django.contrib.auth.models import User, Group
from .base import BaseSystemTest


@pytest.mark.django_db(transaction=True)
class TestUserCreation(BaseSystemTest, unittest.TestCase):
    """Test user creation via management commands."""
    
    def test_create_basic_user(self):
        """Create a user with minimum required fields."""
        code, out, err = self.run_command(
            "create_user testuser01 --email test@example.com --force"
        )
        self.assertEqual(code, 0, f"Command failed with stderr: {err}")
        self.assertTrue(User.objects.filter(username='testuser01').exists())
    
    def test_create_user_with_token(self):
        """Create a user with API token generation."""
        code, out, err = self.run_command(
            "create_user testuser02 --email test2@example.com --with-token --force"
        )
        self.assertEqual(code, 0, f"Command failed with stderr: {err}")
        # Check that API token is mentioned in output
        self.assertIn("API Token", out or err)
        self.assertTrue(User.objects.filter(username='testuser02').exists())
    
    def test_create_user_with_group(self):
        """Create a user and add to manager group."""
        # Ensure group exists
        self.run_command("setup_rental_manager --create-group")
        
        code, out, err = self.run_command(
            "create_user testuser03 --email test3@example.com --add-to-group rental --force"
        )
        self.assertEqual(code, 0, f"Command failed with stderr: {err}")
        
        user = User.objects.get(username='testuser03')
        self.assertTrue(user.groups.filter(name='Rental Manager').exists())
    
    def test_create_oidc_only_user(self):
        """Create a user without password (OIDC/SSO only)."""
        code, out, err = self.run_command(
            "create_user testuser04 --email test4@example.com --no-password --force"
        )
        self.assertEqual(code, 0, f"Command failed with stderr: {err}")
        
        user = User.objects.get(username='testuser04')
        self.assertFalse(user.has_usable_password())
    
    def test_dry_run_mode(self):
        """Verify dry-run doesn't create user."""
        code, out, err = self.run_command(
            "create_user dryrunuser --email dry@example.com",
            dry_run=True
        )
        self.assertEqual(code, 0, f"Command failed with stderr: {err}")
        # Check for dry-run indicator in output
        self.assertTrue(
            "[DRY-RUN]" in (out or err) or "dry-run" in (out or err).lower(),
            f"Expected dry-run indicator in output: {out or err}"
        )
        self.assertFalse(User.objects.filter(username='dryrunuser').exists())


@pytest.mark.django_db(transaction=True)
class TestGroupManagement(BaseSystemTest, unittest.TestCase):
    """Test manager group setup and membership."""
    
    def test_create_billing_manager_group(self):
        """Create Billing Manager group with permissions."""
        code, out, err = self.run_command(
            "setup_billing_manager --create-group"
        )
        self.assertEqual(code, 0, f"Command failed with stderr: {err}")
        self.assertTrue(Group.objects.filter(name='Billing Manager').exists())
    
    def test_add_user_to_group(self):
        """Add user to manager group."""
        # Create user first
        self.run_command("create_user grouptest --email grouptest@example.com --force")
        # Ensure group exists
        self.run_command("setup_billing_manager --create-group")
        
        code, out, err = self.run_command(
            "setup_billing_manager --add-user grouptest"
        )
        self.assertEqual(code, 0, f"Command failed with stderr: {err}")
        
        user = User.objects.get(username='grouptest')
        self.assertTrue(user.groups.filter(name='Billing Manager').exists())


@pytest.mark.django_db(transaction=True)
class TestAccountMaintenanceFee(BaseSystemTest, unittest.TestCase):
    """Test account maintenance fee configuration."""
    
    def test_set_amf_basic(self):
        """Set user to basic maintenance status."""
        # Requires project to exist first
        username = "amftest"
        project_name = f"{username}_group"
        
        # Create user
        self.run_command(f"create_user {username} --email {username}@example.com --force")
        # Create project (assuming create_orcd_project command exists)
        self.run_command(f"create_orcd_project {username} --force")
        
        code, out, err = self.run_command(
            f"set_user_amf {username} basic --project {project_name} --force"
        )
        self.assertEqual(code, 0, f"Command failed with stderr: {err}")
    
    def test_set_amf_advanced(self):
        """Set user to advanced maintenance status."""
        username = "amftest2"
        project_name = f"{username}_group"
        
        # Create user
        self.run_command(f"create_user {username} --email {username}@example.com --force")
        # Create project
        self.run_command(f"create_orcd_project {username} --force")
        
        code, out, err = self.run_command(
            f"set_user_amf {username} advanced --project {project_name} --force"
        )
        self.assertEqual(code, 0, f"Command failed with stderr: {err}")
    
    def test_set_amf_requires_project(self):
        """Verify basic/advanced status requires billing project."""
        username = "amftest3"
        
        # Create user
        self.run_command(f"create_user {username} --email {username}@example.com --force")
        
        # Attempt to set AMF without project (should fail)
        code, out, err = self.run_command(
            f"set_user_amf {username} basic"  # No --project
        )
        self.assertNotEqual(code, 0, "Command should have failed without --project")
        # Check for error message about requiring project
        error_output = err or out
        self.assertTrue(
            "requires" in error_output.lower() or "project" in error_output.lower(),
            f"Expected error about requiring project, got: {error_output}"
        )


@pytest.mark.django_db(transaction=True)
class TestBulkUserCreation(BaseSystemTest, unittest.TestCase):
    """Test creating multiple users from YAML config."""
    
    def test_create_users_from_yaml(self):
        """Create all users defined in users.yaml.
        
        The users.yaml uses a simplified schema with a single 'users' list.
        All users are created with PI status (can create and own projects).
        Privileged roles are assigned via the 'groups' field.
        """
        from ..utils.yaml_loader import load_users_config
        from ..utils.command_generator import CommandGenerator
        
        # Get config path relative to this file
        config_path = Path(__file__).parent.parent / 'config' / 'users.yaml'
        
        if not config_path.exists():
            self.skipTest(f"Config file not found: {config_path}")
        
        generator = CommandGenerator(str(config_path))
        commands = generator.generate_user_commands()
        
        # Execute each command and verify success
        for cmd in commands:
            code, out, err = self.run_command(cmd)
            self.assertEqual(
                code, 0,
                f"Failed to execute command: {cmd}\nstdout: {out}\nstderr: {err}"
            )
        
        # Verify that users were created
        config = load_users_config(str(config_path))
        all_users = config.get('users', [])
        
        for user_config in all_users:
            username = user_config.get('username')
            if username:
                self.assertTrue(
                    User.objects.filter(username=username).exists(),
                    f"User {username} was not created"
                )

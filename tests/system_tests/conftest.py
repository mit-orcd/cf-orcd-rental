"""pytest configuration for system tests.

Configures pytest-django to use the existing database created by
tests/setup/setup_environment.sh rather than creating a test database.

Key configuration:
1. Sets DJANGO_SETTINGS_MODULE before pytest-django initializes
2. Overrides django_db_setup to skip test database creation
3. Automatically grants database access to all tests

IMPORTANT: Do NOT override django_db_blocker - it breaks pytest-django internals.
"""

import os
import pytest

# Set Django settings before pytest-django initializes
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coldfront.config.settings')


def pytest_configure(config):
    """Configure pytest with Django settings."""
    # Register custom markers
    config.addinivalue_line(
        "markers", "django_db: mark test as needing database access"
    )


@pytest.fixture(scope='session')
def django_db_setup(django_db_blocker):
    """Override to seed test database with ColdFront initial data.
    
    When pytest-django creates a test database, it doesn't include the data
    that `coldfront initial_setup` would normally create. This fixture seeds
    the test database with the required model instances so that subprocess
    coldfront commands can function properly.
    
    Required data:
    - ProjectStatusChoice: Active, Inactive, Archived, New
    - ProjectUserRoleChoice: Manager, User
    - ProjectUserStatusChoice: Active, Pending, Removed
    - FieldOfScience: Other (is_selectable=True)
    """
    with django_db_blocker.unblock():
        # Import models inside function to avoid import errors before Django setup
        from coldfront.core.project.models import (
            ProjectStatusChoice,
            ProjectUserRoleChoice,
            ProjectUserStatusChoice,
        )
        from coldfront.core.field_of_science.models import FieldOfScience
        
        # Create ProjectStatusChoice instances
        for name in ["Active", "Inactive", "Archived", "New"]:
            ProjectStatusChoice.objects.get_or_create(name=name)
        
        # Create ProjectUserRoleChoice instances
        for name in ["Manager", "User"]:
            ProjectUserRoleChoice.objects.get_or_create(name=name)
        
        # Create ProjectUserStatusChoice instances
        for name in ["Active", "Pending", "Removed"]:
            ProjectUserStatusChoice.objects.get_or_create(name=name)
        
        # Create FieldOfScience instance
        FieldOfScience.objects.get_or_create(
            description="Other",
            defaults={"is_selectable": True}
        )
    
    yield


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(request):
    """Automatically grant database access to all tests.
    
    Since these are system tests that execute management commands
    via subprocess, all tests need database access.
    
    Note: This adds the marker without depending on the `db` fixture,
    avoiding circular dependencies with pytest-django internals.
    """
    # Apply django_db marker programmatically if not already present
    if not request.node.get_closest_marker('django_db'):
        request.node.add_marker(pytest.mark.django_db(transaction=True))

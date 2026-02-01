"""pytest configuration for system tests.

This module configures pytest-django to work with the ColdFront environment
set up by tests/setup/setup_environment.sh.

The key configuration here:
1. Sets DJANGO_SETTINGS_MODULE before any Django imports
2. Calls django.setup() to initialize Django
3. Configures pytest-django to use the existing database (not create a new one)
"""

import os
import sys

# Ensure Django settings are configured before any imports
# This must happen before importing django or any Django models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coldfront.config.settings')

import django
import pytest

# Initialize Django - this must be done before importing any models
django.setup()


def pytest_configure(config):
    """Configure pytest with Django settings."""
    # Register custom markers
    config.addinivalue_line(
        "markers", "django_db: mark test as needing database access"
    )


@pytest.fixture(scope='session')
def django_db_setup():
    """Use the existing database created by setup_environment.sh.
    
    This fixture overrides pytest-django's default behavior of creating
    a test database. Instead, we use the database that was set up by
    the setup_environment.sh script, which includes:
    - All migrations applied
    - Initial ColdFront data (from initial_setup)
    - Manager groups created
    - Fixtures loaded
    """
    # Don't create a new database - use the existing one
    pass


@pytest.fixture(scope='session')
def django_db_blocker():
    """Allow database access in session-scoped fixtures."""
    from django.test.utils import CaptureQueriesContext
    from django.db import connection
    return None


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """Automatically enable database access for all tests.
    
    This removes the need to mark every test with @pytest.mark.django_db.
    Since these are system tests that interact with the database via
    management commands, all tests need database access.
    """
    pass


# pytest-django settings
def pytest_collection_modifyitems(config, items):
    """Add django_db marker to all tests automatically."""
    for item in items:
        # Add django_db marker to all test items
        item.add_marker(pytest.mark.django_db(transaction=True))

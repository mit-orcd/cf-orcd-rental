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
def django_db_setup():
    """Override to use existing database instead of creating test database.
    
    The database has already been set up by setup_environment.sh with:
    - All migrations applied
    - Initial ColdFront data via initial_setup (includes ProjectStatusChoice, etc.)
    - Manager groups created
    - Fixtures loaded
    
    By yielding without calling django.test.utils functions to create/destroy
    a test database, pytest-django will use the default database as-is.
    
    Note: We do NOT seed data here because subprocess coldfront commands
    run outside pytest's database context. Seeding must happen in
    initialize_database.sh during the setup phase.
    """
    # Don't create a test database - just use the existing one
    yield
    # Don't destroy anything on teardown


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

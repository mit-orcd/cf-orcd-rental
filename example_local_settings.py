# =============================================================================
# Example local_settings.py for ColdFront with ORCD Direct Charge Plugin
# =============================================================================
# Copy this file to your coldfront directory as local_settings.py and customize
# as needed for your deployment.

import os

# =============================================================================
# Site Customization
# =============================================================================
CENTER_NAME = "MIT ORCD Rental Services"

# =============================================================================
# Development Settings
# =============================================================================

# Authentication - use standard Django auth for local development
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

# Cookie/Session settings for HTTP (non-HTTPS) development
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_DOMAIN = None


# =============================================================================
# ORCD Direct Charge Plugin
# =============================================================================
INSTALLED_APPS += [
                   'coldfront_orcd_direct_charge'
                  ]

# Set to True to re-enable Center Summary in the navigation bar
# CENTER_SUMMARY_ENABLE = False

# Set to False to hide the Allocations section on the home page
HOME_PAGE_ALLOCATIONS_ENABLE = False


# =============================================================================
# Auto-Configuration Features (ORCD Direct Charge Plugin)
# =============================================================================
# These features automatically configure user accounts when enabled.
# WARNING: Changes are IRREVERSIBLE - once applied, accounts keep their
# settings even if the feature is later disabled.
#
# Features can be enabled via:
#   1. Setting the variable directly below (takes precedence)
#   2. Setting an environment variable (e.g., AUTO_PI_ENABLE=true)
#
# When AUTO_PI_ENABLE is True:
#   - All existing users have is_pi set to True on app startup
#   - All new users automatically get is_pi=True via signal
#   - Users can create projects without manual PI approval
#
# When AUTO_DEFAULT_PROJECT_ENABLE is True:
#   - All existing users get a USERNAME_group project on app startup
#   - All new users automatically get the project via signal
#   - User is set as PI (required to own a project)
#   - User is added as Manager on their project with Active status

# Default: disabled (set to True to enable, or use environment variable)
AUTO_PI_ENABLE = False

# Check for environment variable override
if os.environ.get("AUTO_PI_ENABLE", "").lower() == "true":
    AUTO_PI_ENABLE = True

# Default: disabled (set to True to enable, or use environment variable)
AUTO_DEFAULT_PROJECT_ENABLE = False

# Check for environment variable override
if os.environ.get("AUTO_DEFAULT_PROJECT_ENABLE", "").lower() == "true":
    AUTO_DEFAULT_PROJECT_ENABLE = True


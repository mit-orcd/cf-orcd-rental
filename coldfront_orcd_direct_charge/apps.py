# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

import os

from django.apps import AppConfig
from django.conf import settings


class OrcdDirectChargeConfig(AppConfig):
    name = "coldfront_orcd_direct_charge"
    verbose_name = "ORCD Direct Charge"

    def ready(self):
        # Import signals to register handlers
        from coldfront_orcd_direct_charge import signals  # noqa: F401

        # Connect ProjectMemberRole signals (avoids circular imports)
        signals.connect_member_role_signals()

        # Dynamically add the plugin templates directory to TEMPLATES['DIRS']
        # This allows the plugin to override core ColdFront templates
        plugin_templates_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "templates"
        )

        # Prepend our templates directory so it takes priority
        for template_setting in settings.TEMPLATES:
            if plugin_templates_dir not in template_setting["DIRS"]:
                template_setting["DIRS"] = [plugin_templates_dir] + list(
                    template_setting["DIRS"]
                )

        # Set default for CENTER_SUMMARY_ENABLE if not already set
        if not hasattr(settings, "CENTER_SUMMARY_ENABLE"):
            settings.CENTER_SUMMARY_ENABLE = False

        # Ensure CENTER_SUMMARY_ENABLE is exported to templates
        if "CENTER_SUMMARY_ENABLE" not in settings.SETTINGS_EXPORT:
            settings.SETTINGS_EXPORT.append("CENTER_SUMMARY_ENABLE")

        # Set default for HOME_PAGE_ALLOCATIONS_ENABLE if not already set
        # Default is True to maintain backward compatibility
        if not hasattr(settings, "HOME_PAGE_ALLOCATIONS_ENABLE"):
            settings.HOME_PAGE_ALLOCATIONS_ENABLE = True

        # Ensure HOME_PAGE_ALLOCATIONS_ENABLE is exported to templates
        if "HOME_PAGE_ALLOCATIONS_ENABLE" not in settings.SETTINGS_EXPORT:
            settings.SETTINGS_EXPORT.append("HOME_PAGE_ALLOCATIONS_ENABLE")

        # =============================================================================
        # Auto-Configuration Features
        # These features modify user accounts. Changes are IRREVERSIBLE - once applied,
        # accounts keep their settings even if the feature is disabled.
        # =============================================================================

        # AUTO_PI_ENABLE: When True, all users are automatically set as PIs (is_pi=True)
        # This allows all users to create projects without manual PI approval.
        # Precedence: local_settings.py > environment variable > default (False)
        if not hasattr(settings, "AUTO_PI_ENABLE"):
            settings.AUTO_PI_ENABLE = (
                os.environ.get("AUTO_PI_ENABLE", "").lower() == "true"
            )

        # Export AUTO_PI_ENABLE to templates (used to hide PI Status when always True)
        if "AUTO_PI_ENABLE" not in settings.SETTINGS_EXPORT:
            settings.SETTINGS_EXPORT.append("AUTO_PI_ENABLE")

        # AUTO_DEFAULT_PROJECT_ENABLE: When True, creates USERNAME_personal and USERNAME_group projects for each user
        # Each user gets personal and group projects they own as PI.
        # Requires user to be a PI (will auto-enable is_pi for project owners).
        # Precedence: local_settings.py > environment variable > default (False)
        if not hasattr(settings, "AUTO_DEFAULT_PROJECT_ENABLE"):
            settings.AUTO_DEFAULT_PROJECT_ENABLE = (
                os.environ.get("AUTO_DEFAULT_PROJECT_ENABLE", "").lower() == "true"
            )

        # Apply auto features to existing users (deferred to avoid issues during migrations)
        # Always ensure maintenance status exists for all users
        self._ensure_maintenance_status_if_ready()

        if settings.AUTO_PI_ENABLE or settings.AUTO_DEFAULT_PROJECT_ENABLE:
            self._apply_auto_features_if_ready()

    def _ensure_maintenance_status_if_ready(self):
        """Ensure all users have a maintenance status if database is ready."""
        from django.db import connection

        try:
            table_names = connection.introspection.table_names()
            # Check if both auth_user and our maintenance status table exist
            if (
                "auth_user" in table_names
                and "coldfront_orcd_direct_charge_usermaintenancestatus" in table_names
            ):
                self._ensure_maintenance_status()
        except Exception:
            # Database might not be ready yet (e.g., during initial setup)
            pass

    def _ensure_maintenance_status(self):
        """Ensure all users have a UserMaintenanceStatus record."""
        from django.contrib.auth.models import User
        from coldfront_orcd_direct_charge.models import UserMaintenanceStatus

        for user in User.objects.all():
            UserMaintenanceStatus.objects.get_or_create(
                user=user,
                defaults={"status": UserMaintenanceStatus.StatusChoices.INACTIVE},
            )

    def _apply_auto_features_if_ready(self):
        """Apply auto features to existing users if database is ready."""
        from django.db import connection

        # Check if auth_user table exists (avoids errors during initial migrations)
        try:
            table_names = connection.introspection.table_names()
            if "auth_user" in table_names:
                self._apply_auto_features()
        except Exception:
            # Database might not be ready yet (e.g., during initial setup)
            pass

    def _apply_auto_features(self):
        """Apply auto features to existing users."""
        from django.contrib.auth.models import User
        from coldfront.core.user.models import UserProfile

        # AUTO_PI_ENABLE: Set all users as PIs
        if settings.AUTO_PI_ENABLE:
            # Update all UserProfiles where is_pi is False
            UserProfile.objects.filter(is_pi=False).update(is_pi=True)

        # AUTO_DEFAULT_PROJECT_ENABLE: Create personal and group projects for each user
        if settings.AUTO_DEFAULT_PROJECT_ENABLE:
            from coldfront_orcd_direct_charge.signals import (
                create_default_project_for_user,
                create_group_project_for_user,
            )

            for user in User.objects.all():
                create_default_project_for_user(user)
                create_group_project_for_user(user)


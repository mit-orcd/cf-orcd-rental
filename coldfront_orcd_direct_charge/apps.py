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

        # Connect activity logging signals
        signals.connect_activity_log_signals()

        # Connect NodeType to RentalSKU synchronization signals
        # This ensures RentalSKU records are created/updated when NodeTypes change
        signals.connect_nodetype_sku_signals()

        # =============================================================================
        # Runtime Configuration
        # Load plugin configuration from YAML file and register SIGHUP handler
        # for hot-reloading via: systemctl reload coldfront
        # =============================================================================
        from coldfront_orcd_direct_charge import config
        config.load_config()

        # Register SIGHUP handler for runtime configuration reload
        signals.register_sighup_handler()

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

        # Apply runtime configuration to Django settings
        self._apply_runtime_config()

        # Apply auto features to existing users (deferred to avoid issues during migrations)
        # Always ensure maintenance status exists for all users
        self._ensure_maintenance_status_if_ready()

        if settings.AUTO_PI_ENABLE or settings.AUTO_DEFAULT_PROJECT_ENABLE:
            self._apply_auto_features_if_ready()

    def _apply_runtime_config(self):
        """
        Apply runtime configuration to Django settings.

        Configuration precedence (highest to lowest):
        1. Django local_settings.py (checked via hasattr)
        2. plugin_config.yaml (read by config module)
        3. Environment variables (backward compatibility)
        4. Code defaults (in config.DEFAULT_CONFIG)
        """
        from coldfront_orcd_direct_charge import config

        # Check if config file exists for precedence decisions
        config_file_exists = os.path.exists(config.get_config_path())

        # ---------------------------------------------------------------------
        # UI Options
        # ---------------------------------------------------------------------

        # CENTER_SUMMARY_ENABLE: Show Center Summary in navbar
        # Precedence: local_settings.py > config file > default (False)
        if not hasattr(settings, "CENTER_SUMMARY_ENABLE"):
            settings.CENTER_SUMMARY_ENABLE = config.get('center_summary_enable', False)

        # Ensure CENTER_SUMMARY_ENABLE is exported to templates
        if "CENTER_SUMMARY_ENABLE" not in settings.SETTINGS_EXPORT:
            settings.SETTINGS_EXPORT.append("CENTER_SUMMARY_ENABLE")

        # HOME_PAGE_ALLOCATIONS_ENABLE: Show Allocations section on home page
        # Precedence: local_settings.py > config file > default (True)
        if not hasattr(settings, "HOME_PAGE_ALLOCATIONS_ENABLE"):
            settings.HOME_PAGE_ALLOCATIONS_ENABLE = config.get(
                'home_page_allocations_enable', True
            )

        # Ensure HOME_PAGE_ALLOCATIONS_ENABLE is exported to templates
        if "HOME_PAGE_ALLOCATIONS_ENABLE" not in settings.SETTINGS_EXPORT:
            settings.SETTINGS_EXPORT.append("HOME_PAGE_ALLOCATIONS_ENABLE")

        # PASSWORD_LOGIN_ENABLE: Allow username/password login form
        # Precedence: local_settings.py > config file > default (False)
        if not hasattr(settings, "PASSWORD_LOGIN_ENABLE"):
            settings.PASSWORD_LOGIN_ENABLE = config.get('password_login_enable', False)

        # Ensure PASSWORD_LOGIN_ENABLE is exported to templates
        if "PASSWORD_LOGIN_ENABLE" not in settings.SETTINGS_EXPORT:
            settings.SETTINGS_EXPORT.append("PASSWORD_LOGIN_ENABLE")

        # ---------------------------------------------------------------------
        # Auto-Configuration Features
        # These features modify user accounts. Changes are IRREVERSIBLE - once
        # applied, accounts keep their settings even if the feature is disabled.
        # ---------------------------------------------------------------------

        # AUTO_PI_ENABLE: When True, all users are automatically set as PIs
        # Precedence: local_settings.py > config file > env var > default (False)
        if not hasattr(settings, "AUTO_PI_ENABLE"):
            if config_file_exists:
                # Config file takes precedence when it exists
                settings.AUTO_PI_ENABLE = config.get('auto_pi_enable', False)
            else:
                # Backward compatibility: use env var when no config file
                settings.AUTO_PI_ENABLE = (
                    os.environ.get("AUTO_PI_ENABLE", "").lower() == "true"
                )

        # Export AUTO_PI_ENABLE to templates (used to hide PI Status when always True)
        if "AUTO_PI_ENABLE" not in settings.SETTINGS_EXPORT:
            settings.SETTINGS_EXPORT.append("AUTO_PI_ENABLE")

        # AUTO_DEFAULT_PROJECT_ENABLE: When True, creates USERNAME_group project
        # Precedence: local_settings.py > config file > env var > default (False)
        if not hasattr(settings, "AUTO_DEFAULT_PROJECT_ENABLE"):
            if config_file_exists:
                # Config file takes precedence when it exists
                settings.AUTO_DEFAULT_PROJECT_ENABLE = config.get(
                    'auto_default_project_enable', False
                )
            else:
                # Backward compatibility: use env var when no config file
                settings.AUTO_DEFAULT_PROJECT_ENABLE = (
                    os.environ.get("AUTO_DEFAULT_PROJECT_ENABLE", "").lower() == "true"
                )

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

        # AUTO_DEFAULT_PROJECT_ENABLE: Create group project for each user
        if settings.AUTO_DEFAULT_PROJECT_ENABLE:
            from coldfront_orcd_direct_charge.signals import (
                create_group_project_for_user,
            )

            for user in User.objects.all():
                create_group_project_for_user(user)


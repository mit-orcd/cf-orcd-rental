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


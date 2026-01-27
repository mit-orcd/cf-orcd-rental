# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Configuration export functionality.

This module provides functions to collect and export configuration settings
from the Django/ColdFront/Plugin stack. Configuration is exported to a
dedicated 'config/' directory within the export tree.

Exported configuration categories:
    - plugin_config: ORCD Direct Charge plugin settings
    - coldfront_config: ColdFront-specific settings
    - django_config: Core Django settings (non-sensitive)
    - environment: Runtime environment metadata

Security:
    Sensitive settings (passwords, secrets, API keys) are explicitly
    excluded from export to prevent credential exposure.
"""

import json
import platform
import re
import socket
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Patterns for settings that should NEVER be exported (security)
SENSITIVE_PATTERNS = [
    r'.*PASSWORD.*',
    r'.*SECRET.*',
    r'.*TOKEN.*',
    r'.*CREDENTIAL.*',
    r'.*PRIVATE.*',
    r'^API_KEY$',
    r'^AWS_.*',
    r'^SOCIAL_AUTH_.*_KEY$',
    r'^SOCIAL_AUTH_.*_SECRET$',
    r'^DATABASE_URL$',
    r'^REDIS_URL$',
    r'^CELERY_BROKER_URL$',
]

# Compile patterns for efficiency
_SENSITIVE_REGEXES = [re.compile(p, re.IGNORECASE) for p in SENSITIVE_PATTERNS]


def is_sensitive_setting(name: str) -> bool:
    """Check if a setting name matches sensitive patterns.
    
    Args:
        name: Setting name to check
        
    Returns:
        True if the setting should be excluded for security
    """
    for regex in _SENSITIVE_REGEXES:
        if regex.match(name):
            return True
    return False


@dataclass
class ConfigSetting:
    """A single configuration setting with metadata.
    
    Attributes:
        value: The setting value
        type: Python type name (str, bool, int, list, etc.)
        source: Where the setting came from (settings, config_file, default)
        description: Human-readable description
    """
    value: Any
    type: str
    source: str = "settings"
    description: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class ConfigExportResult:
    """Result of a configuration export operation.
    
    Attributes:
        success: Whether export completed successfully
        config_dir: Path to the config directory created
        categories: Dict mapping category name to setting count
        errors: List of error messages
        warnings: List of warning messages
    """
    success: bool
    config_dir: str
    categories: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def collect_plugin_config() -> Dict[str, ConfigSetting]:
    """Collect ORCD Direct Charge plugin configuration.
    
    Collects settings from:
    1. Runtime config module (config.py)
    2. Django settings overrides
    
    Returns:
        Dict mapping setting name to ConfigSetting
    """
    from coldfront_orcd_direct_charge import config as plugin_config
    
    plugin_settings = {}
    
    # Plugin runtime configuration settings
    config_definitions = {
        'center_summary_enable': {
            'description': 'Show Center Summary link in navbar',
            'default': False,
        },
        'home_page_allocations_enable': {
            'description': 'Show Allocations section on home page',
            'default': True,
        },
        'auto_pi_enable': {
            'description': 'Auto-set all users as Principal Investigators',
            'default': False,
        },
        'auto_default_project_enable': {
            'description': 'Auto-create USERNAME_group project for users',
            'default': False,
        },
        'password_login_enable': {
            'description': 'Enable username/password login form',
            'default': False,
        },
    }
    
    for setting_name, definition in config_definitions.items():
        # Get value from runtime config
        value = plugin_config.get(setting_name, definition['default'])
        
        # Check if overridden in Django settings
        django_setting_name = setting_name.upper()
        source = "config_file"
        if hasattr(settings, django_setting_name):
            django_value = getattr(settings, django_setting_name)
            if django_value != value:
                value = django_value
                source = "django_settings"
        
        plugin_settings[setting_name] = ConfigSetting(
            value=value,
            type=type(value).__name__,
            source=source,
            description=definition['description'],
        )
    
    return plugin_settings


def collect_coldfront_config() -> Dict[str, ConfigSetting]:
    """Collect ColdFront-specific configuration settings.
    
    Returns:
        Dict mapping setting name to ConfigSetting
    """
    coldfront_settings = {}
    
    # ColdFront settings to export
    settings_definitions = {
        'CENTER_NAME': {
            'description': 'Display name of the HPC center',
            'default': 'HPC Center',
        },
        'CENTER_BASE_URL': {
            'description': 'Base URL of the portal',
            'default': '',
        },
        'PROJECT_ENABLE_PROJECT_REVIEW': {
            'description': 'Enable periodic project review workflow',
            'default': True,
        },
        'ALLOCATION_ENABLE_ALLOCATION_RENEWAL': {
            'description': 'Enable allocation renewal workflow',
            'default': True,
        },
        'ALLOCATION_DEFAULT_ALLOCATION_LENGTH': {
            'description': 'Default allocation duration in days',
            'default': 365,
        },
        'EMAIL_ENABLED': {
            'description': 'Master switch for email notifications',
            'default': False,
        },
        'EMAIL_SENDER': {
            'description': 'From address for portal emails',
            'default': '',
        },
        'EMAIL_SIGNATURE': {
            'description': 'Signature appended to portal emails',
            'default': '',
        },
        'EMAIL_SUBJECT_PREFIX': {
            'description': 'Prefix for email subject lines',
            'default': '',
        },
    }
    
    for setting_name, definition in settings_definitions.items():
        if hasattr(settings, setting_name):
            value = getattr(settings, setting_name)
            coldfront_settings[setting_name] = ConfigSetting(
                value=value,
                type=type(value).__name__,
                source="django_settings",
                description=definition['description'],
            )
        else:
            # Record default value
            coldfront_settings[setting_name] = ConfigSetting(
                value=definition['default'],
                type=type(definition['default']).__name__,
                source="default",
                description=definition['description'],
            )
    
    return coldfront_settings


def collect_django_config() -> Dict[str, ConfigSetting]:
    """Collect core Django configuration settings.
    
    Sensitive settings (passwords, secrets) are explicitly excluded.
    
    Returns:
        Dict mapping setting name to ConfigSetting
    """
    django_settings = {}
    
    # Django settings to export (non-sensitive)
    settings_definitions = {
        'DEBUG': {
            'description': 'Django debug mode',
        },
        'TIME_ZONE': {
            'description': 'Server timezone',
        },
        'LANGUAGE_CODE': {
            'description': 'Default language code',
        },
        'USE_TZ': {
            'description': 'Use timezone-aware datetimes',
        },
    }
    
    for setting_name, definition in settings_definitions.items():
        if hasattr(settings, setting_name):
            value = getattr(settings, setting_name)
            django_settings[setting_name] = ConfigSetting(
                value=value,
                type=type(value).__name__,
                source="django_settings",
                description=definition['description'],
            )
    
    # INSTALLED_APPS - important for compatibility checking
    if hasattr(settings, 'INSTALLED_APPS'):
        django_settings['INSTALLED_APPS'] = ConfigSetting(
            value=list(settings.INSTALLED_APPS),
            type="list",
            source="django_settings",
            description="Enabled Django applications",
        )
    
    # AUTHENTICATION_BACKENDS
    if hasattr(settings, 'AUTHENTICATION_BACKENDS'):
        django_settings['AUTHENTICATION_BACKENDS'] = ConfigSetting(
            value=list(settings.AUTHENTICATION_BACKENDS),
            type="list",
            source="django_settings",
            description="Authentication backends in use",
        )
    
    # DATABASE_ENGINE only (not connection string)
    if hasattr(settings, 'DATABASES') and 'default' in settings.DATABASES:
        engine = settings.DATABASES['default'].get('ENGINE', '')
        django_settings['DATABASE_ENGINE'] = ConfigSetting(
            value=engine,
            type="str",
            source="django_settings",
            description="Database backend engine",
        )
    
    return django_settings


def collect_environment_metadata() -> Dict[str, Any]:
    """Collect runtime environment metadata.
    
    This is informational only and not compared during import.
    
    Returns:
        Dict with environment metadata
    """
    import django
    
    try:
        from coldfront import __version__ as coldfront_version
    except ImportError:
        coldfront_version = "unknown"
    
    try:
        from coldfront_orcd_direct_charge import __version__ as plugin_version
    except (ImportError, AttributeError):
        plugin_version = "unknown"
    
    return {
        'python_version': platform.python_version(),
        'django_version': django.__version__,
        'coldfront_version': coldfront_version,
        'plugin_version': plugin_version,
        'hostname': socket.gethostname(),
        'platform': platform.platform(),
        'exported_at': timezone.now().isoformat(),
    }


def export_configuration(
    output_dir: str,
    dry_run: bool = False,
) -> ConfigExportResult:
    """Export all configuration to the config/ subdirectory.
    
    Creates a 'config/' directory within output_dir containing:
    - plugin_config.json
    - coldfront_config.json
    - django_config.json
    - environment.json
    - manifest.json
    
    Args:
        output_dir: Root export directory
        dry_run: If True, collect but don't write files
        
    Returns:
        ConfigExportResult with export status and counts
    """
    from .config_manifest import generate_config_manifest
    
    result = ConfigExportResult(
        success=True,
        config_dir=str(Path(output_dir) / "config"),
    )
    
    try:
        # Collect all configuration
        plugin_config = collect_plugin_config()
        coldfront_config = collect_coldfront_config()
        django_config = collect_django_config()
        environment = collect_environment_metadata()
        
        result.categories = {
            'plugin_config': len(plugin_config),
            'coldfront_config': len(coldfront_config),
            'django_config': len(django_config),
            'environment': len(environment),
        }
        
        if dry_run:
            return result
        
        # Create config directory
        config_dir = Path(output_dir) / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        result.config_dir = str(config_dir)
        
        # Write plugin config
        _write_config_file(
            config_dir / "plugin_config.json",
            "plugin_config",
            {k: v.to_dict() for k, v in plugin_config.items()},
        )
        
        # Write coldfront config
        _write_config_file(
            config_dir / "coldfront_config.json",
            "coldfront_config",
            {k: v.to_dict() for k, v in coldfront_config.items()},
        )
        
        # Write django config
        _write_config_file(
            config_dir / "django_config.json",
            "django_config",
            {k: v.to_dict() for k, v in django_config.items()},
        )
        
        # Write environment metadata
        _write_config_file(
            config_dir / "environment.json",
            "environment",
            environment,
        )
        
        # Generate and write config manifest
        manifest = generate_config_manifest(
            str(config_dir),
            result.categories,
        )
        manifest.save(str(config_dir))
        
    except Exception as e:
        logger.exception("Failed to export configuration")
        result.success = False
        result.errors.append(str(e))
    
    return result


def _write_config_file(
    path: Path,
    category: str,
    settings_data: Dict,
) -> None:
    """Write a configuration file with standard structure.
    
    Args:
        path: Output file path
        category: Configuration category name
        settings_data: Settings to write
    """
    from .manifest import EXPORT_VERSION
    
    data = {
        "export_version": EXPORT_VERSION,
        "exported_at": timezone.now().isoformat(),
        "category": category,
        "settings": settings_data,
    }
    
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)

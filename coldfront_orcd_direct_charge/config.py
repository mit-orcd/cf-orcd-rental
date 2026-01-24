# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Runtime configuration module for ORCD Direct Charge plugin.

This module provides thread-safe configuration management with support for:
- Loading configuration from a YAML file
- Hot-reloading configuration via SIGHUP signal
- Default values when no configuration file exists

Configuration file location is determined by:
1. ORCD_PLUGIN_CONFIG environment variable
2. Default: /srv/coldfront/plugin_config.yaml

Usage:
    from coldfront_orcd_direct_charge import config

    # Get a configuration value
    value = config.get('center_summary_enable', False)

    # Reload configuration (typically triggered by SIGHUP)
    config.reload_config()
"""

import os
import logging
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

# Thread-safe configuration storage
_config = {}
_config_lock = Lock()

# Default configuration values
# These are conservative defaults matching the code defaults in apps.py
# Production deployments typically override these via the config file
DEFAULT_CONFIG = {
    # UI Options
    'center_summary_enable': False,        # Default: False - Center Summary hidden in navbar
    'home_page_allocations_enable': True,  # Default: True - Show Allocations on home page
    # Auto-configuration features
    # NOTE: Code defaults are False, but production deployment sets True via env vars
    # These defaults are fallbacks only used when no config file exists
    'auto_pi_enable': False,               # Default: False - Users must be manually set as PIs
    'auto_default_project_enable': False,  # Default: False - No auto USERNAME_group project
}


def get_config_path():
    """
    Get path to plugin config file.

    Returns:
        str: Path to the configuration file. Checks ORCD_PLUGIN_CONFIG
             environment variable first, then falls back to default location.
    """
    return os.environ.get(
        'ORCD_PLUGIN_CONFIG',
        '/srv/coldfront/plugin_config.yaml'
    )


def _load_yaml_file(config_path):
    """
    Load YAML file, handling the case where PyYAML is not installed.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        dict: Parsed configuration or empty dict if file cannot be parsed.
    """
    try:
        import yaml
    except ImportError:
        logger.warning(
            "PyYAML not installed - cannot load config file %s. "
            "Install with: pip install pyyaml",
            config_path
        )
        return {}

    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error("Failed to load config file %s: %s", config_path, e)
        return {}


def load_config():
    """
    Load configuration from YAML file.

    This function is thread-safe and can be called from any thread.
    Configuration is loaded from the path specified by get_config_path().

    If the configuration file does not exist, default values are used.
    If the file exists but cannot be parsed, defaults are used and an
    error is logged.

    Returns:
        dict: The current configuration (copy of internal state).
    """
    global _config
    config_path = get_config_path()

    with _config_lock:
        # Start with defaults
        _config = DEFAULT_CONFIG.copy()

        if os.path.exists(config_path):
            file_config = _load_yaml_file(config_path)
            if file_config:
                _config.update(file_config)
                logger.info("Loaded plugin config from %s", config_path)
        else:
            logger.info("No config file at %s, using defaults", config_path)

        return _config.copy()


def get(key, default=None):
    """
    Get a configuration value (thread-safe).

    Args:
        key: The configuration key to retrieve.
        default: Value to return if key is not found. If None, uses the
                 default from DEFAULT_CONFIG if available.

    Returns:
        The configuration value, or default if not found.
    """
    with _config_lock:
        if default is None and key in DEFAULT_CONFIG:
            default = DEFAULT_CONFIG[key]
        return _config.get(key, default)


def get_all():
    """
    Get a copy of all configuration values (thread-safe).

    Returns:
        dict: Copy of the current configuration.
    """
    with _config_lock:
        return _config.copy()


def reload_config():
    """
    Reload configuration from file.

    This is the function that should be called when SIGHUP is received.
    It reloads the configuration from the file and logs the reload.

    Returns:
        dict: The newly loaded configuration.
    """
    result = load_config()
    logger.info("Plugin configuration reloaded")
    return result

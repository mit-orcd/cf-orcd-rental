# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tests for configuration export functionality."""

import json
import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings

from coldfront_orcd_direct_charge.backup.config_exporter import (
    collect_plugin_config,
    collect_coldfront_config,
    collect_django_config,
    collect_environment_metadata,
    export_configuration,
    is_sensitive_setting,
    ConfigSetting,
)


class TestSensitiveSettingDetection(TestCase):
    """Tests for sensitive setting detection."""
    
    def test_password_detected(self):
        """Settings with PASSWORD are sensitive."""
        self.assertTrue(is_sensitive_setting("DATABASE_PASSWORD"))
        self.assertTrue(is_sensitive_setting("EMAIL_HOST_PASSWORD"))
        self.assertTrue(is_sensitive_setting("MY_PASSWORD_HERE"))
    
    def test_secret_detected(self):
        """Settings with SECRET are sensitive."""
        self.assertTrue(is_sensitive_setting("SECRET_KEY"))
        self.assertTrue(is_sensitive_setting("CLIENT_SECRET"))
        self.assertTrue(is_sensitive_setting("MY_SECRET"))
    
    def test_token_detected(self):
        """Settings with TOKEN are sensitive."""
        self.assertTrue(is_sensitive_setting("API_TOKEN"))
        self.assertTrue(is_sensitive_setting("AUTH_TOKEN"))
    
    def test_safe_settings_not_detected(self):
        """Normal settings are not sensitive."""
        self.assertFalse(is_sensitive_setting("DEBUG"))
        self.assertFalse(is_sensitive_setting("CENTER_NAME"))
        self.assertFalse(is_sensitive_setting("INSTALLED_APPS"))
        self.assertFalse(is_sensitive_setting("TIME_ZONE"))


class TestCollectPluginConfig(TestCase):
    """Tests for plugin configuration collection."""
    
    def test_returns_expected_settings(self):
        """Plugin config collection returns expected settings."""
        config = collect_plugin_config()
        
        # Check expected settings exist
        self.assertIn("center_summary_enable", config)
        self.assertIn("home_page_allocations_enable", config)
        self.assertIn("auto_pi_enable", config)
        self.assertIn("auto_default_project_enable", config)
        self.assertIn("password_login_enable", config)
    
    def test_returns_config_setting_objects(self):
        """Each setting is a ConfigSetting instance."""
        config = collect_plugin_config()
        
        for name, setting in config.items():
            self.assertIsInstance(setting, ConfigSetting)
            self.assertIsNotNone(setting.value)
            self.assertIsNotNone(setting.type)
            self.assertIn(setting.type, ["bool", "str", "int", "list"])


class TestCollectColdfrontConfig(TestCase):
    """Tests for ColdFront configuration collection."""
    
    @override_settings(CENTER_NAME="Test Center")
    def test_center_name_collected(self):
        """CENTER_NAME is collected from settings."""
        config = collect_coldfront_config()
        
        self.assertIn("CENTER_NAME", config)
        self.assertEqual(config["CENTER_NAME"].value, "Test Center")
    
    def test_returns_expected_settings(self):
        """ColdFront config collection returns expected settings."""
        config = collect_coldfront_config()
        
        # These should exist (may have default values)
        self.assertIn("CENTER_NAME", config)
        self.assertIn("CENTER_BASE_URL", config)


class TestCollectDjangoConfig(TestCase):
    """Tests for Django configuration collection."""
    
    def test_installed_apps_collected(self):
        """INSTALLED_APPS is collected."""
        config = collect_django_config()
        
        self.assertIn("INSTALLED_APPS", config)
        self.assertEqual(config["INSTALLED_APPS"].type, "list")
        self.assertIsInstance(config["INSTALLED_APPS"].value, list)
    
    def test_debug_collected(self):
        """DEBUG setting is collected."""
        config = collect_django_config()
        
        self.assertIn("DEBUG", config)
        self.assertEqual(config["DEBUG"].type, "bool")
    
    def test_database_engine_collected(self):
        """Database engine is collected (not connection string)."""
        config = collect_django_config()
        
        self.assertIn("DATABASE_ENGINE", config)
        # Should be the engine, not full connection info
        self.assertNotIn("PASSWORD", config["DATABASE_ENGINE"].value.upper())


class TestCollectEnvironmentMetadata(TestCase):
    """Tests for environment metadata collection."""
    
    def test_returns_expected_fields(self):
        """Environment metadata contains expected fields."""
        metadata = collect_environment_metadata()
        
        self.assertIn("python_version", metadata)
        self.assertIn("django_version", metadata)
        self.assertIn("coldfront_version", metadata)
        self.assertIn("plugin_version", metadata)
        self.assertIn("hostname", metadata)
        self.assertIn("exported_at", metadata)
    
    def test_versions_are_strings(self):
        """Version fields are strings."""
        metadata = collect_environment_metadata()
        
        self.assertIsInstance(metadata["python_version"], str)
        self.assertIsInstance(metadata["django_version"], str)


class TestExportConfiguration(TestCase):
    """Tests for full configuration export."""
    
    def test_dry_run_does_not_create_files(self):
        """Dry run collects config but doesn't write files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = export_configuration(tmpdir, dry_run=True)
            
            self.assertTrue(result.success)
            self.assertIn("plugin_config", result.categories)
            
            # No files should be created
            config_dir = Path(tmpdir) / "config"
            self.assertFalse(config_dir.exists())
    
    def test_export_creates_config_directory(self):
        """Export creates config/ directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = export_configuration(tmpdir, dry_run=False)
            
            self.assertTrue(result.success)
            
            config_dir = Path(tmpdir) / "config"
            self.assertTrue(config_dir.exists())
            self.assertTrue(config_dir.is_dir())
    
    def test_export_creates_expected_files(self):
        """Export creates all expected JSON files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = export_configuration(tmpdir, dry_run=False)
            
            self.assertTrue(result.success)
            
            config_dir = Path(tmpdir) / "config"
            
            expected_files = [
                "plugin_config.json",
                "coldfront_config.json",
                "django_config.json",
                "environment.json",
                "manifest.json",
            ]
            
            for filename in expected_files:
                filepath = config_dir / filename
                self.assertTrue(filepath.exists(), f"Missing file: {filename}")
    
    def test_config_files_are_valid_json(self):
        """Exported config files are valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            export_configuration(tmpdir, dry_run=False)
            
            config_dir = Path(tmpdir) / "config"
            
            for json_file in config_dir.glob("*.json"):
                with open(json_file) as f:
                    data = json.load(f)
                self.assertIsInstance(data, dict)
    
    def test_config_file_structure(self):
        """Config files have expected structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            export_configuration(tmpdir, dry_run=False)
            
            config_dir = Path(tmpdir) / "config"
            
            with open(config_dir / "plugin_config.json") as f:
                data = json.load(f)
            
            self.assertIn("export_version", data)
            self.assertIn("exported_at", data)
            self.assertIn("category", data)
            self.assertIn("settings", data)
            self.assertEqual(data["category"], "plugin_config")
    
    def test_result_contains_category_counts(self):
        """Export result contains counts per category."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = export_configuration(tmpdir, dry_run=False)
            
            self.assertIn("plugin_config", result.categories)
            self.assertIn("coldfront_config", result.categories)
            self.assertIn("django_config", result.categories)
            self.assertIn("environment", result.categories)
            
            # Each category should have at least 1 setting
            for category, count in result.categories.items():
                self.assertGreater(count, 0, f"Category {category} has no settings")

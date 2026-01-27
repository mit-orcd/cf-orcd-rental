# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tests for configuration import and comparison functionality."""

import json
import tempfile
from pathlib import Path

from django.test import TestCase

from coldfront_orcd_direct_charge.backup.config_exporter import export_configuration
from coldfront_orcd_direct_charge.backup.config_importer import (
    compare_configurations,
    load_exported_config,
    collect_current_config,
    format_diff_report,
    check_config_compatibility,
    get_setting_severity,
    ConfigDifference,
    ConfigurationComparisonReport,
    ComparisonStatus,
    DifferenceSeverity,
)


class TestGetSettingSeverity(TestCase):
    """Tests for setting severity classification."""
    
    def test_critical_settings(self):
        """Critical settings are classified correctly."""
        self.assertEqual(
            get_setting_severity("INSTALLED_APPS"),
            DifferenceSeverity.CRITICAL
        )
        self.assertEqual(
            get_setting_severity("DATABASE_ENGINE"),
            DifferenceSeverity.CRITICAL
        )
    
    def test_warning_settings(self):
        """Warning settings are classified correctly."""
        self.assertEqual(
            get_setting_severity("auto_pi_enable"),
            DifferenceSeverity.WARNING
        )
        self.assertEqual(
            get_setting_severity("CENTER_NAME"),
            DifferenceSeverity.WARNING
        )
    
    def test_info_settings(self):
        """Info settings are classified correctly."""
        self.assertEqual(
            get_setting_severity("DEBUG"),
            DifferenceSeverity.INFO
        )
        self.assertEqual(
            get_setting_severity("TIME_ZONE"),
            DifferenceSeverity.INFO
        )
    
    def test_unknown_settings_default_to_info(self):
        """Unknown settings default to INFO severity."""
        self.assertEqual(
            get_setting_severity("UNKNOWN_SETTING"),
            DifferenceSeverity.INFO
        )


class TestCompareConfigurations(TestCase):
    """Tests for configuration comparison logic."""
    
    def test_identical_configs(self):
        """Identical configurations report as IDENTICAL."""
        config = {
            "plugin_config": {
                "setting1": {"value": True, "type": "bool"},
                "setting2": {"value": "test", "type": "str"},
            }
        }
        
        report = compare_configurations(config, config)
        
        self.assertEqual(report.status, ComparisonStatus.IDENTICAL)
        self.assertEqual(len(report.differences), 0)
    
    def test_different_values_detected(self):
        """Different values are detected."""
        exported = {
            "plugin_config": {
                "auto_pi_enable": {"value": True, "type": "bool"},
            }
        }
        current = {
            "plugin_config": {
                "auto_pi_enable": {"value": False, "type": "bool"},
            }
        }
        
        report = compare_configurations(exported, current)
        
        self.assertEqual(report.status, ComparisonStatus.DIFFERENCES_FOUND)
        self.assertEqual(len(report.differences), 1)
        self.assertEqual(report.differences[0].setting_name, "auto_pi_enable")
        self.assertEqual(report.differences[0].difference_type, "changed")
    
    def test_missing_in_current_detected(self):
        """Settings missing in current are detected."""
        exported = {
            "plugin_config": {
                "new_setting": {"value": True, "type": "bool"},
            }
        }
        current = {
            "plugin_config": {}
        }
        
        report = compare_configurations(exported, current)
        
        self.assertEqual(len(report.differences), 1)
        self.assertEqual(report.differences[0].difference_type, "missing_in_current")
    
    def test_missing_in_export_detected(self):
        """Settings missing in export are detected."""
        exported = {
            "plugin_config": {}
        }
        current = {
            "plugin_config": {
                "extra_setting": {"value": True, "type": "bool"},
            }
        }
        
        report = compare_configurations(exported, current)
        
        self.assertEqual(len(report.differences), 1)
        self.assertEqual(report.differences[0].difference_type, "missing_in_export")
    
    def test_critical_differences_set_status(self):
        """Critical differences set status to CRITICAL_DIFFERENCES."""
        exported = {
            "django_config": {
                "INSTALLED_APPS": {"value": ["app1", "app2"], "type": "list"},
            }
        }
        current = {
            "django_config": {
                "INSTALLED_APPS": {"value": ["app1"], "type": "list"},
            }
        }
        
        report = compare_configurations(exported, current)
        
        self.assertEqual(report.status, ComparisonStatus.CRITICAL_DIFFERENCES)
        self.assertTrue(report.has_critical_differences())
    
    def test_list_comparison_order_independent(self):
        """Lists are compared regardless of order."""
        exported = {
            "django_config": {
                "INSTALLED_APPS": {"value": ["app1", "app2", "app3"], "type": "list"},
            }
        }
        current = {
            "django_config": {
                "INSTALLED_APPS": {"value": ["app3", "app1", "app2"], "type": "list"},
            }
        }
        
        report = compare_configurations(exported, current)
        
        # Same items, different order - should be identical
        self.assertEqual(report.status, ComparisonStatus.IDENTICAL)


class TestConfigurationComparisonReport(TestCase):
    """Tests for ConfigurationComparisonReport class."""
    
    def test_has_any_differences(self):
        """has_any_differences works correctly."""
        report = ConfigurationComparisonReport(
            status=ComparisonStatus.DIFFERENCES_FOUND,
            total_settings_compared=5,
            differences=[
                ConfigDifference(
                    setting_name="test",
                    category="plugin_config",
                    exported_value=True,
                    current_value=False,
                    difference_type="changed",
                    severity=DifferenceSeverity.WARNING,
                )
            ],
        )
        
        self.assertTrue(report.has_any_differences())
    
    def test_get_differences_by_severity(self):
        """Differences can be filtered by severity."""
        report = ConfigurationComparisonReport(
            status=ComparisonStatus.DIFFERENCES_FOUND,
            total_settings_compared=5,
            differences=[
                ConfigDifference(
                    setting_name="warning_setting",
                    category="plugin_config",
                    exported_value=True,
                    current_value=False,
                    difference_type="changed",
                    severity=DifferenceSeverity.WARNING,
                ),
                ConfigDifference(
                    setting_name="info_setting",
                    category="plugin_config",
                    exported_value="a",
                    current_value="b",
                    difference_type="changed",
                    severity=DifferenceSeverity.INFO,
                ),
            ],
        )
        
        warnings = report.get_differences_by_severity(DifferenceSeverity.WARNING)
        infos = report.get_differences_by_severity(DifferenceSeverity.INFO)
        
        self.assertEqual(len(warnings), 1)
        self.assertEqual(len(infos), 1)
        self.assertEqual(warnings[0].setting_name, "warning_setting")
        self.assertEqual(infos[0].setting_name, "info_setting")
    
    def test_to_dict(self):
        """Report can be converted to dict."""
        report = ConfigurationComparisonReport(
            status=ComparisonStatus.IDENTICAL,
            total_settings_compared=10,
            identical_count=10,
        )
        
        data = report.to_dict()
        
        self.assertEqual(data["status"], "identical")
        self.assertEqual(data["total_settings_compared"], 10)
        self.assertEqual(data["identical_count"], 10)
    
    def test_to_json(self):
        """Report can be serialized to JSON."""
        report = ConfigurationComparisonReport(
            status=ComparisonStatus.IDENTICAL,
            total_settings_compared=5,
        )
        
        json_str = report.to_json()
        data = json.loads(json_str)
        
        self.assertEqual(data["status"], "identical")


class TestFormatDiffReport(TestCase):
    """Tests for diff report formatting."""
    
    def test_identical_format(self):
        """Identical configs format appropriately."""
        report = ConfigurationComparisonReport(
            status=ComparisonStatus.IDENTICAL,
            total_settings_compared=10,
        )
        
        output = format_diff_report(report)
        
        self.assertIn("IDENTICAL", output)
        self.assertIn("10 settings", output)
    
    def test_differences_format(self):
        """Differences are formatted with severity labels."""
        report = ConfigurationComparisonReport(
            status=ComparisonStatus.DIFFERENCES_FOUND,
            total_settings_compared=5,
            differences=[
                ConfigDifference(
                    setting_name="test_setting",
                    category="plugin_config",
                    exported_value=True,
                    current_value=False,
                    difference_type="changed",
                    severity=DifferenceSeverity.WARNING,
                    impact="Test impact",
                ),
            ],
        )
        
        output = format_diff_report(report)
        
        self.assertIn("[WARNING]", output)
        self.assertIn("test_setting", output)
        self.assertIn("Exported: True", output)
        self.assertIn("Current:  False", output)
        self.assertIn("Test impact", output)


class TestLoadExportedConfig(TestCase):
    """Tests for loading exported configuration."""
    
    def test_load_from_export(self):
        """Config can be loaded from export directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Export config first
            export_configuration(tmpdir, dry_run=False)
            
            config_dir = Path(tmpdir) / "config"
            
            # Load it back
            config = load_exported_config(config_dir)
            
            self.assertIn("plugin_config", config)
            self.assertIn("coldfront_config", config)
            self.assertIn("django_config", config)


class TestCollectCurrentConfig(TestCase):
    """Tests for collecting current configuration."""
    
    def test_returns_all_categories(self):
        """Current config includes all categories."""
        config = collect_current_config()
        
        self.assertIn("plugin_config", config)
        self.assertIn("coldfront_config", config)
        self.assertIn("django_config", config)


class TestCheckConfigCompatibility(TestCase):
    """Tests for the convenience compatibility check function."""
    
    def test_returns_report(self):
        """check_config_compatibility returns a report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Export config first
            export_configuration(tmpdir, dry_run=False)
            
            config_dir = Path(tmpdir) / "config"
            
            # Check compatibility
            report = check_config_compatibility(config_dir)
            
            # Should be identical since we just exported
            self.assertIsInstance(report, ConfigurationComparisonReport)
            # Note: might not be IDENTICAL due to timing differences in exported_at

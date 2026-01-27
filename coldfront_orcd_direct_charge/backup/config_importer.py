# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Configuration import and comparison functionality.

This module provides functions to load exported configuration and compare
it against the current instance's configuration. It generates detailed
difference reports with severity levels to alert operators to potential
issues before importing data.

Comparison Features:
    - Compare plugin, ColdFront, and Django settings
    - Classify differences by severity (critical, warning, info)
    - Generate human-readable and JSON reports
    - Skip environment metadata (informational only)

Severity Levels:
    - critical: Could cause data loss or system instability
    - warning: Affects behavior but safe to differ
    - info: Informational, no action required
"""

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class DifferenceSeverity(Enum):
    """Severity levels for configuration differences."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class ComparisonStatus(Enum):
    """Overall status of configuration comparison."""
    IDENTICAL = "identical"
    DIFFERENCES_FOUND = "differences_found"
    CRITICAL_DIFFERENCES = "critical_differences"


@dataclass
class ConfigDifference:
    """A single configuration difference.
    
    Attributes:
        setting_name: Name of the setting
        category: Configuration category (plugin_config, etc.)
        exported_value: Value from the export
        current_value: Value on the current instance
        difference_type: Type of difference (changed, missing_in_current, etc.)
        severity: Severity level of this difference
        description: Human-readable description of the setting
        impact: Explanation of how this difference affects behavior
    """
    setting_name: str
    category: str
    exported_value: Any
    current_value: Any
    difference_type: str  # "changed", "missing_in_current", "missing_in_export"
    severity: DifferenceSeverity
    description: str = ""
    impact: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['severity'] = self.severity.value
        return result


@dataclass
class ConfigurationComparisonReport:
    """Detailed report of configuration comparison.
    
    Attributes:
        status: Overall comparison status
        total_settings_compared: Number of settings compared
        identical_count: Number of settings that match
        differences: List of ConfigDifference objects
        warnings: List of warning messages
        critical_issues: List of critical issue messages
        categories_compared: List of categories that were compared
    """
    status: ComparisonStatus
    total_settings_compared: int
    identical_count: int = 0
    differences: List[ConfigDifference] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    critical_issues: List[str] = field(default_factory=list)
    categories_compared: List[str] = field(default_factory=list)
    
    def has_critical_differences(self) -> bool:
        """Check if any critical differences exist."""
        return self.status == ComparisonStatus.CRITICAL_DIFFERENCES or bool(self.critical_issues)
    
    def has_any_differences(self) -> bool:
        """Check if any differences exist."""
        return bool(self.differences)
    
    def get_differences_by_severity(self, severity: DifferenceSeverity) -> List[ConfigDifference]:
        """Get differences filtered by severity level."""
        return [d for d in self.differences if d.severity == severity]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'status': self.status.value,
            'total_settings_compared': self.total_settings_compared,
            'identical_count': self.identical_count,
            'difference_count': len(self.differences),
            'differences': [d.to_dict() for d in self.differences],
            'warnings': self.warnings,
            'critical_issues': self.critical_issues,
            'categories_compared': self.categories_compared,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)
    
    def save(self, path: str) -> str:
        """Save report to JSON file.
        
        Args:
            path: Output file path
            
        Returns:
            Path to saved file
        """
        with open(path, "w") as f:
            f.write(self.to_json())
        return path


# Severity classification for settings
# Settings not listed here default to INFO
SETTING_SEVERITY = {
    # Critical - could cause data loss or system instability
    'INSTALLED_APPS': DifferenceSeverity.CRITICAL,
    'DATABASE_ENGINE': DifferenceSeverity.CRITICAL,
    'AUTHENTICATION_BACKENDS': DifferenceSeverity.CRITICAL,
    
    # Warning - affects behavior but safe to differ
    'auto_pi_enable': DifferenceSeverity.WARNING,
    'auto_default_project_enable': DifferenceSeverity.WARNING,
    'center_summary_enable': DifferenceSeverity.WARNING,
    'home_page_allocations_enable': DifferenceSeverity.WARNING,
    'password_login_enable': DifferenceSeverity.WARNING,
    'CENTER_NAME': DifferenceSeverity.WARNING,
    'CENTER_BASE_URL': DifferenceSeverity.WARNING,
    'PROJECT_ENABLE_PROJECT_REVIEW': DifferenceSeverity.WARNING,
    'ALLOCATION_ENABLE_ALLOCATION_RENEWAL': DifferenceSeverity.WARNING,
    'ALLOCATION_DEFAULT_ALLOCATION_LENGTH': DifferenceSeverity.WARNING,
    'EMAIL_ENABLED': DifferenceSeverity.WARNING,
    'EMAIL_SENDER': DifferenceSeverity.WARNING,
    
    # Info - informational only
    'DEBUG': DifferenceSeverity.INFO,
    'TIME_ZONE': DifferenceSeverity.INFO,
    'LANGUAGE_CODE': DifferenceSeverity.INFO,
    'USE_TZ': DifferenceSeverity.INFO,
    'EMAIL_SIGNATURE': DifferenceSeverity.INFO,
    'EMAIL_SUBJECT_PREFIX': DifferenceSeverity.INFO,
}

# Impact messages for common settings
SETTING_IMPACTS = {
    'auto_pi_enable': "Users may or may not be auto-assigned PI status",
    'auto_default_project_enable': "Users may or may not get auto-created projects",
    'center_summary_enable': "Center Summary navbar visibility may differ",
    'home_page_allocations_enable': "Home page allocation display may differ",
    'password_login_enable': "Password login availability may differ",
    'CENTER_NAME': "Portal branding/name will differ",
    'INSTALLED_APPS': "Missing apps may cause import failures or missing features",
    'DATABASE_ENGINE': "Database compatibility may be affected",
    'AUTHENTICATION_BACKENDS': "User authentication methods may differ",
}


def get_setting_severity(setting_name: str) -> DifferenceSeverity:
    """Get severity level for a setting.
    
    Args:
        setting_name: Name of the setting
        
    Returns:
        Severity level (defaults to INFO if not defined)
    """
    return SETTING_SEVERITY.get(setting_name, DifferenceSeverity.INFO)


def get_setting_impact(setting_name: str) -> str:
    """Get impact description for a setting.
    
    Args:
        setting_name: Name of the setting
        
    Returns:
        Impact description or empty string
    """
    return SETTING_IMPACTS.get(setting_name, "")


def load_exported_config(config_dir: Path) -> Dict[str, Dict]:
    """Load configuration from export directory.
    
    Args:
        config_dir: Path to config/ directory in export
        
    Returns:
        Dict mapping category to settings dict
    """
    config = {}
    
    config_files = [
        'plugin_config.json',
        'coldfront_config.json',
        'django_config.json',
    ]
    
    for filename in config_files:
        filepath = config_dir / filename
        if filepath.exists():
            with open(filepath, "r") as f:
                data = json.load(f)
            category = data.get('category', filename.replace('.json', ''))
            config[category] = data.get('settings', {})
    
    return config


def collect_current_config() -> Dict[str, Dict]:
    """Collect current instance configuration.
    
    Uses the same collection logic as the exporter to ensure
    consistent comparison.
    
    Returns:
        Dict mapping category to settings dict
    """
    from .config_exporter import (
        collect_plugin_config,
        collect_coldfront_config,
        collect_django_config,
    )
    
    return {
        'plugin_config': {k: v.to_dict() for k, v in collect_plugin_config().items()},
        'coldfront_config': {k: v.to_dict() for k, v in collect_coldfront_config().items()},
        'django_config': {k: v.to_dict() for k, v in collect_django_config().items()},
    }


def _compare_values(exported_value: Any, current_value: Any) -> bool:
    """Compare two configuration values.
    
    Handles special cases like list comparison (order-independent).
    
    Args:
        exported_value: Value from export
        current_value: Current value
        
    Returns:
        True if values are equivalent
    """
    # Handle None comparisons
    if exported_value is None and current_value is None:
        return True
    if exported_value is None or current_value is None:
        return False
    
    # Handle list comparisons (order-independent for apps, backends, etc.)
    if isinstance(exported_value, list) and isinstance(current_value, list):
        return set(exported_value) == set(current_value)
    
    # Standard comparison
    return exported_value == current_value


def compare_configurations(
    exported: Dict[str, Dict],
    current: Dict[str, Dict],
) -> ConfigurationComparisonReport:
    """Compare exported configuration against current instance.
    
    Args:
        exported: Exported configuration from load_exported_config()
        current: Current configuration from collect_current_config()
        
    Returns:
        ConfigurationComparisonReport with detailed results
    """
    differences = []
    warnings = []
    critical_issues = []
    total_compared = 0
    identical_count = 0
    categories_compared = []
    
    # Compare each category
    for category in set(exported.keys()) | set(current.keys()):
        if category not in exported:
            warnings.append(f"Category '{category}' exists in current but not in export")
            continue
        if category not in current:
            warnings.append(f"Category '{category}' exists in export but not in current")
            continue
        
        categories_compared.append(category)
        exported_settings = exported[category]
        current_settings = current[category]
        
        # Check all settings in both
        all_settings = set(exported_settings.keys()) | set(current_settings.keys())
        
        for setting_name in all_settings:
            total_compared += 1
            
            exported_data = exported_settings.get(setting_name, {})
            current_data = current_settings.get(setting_name, {})
            
            exported_value = exported_data.get('value') if exported_data else None
            current_value = current_data.get('value') if current_data else None
            description = (
                exported_data.get('description', '') or 
                current_data.get('description', '')
            )
            
            # Determine difference type
            if setting_name not in exported_settings:
                difference_type = "missing_in_export"
            elif setting_name not in current_settings:
                difference_type = "missing_in_current"
            elif _compare_values(exported_value, current_value):
                identical_count += 1
                continue  # No difference
            else:
                difference_type = "changed"
            
            # Create difference record
            severity = get_setting_severity(setting_name)
            impact = get_setting_impact(setting_name)
            
            diff = ConfigDifference(
                setting_name=setting_name,
                category=category,
                exported_value=exported_value,
                current_value=current_value,
                difference_type=difference_type,
                severity=severity,
                description=description,
                impact=impact,
            )
            differences.append(diff)
            
            # Track critical issues
            if severity == DifferenceSeverity.CRITICAL:
                critical_issues.append(
                    f"{setting_name}: {difference_type} - "
                    f"exported={exported_value}, current={current_value}"
                )
    
    # Determine overall status
    if not differences:
        status = ComparisonStatus.IDENTICAL
    elif critical_issues:
        status = ComparisonStatus.CRITICAL_DIFFERENCES
    else:
        status = ComparisonStatus.DIFFERENCES_FOUND
    
    return ConfigurationComparisonReport(
        status=status,
        total_settings_compared=total_compared,
        identical_count=identical_count,
        differences=differences,
        warnings=warnings,
        critical_issues=critical_issues,
        categories_compared=categories_compared,
    )


def format_diff_report(report: ConfigurationComparisonReport) -> str:
    """Format comparison report for console output.
    
    Args:
        report: ConfigurationComparisonReport to format
        
    Returns:
        Human-readable multi-line string
    """
    lines = []
    
    if report.status == ComparisonStatus.IDENTICAL:
        lines.append("Configuration: IDENTICAL")
        lines.append(f"  {report.total_settings_compared} settings compared, all match")
        return "\n".join(lines)
    
    # Header
    diff_count = len(report.differences)
    lines.append(f"DIFFERENCES FOUND ({diff_count} settings differ):")
    lines.append("")
    
    # Group by severity
    for severity in [DifferenceSeverity.CRITICAL, DifferenceSeverity.WARNING, DifferenceSeverity.INFO]:
        severity_diffs = report.get_differences_by_severity(severity)
        if not severity_diffs:
            continue
        
        for diff in severity_diffs:
            severity_label = f"[{severity.value.upper()}]"
            lines.append(f"{severity_label} {diff.setting_name}")
            lines.append(f"  Exported: {_format_value(diff.exported_value)}")
            lines.append(f"  Current:  {_format_value(diff.current_value)}")
            if diff.impact:
                lines.append(f"  Impact: {diff.impact}")
            lines.append("")
    
    # Critical issues summary
    if report.critical_issues:
        lines.append("CRITICAL ISSUES:")
        for issue in report.critical_issues:
            lines.append(f"  - {issue}")
    else:
        lines.append("CRITICAL ISSUES: None")
    
    return "\n".join(lines)


def _format_value(value: Any) -> str:
    """Format a value for display.
    
    Args:
        value: Value to format
        
    Returns:
        Formatted string representation
    """
    if value is None:
        return "(not set)"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, list):
        if len(value) > 3:
            return f"[{len(value)} items]"
        return str(value)
    return str(value)


def check_config_compatibility(config_dir: Path) -> ConfigurationComparisonReport:
    """Check configuration compatibility with current instance.
    
    Convenience function that loads exported config and compares
    against current instance.
    
    Args:
        config_dir: Path to config/ directory in export
        
    Returns:
        ConfigurationComparisonReport
    """
    exported = load_exported_config(config_dir)
    current = collect_current_config()
    return compare_configurations(exported, current)

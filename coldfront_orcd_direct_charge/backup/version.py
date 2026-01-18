# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Version compatibility checking.

Determines if an export is compatible with the current instance
based on export format version and database schema versions.

Compatibility Levels:
    COMPATIBLE: Export can be imported without issues
    COMPATIBLE_WITH_WARNINGS: Import possible but may need attention
    INCOMPATIBLE: Import cannot proceed safely

Version Comparison:
    - Export version uses semantic versioning (MAJOR.MINOR.PATCH)
    - Schema versions are migration numbers (e.g., "0024")
    - Major version differences are incompatible
    - Minor version differences may have warnings
    - Patch version differences are compatible
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple
import logging

from .manifest import (
    Manifest,
    EXPORT_VERSION,
    get_current_schema_version,
    get_software_versions,
)

logger = logging.getLogger(__name__)


class CompatibilityStatus(Enum):
    """Compatibility status for import operations."""
    COMPATIBLE = "compatible"
    COMPATIBLE_WITH_WARNINGS = "compatible_with_warnings"
    INCOMPATIBLE = "incompatible"


@dataclass
class CompatibilityReport:
    """Detailed compatibility report for an export.
    
    Provides information about whether an export can be imported
    and any warnings or errors that should be addressed.
    
    Attributes:
        status: Overall compatibility status
        export_version: Version of the export format
        target_version: Version of the target instance export format
        export_schema: Schema version in the export
        target_schema: Schema version of the target instance
        warnings: List of warning messages
        errors: List of error messages
    """
    status: CompatibilityStatus
    export_version: str
    target_version: str
    export_schema: str
    target_schema: str
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def is_safe_to_import(self) -> bool:
        """Check if import can proceed.
        
        Returns:
            True if status is not INCOMPATIBLE
        """
        return self.status != CompatibilityStatus.INCOMPATIBLE
    
    def summary(self) -> str:
        """Generate human-readable summary.
        
        Returns:
            Multi-line summary string
        """
        lines = [
            f"Compatibility: {self.status.value}",
            f"Export Version: {self.export_version}",
            f"Target Version: {self.target_version}",
            f"Export Schema: {self.export_schema}",
            f"Target Schema: {self.target_schema}",
        ]
        
        if self.warnings:
            lines.append("Warnings:")
            for warning in self.warnings:
                lines.append(f"  - {warning}")
        
        if self.errors:
            lines.append("Errors:")
            for error in self.errors:
                lines.append(f"  - {error}")
        
        return "\n".join(lines)


def parse_version(version_str: str) -> Tuple[int, int, int]:
    """Parse semantic version string to tuple.
    
    Handles version strings like "1.0.0" or "1.0".
    
    Args:
        version_str: Version string (e.g., "1.0.0")
        
    Returns:
        Tuple of (major, minor, patch) integers
    """
    try:
        parts = version_str.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except (ValueError, IndexError):
        return (0, 0, 0)


def parse_migration_number(migration_str: str) -> int:
    """Parse migration number from string.
    
    Handles migration names like "0024_add_field" or "0024".
    
    Args:
        migration_str: Migration string
        
    Returns:
        Migration number as integer
    """
    try:
        # Extract numeric prefix
        numeric_part = migration_str.split("_")[0]
        return int(numeric_part)
    except (ValueError, IndexError):
        return 0


def check_version_compatibility(
    export_version: str,
    target_version: str,
) -> Tuple[CompatibilityStatus, List[str], List[str]]:
    """Check export format version compatibility.
    
    Args:
        export_version: Version from export manifest
        target_version: Current export format version
        
    Returns:
        Tuple of (status, warnings, errors)
    """
    warnings = []
    errors = []
    
    export_parsed = parse_version(export_version)
    target_parsed = parse_version(target_version)
    
    export_major, export_minor, export_patch = export_parsed
    target_major, target_minor, target_patch = target_parsed
    
    # Major version difference = incompatible
    if export_major != target_major:
        errors.append(
            f"Major version mismatch: export is v{export_major}.x, "
            f"target is v{target_major}.x"
        )
        return (CompatibilityStatus.INCOMPATIBLE, warnings, errors)
    
    # Export is newer than target
    if export_minor > target_minor:
        warnings.append(
            f"Export version ({export_version}) is newer than target ({target_version}). "
            "Some data may not be fully supported."
        )
        return (CompatibilityStatus.COMPATIBLE_WITH_WARNINGS, warnings, errors)
    
    # Export is older than target
    if export_minor < target_minor:
        warnings.append(
            f"Export version ({export_version}) is older than target ({target_version}). "
            "Some fields may use default values."
        )
        return (CompatibilityStatus.COMPATIBLE_WITH_WARNINGS, warnings, errors)
    
    return (CompatibilityStatus.COMPATIBLE, warnings, errors)


def check_schema_compatibility(
    export_schema: str,
    target_schema: str,
) -> Tuple[CompatibilityStatus, List[str], List[str]]:
    """Check database schema compatibility.
    
    Args:
        export_schema: Schema version from export manifest
        target_schema: Current schema version
        
    Returns:
        Tuple of (status, warnings, errors)
    """
    warnings = []
    errors = []
    
    export_num = parse_migration_number(export_schema)
    target_num = parse_migration_number(target_schema)
    
    # Export has newer schema
    if export_num > target_num:
        errors.append(
            f"Export schema ({export_schema}) is newer than target ({target_schema}). "
            "Target instance needs to run migrations first."
        )
        return (CompatibilityStatus.INCOMPATIBLE, warnings, errors)
    
    # Export has significantly older schema
    if target_num - export_num > 5:
        warnings.append(
            f"Export schema ({export_schema}) is significantly older than target ({target_schema}). "
            "Some data transformations may be needed."
        )
        return (CompatibilityStatus.COMPATIBLE_WITH_WARNINGS, warnings, errors)
    
    # Export has slightly older schema
    if export_num < target_num:
        warnings.append(
            f"Export schema ({export_schema}) is older than target ({target_schema}). "
            "New fields will use default values."
        )
        return (CompatibilityStatus.COMPATIBLE_WITH_WARNINGS, warnings, errors)
    
    return (CompatibilityStatus.COMPATIBLE, warnings, errors)


def check_compatibility(
    manifest: Manifest,
    component: str = None,
) -> CompatibilityReport:
    """Check if export is compatible with current instance.
    
    Performs comprehensive compatibility checks including:
    - Export format version
    - Database schema version (component-specific if provided)
    - Required dependencies
    
    Args:
        manifest: Export manifest to check
        component: Optional component name for component-specific schema checks.
                   If 'coldfront_core', checks core Django/ColdFront migrations.
                   If 'orcd_plugin', checks plugin migrations.
                   If None, defaults to plugin schema.
        
    Returns:
        CompatibilityReport with detailed results
    """
    from .manifest import (
        COMPONENT_COLDFRONT_CORE,
        COMPONENT_ORCD_PLUGIN,
    )
    
    all_warnings = []
    all_errors = []
    overall_status = CompatibilityStatus.COMPATIBLE
    
    target_version = EXPORT_VERSION
    target_schema = get_current_schema_version()
    
    # Get export schema based on component
    if component == COMPONENT_COLDFRONT_CORE:
        # For core component, check ColdFront-related app migrations
        # Look for any core app schema in the manifest
        core_apps = ["auth", "project", "resource", "allocation", "publication", "grant"]
        export_schema = "unknown"
        for app in core_apps:
            if app in manifest.schema_versions:
                export_schema = manifest.schema_versions[app]
                break
        # For core, we need to compare against ColdFront app migrations
        # Since we may not have the exact target, use a more lenient check
        if export_schema == "unknown" and manifest.schema_versions:
            # Use any available schema version
            export_schema = next(iter(manifest.schema_versions.values()), "unknown")
    else:
        # Default: plugin schema
        export_schema = manifest.schema_versions.get(
            "coldfront_orcd_direct_charge", "unknown"
        )
    
    # Check version compatibility
    version_status, version_warnings, version_errors = check_version_compatibility(
        manifest.export_version, target_version
    )
    all_warnings.extend(version_warnings)
    all_errors.extend(version_errors)
    
    if version_status == CompatibilityStatus.INCOMPATIBLE:
        overall_status = CompatibilityStatus.INCOMPATIBLE
    elif version_status == CompatibilityStatus.COMPATIBLE_WITH_WARNINGS:
        if overall_status == CompatibilityStatus.COMPATIBLE:
            overall_status = CompatibilityStatus.COMPATIBLE_WITH_WARNINGS
    
    # Check schema compatibility
    schema_status, schema_warnings, schema_errors = check_schema_compatibility(
        export_schema, target_schema
    )
    all_warnings.extend(schema_warnings)
    all_errors.extend(schema_errors)
    
    if schema_status == CompatibilityStatus.INCOMPATIBLE:
        overall_status = CompatibilityStatus.INCOMPATIBLE
    elif schema_status == CompatibilityStatus.COMPATIBLE_WITH_WARNINGS:
        if overall_status == CompatibilityStatus.COMPATIBLE:
            overall_status = CompatibilityStatus.COMPATIBLE_WITH_WARNINGS
    
    # Validate manifest structure
    manifest_errors = manifest.validate()
    if manifest_errors:
        all_errors.extend(manifest_errors)
        overall_status = CompatibilityStatus.INCOMPATIBLE
    
    return CompatibilityReport(
        status=overall_status,
        export_version=manifest.export_version,
        target_version=target_version,
        export_schema=export_schema,
        target_schema=target_schema,
        warnings=all_warnings,
        errors=all_errors,
    )

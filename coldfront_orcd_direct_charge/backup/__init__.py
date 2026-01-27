# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Portal data backup and restore system.

This module provides a comprehensive system for exporting and importing
portal data. It supports versioned exports with compatibility checking,
allowing data migration between portal instances.

Components:
    - coldfront_core: ColdFront core models (User, Project, Allocation, etc.)
    - orcd_plugin: ORCD plugin models (NodeType, Reservation, etc.)
    - config: Configuration settings (plugin, ColdFront, Django)

Key classes:
    - BaseExporter, BaseImporter: Abstract base classes for model serialization
    - CoreExporterRegistry, PluginExporterRegistry: Component-specific registries
    - RootManifest, Manifest: Export metadata with version and checksum info
    - Version compatibility checking for safe imports
    - Configuration export/import with diff detection

Usage:
    # Export
    from coldfront_orcd_direct_charge.backup import (
        CoreExporterRegistry,
        PluginExporterRegistry,
        generate_root_manifest,
        export_configuration,
    )
    
    # Import  
    from coldfront_orcd_direct_charge.backup import (
        CoreImporterRegistry,
        PluginImporterRegistry,
        check_compatibility,
        check_config_compatibility,
    )

Example management commands:
    coldfront export_portal_data --output /path/to/backup/
    coldfront export_portal_data --output /path/ --component coldfront_core
    coldfront export_portal_data --output /path/ --no-config
    coldfront import_portal_data /path/to/backup/ --dry-run
    coldfront import_portal_data /path/to/backup/ --ignore-config-diff
    coldfront check_import_compatibility /path/to/backup/
"""

from .base import (
    BaseExporter,
    BaseImporter,
    ExportResult,
    ImportResult,
)
from .registry import (
    # New component-aware registries
    CoreExporterRegistry,
    PluginExporterRegistry,
    CoreImporterRegistry,
    PluginImporterRegistry,
    # Backward compatibility aliases
    ExporterRegistry,
    ImporterRegistry,
    # Component constants
    COMPONENT_COLDFRONT_CORE,
    COMPONENT_ORCD_PLUGIN,
)
from .manifest import (
    # New multi-component manifests
    RootManifest,
    Manifest,
    SoftwareVersions,
    ComponentInfo,
    generate_root_manifest,
    generate_component_manifest,
    # Backward compatibility
    generate_manifest,
    get_current_schema_version,
    EXPORT_FORMAT,
    EXPORT_VERSION,
    MANIFEST_FILENAME,
    COMPONENT_CONFIG,
)
from .version import (
    CompatibilityStatus,
    CompatibilityReport,
    check_compatibility,
)
from .config_exporter import (
    export_configuration,
    ConfigExportResult,
    ConfigSetting,
    collect_plugin_config,
    collect_coldfront_config,
    collect_django_config,
    collect_environment_metadata,
)
from .config_importer import (
    check_config_compatibility,
    compare_configurations,
    format_diff_report,
    load_exported_config,
    collect_current_config,
    ConfigurationComparisonReport,
    ConfigDifference,
    ComparisonStatus,
    DifferenceSeverity,
)
from .config_manifest import (
    ConfigManifest,
    generate_config_manifest,
    verify_config_checksum,
)

__all__ = [
    # Base classes
    "BaseExporter",
    "BaseImporter",
    "ExportResult",
    "ImportResult",
    # Component registries
    "CoreExporterRegistry",
    "PluginExporterRegistry",
    "CoreImporterRegistry",
    "PluginImporterRegistry",
    # Backward compatibility
    "ExporterRegistry",
    "ImporterRegistry",
    # Component constants
    "COMPONENT_COLDFRONT_CORE",
    "COMPONENT_ORCD_PLUGIN",
    "COMPONENT_CONFIG",
    # Manifest classes
    "RootManifest",
    "Manifest",
    "SoftwareVersions",
    "ComponentInfo",
    "generate_root_manifest",
    "generate_component_manifest",
    "generate_manifest",
    "get_current_schema_version",
    "EXPORT_FORMAT",
    "EXPORT_VERSION",
    "MANIFEST_FILENAME",
    # Compatibility
    "CompatibilityStatus",
    "CompatibilityReport",
    "check_compatibility",
    # Configuration export
    "export_configuration",
    "ConfigExportResult",
    "ConfigSetting",
    "collect_plugin_config",
    "collect_coldfront_config",
    "collect_django_config",
    "collect_environment_metadata",
    # Configuration import/comparison
    "check_config_compatibility",
    "compare_configurations",
    "format_diff_report",
    "load_exported_config",
    "collect_current_config",
    "ConfigurationComparisonReport",
    "ConfigDifference",
    "ComparisonStatus",
    "DifferenceSeverity",
    # Configuration manifest
    "ConfigManifest",
    "generate_config_manifest",
    "verify_config_checksum",
]

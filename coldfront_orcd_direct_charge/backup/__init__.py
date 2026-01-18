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

Key classes:
    - BaseExporter, BaseImporter: Abstract base classes for model serialization
    - CoreExporterRegistry, PluginExporterRegistry: Component-specific registries
    - RootManifest, Manifest: Export metadata with version and checksum info
    - Version compatibility checking for safe imports

Usage:
    # Export
    from coldfront_orcd_direct_charge.backup import (
        CoreExporterRegistry,
        PluginExporterRegistry,
        generate_root_manifest,
    )
    
    # Import  
    from coldfront_orcd_direct_charge.backup import (
        CoreImporterRegistry,
        PluginImporterRegistry,
        check_compatibility,
    )

Example management commands:
    coldfront export_portal_data --output /path/to/backup/
    coldfront export_portal_data --output /path/ --component coldfront_core
    coldfront import_portal_data /path/to/backup/ --dry-run
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
)
from .version import (
    CompatibilityStatus,
    CompatibilityReport,
    check_compatibility,
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
]

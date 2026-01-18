# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Portal data backup and restore system.

This module provides a comprehensive system for exporting and importing
portal data. It supports versioned exports with compatibility checking,
allowing data migration between portal instances.

Key components:
    - BaseExporter, BaseImporter: Abstract base classes for model serialization
    - ExporterRegistry, ImporterRegistry: Registration and dependency ordering
    - Manifest: Export metadata with version and checksum information
    - Version compatibility checking for safe imports

Usage:
    # Export
    from coldfront_orcd_direct_charge.backup import ExporterRegistry, generate_manifest
    
    # Import  
    from coldfront_orcd_direct_charge.backup import ImporterRegistry, check_compatibility

Example management commands:
    coldfront export_portal_data --output /path/to/backup/
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
    ExporterRegistry,
    ImporterRegistry,
)
from .manifest import (
    Manifest,
    SoftwareVersions,
    generate_manifest,
    get_current_schema_version,
    EXPORT_FORMAT,
    EXPORT_VERSION,
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
    # Registry
    "ExporterRegistry",
    "ImporterRegistry",
    # Manifest
    "Manifest",
    "SoftwareVersions",
    "generate_manifest",
    "get_current_schema_version",
    "EXPORT_FORMAT",
    "EXPORT_VERSION",
    # Compatibility
    "CompatibilityStatus",
    "CompatibilityReport",
    "check_compatibility",
]

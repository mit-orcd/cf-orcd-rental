# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Manifest generation and validation.

The manifest contains metadata about an export including versions,
timestamps, data counts, and checksums for integrity verification.

Export Structure (v2.0.0):
    export_YYYYMMDD_HHMMSS/
    ├── manifest.json           # Root manifest
    ├── coldfront_core/
    │   └── manifest.json       # Core component manifest
    └── orcd_plugin/
        └── manifest.json       # Plugin component manifest

Root Manifest Structure:
    {
        "export_version": "2.0.0",
        "export_format": "orcd-portal-export",
        "created_at": "2026-01-17T12:00:00-05:00",
        "components": {
            "coldfront_core": {...},
            "orcd_plugin": {...}
        },
        "total_records": 1250,
        "checksum": {...}
    }

Component Manifest Structure:
    {
        "export_version": "2.0.0",
        "component": "coldfront_core",
        "created_at": "...",
        "software_versions": {...},
        "schema_versions": {...},
        "data_counts": {...},
        "checksum": {...}
    }
"""

import hashlib
import json
import platform
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Export format constants
EXPORT_FORMAT = "orcd-portal-export"
EXPORT_VERSION = "2.0.0"

# Component names
COMPONENT_COLDFRONT_CORE = "coldfront_core"
COMPONENT_ORCD_PLUGIN = "orcd_plugin"

# Manifest filename
MANIFEST_FILENAME = "manifest.json"


@dataclass
class SoftwareVersions:
    """Software version information for an export.
    
    Attributes:
        coldfront: ColdFront core version
        coldfront_orcd_direct_charge: Plugin version
        django: Django version
        python: Python version
    """
    coldfront: str
    coldfront_orcd_direct_charge: str
    django: str
    python: str


@dataclass
class ComponentInfo:
    """Information about a component in the root manifest.
    
    Attributes:
        path: Relative path to component directory
        manifest: Relative path to component manifest
        data_counts: Dict mapping model name to record count
    """
    path: str
    manifest: str
    data_counts: Dict[str, int]


@dataclass
class RootManifest:
    """Root manifest that references component manifests.
    
    The root manifest provides an overview of the entire export,
    with references to individual component manifests.
    """
    export_version: str
    export_format: str
    created_at: str
    source_portal: Dict[str, str]
    software_versions: SoftwareVersions
    components: Dict[str, Dict]
    total_records: int
    checksum: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)
    
    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    def save(self, output_dir: str) -> str:
        """Save manifest to file."""
        output_path = Path(output_dir) / MANIFEST_FILENAME
        with open(output_path, "w") as f:
            f.write(self.to_json())
        return str(output_path)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "RootManifest":
        """Create from dictionary."""
        sw_versions = data.get("software_versions", {})
        if isinstance(sw_versions, dict) and sw_versions:
            sw_versions = SoftwareVersions(**sw_versions)
        elif not sw_versions:
            sw_versions = SoftwareVersions("", "", "", "")
        
        return cls(
            export_version=data.get("export_version", ""),
            export_format=data.get("export_format", ""),
            created_at=data.get("created_at", ""),
            source_portal=data.get("source_portal", {}),
            software_versions=sw_versions,
            components=data.get("components", {}),
            total_records=data.get("total_records", 0),
            checksum=data.get("checksum"),
        )
    
    @classmethod
    def from_file(cls, path: str) -> "RootManifest":
        """Load from file."""
        manifest_path = Path(path)
        if manifest_path.is_dir():
            manifest_path = manifest_path / MANIFEST_FILENAME
        
        with open(manifest_path, "r") as f:
            data = json.load(f)
        
        return cls.from_dict(data)
    
    def get_component_names(self) -> List[str]:
        """Get list of component names in this export."""
        return list(self.components.keys())
    
    def has_component(self, component: str) -> bool:
        """Check if a component exists in this export."""
        return component in self.components


@dataclass
class Manifest:
    """Component manifest with version and integrity information.
    
    Each component (coldfront_core, orcd_plugin) has its own manifest
    with component-specific metadata.
    """
    export_version: str
    export_format: str
    created_at: str
    component: str
    source_portal: Dict[str, str]
    software_versions: SoftwareVersions
    schema_versions: Dict[str, str]
    data_counts: Dict[str, int]
    checksum: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict:
        """Convert manifest to dictionary."""
        return asdict(self)
    
    def to_json(self, indent: int = 2) -> str:
        """Serialize manifest to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    def save(self, output_dir: str) -> str:
        """Save manifest to file."""
        output_path = Path(output_dir) / MANIFEST_FILENAME
        with open(output_path, "w") as f:
            f.write(self.to_json())
        return str(output_path)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Manifest":
        """Create manifest from dictionary."""
        sw_versions = data.get("software_versions", {})
        if isinstance(sw_versions, dict) and sw_versions:
            sw_versions = SoftwareVersions(**sw_versions)
        elif not sw_versions:
            sw_versions = SoftwareVersions("", "", "", "")
        
        return cls(
            export_version=data.get("export_version", ""),
            export_format=data.get("export_format", ""),
            created_at=data.get("created_at", ""),
            component=data.get("component", ""),
            source_portal=data.get("source_portal", {}),
            software_versions=sw_versions,
            schema_versions=data.get("schema_versions", {}),
            data_counts=data.get("data_counts", {}),
            checksum=data.get("checksum"),
        )
    
    @classmethod
    def from_file(cls, path: str) -> "Manifest":
        """Load manifest from file."""
        manifest_path = Path(path)
        if manifest_path.is_dir():
            manifest_path = manifest_path / MANIFEST_FILENAME
        
        with open(manifest_path, "r") as f:
            data = json.load(f)
        
        return cls.from_dict(data)
    
    def validate(self) -> List[str]:
        """Validate manifest structure and required fields."""
        errors = []
        
        if not self.export_version:
            errors.append("Missing export_version")
        if not self.export_format:
            errors.append("Missing export_format")
        if self.export_format != EXPORT_FORMAT:
            errors.append(f"Invalid export_format: {self.export_format}")
        if not self.created_at:
            errors.append("Missing created_at timestamp")
        if not self.software_versions:
            errors.append("Missing software_versions")
        if not self.schema_versions:
            errors.append("Missing schema_versions")
        
        return errors


def get_software_versions() -> SoftwareVersions:
    """Get current software versions."""
    import django
    
    try:
        from coldfront import __version__ as coldfront_version
    except ImportError:
        coldfront_version = "unknown"
    
    try:
        from coldfront_orcd_direct_charge import __version__ as plugin_version
    except (ImportError, AttributeError):
        plugin_version = "unknown"
    
    return SoftwareVersions(
        coldfront=coldfront_version,
        coldfront_orcd_direct_charge=plugin_version,
        django=django.__version__,
        python=platform.python_version(),
    )


def get_current_schema_version(app_name: str = "coldfront_orcd_direct_charge") -> str:
    """Get current migration number for an app.
    
    Args:
        app_name: Django app name to get schema version for
        
    Returns:
        Migration number as string (e.g., "0024")
    """
    try:
        from django.db.migrations.recorder import MigrationRecorder
        from django.db import connection
        
        recorder = MigrationRecorder(connection)
        applied = recorder.applied_migrations()
        
        app_migrations = [
            name for (app, name) in applied 
            if app == app_name
        ]
        
        if app_migrations:
            return max(app_migrations)
        
        return "0000"
    except Exception as e:
        logger.warning(f"Could not determine schema version for {app_name}: {e}")
        return "unknown"


def calculate_checksum(export_dir: str, algorithm: str = "sha256") -> Dict[str, str]:
    """Calculate checksum of all export files in a directory.
    
    Args:
        export_dir: Directory containing export files
        algorithm: Hash algorithm to use
        
    Returns:
        Dict with algorithm and checksum value
    """
    hasher = hashlib.new(algorithm)
    export_path = Path(export_dir)
    
    # Hash all JSON files except manifest, recursively
    for json_file in sorted(export_path.rglob("*.json")):
        if json_file.name != MANIFEST_FILENAME:
            with open(json_file, "rb") as f:
                hasher.update(f.read())
    
    return {
        "algorithm": algorithm,
        "value": hasher.hexdigest(),
    }


def calculate_component_checksum(component_dir: str, algorithm: str = "sha256") -> Dict[str, str]:
    """Calculate checksum for a component directory."""
    hasher = hashlib.new(algorithm)
    component_path = Path(component_dir)
    
    for json_file in sorted(component_path.rglob("*.json")):
        if json_file.name != MANIFEST_FILENAME:
            with open(json_file, "rb") as f:
                hasher.update(f.read())
    
    return {
        "algorithm": algorithm,
        "value": hasher.hexdigest(),
    }


def verify_checksum(manifest: Manifest, export_dir: str) -> bool:
    """Verify checksum of export files against manifest."""
    if not manifest.checksum:
        logger.warning("Manifest does not contain checksum")
        return True
    
    algorithm = manifest.checksum.get("algorithm", "sha256")
    expected = manifest.checksum.get("value", "")
    
    actual = calculate_component_checksum(export_dir, algorithm)
    
    return actual["value"] == expected


def generate_component_manifest(
    component_dir: str,
    component: str,
    data_counts: Dict[str, int],
    source_url: str = "",
    source_name: str = "ORCD Rental Portal",
) -> Manifest:
    """Generate manifest for a component.
    
    Args:
        component_dir: Directory containing component export files
        component: Component name (coldfront_core or orcd_plugin)
        data_counts: Dict mapping model name to record count
        source_url: URL of the source portal
        source_name: Name of the source portal
        
    Returns:
        Generated Manifest instance
    """
    from django.utils import timezone
    created_at = timezone.now().isoformat()
    
    checksum = calculate_component_checksum(component_dir)
    
    # Determine schema versions based on component
    if component == COMPONENT_COLDFRONT_CORE:
        schema_versions = {
            "auth": get_current_schema_version("auth"),
            "project": get_current_schema_version("project"),
            "resource": get_current_schema_version("resource"),
            "allocation": get_current_schema_version("allocation"),
        }
    else:
        schema_versions = {
            "coldfront_orcd_direct_charge": get_current_schema_version(),
        }
    
    manifest = Manifest(
        export_version=EXPORT_VERSION,
        export_format=EXPORT_FORMAT,
        created_at=created_at,
        component=component,
        source_portal={
            "url": source_url,
            "name": source_name,
        },
        software_versions=get_software_versions(),
        schema_versions=schema_versions,
        data_counts=data_counts,
        checksum=checksum,
    )
    
    return manifest


def generate_root_manifest(
    export_dir: str,
    component_data: Dict[str, Dict[str, int]],
    source_url: str = "",
    source_name: str = "ORCD Rental Portal",
) -> RootManifest:
    """Generate root manifest for an export.
    
    Args:
        export_dir: Root export directory
        component_data: Dict mapping component name to data_counts dict
        source_url: URL of the source portal
        source_name: Name of the source portal
        
    Returns:
        Generated RootManifest instance
    """
    from django.utils import timezone
    created_at = timezone.now().isoformat()
    
    # Build components info
    components = {}
    total_records = 0
    
    for component, data_counts in component_data.items():
        component_total = sum(data_counts.values())
        total_records += component_total
        
        components[component] = {
            "path": f"{component}/",
            "manifest": f"{component}/{MANIFEST_FILENAME}",
            "data_counts": data_counts,
            "record_count": component_total,
        }
    
    checksum = calculate_checksum(export_dir)
    
    manifest = RootManifest(
        export_version=EXPORT_VERSION,
        export_format=EXPORT_FORMAT,
        created_at=created_at,
        source_portal={
            "url": source_url,
            "name": source_name,
        },
        software_versions=get_software_versions(),
        components=components,
        total_records=total_records,
        checksum=checksum,
    )
    
    return manifest


# Backward compatibility
def generate_manifest(
    export_dir: str,
    data_counts: Dict[str, int],
    source_url: str = "",
    source_name: str = "ORCD Rental Portal",
) -> Manifest:
    """Generate manifest for a single-component export (backward compatible).
    
    For new exports, use generate_component_manifest() and generate_root_manifest().
    """
    return generate_component_manifest(
        export_dir,
        COMPONENT_ORCD_PLUGIN,
        data_counts,
        source_url,
        source_name,
    )

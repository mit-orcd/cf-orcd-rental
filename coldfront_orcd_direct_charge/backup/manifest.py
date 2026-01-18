# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Manifest generation and validation.

The manifest contains metadata about an export including versions,
timestamps, data counts, and checksums for integrity verification.

Manifest Structure:
    {
        "export_version": "1.0.0",
        "export_format": "orcd-portal-export",
        "created_at": "2026-01-17T12:00:00-05:00",
        "source_portal": {
            "url": "https://portal.example.com",
            "name": "ORCD Rental Portal"
        },
        "software_versions": {
            "coldfront": "1.1.7",
            "coldfront_orcd_direct_charge": "0.3.1",
            "django": "4.2.0",
            "python": "3.11.0"
        },
        "schema_versions": {
            "coldfront_orcd_direct_charge": "0024"
        },
        "data_counts": {
            "node_types": 5,
            "gpu_node_instances": 20,
            ...
        },
        "checksum": {
            "algorithm": "sha256",
            "value": "abc123..."
        }
    }
"""

import hashlib
import json
import platform
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Export format constants
EXPORT_FORMAT = "orcd-portal-export"
EXPORT_VERSION = "1.0.0"

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
class Manifest:
    """Export manifest with version and integrity information.
    
    The manifest is generated during export and validated during import
    to ensure data integrity and compatibility.
    
    Attributes:
        export_version: Version of the export format
        export_format: Format identifier
        created_at: ISO timestamp of export creation
        source_portal: Dict with url and name of source portal
        software_versions: SoftwareVersions dataclass
        schema_versions: Dict mapping app name to migration number
        data_counts: Dict mapping model name to record count
        checksum: Optional dict with algorithm and value
    """
    export_version: str
    export_format: str
    created_at: str
    source_portal: Dict[str, str]
    software_versions: SoftwareVersions
    schema_versions: Dict[str, str]
    data_counts: Dict[str, int]
    checksum: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict:
        """Convert manifest to dictionary.
        
        Returns:
            Dict representation of manifest
        """
        data = asdict(self)
        return data
    
    def to_json(self, indent: int = 2) -> str:
        """Serialize manifest to JSON string.
        
        Args:
            indent: Indentation level for pretty printing
            
        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=indent)
    
    def save(self, output_dir: str) -> str:
        """Save manifest to file.
        
        Args:
            output_dir: Directory to save manifest to
            
        Returns:
            Path to saved manifest file
        """
        output_path = Path(output_dir) / MANIFEST_FILENAME
        with open(output_path, "w") as f:
            f.write(self.to_json())
        return str(output_path)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Manifest":
        """Create manifest from dictionary.
        
        Args:
            data: Dict representation of manifest
            
        Returns:
            Manifest instance
        """
        # Convert nested software_versions dict to dataclass
        sw_versions = data.get("software_versions", {})
        if isinstance(sw_versions, dict):
            sw_versions = SoftwareVersions(**sw_versions)
        
        return cls(
            export_version=data.get("export_version", ""),
            export_format=data.get("export_format", ""),
            created_at=data.get("created_at", ""),
            source_portal=data.get("source_portal", {}),
            software_versions=sw_versions,
            schema_versions=data.get("schema_versions", {}),
            data_counts=data.get("data_counts", {}),
            checksum=data.get("checksum"),
        )
    
    @classmethod
    def from_file(cls, path: str) -> "Manifest":
        """Load manifest from file.
        
        Args:
            path: Path to manifest file
            
        Returns:
            Manifest instance
            
        Raises:
            FileNotFoundError: If manifest file doesn't exist
            json.JSONDecodeError: If file is not valid JSON
        """
        manifest_path = Path(path)
        
        # If path is a directory, look for manifest.json inside
        if manifest_path.is_dir():
            manifest_path = manifest_path / MANIFEST_FILENAME
        
        with open(manifest_path, "r") as f:
            data = json.load(f)
        
        return cls.from_dict(data)
    
    def validate(self) -> List[str]:
        """Validate manifest structure and required fields.
        
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        # Check required fields
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
    """Get current software versions.
    
    Returns:
        SoftwareVersions with current version info
    """
    import django
    
    # Get ColdFront version
    try:
        from coldfront import __version__ as coldfront_version
    except ImportError:
        coldfront_version = "unknown"
    
    # Get plugin version
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


def get_current_schema_version() -> str:
    """Get current migration number for the plugin.
    
    Returns:
        Migration number as string (e.g., "0024")
    """
    try:
        from django.db.migrations.recorder import MigrationRecorder
        from django.db import connection
        
        recorder = MigrationRecorder(connection)
        applied = recorder.applied_migrations()
        
        # Get all migrations for our app
        app_migrations = [
            name for (app, name) in applied 
            if app == "coldfront_orcd_direct_charge"
        ]
        
        if app_migrations:
            # Return the highest migration number
            return max(app_migrations)
        
        return "0000"
    except Exception as e:
        logger.warning(f"Could not determine schema version: {e}")
        return "unknown"


def calculate_checksum(export_dir: str, algorithm: str = "sha256") -> Dict[str, str]:
    """Calculate checksum of all export files.
    
    Args:
        export_dir: Directory containing export files
        algorithm: Hash algorithm to use
        
    Returns:
        Dict with algorithm and checksum value
    """
    hasher = hashlib.new(algorithm)
    export_path = Path(export_dir)
    
    # Hash all JSON files except manifest
    for json_file in sorted(export_path.glob("*.json")):
        if json_file.name != MANIFEST_FILENAME:
            with open(json_file, "rb") as f:
                hasher.update(f.read())
    
    return {
        "algorithm": algorithm,
        "value": hasher.hexdigest(),
    }


def verify_checksum(manifest: Manifest, export_dir: str) -> bool:
    """Verify checksum of export files against manifest.
    
    Args:
        manifest: Manifest to verify against
        export_dir: Directory containing export files
        
    Returns:
        True if checksum matches, False otherwise
    """
    if not manifest.checksum:
        logger.warning("Manifest does not contain checksum")
        return True  # No checksum to verify
    
    algorithm = manifest.checksum.get("algorithm", "sha256")
    expected = manifest.checksum.get("value", "")
    
    actual = calculate_checksum(export_dir, algorithm)
    
    return actual["value"] == expected


def generate_manifest(
    export_dir: str,
    data_counts: Dict[str, int],
    source_url: str = "",
    source_name: str = "ORCD Rental Portal",
) -> Manifest:
    """Generate manifest for an export.
    
    Args:
        export_dir: Directory containing export files
        data_counts: Dict mapping model name to record count
        source_url: URL of the source portal
        source_name: Name of the source portal
        
    Returns:
        Generated Manifest instance
    """
    # Get current timestamp in ISO format with timezone
    from django.utils import timezone
    created_at = timezone.now().isoformat()
    
    # Calculate checksum of export files
    checksum = calculate_checksum(export_dir)
    
    manifest = Manifest(
        export_version=EXPORT_VERSION,
        export_format=EXPORT_FORMAT,
        created_at=created_at,
        source_portal={
            "url": source_url,
            "name": source_name,
        },
        software_versions=get_software_versions(),
        schema_versions={
            "coldfront_orcd_direct_charge": get_current_schema_version(),
        },
        data_counts=data_counts,
        checksum=checksum,
    )
    
    return manifest

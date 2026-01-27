# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Configuration manifest handling.

This module provides manifest generation and handling specific to the
configuration component of exports. The config manifest tracks which
configuration categories were exported and their setting counts.

Config Manifest Structure:
    {
        "export_version": "2.1.0",
        "export_format": "orcd-portal-export",
        "created_at": "2026-01-26T10:00:00-05:00",
        "component": "config",
        "categories": {
            "plugin_config": 5,
            "coldfront_config": 8,
            "django_config": 6,
            "environment": 4
        },
        "total_settings": 23,
        "checksum": {...}
    }
"""

import hashlib
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Optional
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class ConfigManifest:
    """Manifest for the configuration component.
    
    Attributes:
        export_version: Export format version
        export_format: Export format identifier
        created_at: ISO timestamp of creation
        component: Component name ("config")
        categories: Dict mapping category name to setting count
        total_settings: Total number of settings exported
        checksum: Optional integrity checksum
    """
    export_version: str
    export_format: str
    created_at: str
    component: str
    categories: Dict[str, int]
    total_settings: int
    checksum: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)
    
    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    def save(self, output_dir: str) -> str:
        """Save manifest to file.
        
        Args:
            output_dir: Directory to save manifest in
            
        Returns:
            Path to saved manifest file
        """
        from .manifest import MANIFEST_FILENAME
        
        output_path = Path(output_dir) / MANIFEST_FILENAME
        with open(output_path, "w") as f:
            f.write(self.to_json())
        return str(output_path)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ConfigManifest":
        """Create from dictionary."""
        return cls(
            export_version=data.get("export_version", ""),
            export_format=data.get("export_format", ""),
            created_at=data.get("created_at", ""),
            component=data.get("component", "config"),
            categories=data.get("categories", {}),
            total_settings=data.get("total_settings", 0),
            checksum=data.get("checksum"),
        )
    
    @classmethod
    def from_file(cls, path: str) -> "ConfigManifest":
        """Load from file.
        
        Args:
            path: Path to manifest file or directory containing manifest.json
            
        Returns:
            ConfigManifest instance
        """
        from .manifest import MANIFEST_FILENAME
        
        manifest_path = Path(path)
        if manifest_path.is_dir():
            manifest_path = manifest_path / MANIFEST_FILENAME
        
        with open(manifest_path, "r") as f:
            data = json.load(f)
        
        return cls.from_dict(data)
    
    def validate(self) -> list:
        """Validate manifest structure.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not self.export_version:
            errors.append("Missing export_version")
        if not self.export_format:
            errors.append("Missing export_format")
        if self.component != "config":
            errors.append(f"Invalid component: {self.component} (expected 'config')")
        if not self.categories:
            errors.append("Missing categories")
        
        return errors


def calculate_config_checksum(config_dir: str, algorithm: str = "sha256") -> Dict[str, str]:
    """Calculate checksum of all config files in directory.
    
    Args:
        config_dir: Path to config directory
        algorithm: Hash algorithm to use
        
    Returns:
        Dict with algorithm and checksum value
    """
    from .manifest import MANIFEST_FILENAME
    
    hasher = hashlib.new(algorithm)
    config_path = Path(config_dir)
    
    # Hash all JSON files except manifest
    for json_file in sorted(config_path.glob("*.json")):
        if json_file.name != MANIFEST_FILENAME:
            with open(json_file, "rb") as f:
                hasher.update(f.read())
    
    return {
        "algorithm": algorithm,
        "value": hasher.hexdigest(),
    }


def generate_config_manifest(
    config_dir: str,
    categories: Dict[str, int],
) -> ConfigManifest:
    """Generate manifest for the configuration component.
    
    Args:
        config_dir: Path to config directory
        categories: Dict mapping category name to setting count
        
    Returns:
        ConfigManifest instance
    """
    from .manifest import EXPORT_VERSION, EXPORT_FORMAT
    
    created_at = timezone.now().isoformat()
    total_settings = sum(categories.values())
    
    # Calculate checksum (only if files exist)
    checksum = None
    config_path = Path(config_dir)
    if config_path.exists() and any(config_path.glob("*.json")):
        checksum = calculate_config_checksum(config_dir)
    
    return ConfigManifest(
        export_version=EXPORT_VERSION,
        export_format=EXPORT_FORMAT,
        created_at=created_at,
        component="config",
        categories=categories,
        total_settings=total_settings,
        checksum=checksum,
    )


def verify_config_checksum(manifest: ConfigManifest, config_dir: str) -> bool:
    """Verify checksum of config files against manifest.
    
    Args:
        manifest: Config manifest to verify against
        config_dir: Path to config directory
        
    Returns:
        True if checksum matches or no checksum in manifest
    """
    if not manifest.checksum:
        logger.warning("Config manifest does not contain checksum")
        return True
    
    algorithm = manifest.checksum.get("algorithm", "sha256")
    expected = manifest.checksum.get("value", "")
    
    actual = calculate_config_checksum(config_dir, algorithm)
    
    return actual["value"] == expected

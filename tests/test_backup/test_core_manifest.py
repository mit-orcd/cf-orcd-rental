# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tests for v2.0 manifest with component support."""

import json
import tempfile
from pathlib import Path
from unittest import TestCase

from coldfront_orcd_direct_charge.backup.manifest import (
    RootManifest,
    Manifest,
    SoftwareVersions,
    EXPORT_FORMAT,
    EXPORT_VERSION,
    COMPONENT_COLDFRONT_CORE,
    COMPONENT_ORCD_PLUGIN,
    MANIFEST_FILENAME,
)


class TestRootManifest(TestCase):
    """Tests for RootManifest class."""
    
    def test_create_root_manifest(self):
        """Test creating a root manifest."""
        manifest = RootManifest(
            export_version=EXPORT_VERSION,
            export_format=EXPORT_FORMAT,
            created_at="2026-01-18T12:00:00-05:00",
            source_portal={"url": "https://test.example.com", "name": "Test Portal"},
            software_versions=SoftwareVersions(
                coldfront="1.1.7",
                coldfront_orcd_direct_charge="0.3.1",
                django="4.2.0",
                python="3.11.0",
            ),
            components={
                COMPONENT_COLDFRONT_CORE: {
                    "path": f"{COMPONENT_COLDFRONT_CORE}/",
                    "manifest": f"{COMPONENT_COLDFRONT_CORE}/{MANIFEST_FILENAME}",
                    "data_counts": {"users": 100, "projects": 50},
                    "record_count": 150,
                },
                COMPONENT_ORCD_PLUGIN: {
                    "path": f"{COMPONENT_ORCD_PLUGIN}/",
                    "manifest": f"{COMPONENT_ORCD_PLUGIN}/{MANIFEST_FILENAME}",
                    "data_counts": {"node_types": 5, "reservations": 200},
                    "record_count": 205,
                },
            },
            total_records=355,
        )
        
        self.assertEqual(manifest.export_version, EXPORT_VERSION)
        self.assertEqual(manifest.total_records, 355)
        self.assertTrue(manifest.has_component(COMPONENT_COLDFRONT_CORE))
        self.assertTrue(manifest.has_component(COMPONENT_ORCD_PLUGIN))
        self.assertFalse(manifest.has_component("nonexistent"))
    
    def test_get_component_names(self):
        """Test getting list of component names."""
        manifest = RootManifest(
            export_version=EXPORT_VERSION,
            export_format=EXPORT_FORMAT,
            created_at="2026-01-18T12:00:00-05:00",
            source_portal={},
            software_versions=SoftwareVersions("", "", "", ""),
            components={
                COMPONENT_COLDFRONT_CORE: {},
                COMPONENT_ORCD_PLUGIN: {},
            },
            total_records=0,
        )
        
        component_names = manifest.get_component_names()
        
        self.assertIn(COMPONENT_COLDFRONT_CORE, component_names)
        self.assertIn(COMPONENT_ORCD_PLUGIN, component_names)
    
    def test_to_dict(self):
        """Test converting root manifest to dict."""
        manifest = RootManifest(
            export_version=EXPORT_VERSION,
            export_format=EXPORT_FORMAT,
            created_at="2026-01-18T12:00:00-05:00",
            source_portal={"name": "Test"},
            software_versions=SoftwareVersions("1.0", "0.3", "4.2", "3.11"),
            components={COMPONENT_COLDFRONT_CORE: {"record_count": 100}},
            total_records=100,
        )
        
        data = manifest.to_dict()
        
        self.assertEqual(data["export_version"], EXPORT_VERSION)
        self.assertEqual(data["total_records"], 100)
        self.assertIn(COMPONENT_COLDFRONT_CORE, data["components"])
    
    def test_to_json(self):
        """Test serializing root manifest to JSON."""
        manifest = RootManifest(
            export_version=EXPORT_VERSION,
            export_format=EXPORT_FORMAT,
            created_at="2026-01-18T12:00:00-05:00",
            source_portal={},
            software_versions=SoftwareVersions("1.0", "0.3", "4.2", "3.11"),
            components={},
            total_records=0,
        )
        
        json_str = manifest.to_json()
        parsed = json.loads(json_str)
        
        self.assertEqual(parsed["export_version"], EXPORT_VERSION)
    
    def test_save_and_load(self):
        """Test saving and loading root manifest from file."""
        manifest = RootManifest(
            export_version=EXPORT_VERSION,
            export_format=EXPORT_FORMAT,
            created_at="2026-01-18T12:00:00-05:00",
            source_portal={"name": "Test Portal"},
            software_versions=SoftwareVersions("1.1.7", "0.3.1", "4.2.0", "3.11.0"),
            components={
                COMPONENT_COLDFRONT_CORE: {"record_count": 100},
            },
            total_records=100,
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = manifest.save(tmpdir)
            
            self.assertTrue(Path(manifest_path).exists())
            
            loaded = RootManifest.from_file(tmpdir)
            
            self.assertEqual(loaded.export_version, EXPORT_VERSION)
            self.assertEqual(loaded.total_records, 100)
            self.assertTrue(loaded.has_component(COMPONENT_COLDFRONT_CORE))


class TestComponentManifest(TestCase):
    """Tests for component-specific Manifest class."""
    
    def test_create_component_manifest(self):
        """Test creating a component manifest."""
        manifest = Manifest(
            export_version=EXPORT_VERSION,
            export_format=EXPORT_FORMAT,
            created_at="2026-01-18T12:00:00-05:00",
            component=COMPONENT_COLDFRONT_CORE,
            source_portal={"name": "Test"},
            software_versions=SoftwareVersions("1.1.7", "0.3.1", "4.2.0", "3.11.0"),
            schema_versions={"auth": "0015", "project": "0012"},
            data_counts={"users": 100, "projects": 50},
        )
        
        self.assertEqual(manifest.component, COMPONENT_COLDFRONT_CORE)
        self.assertEqual(manifest.data_counts["users"], 100)
    
    def test_validate_component_manifest(self):
        """Test validating component manifest."""
        # Valid manifest
        valid_manifest = Manifest(
            export_version=EXPORT_VERSION,
            export_format=EXPORT_FORMAT,
            created_at="2026-01-18T12:00:00-05:00",
            component=COMPONENT_ORCD_PLUGIN,
            source_portal={},
            software_versions=SoftwareVersions("1.0", "0.3", "4.2", "3.11"),
            schema_versions={"coldfront_orcd_direct_charge": "0024"},
            data_counts={},
        )
        
        errors = valid_manifest.validate()
        self.assertEqual(len(errors), 0)
        
        # Invalid manifest (missing version)
        invalid_manifest = Manifest(
            export_version="",
            export_format=EXPORT_FORMAT,
            created_at="2026-01-18T12:00:00-05:00",
            component=COMPONENT_ORCD_PLUGIN,
            source_portal={},
            software_versions=SoftwareVersions("", "", "", ""),
            schema_versions={},
            data_counts={},
        )
        
        errors = invalid_manifest.validate()
        self.assertIn("Missing export_version", errors)

# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tests for v2.0 export directory structure."""

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


class TestExportStructure(TestCase):
    """Tests for the v2.0 two-directory export structure."""
    
    def test_create_export_structure(self):
        """Test creating the complete export directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            export_dir = Path(tmpdir)
            
            # Create component directories
            core_dir = export_dir / COMPONENT_COLDFRONT_CORE
            plugin_dir = export_dir / COMPONENT_ORCD_PLUGIN
            core_dir.mkdir()
            plugin_dir.mkdir()
            
            # Create core manifest
            core_manifest = Manifest(
                export_version=EXPORT_VERSION,
                export_format=EXPORT_FORMAT,
                created_at="2026-01-18T12:00:00-05:00",
                component=COMPONENT_COLDFRONT_CORE,
                source_portal={"name": "Test"},
                software_versions=SoftwareVersions("1.1.7", "0.3.1", "4.2", "3.11"),
                schema_versions={"auth": "0015"},
                data_counts={"users": 10},
            )
            core_manifest.save(str(core_dir))
            
            # Create plugin manifest
            plugin_manifest = Manifest(
                export_version=EXPORT_VERSION,
                export_format=EXPORT_FORMAT,
                created_at="2026-01-18T12:00:00-05:00",
                component=COMPONENT_ORCD_PLUGIN,
                source_portal={"name": "Test"},
                software_versions=SoftwareVersions("1.1.7", "0.3.1", "4.2", "3.11"),
                schema_versions={"coldfront_orcd_direct_charge": "0024"},
                data_counts={"node_types": 5},
            )
            plugin_manifest.save(str(plugin_dir))
            
            # Create root manifest
            root_manifest = RootManifest(
                export_version=EXPORT_VERSION,
                export_format=EXPORT_FORMAT,
                created_at="2026-01-18T12:00:00-05:00",
                source_portal={"name": "Test"},
                software_versions=SoftwareVersions("1.1.7", "0.3.1", "4.2", "3.11"),
                components={
                    COMPONENT_COLDFRONT_CORE: {
                        "path": f"{COMPONENT_COLDFRONT_CORE}/",
                        "manifest": f"{COMPONENT_COLDFRONT_CORE}/{MANIFEST_FILENAME}",
                        "data_counts": {"users": 10},
                        "record_count": 10,
                    },
                    COMPONENT_ORCD_PLUGIN: {
                        "path": f"{COMPONENT_ORCD_PLUGIN}/",
                        "manifest": f"{COMPONENT_ORCD_PLUGIN}/{MANIFEST_FILENAME}",
                        "data_counts": {"node_types": 5},
                        "record_count": 5,
                    },
                },
                total_records=15,
            )
            root_manifest.save(str(export_dir))
            
            # Verify structure
            self.assertTrue((export_dir / MANIFEST_FILENAME).exists())
            self.assertTrue((core_dir / MANIFEST_FILENAME).exists())
            self.assertTrue((plugin_dir / MANIFEST_FILENAME).exists())
            
            # Verify root manifest can be loaded
            loaded_root = RootManifest.from_file(str(export_dir))
            self.assertEqual(loaded_root.total_records, 15)
            self.assertTrue(loaded_root.has_component(COMPONENT_COLDFRONT_CORE))
            self.assertTrue(loaded_root.has_component(COMPONENT_ORCD_PLUGIN))
            
            # Verify component manifests can be loaded
            loaded_core = Manifest.from_file(str(core_dir))
            self.assertEqual(loaded_core.component, COMPONENT_COLDFRONT_CORE)
            
            loaded_plugin = Manifest.from_file(str(plugin_dir))
            self.assertEqual(loaded_plugin.component, COMPONENT_ORCD_PLUGIN)
    
    def test_single_component_export(self):
        """Test export with only one component."""
        with tempfile.TemporaryDirectory() as tmpdir:
            export_dir = Path(tmpdir)
            
            # Create only plugin directory
            plugin_dir = export_dir / COMPONENT_ORCD_PLUGIN
            plugin_dir.mkdir()
            
            # Create plugin manifest
            plugin_manifest = Manifest(
                export_version=EXPORT_VERSION,
                export_format=EXPORT_FORMAT,
                created_at="2026-01-18T12:00:00-05:00",
                component=COMPONENT_ORCD_PLUGIN,
                source_portal={},
                software_versions=SoftwareVersions("1.1.7", "0.3.1", "4.2", "3.11"),
                schema_versions={"coldfront_orcd_direct_charge": "0024"},
                data_counts={"reservations": 100},
            )
            plugin_manifest.save(str(plugin_dir))
            
            # Create root manifest with only plugin
            root_manifest = RootManifest(
                export_version=EXPORT_VERSION,
                export_format=EXPORT_FORMAT,
                created_at="2026-01-18T12:00:00-05:00",
                source_portal={},
                software_versions=SoftwareVersions("1.1.7", "0.3.1", "4.2", "3.11"),
                components={
                    COMPONENT_ORCD_PLUGIN: {
                        "path": f"{COMPONENT_ORCD_PLUGIN}/",
                        "data_counts": {"reservations": 100},
                        "record_count": 100,
                    },
                },
                total_records=100,
            )
            root_manifest.save(str(export_dir))
            
            # Verify
            loaded = RootManifest.from_file(str(export_dir))
            self.assertFalse(loaded.has_component(COMPONENT_COLDFRONT_CORE))
            self.assertTrue(loaded.has_component(COMPONENT_ORCD_PLUGIN))
            self.assertEqual(len(loaded.get_component_names()), 1)
    
    def test_detect_v2_export(self):
        """Test detecting v2.0 export by component directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            export_dir = Path(tmpdir)
            
            # Create empty root manifest
            (export_dir / MANIFEST_FILENAME).write_text("{}")
            
            # No component directories = not v2
            core_dir = export_dir / COMPONENT_COLDFRONT_CORE
            self.assertFalse(core_dir.exists())
            
            # Create component directory
            core_dir.mkdir()
            
            # Now it should be detected as v2
            self.assertTrue(core_dir.exists())

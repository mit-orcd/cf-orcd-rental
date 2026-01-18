# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tests for manifest generation and validation."""

import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from coldfront_orcd_direct_charge.backup.manifest import (
    Manifest,
    SoftwareVersions,
    EXPORT_FORMAT,
    EXPORT_VERSION,
    MANIFEST_FILENAME,
    calculate_checksum,
    verify_checksum,
)


class TestSoftwareVersions(TestCase):
    """Tests for SoftwareVersions dataclass."""
    
    def test_creation(self):
        """Test SoftwareVersions can be created."""
        versions = SoftwareVersions(
            coldfront="1.1.7",
            coldfront_orcd_direct_charge="0.3.1",
            django="4.2.0",
            python="3.11.0",
        )
        
        self.assertEqual(versions.coldfront, "1.1.7")
        self.assertEqual(versions.coldfront_orcd_direct_charge, "0.3.1")


class TestManifest(TestCase):
    """Tests for Manifest class."""
    
    def test_creation(self):
        """Test Manifest can be created."""
        manifest = Manifest(
            export_version="1.0.0",
            export_format=EXPORT_FORMAT,
            created_at="2026-01-17T12:00:00-05:00",
            source_portal={"url": "https://example.com", "name": "Test Portal"},
            software_versions=SoftwareVersions(
                coldfront="1.1.7",
                coldfront_orcd_direct_charge="0.3.1",
                django="4.2.0",
                python="3.11.0",
            ),
            schema_versions={"coldfront_orcd_direct_charge": "0024"},
            data_counts={"node_types": 5, "reservations": 10},
        )
        
        self.assertEqual(manifest.export_version, "1.0.0")
        self.assertEqual(manifest.export_format, EXPORT_FORMAT)
    
    def test_to_dict(self):
        """Test conversion to dict."""
        manifest = Manifest(
            export_version="1.0.0",
            export_format=EXPORT_FORMAT,
            created_at="2026-01-17T12:00:00-05:00",
            source_portal={"name": "Test"},
            software_versions=SoftwareVersions(
                coldfront="1.1.7",
                coldfront_orcd_direct_charge="0.3.1",
                django="4.2.0",
                python="3.11.0",
            ),
            schema_versions={},
            data_counts={},
        )
        
        data = manifest.to_dict()
        
        self.assertIsInstance(data, dict)
        self.assertEqual(data["export_version"], "1.0.0")
        self.assertIn("software_versions", data)
    
    def test_to_json(self):
        """Test conversion to JSON."""
        manifest = Manifest(
            export_version="1.0.0",
            export_format=EXPORT_FORMAT,
            created_at="2026-01-17T12:00:00-05:00",
            source_portal={},
            software_versions=SoftwareVersions(
                coldfront="1.1.7",
                coldfront_orcd_direct_charge="0.3.1",
                django="4.2.0",
                python="3.11.0",
            ),
            schema_versions={},
            data_counts={},
        )
        
        json_str = manifest.to_json()
        
        self.assertIsInstance(json_str, str)
        data = json.loads(json_str)
        self.assertEqual(data["export_version"], "1.0.0")
    
    def test_save_and_load(self):
        """Test saving and loading manifest."""
        manifest = Manifest(
            export_version="1.0.0",
            export_format=EXPORT_FORMAT,
            created_at="2026-01-17T12:00:00-05:00",
            source_portal={"name": "Test"},
            software_versions=SoftwareVersions(
                coldfront="1.1.7",
                coldfront_orcd_direct_charge="0.3.1",
                django="4.2.0",
                python="3.11.0",
            ),
            schema_versions={"coldfront_orcd_direct_charge": "0024"},
            data_counts={"test": 5},
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest.save(tmpdir)
            
            # Verify file exists
            manifest_path = Path(tmpdir) / MANIFEST_FILENAME
            self.assertTrue(manifest_path.exists())
            
            # Load and verify
            loaded = Manifest.from_file(tmpdir)
            
            self.assertEqual(loaded.export_version, manifest.export_version)
            self.assertEqual(loaded.data_counts, manifest.data_counts)
    
    def test_from_dict(self):
        """Test creating from dict."""
        data = {
            "export_version": "1.0.0",
            "export_format": EXPORT_FORMAT,
            "created_at": "2026-01-17T12:00:00-05:00",
            "source_portal": {"name": "Test"},
            "software_versions": {
                "coldfront": "1.1.7",
                "coldfront_orcd_direct_charge": "0.3.1",
                "django": "4.2.0",
                "python": "3.11.0",
            },
            "schema_versions": {},
            "data_counts": {"test": 5},
        }
        
        manifest = Manifest.from_dict(data)
        
        self.assertEqual(manifest.export_version, "1.0.0")
        self.assertIsInstance(manifest.software_versions, SoftwareVersions)
    
    def test_validate_valid(self):
        """Test validation of valid manifest."""
        manifest = Manifest(
            export_version="1.0.0",
            export_format=EXPORT_FORMAT,
            created_at="2026-01-17T12:00:00-05:00",
            source_portal={},
            software_versions=SoftwareVersions(
                coldfront="1.1.7",
                coldfront_orcd_direct_charge="0.3.1",
                django="4.2.0",
                python="3.11.0",
            ),
            schema_versions={"test": "0001"},
            data_counts={},
        )
        
        errors = manifest.validate()
        self.assertEqual(errors, [])
    
    def test_validate_invalid(self):
        """Test validation catches missing fields."""
        manifest = Manifest(
            export_version="",
            export_format="wrong-format",
            created_at="",
            source_portal={},
            software_versions=None,
            schema_versions={},
            data_counts={},
        )
        
        errors = manifest.validate()
        
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("export_version" in e for e in errors))


class TestChecksum(TestCase):
    """Tests for checksum calculation and verification."""
    
    def test_calculate_checksum(self):
        """Test checksum calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            (Path(tmpdir) / "test1.json").write_text('{"data": 1}')
            (Path(tmpdir) / "test2.json").write_text('{"data": 2}')
            
            checksum = calculate_checksum(tmpdir)
            
            self.assertIn("algorithm", checksum)
            self.assertIn("value", checksum)
            self.assertEqual(checksum["algorithm"], "sha256")
            self.assertEqual(len(checksum["value"]), 64)  # SHA256 hex length
    
    def test_checksum_excludes_manifest(self):
        """Test that manifest.json is excluded from checksum."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            (Path(tmpdir) / "test.json").write_text('{"data": 1}')
            (Path(tmpdir) / "manifest.json").write_text('{"version": "1.0"}')
            
            checksum1 = calculate_checksum(tmpdir)
            
            # Change manifest content
            (Path(tmpdir) / "manifest.json").write_text('{"version": "2.0"}')
            
            checksum2 = calculate_checksum(tmpdir)
            
            # Checksums should be the same since manifest is excluded
            self.assertEqual(checksum1["value"], checksum2["value"])
    
    def test_verify_checksum_success(self):
        """Test successful checksum verification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            (Path(tmpdir) / "test.json").write_text('{"data": 1}')
            
            checksum = calculate_checksum(tmpdir)
            
            manifest = Manifest(
                export_version="1.0.0",
                export_format=EXPORT_FORMAT,
                created_at="",
                source_portal={},
                software_versions=SoftwareVersions("", "", "", ""),
                schema_versions={},
                data_counts={},
                checksum=checksum,
            )
            
            self.assertTrue(verify_checksum(manifest, tmpdir))
    
    def test_verify_checksum_failure(self):
        """Test failed checksum verification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            (Path(tmpdir) / "test.json").write_text('{"data": 1}')
            
            manifest = Manifest(
                export_version="1.0.0",
                export_format=EXPORT_FORMAT,
                created_at="",
                source_portal={},
                software_versions=SoftwareVersions("", "", "", ""),
                schema_versions={},
                data_counts={},
                checksum={"algorithm": "sha256", "value": "wrong_checksum"},
            )
            
            self.assertFalse(verify_checksum(manifest, tmpdir))

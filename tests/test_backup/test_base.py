# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tests for base exporter and importer classes."""

import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

from coldfront_orcd_direct_charge.backup.base import (
    BaseExporter,
    BaseImporter,
    ExportResult,
    ImportResult,
)


class TestExportResult(TestCase):
    """Tests for ExportResult dataclass."""
    
    def test_creation(self):
        """Test ExportResult can be created with required fields."""
        result = ExportResult(
            model_name="test_model",
            count=10,
            file_path="/tmp/test.json",
            success=True,
        )
        self.assertEqual(result.model_name, "test_model")
        self.assertEqual(result.count, 10)
        self.assertEqual(result.file_path, "/tmp/test.json")
        self.assertTrue(result.success)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.warnings, [])
    
    def test_with_errors(self):
        """Test ExportResult with errors."""
        result = ExportResult(
            model_name="test_model",
            count=0,
            file_path="/tmp/test.json",
            success=False,
            errors=["Error 1", "Error 2"],
        )
        self.assertFalse(result.success)
        self.assertEqual(len(result.errors), 2)


class TestImportResult(TestCase):
    """Tests for ImportResult dataclass."""
    
    def test_creation(self):
        """Test ImportResult can be created with required fields."""
        result = ImportResult(model_name="test_model")
        self.assertEqual(result.model_name, "test_model")
        self.assertEqual(result.created, 0)
        self.assertEqual(result.updated, 0)
        self.assertEqual(result.skipped, 0)
    
    def test_total_processed(self):
        """Test total_processed property."""
        result = ImportResult(
            model_name="test_model",
            created=5,
            updated=3,
            skipped=2,
        )
        self.assertEqual(result.total_processed, 10)
    
    def test_success(self):
        """Test success property."""
        result = ImportResult(model_name="test_model")
        self.assertTrue(result.success)
        
        result.errors.append("An error")
        self.assertFalse(result.success)


class ConcreteExporter(BaseExporter):
    """Concrete implementation for testing."""
    
    model_name = "test_exporter"
    dependencies = []
    
    def __init__(self, records=None):
        self._records = records or []
    
    def get_queryset(self):
        mock_qs = MagicMock()
        mock_qs.count.return_value = len(self._records)
        mock_qs.__iter__ = lambda s: iter(self._records)
        return mock_qs
    
    def serialize_record(self, instance):
        return {
            "natural_key": (instance["id"],),
            "fields": instance,
        }


class TestBaseExporter(TestCase):
    """Tests for BaseExporter class."""
    
    def test_get_filename(self):
        """Test get_filename returns correct format."""
        exporter = ConcreteExporter()
        self.assertEqual(exporter.get_filename(), "test_exporter.json")
    
    def test_export_empty(self):
        """Test exporting with no records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = ConcreteExporter(records=[])
            result = exporter.export(tmpdir)
            
            self.assertTrue(result.success)
            self.assertEqual(result.count, 0)
            
            # Check file was created
            output_path = Path(tmpdir) / "test_exporter.json"
            self.assertTrue(output_path.exists())
            
            with open(output_path) as f:
                data = json.load(f)
            
            self.assertEqual(data["model"], "test_exporter")
            self.assertEqual(data["count"], 0)
            self.assertEqual(data["records"], [])
    
    def test_export_with_records(self):
        """Test exporting with records."""
        records = [
            {"id": 1, "name": "Test 1"},
            {"id": 2, "name": "Test 2"},
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = ConcreteExporter(records=records)
            result = exporter.export(tmpdir)
            
            self.assertTrue(result.success)
            self.assertEqual(result.count, 2)
            
            output_path = Path(tmpdir) / "test_exporter.json"
            with open(output_path) as f:
                data = json.load(f)
            
            self.assertEqual(len(data["records"]), 2)


class ConcreteImporter(BaseImporter):
    """Concrete implementation for testing."""
    
    model_name = "test_importer"
    dependencies = []
    
    def __init__(self):
        self._store = {}
    
    def get_existing(self, natural_key):
        if not natural_key:
            return None
        key = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
        return self._store.get(key)
    
    def deserialize_record(self, data):
        return data.get("fields", {})
    
    def create_record(self, data):
        fields = data.get("fields", {})
        self._store[fields.get("id")] = fields
        return fields
    
    def update_record(self, existing, data):
        fields = data.get("fields", {})
        existing.update(fields)
        return existing


class TestBaseImporter(TestCase):
    """Tests for BaseImporter class."""
    
    def test_get_filename(self):
        """Test get_filename returns correct format."""
        importer = ConcreteImporter()
        self.assertEqual(importer.get_filename(), "test_importer.json")
    
    def test_import_create(self):
        """Test importing creates new records."""
        records = [
            {"natural_key": (1,), "fields": {"id": 1, "name": "Test 1"}},
            {"natural_key": (2,), "fields": {"id": 2, "name": "Test 2"}},
        ]
        
        importer = ConcreteImporter()
        result = importer.import_records(records)
        
        self.assertTrue(result.success)
        self.assertEqual(result.created, 2)
        self.assertEqual(result.updated, 0)
    
    def test_import_update(self):
        """Test importing updates existing records."""
        importer = ConcreteImporter()
        importer._store[1] = {"id": 1, "name": "Old Name"}
        
        records = [
            {"natural_key": (1,), "fields": {"id": 1, "name": "New Name"}},
        ]
        
        result = importer.import_records(records)
        
        self.assertTrue(result.success)
        self.assertEqual(result.created, 0)
        self.assertEqual(result.updated, 1)
        self.assertEqual(importer._store[1]["name"], "New Name")
    
    def test_import_mode_create_only(self):
        """Test create-only mode skips existing records."""
        importer = ConcreteImporter()
        importer._store[1] = {"id": 1, "name": "Existing"}
        
        records = [
            {"natural_key": (1,), "fields": {"id": 1, "name": "Should Skip"}},
            {"natural_key": (2,), "fields": {"id": 2, "name": "Should Create"}},
        ]
        
        result = importer.import_records(records, mode="create-only")
        
        self.assertEqual(result.created, 1)
        self.assertEqual(result.skipped, 1)
        self.assertEqual(importer._store[1]["name"], "Existing")
    
    def test_import_mode_update_only(self):
        """Test update-only mode skips new records."""
        importer = ConcreteImporter()
        importer._store[1] = {"id": 1, "name": "Existing"}
        
        records = [
            {"natural_key": (1,), "fields": {"id": 1, "name": "Updated"}},
            {"natural_key": (2,), "fields": {"id": 2, "name": "Should Skip"}},
        ]
        
        result = importer.import_records(records, mode="update-only")
        
        self.assertEqual(result.updated, 1)
        self.assertEqual(result.skipped, 1)
        self.assertNotIn(2, importer._store)
    
    def test_import_dry_run(self):
        """Test dry run doesn't modify data."""
        records = [
            {"natural_key": (1,), "fields": {"id": 1, "name": "Test"}},
        ]
        
        importer = ConcreteImporter()
        result = importer.import_records(records, dry_run=True)
        
        self.assertEqual(result.created, 1)
        self.assertNotIn(1, importer._store)  # Not actually created

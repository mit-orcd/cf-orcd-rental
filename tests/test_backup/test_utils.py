# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tests for backup utility functions."""

import tempfile
from datetime import datetime, date, time
from decimal import Decimal
from pathlib import Path
from unittest import TestCase

from coldfront_orcd_direct_charge.backup.utils import (
    serialize_datetime,
    serialize_date,
    serialize_time,
    serialize_decimal,
    deserialize_datetime,
    deserialize_date,
    deserialize_decimal,
    create_export_directory,
    validate_import_directory,
)


class TestSerializeDatetime(TestCase):
    """Tests for datetime serialization."""
    
    def test_serialize_datetime(self):
        """Test serializing datetime."""
        dt = datetime(2026, 1, 17, 12, 30, 45)
        result = serialize_datetime(dt)
        
        self.assertIsInstance(result, str)
        self.assertIn("2026-01-17", result)
    
    def test_serialize_datetime_none(self):
        """Test serializing None datetime."""
        result = serialize_datetime(None)
        self.assertIsNone(result)
    
    def test_deserialize_datetime(self):
        """Test deserializing datetime string."""
        result = deserialize_datetime("2026-01-17T12:30:45")
        
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 17)
    
    def test_deserialize_datetime_none(self):
        """Test deserializing None."""
        result = deserialize_datetime(None)
        self.assertIsNone(result)
    
    def test_deserialize_datetime_empty(self):
        """Test deserializing empty string."""
        result = deserialize_datetime("")
        self.assertIsNone(result)


class TestSerializeDate(TestCase):
    """Tests for date serialization."""
    
    def test_serialize_date(self):
        """Test serializing date."""
        d = date(2026, 1, 17)
        result = serialize_date(d)
        
        self.assertEqual(result, "2026-01-17")
    
    def test_serialize_date_none(self):
        """Test serializing None date."""
        result = serialize_date(None)
        self.assertIsNone(result)
    
    def test_deserialize_date(self):
        """Test deserializing date string."""
        result = deserialize_date("2026-01-17")
        
        self.assertIsInstance(result, date)
        self.assertEqual(result.year, 2026)
    
    def test_deserialize_date_none(self):
        """Test deserializing None."""
        result = deserialize_date(None)
        self.assertIsNone(result)


class TestSerializeTime(TestCase):
    """Tests for time serialization."""
    
    def test_serialize_time(self):
        """Test serializing time."""
        t = time(12, 30, 45)
        result = serialize_time(t)
        
        self.assertEqual(result, "12:30:45")
    
    def test_serialize_time_none(self):
        """Test serializing None time."""
        result = serialize_time(None)
        self.assertIsNone(result)


class TestSerializeDecimal(TestCase):
    """Tests for Decimal serialization."""
    
    def test_serialize_decimal(self):
        """Test serializing Decimal."""
        d = Decimal("123.456")
        result = serialize_decimal(d)
        
        self.assertEqual(result, "123.456")
    
    def test_serialize_decimal_none(self):
        """Test serializing None Decimal."""
        result = serialize_decimal(None)
        self.assertIsNone(result)
    
    def test_deserialize_decimal(self):
        """Test deserializing Decimal string."""
        result = deserialize_decimal("123.456")
        
        self.assertIsInstance(result, Decimal)
        self.assertEqual(result, Decimal("123.456"))
    
    def test_deserialize_decimal_none(self):
        """Test deserializing None."""
        result = deserialize_decimal(None)
        self.assertIsNone(result)


class TestCreateExportDirectory(TestCase):
    """Tests for export directory creation."""
    
    def test_create_with_timestamp(self):
        """Test creating directory with timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = create_export_directory(tmpdir, timestamp=True)
            
            self.assertTrue(Path(result).exists())
            self.assertTrue(Path(result).is_dir())
            self.assertIn("export_", result)
    
    def test_create_without_timestamp(self):
        """Test creating directory without timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "test_export"
            result = create_export_directory(str(target), timestamp=False)
            
            self.assertTrue(Path(result).exists())
            self.assertEqual(result, str(target))


class TestValidateImportDirectory(TestCase):
    """Tests for import directory validation."""
    
    def test_valid_directory(self):
        """Test validating valid export directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create manifest
            (Path(tmpdir) / "manifest.json").write_text("{}")
            
            result = validate_import_directory(tmpdir)
            self.assertTrue(result)
    
    def test_invalid_directory_no_manifest(self):
        """Test directory without manifest is invalid."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = validate_import_directory(tmpdir)
            self.assertFalse(result)
    
    def test_invalid_not_directory(self):
        """Test file path is invalid."""
        with tempfile.NamedTemporaryFile() as f:
            result = validate_import_directory(f.name)
            self.assertFalse(result)

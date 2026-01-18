# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tests for version compatibility checking."""

from unittest import TestCase
from unittest.mock import patch

from coldfront_orcd_direct_charge.backup.version import (
    CompatibilityStatus,
    CompatibilityReport,
    check_version_compatibility,
    check_schema_compatibility,
    parse_version,
    parse_migration_number,
)


class TestParseVersion(TestCase):
    """Tests for version parsing."""
    
    def test_parse_full_version(self):
        """Test parsing full semantic version."""
        result = parse_version("1.2.3")
        self.assertEqual(result, (1, 2, 3))
    
    def test_parse_two_part_version(self):
        """Test parsing two-part version."""
        result = parse_version("1.2")
        self.assertEqual(result, (1, 2, 0))
    
    def test_parse_one_part_version(self):
        """Test parsing single number version."""
        result = parse_version("1")
        self.assertEqual(result, (1, 0, 0))
    
    def test_parse_invalid_version(self):
        """Test parsing invalid version returns zeros."""
        result = parse_version("invalid")
        self.assertEqual(result, (0, 0, 0))
    
    def test_parse_empty_version(self):
        """Test parsing empty version returns zeros."""
        result = parse_version("")
        self.assertEqual(result, (0, 0, 0))


class TestParseMigrationNumber(TestCase):
    """Tests for migration number parsing."""
    
    def test_parse_simple_number(self):
        """Test parsing simple migration number."""
        result = parse_migration_number("0024")
        self.assertEqual(result, 24)
    
    def test_parse_with_name(self):
        """Test parsing migration with name suffix."""
        result = parse_migration_number("0024_add_new_field")
        self.assertEqual(result, 24)
    
    def test_parse_invalid(self):
        """Test parsing invalid migration returns zero."""
        result = parse_migration_number("invalid")
        self.assertEqual(result, 0)


class TestVersionCompatibility(TestCase):
    """Tests for version compatibility checking."""
    
    def test_same_version_compatible(self):
        """Test same versions are compatible."""
        status, warnings, errors = check_version_compatibility("1.0.0", "1.0.0")
        
        self.assertEqual(status, CompatibilityStatus.COMPATIBLE)
        self.assertEqual(len(warnings), 0)
        self.assertEqual(len(errors), 0)
    
    def test_major_version_mismatch_incompatible(self):
        """Test major version mismatch is incompatible."""
        status, warnings, errors = check_version_compatibility("2.0.0", "1.0.0")
        
        self.assertEqual(status, CompatibilityStatus.INCOMPATIBLE)
        self.assertGreater(len(errors), 0)
    
    def test_newer_minor_version_warning(self):
        """Test newer minor version generates warning."""
        status, warnings, errors = check_version_compatibility("1.2.0", "1.1.0")
        
        self.assertEqual(status, CompatibilityStatus.COMPATIBLE_WITH_WARNINGS)
        self.assertGreater(len(warnings), 0)
    
    def test_older_minor_version_warning(self):
        """Test older minor version generates warning."""
        status, warnings, errors = check_version_compatibility("1.0.0", "1.1.0")
        
        self.assertEqual(status, CompatibilityStatus.COMPATIBLE_WITH_WARNINGS)
        self.assertGreater(len(warnings), 0)


class TestSchemaCompatibility(TestCase):
    """Tests for schema compatibility checking."""
    
    def test_same_schema_compatible(self):
        """Test same schema versions are compatible."""
        status, warnings, errors = check_schema_compatibility("0024", "0024")
        
        self.assertEqual(status, CompatibilityStatus.COMPATIBLE)
    
    def test_newer_schema_incompatible(self):
        """Test newer export schema is incompatible."""
        status, warnings, errors = check_schema_compatibility("0030", "0024")
        
        self.assertEqual(status, CompatibilityStatus.INCOMPATIBLE)
        self.assertGreater(len(errors), 0)
    
    def test_older_schema_warning(self):
        """Test older export schema generates warning."""
        status, warnings, errors = check_schema_compatibility("0020", "0024")
        
        self.assertEqual(status, CompatibilityStatus.COMPATIBLE_WITH_WARNINGS)
        self.assertGreater(len(warnings), 0)
    
    def test_significantly_older_schema(self):
        """Test significantly older schema generates warning."""
        status, warnings, errors = check_schema_compatibility("0010", "0024")
        
        self.assertEqual(status, CompatibilityStatus.COMPATIBLE_WITH_WARNINGS)


class TestCompatibilityReport(TestCase):
    """Tests for CompatibilityReport."""
    
    def test_is_safe_to_import_compatible(self):
        """Test compatible reports allow import."""
        report = CompatibilityReport(
            status=CompatibilityStatus.COMPATIBLE,
            export_version="1.0.0",
            target_version="1.0.0",
            export_schema="0024",
            target_schema="0024",
            warnings=[],
            errors=[],
        )
        
        self.assertTrue(report.is_safe_to_import())
    
    def test_is_safe_to_import_with_warnings(self):
        """Test reports with warnings still allow import."""
        report = CompatibilityReport(
            status=CompatibilityStatus.COMPATIBLE_WITH_WARNINGS,
            export_version="1.0.0",
            target_version="1.1.0",
            export_schema="0020",
            target_schema="0024",
            warnings=["Some warning"],
            errors=[],
        )
        
        self.assertTrue(report.is_safe_to_import())
    
    def test_is_safe_to_import_incompatible(self):
        """Test incompatible reports don't allow import."""
        report = CompatibilityReport(
            status=CompatibilityStatus.INCOMPATIBLE,
            export_version="2.0.0",
            target_version="1.0.0",
            export_schema="0030",
            target_schema="0024",
            warnings=[],
            errors=["Major version mismatch"],
        )
        
        self.assertFalse(report.is_safe_to_import())
    
    def test_summary(self):
        """Test summary generation."""
        report = CompatibilityReport(
            status=CompatibilityStatus.COMPATIBLE_WITH_WARNINGS,
            export_version="1.0.0",
            target_version="1.1.0",
            export_schema="0020",
            target_schema="0024",
            warnings=["Warning 1"],
            errors=[],
        )
        
        summary = report.summary()
        
        self.assertIn("compatible_with_warnings", summary)
        self.assertIn("Warning 1", summary)

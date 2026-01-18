# Backup System Tests

This directory contains tests for the portal backup and restore system.

## Test Files

- `test_base.py` - Tests for BaseExporter and BaseImporter classes
- `test_registry.py` - Tests for ExporterRegistry and ImporterRegistry
- `test_manifest.py` - Tests for manifest generation and validation
- `test_version.py` - Tests for version compatibility checking
- `test_utils.py` - Tests for utility functions

## Running Tests

From the `cf-orcd-rental` directory:

```bash
# Run all backup tests
python -m pytest tests/test_backup/ -v

# Run a specific test file
python -m pytest tests/test_backup/test_base.py -v

# Run with coverage
python -m pytest tests/test_backup/ --cov=coldfront_orcd_direct_charge.backup
```

## Test Coverage

The tests cover:

1. **Base Classes**
   - ExportResult and ImportResult dataclasses
   - BaseExporter file I/O and serialization
   - BaseImporter import modes (create-only, update-only, create-or-update)
   - Dry-run functionality

2. **Registry**
   - Exporter/importer registration
   - Dependency resolution and topological sorting
   - Cyclic dependency detection
   - Include/exclude filtering

3. **Manifest**
   - Manifest creation and serialization
   - Save and load operations
   - Validation of required fields
   - Checksum calculation and verification

4. **Version Compatibility**
   - Semantic version parsing
   - Migration number parsing
   - Version compatibility checking
   - Schema compatibility checking
   - CompatibilityReport generation

5. **Utilities**
   - Date/time serialization
   - Decimal serialization
   - Directory operations

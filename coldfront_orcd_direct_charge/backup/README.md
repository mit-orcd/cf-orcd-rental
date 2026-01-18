# Portal Backup System

**Module**: `coldfront_orcd_direct_charge.backup`  
**Version**: 1.0.0  
**Last Updated**: 2026-01-18

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Technical Deep Dive](#technical-deep-dive)
4. [Usage Examples](#usage-examples)
5. [Keeping the Schema Updated](#keeping-the-schema-updated)
6. [Reference](#reference)

---

## Overview

The Portal Backup System provides a comprehensive solution for exporting and importing all plugin data. It enables:

- **Full data export** to a directory of JSON files with manifest
- **Data import** from another portal instance with conflict handling
- **Version compatibility checking** for safe migrations
- **Dependency-aware ordering** for correct import/export sequence

### Key Design Goals

| Goal | Implementation |
|------|----------------|
| **Portability** | Natural keys instead of database PKs |
| **Safety** | Compatibility checking before import |
| **Extensibility** | Registry pattern for adding new models |
| **Readability** | JSON format with human-readable structure |
| **Integrity** | Checksum verification for data validation |

---

## Architecture

### Module Structure

```
backup/
├── __init__.py              # Package exports
├── base.py                  # Abstract base classes
├── registry.py              # Exporter/Importer registries
├── manifest.py              # Manifest generation and validation
├── version.py               # Compatibility checking
├── utils.py                 # Shared utilities
├── exporters/               # Model-specific exporters
│   ├── __init__.py
│   ├── nodes.py             # NodeType, GpuNodeInstance, CpuNodeInstance
│   ├── reservations.py      # Reservation, ReservationMetadataEntry
│   ├── billing.py           # Cost allocations, snapshots, invoices
│   ├── users.py             # UserMaintenanceStatus, ProjectMemberRole
│   └── rates.py             # RentalSKU, RentalRate
└── importers/               # Model-specific importers
    ├── __init__.py
    ├── nodes.py
    ├── reservations.py
    ├── billing.py
    ├── users.py
    └── rates.py
```

### Class Hierarchy

```
BaseExporter (ABC)
├── NodeTypeExporter
├── GpuNodeInstanceExporter
├── CpuNodeInstanceExporter
├── ReservationExporter
├── ReservationMetadataEntryExporter
├── ProjectCostAllocationExporter
├── ProjectCostObjectExporter
├── CostAllocationSnapshotExporter
├── CostObjectSnapshotExporter
├── InvoicePeriodExporter
├── InvoiceLineOverrideExporter
├── UserMaintenanceStatusExporter
├── ProjectMemberRoleExporter
├── RentalSKUExporter
└── RentalRateExporter

BaseImporter (ABC)
└── (Mirror structure of exporters)
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        EXPORT FLOW                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ExporterRegistry                                                │
│       │                                                          │
│       ▼                                                          │
│  get_ordered_exporters()  ──► Topological sort by dependencies   │
│       │                                                          │
│       ▼                                                          │
│  For each Exporter:                                              │
│       │                                                          │
│       ├── get_queryset() ──► Django QuerySet                     │
│       │                                                          │
│       ├── serialize_record() ──► {natural_key, fields}           │
│       │                                                          │
│       └── export() ──► Write JSON to output_dir                  │
│                                                                   │
│  generate_manifest() ──► manifest.json with versions, checksums  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        IMPORT FLOW                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Load manifest.json                                              │
│       │                                                          │
│       ▼                                                          │
│  check_compatibility() ──► CompatibilityReport                   │
│       │                                                          │
│       ├── INCOMPATIBLE ──► Abort                                 │
│       ├── COMPATIBLE_WITH_WARNINGS ──► Warn, proceed with --force│
│       └── COMPATIBLE ──► Proceed                                 │
│                                                                   │
│  verify_checksum() ──► Validate data integrity                   │
│       │                                                          │
│       ▼                                                          │
│  ImporterRegistry.get_ordered_importers()                        │
│       │                                                          │
│       ▼                                                          │
│  For each Importer:                                              │
│       │                                                          │
│       ├── load_records() ──► Read JSON file                      │
│       │                                                          │
│       ├── get_existing(natural_key) ──► Find or None             │
│       │                                                          │
│       └── create_record() / update_record() based on mode        │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technical Deep Dive

### 1. Natural Keys

Natural keys allow records to be identified without relying on database primary keys, which vary between instances.

| Model | Natural Key | Rationale |
|-------|-------------|-----------|
| `NodeType` | `(name,)` | Name is unique |
| `GpuNodeInstance` | `(associated_resource_address,)` | Address is unique |
| `CpuNodeInstance` | `(associated_resource_address,)` | Address is unique |
| `Reservation` | `(pk,)` | No unique natural key; uses pk mapping |
| `UserMaintenanceStatus` | `(username,)` | One per user |
| `ProjectCostAllocation` | `(project_title,)` | One per project |
| `ProjectMemberRole` | `(project_title, username, role)` | Composite unique |
| `RentalSKU` | `(sku_code,)` | SKU code is unique |
| `RentalRate` | `(sku_code, effective_date)` | Unique together |
| `InvoicePeriod` | `(year, month)` | Unique together |

### 2. Dependency Resolution

The registry uses topological sorting to ensure dependencies are processed first:

```python
# Example dependency chain
NodeTypeExporter.dependencies = []
GpuNodeInstanceExporter.dependencies = ["node_types"]
ReservationExporter.dependencies = ["gpu_node_instances"]
ReservationMetadataEntryExporter.dependencies = ["reservations"]
```

**Sort Algorithm**: Kahn's algorithm (DFS-based) with cycle detection.

```python
def _topological_sort(cls, model_names: set) -> List[Type[BaseExporter]]:
    visited = set()
    in_progress = set()  # For cycle detection
    result = []
    
    def visit(name: str):
        if name in in_progress:
            raise CyclicDependencyError(...)
        if name in visited:
            return
        
        in_progress.add(name)
        for dep in exporter.dependencies:
            if dep in model_names:
                visit(dep)
        in_progress.remove(name)
        visited.add(name)
        result.append(exporter)
    
    for name in model_names:
        visit(name)
    return result
```

### 3. Export File Format

Each model exports to a separate JSON file:

```json
{
  "model": "node_types",
  "count": 5,
  "records": [
    {
      "natural_key": ["H200x8"],
      "fields": {
        "name": "H200x8",
        "category": "GPU",
        "description": "8x NVIDIA H200 GPUs",
        "is_active": true,
        "created": "2026-01-01T00:00:00-05:00",
        "modified": "2026-01-15T12:00:00-05:00"
      }
    }
  ]
}
```

### 4. Manifest Structure

```json
{
  "export_version": "1.0.0",
  "export_format": "orcd-portal-export",
  "created_at": "2026-01-17T14:45:00-05:00",
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
    "coldfront_orcd_direct_charge": "0024_last_migration_name"
  },
  "data_counts": {
    "node_types": 5,
    "gpu_node_instances": 20,
    "reservations": 150
  },
  "checksum": {
    "algorithm": "sha256",
    "value": "abc123..."
  }
}
```

### 5. Version Compatibility

**Semantic Versioning for Export Format**:
- `MAJOR`: Breaking changes (incompatible)
- `MINOR`: Backward-compatible additions (warnings)
- `PATCH`: Bug fixes (compatible)

**Compatibility Matrix**:

| Export Version | Target Version | Status |
|---------------|----------------|--------|
| 1.0.0 | 1.0.0 | ✅ Compatible |
| 1.0.0 | 1.1.0 | ✅ Compatible (new fields use defaults) |
| 1.1.0 | 1.0.0 | ⚠️ Warning (new fields ignored) |
| 1.x.x | 2.x.x | ❌ Incompatible |

**Schema Version Rules**:

| Export Schema | Target Schema | Status |
|--------------|---------------|--------|
| 0024 | 0024 | ✅ Compatible |
| 0020 | 0024 | ⚠️ Warning (4 migrations behind) |
| 0024 | 0020 | ❌ Incompatible (target needs migrations) |

### 6. Import Modes

| Mode | New Records | Existing Records |
|------|-------------|------------------|
| `create-only` | ✅ Create | ⏭️ Skip |
| `update-only` | ⏭️ Skip | ✅ Update |
| `create-or-update` | ✅ Create | ✅ Update |

### 7. Foreign Key Resolution

Foreign keys are stored as natural keys and resolved during import:

```python
def resolve_foreign_key(model_class, natural_key, field_name):
    if hasattr(model_class.objects, "get_by_natural_key"):
        return model_class.objects.get_by_natural_key(*natural_key)
    else:
        return model_class.objects.get(pk=natural_key[0])
```

### 8. PK Mapping for Dependents

Models without natural keys (like `Reservation`) use PK mapping:

```python
class ReservationImporter(BaseImporter):
    _pk_mapping: Dict[int, int] = {}  # old_pk -> new_pk
    
    def create_record(self, data):
        original_pk = data.get("natural_key", (None,))[0]
        instance = self.deserialize_record(data)
        instance.save()
        self._pk_mapping[original_pk] = instance.pk
        return instance
    
    @classmethod
    def get_new_pk(cls, original_pk):
        return cls._pk_mapping.get(original_pk)
```

---

## Usage Examples

### Export Commands

```bash
# Full export with timestamp directory
coldfront export_portal_data --output /backups/portal/

# Export to specific directory (no timestamp)
coldfront export_portal_data -o /backups/portal/my_export --no-timestamp

# Export specific models only
coldfront export_portal_data -o /backups/ \
    --models node_types,gpu_node_instances,cpu_node_instances

# Exclude specific models
coldfront export_portal_data -o /backups/ \
    --exclude reservation_metadata_entries,cost_object_snapshots

# Dry run (show what would be exported)
coldfront export_portal_data -o /backups/ --dry-run

# With source portal metadata
coldfront export_portal_data -o /backups/ \
    --source-url "https://portal.example.com" \
    --source-name "Production Portal"
```

### Import Commands

```bash
# Check compatibility first
coldfront check_import_compatibility /backups/portal/export_20260117/

# Dry run import (validate without changes)
coldfront import_portal_data /backups/portal/export_20260117/ --dry-run

# Validation only
coldfront import_portal_data /backups/portal/export_20260117/ --validate

# Full import (create or update)
coldfront import_portal_data /backups/portal/export_20260117/

# Create-only mode (skip existing records)
coldfront import_portal_data /backups/portal/export_20260117/ --mode create-only

# Update-only mode (skip new records)
coldfront import_portal_data /backups/portal/export_20260117/ --mode update-only

# Import specific models
coldfront import_portal_data /backups/portal/export_20260117/ \
    --models node_types,rental_skus,rental_rates

# Skip conflicts instead of failing
coldfront import_portal_data /backups/portal/export_20260117/ --skip-conflicts

# Force import with warnings
coldfront import_portal_data /backups/portal/export_20260117/ --force

# Skip checksum verification
coldfront import_portal_data /backups/portal/export_20260117/ --no-verify-checksum
```

### Compatibility Check

```bash
coldfront check_import_compatibility /backups/portal/export_20260117/

# Output:
# ============================================================
# EXPORT INFORMATION
# ============================================================
# Export Version:    1.0.0
# Export Format:     orcd-portal-export
# Created:           2026-01-17T14:45:00-05:00
# Source Portal:     Production Portal
# Source URL:        https://portal.example.com
# 
# ============================================================
# CURRENT INSTANCE
# ============================================================
# Export Version:    1.0.0
# Schema Version:    0024_add_rental_sku_metadata
# 
# ============================================================
# COMPATIBILITY CHECK
# ============================================================
# Status: COMPATIBLE
# 
# ============================================================
# DATA SUMMARY
# ============================================================
#   node_types                                        5 records
#   gpu_node_instances                               20 records
#   reservations                                    150 records
#   ...
# ------------------------------------------------------------
#   TOTAL                                           450 records
# 
# ============================================================
# RECOMMENDATION
# ============================================================
# ✓ This export is fully compatible and can be imported.
```

### Programmatic Usage

```python
from coldfront_orcd_direct_charge.backup import (
    ExporterRegistry,
    ImporterRegistry,
    Manifest,
    check_compatibility,
    generate_manifest,
)
from coldfront_orcd_direct_charge.backup.utils import create_export_directory

# Export
output_dir = create_export_directory("/backups/portal/")
data_counts = {}

for exporter_class in ExporterRegistry.get_ordered_exporters():
    exporter = exporter_class()
    result = exporter.export(output_dir)
    data_counts[exporter.model_name] = result.count

manifest = generate_manifest(output_dir, data_counts)
manifest.save(output_dir)

# Import
manifest = Manifest.from_file("/backups/portal/export_20260117/")
report = check_compatibility(manifest)

if report.is_safe_to_import():
    for importer_class in ImporterRegistry.get_ordered_importers():
        importer = importer_class()
        records = importer.load_records("/backups/portal/export_20260117/")
        result = importer.import_records(records, mode="create-or-update")
        print(f"{importer.model_name}: {result.created} created, {result.updated} updated")
```

---

## Keeping the Schema Updated

### When to Update the Backup System

The backup system must be updated when:

1. **New model added** to the plugin
2. **Model field added/removed/renamed**
3. **Model relationships changed**
4. **Natural key definition changed**

### Update Checklist

When modifying `models.py`:

```markdown
## Backup System Update Checklist

- [ ] Check if changes affect existing exporters/importers
- [ ] If new model: Create exporter in `backup/exporters/`
- [ ] If new model: Create importer in `backup/importers/`
- [ ] If new field: Update `serialize_record()` in exporter
- [ ] If new field: Update `deserialize_record()` in importer
- [ ] If new FK: Add to dependencies list
- [ ] If natural key changed: Update both exporter and importer
- [ ] Run tests: `pytest tests/test_backup/`
- [ ] Update EXPORT_VERSION if format changed
```

### Adding a New Model

#### Step 1: Create Exporter

```python
# backup/exporters/new_model.py

from ..base import BaseExporter
from ..registry import ExporterRegistry
from ..utils import serialize_datetime
from ...models import NewModel

@ExporterRegistry.register
class NewModelExporter(BaseExporter):
    """Exporter for NewModel.
    
    Natural key: (unique_field,)
    Dependencies: List any models this references
    """
    
    model_name = "new_models"  # Used as filename: new_models.json
    dependencies = ["parent_models"]  # Models that must export first
    
    def get_queryset(self):
        """Return QuerySet with select_related for efficiency."""
        return NewModel.objects.select_related("parent").order_by("unique_field")
    
    def serialize_record(self, instance):
        """Convert to exportable dict with natural keys."""
        return {
            "natural_key": instance.natural_key(),  # or (instance.unique_field,)
            "fields": {
                "unique_field": instance.unique_field,
                "parent": instance.parent.natural_key() if instance.parent else None,
                "data_field": instance.data_field,
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }
```

#### Step 2: Create Importer

```python
# backup/importers/new_model.py

from ..base import BaseImporter
from ..registry import ImporterRegistry
from ..utils import resolve_foreign_key
from ...models import NewModel, ParentModel

@ImporterRegistry.register
class NewModelImporter(BaseImporter):
    """Importer for NewModel."""
    
    model_name = "new_models"
    dependencies = ["parent_models"]
    
    def get_existing(self, natural_key):
        """Find by natural key."""
        if not natural_key:
            return None
        unique_field = natural_key[0]
        try:
            return NewModel.objects.get(unique_field=unique_field)
        except NewModel.DoesNotExist:
            return None
    
    def deserialize_record(self, data):
        """Create unsaved model instance."""
        fields = data.get("fields", {})
        
        parent = resolve_foreign_key(
            ParentModel, 
            fields.get("parent"),
            "parent"
        )
        
        return NewModel(
            unique_field=fields["unique_field"],
            parent=parent,
            data_field=fields.get("data_field", ""),
        )
    
    def create_record(self, data):
        instance = self.deserialize_record(data)
        instance.save()
        return instance
    
    def update_record(self, existing, data):
        fields = data.get("fields", {})
        existing.data_field = fields.get("data_field", existing.data_field)
        existing.save()
        return existing
```

#### Step 3: Register in Package `__init__.py`

```python
# backup/exporters/__init__.py
from . import new_model  # Add this line

# backup/importers/__init__.py
from . import new_model  # Add this line
```

#### Step 4: Add Tests

```python
# tests/test_backup/test_new_model.py

class TestNewModelExporter(TestCase):
    def test_serialize_record(self):
        # Test serialization
        pass
    
    def test_export(self):
        # Test full export
        pass

class TestNewModelImporter(TestCase):
    def test_import_create(self):
        # Test creating new records
        pass
    
    def test_import_update(self):
        # Test updating existing records
        pass
```

### Updating an Existing Model

When adding a new field:

```python
# In exporter's serialize_record():
def serialize_record(self, instance):
    return {
        "natural_key": instance.natural_key(),
        "fields": {
            # ... existing fields ...
            "new_field": instance.new_field,  # Add new field
        }
    }

# In importer's deserialize_record():
def deserialize_record(self, data):
    fields = data.get("fields", {})
    return Model(
        # ... existing fields ...
        new_field=fields.get("new_field", default_value),  # Handle missing
    )

# In importer's update_record():
def update_record(self, existing, data):
    fields = data.get("fields", {})
    # ... existing updates ...
    existing.new_field = fields.get("new_field", existing.new_field)
    existing.save()
    return existing
```

### Version Bumping

Update `EXPORT_VERSION` in `manifest.py`:

| Change Type | Version Bump | Example |
|-------------|--------------|---------|
| Bug fix in export logic | PATCH | 1.0.0 → 1.0.1 |
| New optional field added | MINOR | 1.0.1 → 1.1.0 |
| Field removed or renamed | MAJOR | 1.1.0 → 2.0.0 |
| New model added | MINOR | 1.1.0 → 1.2.0 |
| Export structure changed | MAJOR | 1.2.0 → 2.0.0 |

---

## Reference

### Exported Models

| Model | Exporter | Natural Key | Dependencies |
|-------|----------|-------------|--------------|
| `NodeType` | `NodeTypeExporter` | `(name,)` | None |
| `GpuNodeInstance` | `GpuNodeInstanceExporter` | `(address,)` | `node_types` |
| `CpuNodeInstance` | `CpuNodeInstanceExporter` | `(address,)` | `node_types` |
| `Reservation` | `ReservationExporter` | `(pk,)` | `gpu_node_instances` |
| `ReservationMetadataEntry` | `ReservationMetadataEntryExporter` | `(pk,)` | `reservations` |
| `ProjectCostAllocation` | `ProjectCostAllocationExporter` | `(project,)` | None |
| `ProjectCostObject` | `ProjectCostObjectExporter` | `(pk,)` | `project_cost_allocations` |
| `CostAllocationSnapshot` | `CostAllocationSnapshotExporter` | `(pk,)` | `project_cost_allocations` |
| `CostObjectSnapshot` | `CostObjectSnapshotExporter` | `(pk,)` | `cost_allocation_snapshots` |
| `InvoicePeriod` | `InvoicePeriodExporter` | `(year, month)` | None |
| `InvoiceLineOverride` | `InvoiceLineOverrideExporter` | `(pk,)` | `invoice_periods`, `reservations` |
| `UserMaintenanceStatus` | `UserMaintenanceStatusExporter` | `(username,)` | None |
| `ProjectMemberRole` | `ProjectMemberRoleExporter` | `(project, user, role)` | None |
| `RentalSKU` | `RentalSKUExporter` | `(sku_code,)` | None |
| `RentalRate` | `RentalRateExporter` | `(sku_code, date)` | `rental_skus` |

### Management Commands

| Command | Description |
|---------|-------------|
| `export_portal_data` | Export data to JSON files |
| `import_portal_data` | Import data from export directory |
| `check_import_compatibility` | Check if export is compatible |

### Key Classes

| Class | Module | Purpose |
|-------|--------|---------|
| `BaseExporter` | `base.py` | Abstract base for exporters |
| `BaseImporter` | `base.py` | Abstract base for importers |
| `ExportResult` | `base.py` | Result of export operation |
| `ImportResult` | `base.py` | Result of import operation |
| `ExporterRegistry` | `registry.py` | Exporter registration and ordering |
| `ImporterRegistry` | `registry.py` | Importer registration and ordering |
| `Manifest` | `manifest.py` | Export metadata and versions |
| `CompatibilityReport` | `version.py` | Compatibility check results |

### Constants

| Constant | Location | Value | Purpose |
|----------|----------|-------|---------|
| `EXPORT_FORMAT` | `manifest.py` | `"orcd-portal-export"` | Format identifier |
| `EXPORT_VERSION` | `manifest.py` | `"1.0.0"` | Current export format version |
| `MANIFEST_FILENAME` | `manifest.py` | `"manifest.json"` | Manifest filename |

---

## Appendix: AI Agent Instructions

When updating the backup system, AI agents should follow these rules:

### Rule 1: Always Update Both Exporter and Importer

When modifying a model, update both the exporter and importer to maintain symmetry.

### Rule 2: Use Natural Keys for Portability

Never serialize primary keys as the main identifier. Always use natural keys that remain consistent across database instances.

### Rule 3: Handle Missing Fields Gracefully

Importers should always provide defaults for optional fields:

```python
field_value = fields.get("field_name", default_value)
```

### Rule 4: Maintain Dependency Order

When adding a model that references another, add it to the `dependencies` list:

```python
dependencies = ["referenced_model_name"]
```

### Rule 5: Register in `__init__.py`

After creating new exporter/importer files, import them in the package `__init__.py`.

### Rule 6: Test After Changes

Run tests to verify changes don't break existing functionality:

```bash
python -m pytest tests/test_backup/ -v
```

### Rule 7: Bump Version When Needed

Update `EXPORT_VERSION` according to semantic versioning rules when making format changes.

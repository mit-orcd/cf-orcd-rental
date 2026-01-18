# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Base classes for export/import operations.

This module provides abstract base classes that define the interface
for all exporters and importers. Each model or group of related models
should have a corresponding exporter/importer that inherits from these.

Architecture:
    BaseExporter -> NodeTypeExporter, GpuNodeInstanceExporter, etc.
    BaseImporter -> NodeTypeImporter, GpuNodeInstanceImporter, etc.

The base classes handle common operations:
    - File I/O for JSON serialization
    - Progress tracking and error collection
    - Dependency ordering validation
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExportResult:
    """Result of an export operation.
    
    Attributes:
        model_name: Identifier for the exported model (e.g., "node_types")
        count: Number of records exported
        file_path: Path to the output JSON file
        success: Whether the export completed without errors
        errors: List of error messages encountered
        warnings: List of warning messages (non-fatal issues)
    """
    model_name: str
    count: int
    file_path: str
    success: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ImportResult:
    """Result of an import operation.
    
    Attributes:
        model_name: Identifier for the imported model
        created: Number of new records created
        updated: Number of existing records updated
        skipped: Number of records skipped (conflicts, etc.)
        errors: List of error messages encountered
        warnings: List of warning messages (non-fatal issues)
    """
    model_name: str
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        """Total number of records processed."""
        return self.created + self.updated + self.skipped

    @property
    def success(self) -> bool:
        """Whether the import completed without errors."""
        return len(self.errors) == 0


class BaseExporter(ABC):
    """Abstract base class for model exporters.
    
    Subclasses must implement:
        - model_name: Unique identifier for this exporter
        - dependencies: List of model_names that must be exported first
        - get_queryset(): Returns QuerySet of records to export
        - serialize_record(): Converts a model instance to dict
    
    The base class provides:
        - export(): Main entry point that handles file I/O
        - get_filename(): Generates consistent output filenames
    
    Example:
        @ExporterRegistry.register
        class NodeTypeExporter(BaseExporter):
            model_name = "node_types"
            dependencies = []
            
            def get_queryset(self):
                return NodeType.objects.all()
            
            def serialize_record(self, instance):
                return {
                    "natural_key": instance.natural_key(),
                    "fields": {"name": instance.name, ...}
                }
    """
    
    # Subclasses must define these
    model_name: str = ""
    dependencies: List[str] = []
    
    @abstractmethod
    def get_queryset(self):
        """Return QuerySet of records to export.
        
        Should use select_related/prefetch_related for efficiency.
        
        Returns:
            Django QuerySet
        """
        pass
    
    @abstractmethod
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Convert model instance to exportable dict with natural keys.
        
        The returned dict should contain:
            - natural_key: Tuple or value for identifying the record
            - fields: Dict of field values to export
            - Timestamps should be ISO format strings
        
        Args:
            instance: Model instance to serialize
            
        Returns:
            Dict suitable for JSON serialization
        """
        pass
    
    def get_filename(self) -> str:
        """Generate the output filename for this exporter.
        
        Returns:
            Filename like "node_types.json"
        """
        return f"{self.model_name}.json"
    
    def export(self, output_dir: str) -> ExportResult:
        """Export all records to JSON file.
        
        Creates a JSON file in output_dir containing all serialized records.
        The file includes metadata for traceability.
        
        Args:
            output_dir: Directory path for output files
            
        Returns:
            ExportResult with counts and status
        """
        output_path = Path(output_dir) / self.get_filename()
        errors: List[str] = []
        warnings: List[str] = []
        records: List[Dict[str, Any]] = []
        
        try:
            queryset = self.get_queryset()
            total = queryset.count()
            
            logger.info(f"Exporting {total} {self.model_name} records...")
            
            for instance in queryset:
                try:
                    record = self.serialize_record(instance)
                    records.append(record)
                except Exception as e:
                    errors.append(f"Error serializing {instance}: {e}")
                    logger.error(f"Error serializing {self.model_name} record: {e}")
            
            # Write to file
            export_data = {
                "model": self.model_name,
                "count": len(records),
                "records": records,
            }
            
            with open(output_path, "w") as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"Exported {len(records)} {self.model_name} records to {output_path}")
            
        except Exception as e:
            errors.append(f"Export failed: {e}")
            logger.error(f"Export failed for {self.model_name}: {e}")
            return ExportResult(
                model_name=self.model_name,
                count=0,
                file_path=str(output_path),
                success=False,
                errors=errors,
                warnings=warnings,
            )
        
        return ExportResult(
            model_name=self.model_name,
            count=len(records),
            file_path=str(output_path),
            success=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )


class BaseImporter(ABC):
    """Abstract base class for model importers.
    
    Subclasses must implement:
        - model_name: Unique identifier for this importer
        - dependencies: List of model_names that must be imported first
        - get_existing(): Find existing record by natural key
        - deserialize_record(): Convert dict to model instance
        - create_record(): Create a new record in the database
        - update_record(): Update an existing record
    
    The base class provides:
        - import_records(): Main entry point for importing
        - load_records(): Load records from JSON file
    
    Import Modes:
        - "create-only": Only create new records, skip existing
        - "update-only": Only update existing records, skip new
        - "create-or-update": Create new or update existing (default)
    """
    
    # Subclasses must define these
    model_name: str = ""
    dependencies: List[str] = []
    
    @abstractmethod
    def get_existing(self, natural_key) -> Optional[Any]:
        """Find existing record by natural key.
        
        Args:
            natural_key: The natural key value(s) to search for
            
        Returns:
            Model instance if found, None otherwise
        """
        pass
    
    @abstractmethod
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Convert dict to model instance (unsaved).
        
        Creates a new model instance populated with data from the export.
        Does NOT save to the database.
        
        Args:
            data: Dict from export file with natural_key and fields
            
        Returns:
            Unsaved model instance
        """
        pass
    
    @abstractmethod
    def create_record(self, data: Dict[str, Any]) -> Any:
        """Create a new record in the database.
        
        Args:
            data: Dict from export file
            
        Returns:
            Created model instance
        """
        pass
    
    @abstractmethod
    def update_record(self, existing: Any, data: Dict[str, Any]) -> Any:
        """Update an existing record.
        
        Args:
            existing: Existing model instance
            data: Dict from export file with new values
            
        Returns:
            Updated model instance
        """
        pass
    
    def get_filename(self) -> str:
        """Generate the expected input filename for this importer.
        
        Returns:
            Filename like "node_types.json"
        """
        return f"{self.model_name}.json"
    
    def load_records(self, import_dir: str) -> List[Dict[str, Any]]:
        """Load records from JSON file.
        
        Args:
            import_dir: Directory containing export files
            
        Returns:
            List of record dicts
            
        Raises:
            FileNotFoundError: If the expected file doesn't exist
        """
        import_path = Path(import_dir) / self.get_filename()
        
        if not import_path.exists():
            raise FileNotFoundError(f"Import file not found: {import_path}")
        
        with open(import_path, "r") as f:
            data = json.load(f)
        
        return data.get("records", [])
    
    def import_records(
        self,
        records: List[Dict[str, Any]],
        mode: str = "create-or-update",
        dry_run: bool = False,
    ) -> ImportResult:
        """Import records from list of dicts.
        
        Args:
            records: List of record dicts from export file
            mode: One of "create-only", "update-only", "create-or-update"
            dry_run: If True, validate but don't save to database
            
        Returns:
            ImportResult with counts and status
        """
        result = ImportResult(model_name=self.model_name)
        
        for record in records:
            try:
                natural_key = record.get("natural_key")
                existing = self.get_existing(natural_key)
                
                if existing:
                    if mode == "create-only":
                        result.skipped += 1
                        continue
                    
                    if not dry_run:
                        self.update_record(existing, record)
                    result.updated += 1
                    
                else:
                    if mode == "update-only":
                        result.skipped += 1
                        continue
                    
                    if not dry_run:
                        self.create_record(record)
                    result.created += 1
                    
            except Exception as e:
                result.errors.append(f"Error importing record {record.get('natural_key')}: {e}")
                logger.error(f"Error importing {self.model_name} record: {e}")
        
        action = "Would import" if dry_run else "Imported"
        logger.info(
            f"{action} {self.model_name}: "
            f"{result.created} created, {result.updated} updated, {result.skipped} skipped"
        )
        
        return result

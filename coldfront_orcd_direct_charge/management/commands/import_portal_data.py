# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Import portal data from JSON export.

This management command imports portal data from a previously exported directory.
It supports both the v2.0 two-directory structure and legacy v1.0 flat exports.

Export Structure (v2.0):
    export_YYYYMMDD_HHMMSS/
    ├── manifest.json           # Root manifest
    ├── coldfront_core/
    │   ├── manifest.json       # Core manifest
    │   └── *.json              # Core data files
    └── orcd_plugin/
        ├── manifest.json       # Plugin manifest
        └── *.json              # Plugin data files

Usage:
    coldfront import_portal_data /path/to/export/ --dry-run
    coldfront import_portal_data /path/to/export/ --component coldfront_core
    coldfront import_portal_data /path/to/export/ --component orcd_plugin
    coldfront import_portal_data /path/to/export/ --mode create-only

Example:
    # Preview what would be imported (all components)
    coldfront import_portal_data /backups/portal/export_20260117/ --dry-run
    
    # Import only ColdFront core data
    coldfront import_portal_data /backups/portal/export_20260117/ --component coldfront_core
    
    # Import only plugin data
    coldfront import_portal_data /backups/portal/export_20260117/ --component orcd_plugin
    
    # Import only new records
    coldfront import_portal_data /backups/portal/export_20260117/ --mode create-only
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from coldfront_orcd_direct_charge.backup import (
    CoreImporterRegistry,
    PluginImporterRegistry,
    Manifest,
    RootManifest,
    check_compatibility,
    CompatibilityStatus,
    COMPONENT_COLDFRONT_CORE,
    COMPONENT_ORCD_PLUGIN,
)
from coldfront_orcd_direct_charge.backup.manifest import (
    verify_checksum,
    MANIFEST_FILENAME,
)
from coldfront_orcd_direct_charge.backup.utils import validate_import_directory
# Import importers to register them
from coldfront_orcd_direct_charge.backup import importers  # noqa: F401


class Command(BaseCommand):
    """Import portal data from JSON export."""
    
    help = "Import portal data from a previously exported JSON backup"
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "export_path",
            help="Path to export directory containing manifest.json and data files.",
        )
        parser.add_argument(
            "--component",
            choices=[COMPONENT_COLDFRONT_CORE, COMPONENT_ORCD_PLUGIN, "all"],
            default="all",
            help=(
                f"Component to import: {COMPONENT_COLDFRONT_CORE}, "
                f"{COMPONENT_ORCD_PLUGIN}, or all (default: all)"
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and show what would be imported without making changes.",
        )
        parser.add_argument(
            "--validate",
            action="store_true",
            help="Only validate the export, don't import.",
        )
        parser.add_argument(
            "--mode",
            choices=["create-only", "update-only", "create-or-update"],
            default="create-or-update",
            help=(
                "Import mode: create-only (skip existing), "
                "update-only (skip new), create-or-update (default)."
            ),
        )
        parser.add_argument(
            "--skip-conflicts",
            action="store_true",
            help="Skip records that would cause conflicts instead of failing.",
        )
        parser.add_argument(
            "--models",
            help="Comma-separated list of models to import (default: all in component).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Proceed even with compatibility warnings.",
        )
        parser.add_argument(
            "--no-verify-checksum",
            action="store_true",
            help="Skip checksum verification.",
        )
    
    def handle(self, *args, **options):
        """Execute the import command."""
        export_path = Path(options["export_path"])
        dry_run = options["dry_run"]
        validate_only = options["validate"]
        component_filter = options["component"]
        mode = options["mode"]
        skip_conflicts = options["skip_conflicts"]
        force = options["force"]
        
        # Validate export directory
        if not export_path.is_dir():
            raise CommandError(f"Export path does not exist: {export_path}")
        
        manifest_path = export_path / MANIFEST_FILENAME
        if not manifest_path.exists():
            raise CommandError(
                f"Invalid export directory: {export_path}\n"
                "Expected a directory containing manifest.json"
            )
        
        # Detect export format version
        is_v2_export = self._is_v2_export(export_path)
        
        if is_v2_export:
            self._handle_v2_import(
                export_path,
                component_filter,
                mode,
                skip_conflicts,
                dry_run,
                validate_only,
                force,
                options,
            )
        else:
            self._handle_v1_import(
                export_path,
                mode,
                skip_conflicts,
                dry_run,
                validate_only,
                force,
                options,
            )
    
    def _is_v2_export(self, export_path: Path) -> bool:
        """Check if this is a v2.0 export with component subdirectories."""
        # V2 exports have component subdirectories
        core_dir = export_path / COMPONENT_COLDFRONT_CORE
        plugin_dir = export_path / COMPONENT_ORCD_PLUGIN
        
        return core_dir.is_dir() or plugin_dir.is_dir()
    
    def _handle_v2_import(
        self,
        export_path: Path,
        component_filter: str,
        mode: str,
        skip_conflicts: bool,
        dry_run: bool,
        validate_only: bool,
        force: bool,
        options: dict,
    ):
        """Handle v2.0 export with component subdirectories."""
        self.stdout.write(f"Loading root manifest from {export_path}...")
        
        try:
            root_manifest = RootManifest.from_file(str(export_path))
        except Exception as e:
            raise CommandError(f"Failed to load root manifest: {e}")
        
        self.stdout.write(f"Export version: {root_manifest.export_version}")
        self.stdout.write(f"Created: {root_manifest.created_at}")
        self.stdout.write(f"Source: {root_manifest.source_portal.get('name', 'Unknown')}")
        self.stdout.write(f"Components: {', '.join(root_manifest.get_component_names())}")
        self.stdout.write(f"Total records: {root_manifest.total_records}")
        
        # Determine which components to import
        import_core = component_filter in ["all", COMPONENT_COLDFRONT_CORE]
        import_plugin = component_filter in ["all", COMPONENT_ORCD_PLUGIN]
        
        # Verify checksum
        if not options["no_verify_checksum"]:
            self.stdout.write("\nVerifying checksum...")
            # For v2, we'd verify the root checksum
            if root_manifest.checksum:
                from coldfront_orcd_direct_charge.backup.manifest import calculate_checksum
                actual = calculate_checksum(str(export_path))
                if actual["value"] == root_manifest.checksum.get("value"):
                    self.stdout.write(self.style.SUCCESS("Checksum verified"))
                else:
                    if not force:
                        raise CommandError("Checksum verification failed. Use --force to proceed.")
                    self.stdout.write(self.style.WARNING("Checksum verification failed (--force used)"))
        
        if validate_only:
            self.stdout.write(self.style.SUCCESS("\nValidation complete."))
            return
        
        # Import components in order (core first, then plugin)
        all_results = []
        
        if import_core and root_manifest.has_component(COMPONENT_COLDFRONT_CORE):
            core_results = self._import_component(
                export_path=export_path / COMPONENT_COLDFRONT_CORE,
                component_name=COMPONENT_COLDFRONT_CORE,
                registry=CoreImporterRegistry,
                mode=mode,
                skip_conflicts=skip_conflicts,
                dry_run=dry_run,
                force=force,
                options=options,
            )
            all_results.extend(core_results)
        
        if import_plugin and root_manifest.has_component(COMPONENT_ORCD_PLUGIN):
            plugin_results = self._import_component(
                export_path=export_path / COMPONENT_ORCD_PLUGIN,
                component_name=COMPONENT_ORCD_PLUGIN,
                registry=PluginImporterRegistry,
                mode=mode,
                skip_conflicts=skip_conflicts,
                dry_run=dry_run,
                force=force,
                options=options,
            )
            all_results.extend(plugin_results)
        
        # Summary
        self._print_summary(all_results, dry_run)
    
    def _handle_v1_import(
        self,
        export_path: Path,
        mode: str,
        skip_conflicts: bool,
        dry_run: bool,
        validate_only: bool,
        force: bool,
        options: dict,
    ):
        """Handle legacy v1.0 flat export (backward compatibility)."""
        self.stdout.write(f"Loading manifest from {export_path}...")
        self.stdout.write(self.style.WARNING("Note: This appears to be a v1.0 export format"))
        
        try:
            manifest = Manifest.from_file(str(export_path))
        except Exception as e:
            raise CommandError(f"Failed to load manifest: {e}")
        
        self.stdout.write(f"Export version: {manifest.export_version}")
        self.stdout.write(f"Created: {manifest.created_at}")
        self.stdout.write(f"Source: {manifest.source_portal.get('name', 'Unknown')}")
        
        # Check compatibility
        self.stdout.write("\nChecking compatibility...")
        report = check_compatibility(manifest)
        
        self.stdout.write(f"Status: {report.status.value}")
        
        if report.warnings:
            self.stdout.write(self.style.WARNING("\nWarnings:"))
            for warning in report.warnings:
                self.stdout.write(self.style.WARNING(f"  - {warning}"))
        
        if report.errors:
            self.stdout.write(self.style.ERROR("\nErrors:"))
            for error in report.errors:
                self.stdout.write(self.style.ERROR(f"  - {error}"))
        
        if report.status == CompatibilityStatus.INCOMPATIBLE:
            raise CommandError("Import cannot proceed due to compatibility errors.")
        
        if report.status == CompatibilityStatus.COMPATIBLE_WITH_WARNINGS and not force:
            if not dry_run and not validate_only:
                raise CommandError("Import aborted due to warnings. Use --force to proceed.")
        
        # Verify checksum
        if not options["no_verify_checksum"]:
            self.stdout.write("\nVerifying checksum...")
            if verify_checksum(manifest, str(export_path)):
                self.stdout.write(self.style.SUCCESS("Checksum verified"))
            else:
                if not force:
                    raise CommandError("Checksum verification failed. Use --force to proceed.")
                self.stdout.write(self.style.WARNING("Checksum verification failed (--force used)"))
        
        # Show data counts
        self.stdout.write("\nData in export:")
        for model_name, count in manifest.data_counts.items():
            self.stdout.write(f"  {model_name}: {count} records")
        
        if validate_only:
            self.stdout.write(self.style.SUCCESS("\nValidation complete."))
            return
        
        # Import using plugin registry (v1 only exported plugin data)
        results = self._import_component(
            export_path=export_path,
            component_name="legacy",
            registry=PluginImporterRegistry,
            mode=mode,
            skip_conflicts=skip_conflicts,
            dry_run=dry_run,
            force=force,
            options=options,
        )
        
        self._print_summary(results, dry_run)
    
    def _import_component(
        self,
        export_path: Path,
        component_name: str,
        registry,
        mode: str,
        skip_conflicts: bool,
        dry_run: bool,
        force: bool,
        options: dict,
    ):
        """Import a single component.
        
        Returns:
            List of ImportResult objects
        """
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"Importing component: {component_name}")
        self.stdout.write("=" * 60)
        
        # Load component manifest if it exists
        component_manifest_path = export_path / MANIFEST_FILENAME
        if component_manifest_path.exists():
            try:
                component_manifest = Manifest.from_file(str(export_path))
                self.stdout.write(f"Component version: {component_manifest.export_version}")
            except Exception:
                pass
        
        # Parse model filters
        include_models = None
        if options.get("models"):
            include_models = [m.strip() for m in options["models"].split(",")]
        
        # Get ordered importers
        try:
            importers_list = registry.get_ordered_importers(include=include_models)
        except KeyError as e:
            self.stdout.write(self.style.WARNING(f"Warning: {e}"))
            return []
        
        if not importers_list:
            self.stdout.write(f"No importers available for {component_name}")
            return []
        
        self.stdout.write(
            f"{'DRY RUN: Would import' if dry_run else 'Importing'} "
            f"{len(importers_list)} model types..."
        )
        
        # Run imports
        all_results = []
        
        try:
            with transaction.atomic():
                for importer_class in importers_list:
                    importer = importer_class()
                    model_name = importer.model_name
                    
                    # Load records from file
                    try:
                        records = self._load_records(export_path, model_name)
                    except FileNotFoundError:
                        self.stdout.write(f"  {model_name}: No export file, skipping")
                        continue
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"  {model_name}: Failed to load - {e}")
                        )
                        continue
                    
                    if not records:
                        self.stdout.write(f"  {model_name}: 0 records")
                        continue
                    
                    # Import records
                    try:
                        result = importer.import_records(
                            records,
                            mode=mode,
                            dry_run=dry_run,
                        )
                        all_results.append(result)
                        
                        status_parts = []
                        if result.created:
                            status_parts.append(f"{result.created} created")
                        if result.updated:
                            status_parts.append(f"{result.updated} updated")
                        if result.skipped:
                            status_parts.append(f"{result.skipped} skipped")
                        
                        status_str = ", ".join(status_parts) if status_parts else "no changes"
                        
                        if result.errors:
                            self.stdout.write(
                                self.style.ERROR(
                                    f"  {model_name}: {status_str}, {len(result.errors)} errors"
                                )
                            )
                            if not skip_conflicts:
                                for error in result.errors[:5]:  # Limit error output
                                    self.stdout.write(self.style.ERROR(f"    {error}"))
                                if len(result.errors) > 5:
                                    self.stdout.write(
                                        self.style.ERROR(
                                            f"    ... and {len(result.errors) - 5} more"
                                        )
                                    )
                        else:
                            self.stdout.write(
                                self.style.SUCCESS(f"  {model_name}: {status_str}")
                            )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"  {model_name}: Exception - {e}")
                        )
                
                # Rollback if dry run
                if dry_run:
                    transaction.set_rollback(True)
                    
        except Exception as e:
            raise CommandError(f"Import failed: {e}")
        
        return all_results
    
    def _load_records(self, export_path: Path, model_name: str):
        """Load records from a JSON file."""
        # Try both naming conventions
        file_path = export_path / f"{model_name}.json"
        
        if not file_path.exists():
            raise FileNotFoundError(f"No file for {model_name}")
        
        with open(file_path, "r") as f:
            data = json.load(f)
        
        return data.get("records", data)  # Handle both formats
    
    def _print_summary(self, all_results, dry_run: bool):
        """Print import summary."""
        total_created = sum(r.created for r in all_results)
        total_updated = sum(r.updated for r in all_results)
        total_skipped = sum(r.skipped for r in all_results)
        total_errors = sum(len(r.errors) for r in all_results)
        
        self.stdout.write("\n" + "=" * 60)
        action = "Would have" if dry_run else "Successfully"
        self.stdout.write(
            f"{action} imported: {total_created} created, "
            f"{total_updated} updated, {total_skipped} skipped"
        )
        
        if total_errors:
            self.stdout.write(self.style.ERROR(f"Total errors: {total_errors}"))

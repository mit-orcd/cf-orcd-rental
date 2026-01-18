# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Import portal data from JSON export.

This management command imports plugin data from a previously exported directory.
It validates compatibility before importing and supports dry-run mode.

Usage:
    coldfront import_portal_data /path/to/export/ --dry-run
    coldfront import_portal_data /path/to/export/ --validate
    coldfront import_portal_data /path/to/export/ --skip-conflicts
    coldfront import_portal_data /path/to/export/ --mode create-only

Example:
    # Preview what would be imported
    coldfront import_portal_data /backups/portal/export_20260117/ --dry-run
    
    # Import only new records
    coldfront import_portal_data /backups/portal/export_20260117/ --mode create-only
    
    # Import with conflict handling
    coldfront import_portal_data /backups/portal/export_20260117/ --skip-conflicts
"""

import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from coldfront_orcd_direct_charge.backup import (
    ImporterRegistry,
    Manifest,
    check_compatibility,
    CompatibilityStatus,
)
from coldfront_orcd_direct_charge.backup.manifest import verify_checksum
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
            help="Comma-separated list of models to import (default: all).",
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
        export_path = options["export_path"]
        dry_run = options["dry_run"]
        validate_only = options["validate"]
        mode = options["mode"]
        skip_conflicts = options["skip_conflicts"]
        force = options["force"]
        
        # Validate export directory
        if not validate_import_directory(export_path):
            raise CommandError(
                f"Invalid export directory: {export_path}\n"
                "Expected a directory containing manifest.json"
            )
        
        # Load manifest
        self.stdout.write(f"Loading manifest from {export_path}...")
        try:
            manifest = Manifest.from_file(export_path)
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
            self.stdout.write(
                self.style.WARNING(
                    "\nThere are compatibility warnings. Use --force to proceed."
                )
            )
            if not dry_run and not validate_only:
                raise CommandError("Import aborted due to warnings. Use --force to proceed.")
        
        # Verify checksum
        if not options["no_verify_checksum"]:
            self.stdout.write("\nVerifying checksum...")
            if verify_checksum(manifest, export_path):
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
        
        # Parse model filters
        include_models = None
        if options["models"]:
            include_models = [m.strip() for m in options["models"].split(",")]
        
        # Get ordered importers
        try:
            importers_list = ImporterRegistry.get_ordered_importers(include=include_models)
        except KeyError as e:
            raise CommandError(str(e))
        
        if not importers_list:
            raise CommandError("No importers available for the specified models.")
        
        self.stdout.write(f"\n{'DRY RUN: Would import' if dry_run else 'Importing'} {len(importers_list)} model types...")
        
        # Run imports
        all_results = []
        
        try:
            with transaction.atomic():
                for importer_class in importers_list:
                    importer = importer_class()
                    model_name = importer.model_name
                    
                    # Load records from file
                    try:
                        records = importer.load_records(export_path)
                    except FileNotFoundError:
                        self.stdout.write(f"  {model_name}: No export file, skipping")
                        continue
                    
                    if not records:
                        self.stdout.write(f"  {model_name}: 0 records")
                        continue
                    
                    # Import records
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
                            self.style.ERROR(f"  {model_name}: {status_str}, {len(result.errors)} errors")
                        )
                        if not skip_conflicts:
                            for error in result.errors:
                                self.stdout.write(self.style.ERROR(f"    {error}"))
                    else:
                        self.stdout.write(self.style.SUCCESS(f"  {model_name}: {status_str}"))
                
                # Rollback if dry run
                if dry_run:
                    transaction.set_rollback(True)
                    
        except Exception as e:
            raise CommandError(f"Import failed: {e}")
        
        # Summary
        total_created = sum(r.created for r in all_results)
        total_updated = sum(r.updated for r in all_results)
        total_skipped = sum(r.skipped for r in all_results)
        total_errors = sum(len(r.errors) for r in all_results)
        
        self.stdout.write("\n" + "=" * 50)
        action = "Would have" if dry_run else "Successfully"
        self.stdout.write(
            f"{action} imported: {total_created} created, {total_updated} updated, {total_skipped} skipped"
        )
        
        if total_errors:
            self.stdout.write(self.style.ERROR(f"Total errors: {total_errors}"))

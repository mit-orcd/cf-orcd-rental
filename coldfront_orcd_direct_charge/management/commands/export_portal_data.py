# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Export portal data to JSON files.

This management command exports all plugin data to a directory of JSON files.
The export includes a manifest with version information for compatibility checking.

Usage:
    coldfront export_portal_data --output /path/to/export/
    coldfront export_portal_data --output /path/ --models node_types,reservations
    coldfront export_portal_data --output /path/ --exclude-activity-log
    coldfront export_portal_data --output /path/ --dry-run

Example:
    # Export all data to a timestamped directory
    coldfront export_portal_data -o /backups/portal/
    
    # Export only node-related data
    coldfront export_portal_data -o /backups/portal/ --models node_types,gpu_node_instances
    
    # Preview what would be exported
    coldfront export_portal_data -o /backups/portal/ --dry-run
"""

import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from coldfront_orcd_direct_charge.backup import (
    ExporterRegistry,
    generate_manifest,
)
from coldfront_orcd_direct_charge.backup.utils import create_export_directory
# Import exporters to register them
from coldfront_orcd_direct_charge.backup import exporters  # noqa: F401


class Command(BaseCommand):
    """Export portal data to JSON files for backup or migration."""
    
    help = "Export portal data to JSON files for backup or migration"
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--output", "-o",
            required=True,
            help="Output directory for export files. A timestamped subdirectory will be created.",
        )
        parser.add_argument(
            "--models",
            help=(
                "Comma-separated list of models to export. "
                "Available: node_types, gpu_node_instances, cpu_node_instances, "
                "reservations, reservation_metadata_entries, project_cost_allocations, "
                "project_cost_objects, cost_allocation_snapshots, cost_object_snapshots, "
                "invoice_periods, invoice_line_overrides, user_maintenance_statuses, "
                "project_member_roles, rental_skus, rental_rates"
            ),
        )
        parser.add_argument(
            "--exclude",
            help="Comma-separated list of models to exclude from export.",
        )
        parser.add_argument(
            "--no-timestamp",
            action="store_true",
            help="Don't create timestamped subdirectory, use output path directly.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be exported without writing files.",
        )
        parser.add_argument(
            "--source-url",
            default="",
            help="URL of this portal instance (for manifest metadata).",
        )
        parser.add_argument(
            "--source-name",
            default="ORCD Rental Portal",
            help="Name of this portal instance (for manifest metadata).",
        )
    
    def handle(self, *args, **options):
        """Execute the export command."""
        output_path = options["output"]
        dry_run = options["dry_run"]
        
        # Parse model filters
        include_models = None
        if options["models"]:
            include_models = [m.strip() for m in options["models"].split(",")]
        
        exclude_models = None
        if options["exclude"]:
            exclude_models = [m.strip() for m in options["exclude"].split(",")]
        
        # Create export directory
        if dry_run:
            export_dir = output_path
            self.stdout.write("DRY RUN - No files will be written\n")
        else:
            use_timestamp = not options["no_timestamp"]
            export_dir = create_export_directory(output_path, timestamp=use_timestamp)
            self.stdout.write(f"Export directory: {export_dir}\n")
        
        # Get ordered exporters
        try:
            exporters_list = ExporterRegistry.get_ordered_exporters(
                include=include_models,
                exclude=exclude_models,
            )
        except KeyError as e:
            raise CommandError(str(e))
        
        if not exporters_list:
            raise CommandError("No exporters available for the specified models.")
        
        self.stdout.write(f"Exporting {len(exporters_list)} model types...\n")
        
        # Run exports
        data_counts = {}
        all_results = []
        
        for exporter_class in exporters_list:
            exporter = exporter_class()
            model_name = exporter.model_name
            
            if dry_run:
                # Just count records
                count = exporter.get_queryset().count()
                self.stdout.write(f"  {model_name}: {count} records")
                data_counts[model_name] = count
            else:
                result = exporter.export(export_dir)
                all_results.append(result)
                data_counts[model_name] = result.count
                
                if result.success:
                    self.stdout.write(
                        self.style.SUCCESS(f"  {model_name}: {result.count} records exported")
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f"  {model_name}: FAILED - {result.errors}")
                    )
                
                if result.warnings:
                    for warning in result.warnings:
                        self.stdout.write(self.style.WARNING(f"    Warning: {warning}"))
        
        # Generate and save manifest
        if not dry_run:
            manifest = generate_manifest(
                export_dir,
                data_counts,
                source_url=options["source_url"],
                source_name=options["source_name"],
            )
            manifest_path = manifest.save(export_dir)
            self.stdout.write(f"\nManifest saved: {manifest_path}")
        
        # Summary
        total_records = sum(data_counts.values())
        total_errors = sum(len(r.errors) for r in all_results) if all_results else 0
        
        self.stdout.write("\n" + "=" * 50)
        if dry_run:
            self.stdout.write(f"Would export {total_records} total records")
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Exported {total_records} total records to {export_dir}")
            )
            if total_errors > 0:
                self.stdout.write(
                    self.style.ERROR(f"Encountered {total_errors} errors")
                )
        
        # List available models if none were exported
        if not exporters_list:
            self.stdout.write("\nAvailable models:")
            for name in ExporterRegistry.get_all_model_names():
                self.stdout.write(f"  - {name}")

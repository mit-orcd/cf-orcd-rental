# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Export portal data to JSON files.

This management command exports portal data to a directory structure with
separate directories for ColdFront core, plugin data, and configuration,
each with its own manifest.

Export Structure:
    export_YYYYMMDD_HHMMSS/
    ├── manifest.json           # Root manifest
    ├── config/                 # Configuration settings
    │   ├── manifest.json       # Config manifest
    │   ├── plugin_config.json  # Plugin settings
    │   ├── coldfront_config.json # ColdFront settings
    │   ├── django_config.json  # Django settings
    │   └── environment.json    # Environment metadata
    ├── coldfront_core/
    │   ├── manifest.json       # Core manifest
    │   └── *.json              # Core data files
    └── orcd_plugin/
        ├── manifest.json       # Plugin manifest
        └── *.json              # Plugin data files

Usage:
    coldfront export_portal_data --output /path/to/export/
    coldfront export_portal_data --output /path/ --component coldfront_core
    coldfront export_portal_data --output /path/ --component orcd_plugin
    coldfront export_portal_data --output /path/ --no-config
    coldfront export_portal_data --output /path/ --dry-run

Example:
    # Export all data (core + plugin + config) to a timestamped directory
    coldfront export_portal_data -o /backups/portal/
    
    # Export only ColdFront core data
    coldfront export_portal_data -o /backups/portal/ --component coldfront_core
    
    # Export only plugin data
    coldfront export_portal_data -o /backups/portal/ --component orcd_plugin
    
    # Export without configuration
    coldfront export_portal_data -o /backups/portal/ --no-config
    
    # Preview what would be exported
    coldfront export_portal_data -o /backups/portal/ --dry-run
"""

import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from coldfront_orcd_direct_charge.backup import (
    CoreExporterRegistry,
    PluginExporterRegistry,
    COMPONENT_COLDFRONT_CORE,
    COMPONENT_ORCD_PLUGIN,
)
from coldfront_orcd_direct_charge.backup.manifest import (
    generate_component_manifest,
    generate_root_manifest,
    COMPONENT_CONFIG,
)
from coldfront_orcd_direct_charge.backup.utils import create_export_directory
from coldfront_orcd_direct_charge.backup.config_exporter import export_configuration
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
            "--component",
            choices=[COMPONENT_COLDFRONT_CORE, COMPONENT_ORCD_PLUGIN, "all"],
            default="all",
            help=(
                f"Component to export: {COMPONENT_COLDFRONT_CORE}, "
                f"{COMPONENT_ORCD_PLUGIN}, or all (default: all)"
            ),
        )
        parser.add_argument(
            "--models",
            help=(
                "Comma-separated list of models to export within the selected component. "
                "Use --list-models to see available models."
            ),
        )
        parser.add_argument(
            "--exclude",
            help="Comma-separated list of models to exclude from export.",
        )
        parser.add_argument(
            "--list-models",
            action="store_true",
            help="List available models for each component and exit.",
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
        parser.add_argument(
            "--no-config",
            action="store_true",
            help="Skip exporting configuration settings.",
        )
    
    def handle(self, *args, **options):
        """Execute the export command."""
        # Handle --list-models
        if options["list_models"]:
            self._list_models()
            return
        
        output_path = options["output"]
        dry_run = options["dry_run"]
        component = options["component"]
        
        # Parse model filters
        include_models = None
        if options["models"]:
            include_models = [m.strip() for m in options["models"].split(",")]
        
        exclude_models = None
        if options["exclude"]:
            exclude_models = [m.strip() for m in options["exclude"].split(",")]
        
        # Determine which components to export
        export_core = component in ["all", COMPONENT_COLDFRONT_CORE]
        export_plugin = component in ["all", COMPONENT_ORCD_PLUGIN]
        
        # Create export directory
        if dry_run:
            export_dir = output_path
            self.stdout.write("DRY RUN - No files will be written\n")
        else:
            use_timestamp = not options["no_timestamp"]
            export_dir = create_export_directory(output_path, timestamp=use_timestamp)
            self.stdout.write(f"Export directory: {export_dir}\n")
        
        component_data = {}
        
        # Export ColdFront core
        if export_core:
            core_data = self._export_component(
                registry=CoreExporterRegistry,
                component_name=COMPONENT_COLDFRONT_CORE,
                export_dir=export_dir,
                include_models=include_models if component == COMPONENT_COLDFRONT_CORE else None,
                exclude_models=exclude_models if component == COMPONENT_COLDFRONT_CORE else None,
                dry_run=dry_run,
                options=options,
            )
            if core_data:
                component_data[COMPONENT_COLDFRONT_CORE] = core_data
        
        # Export ORCD plugin
        if export_plugin:
            plugin_data = self._export_component(
                registry=PluginExporterRegistry,
                component_name=COMPONENT_ORCD_PLUGIN,
                export_dir=export_dir,
                include_models=include_models if component == COMPONENT_ORCD_PLUGIN else None,
                exclude_models=exclude_models if component == COMPONENT_ORCD_PLUGIN else None,
                dry_run=dry_run,
                options=options,
            )
            if plugin_data:
                component_data[COMPONENT_ORCD_PLUGIN] = plugin_data
        
        # Export configuration (unless --no-config specified)
        config_data = {}
        if not options.get("no_config"):
            config_data = self._export_config(export_dir, dry_run)
        
        # Generate root manifest
        if not dry_run and (component_data or config_data):
            # Include config in component_data for manifest
            all_component_data = component_data.copy()
            if config_data:
                all_component_data[COMPONENT_CONFIG] = config_data
            
            root_manifest = generate_root_manifest(
                export_dir,
                all_component_data,
                source_url=options["source_url"],
                source_name=options["source_name"],
            )
            manifest_path = root_manifest.save(export_dir)
            self.stdout.write(f"\nRoot manifest saved: {manifest_path}")
        
        # Summary
        total_records = sum(
            sum(counts.values()) 
            for counts in component_data.values()
        )
        total_settings = sum(config_data.values()) if config_data else 0
        
        self.stdout.write("\n" + "=" * 60)
        if dry_run:
            self.stdout.write(f"Would export {total_records} total records")
            if total_settings:
                self.stdout.write(f"Would export {total_settings} configuration settings")
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Exported {total_records} total records to {export_dir}")
            )
            if total_settings:
                self.stdout.write(
                    self.style.SUCCESS(f"Exported {total_settings} configuration settings")
                )
    
    def _export_component(
        self,
        registry,
        component_name: str,
        export_dir: str,
        include_models,
        exclude_models,
        dry_run: bool,
        options: dict,
    ) -> dict:
        """Export a single component (core or plugin).
        
        Returns:
            Dict of model_name -> record count
        """
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"Exporting component: {component_name}")
        self.stdout.write("=" * 60)
        
        # Get ordered exporters
        try:
            exporters_list = registry.get_ordered_exporters(
                include=include_models,
                exclude=exclude_models,
            )
        except KeyError as e:
            self.stdout.write(
                self.style.WARNING(f"Warning: {e}")
            )
            return {}
        
        if not exporters_list:
            self.stdout.write(f"No exporters available for {component_name}")
            return {}
        
        # Create component directory
        if not dry_run:
            component_dir = Path(export_dir) / component_name
            component_dir.mkdir(parents=True, exist_ok=True)
        else:
            component_dir = Path(export_dir) / component_name
        
        self.stdout.write(f"Exporting {len(exporters_list)} model types...")
        
        # Run exports
        data_counts = {}
        all_results = []
        
        for exporter_class in exporters_list:
            exporter = exporter_class()
            model_name = exporter.model_name
            
            if dry_run:
                # Just count records
                try:
                    count = exporter.get_queryset().count()
                    self.stdout.write(f"  {model_name}: {count} records")
                    data_counts[model_name] = count
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f"  {model_name}: Could not count - {e}")
                    )
                    data_counts[model_name] = 0
            else:
                try:
                    result = exporter.export(str(component_dir))
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
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  {model_name}: Exception - {e}")
                    )
                    data_counts[model_name] = 0
        
        # Generate component manifest
        if not dry_run and data_counts:
            manifest = generate_component_manifest(
                str(component_dir),
                component_name,
                data_counts,
                source_url=options["source_url"],
                source_name=options["source_name"],
            )
            manifest_path = manifest.save(str(component_dir))
            self.stdout.write(f"Component manifest saved: {manifest_path}")
        
        return data_counts
    
    def _export_config(self, export_dir: str, dry_run: bool) -> dict:
        """Export configuration settings.
        
        Args:
            export_dir: Root export directory
            dry_run: If True, don't write files
            
        Returns:
            Dict mapping category name to setting count
        """
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"Exporting component: {COMPONENT_CONFIG}")
        self.stdout.write("=" * 60)
        
        result = export_configuration(export_dir, dry_run=dry_run)
        
        if result.success:
            for category, count in result.categories.items():
                self.stdout.write(
                    self.style.SUCCESS(f"  {category}: {count} settings")
                )
            if not dry_run:
                self.stdout.write(f"Config manifest saved: {result.config_dir}/manifest.json")
        else:
            for error in result.errors:
                self.stdout.write(self.style.ERROR(f"  Error: {error}"))
        
        for warning in result.warnings:
            self.stdout.write(self.style.WARNING(f"  Warning: {warning}"))
        
        return result.categories
    
    def _list_models(self):
        """List available models for each component."""
        self.stdout.write("\nColdFront Core Models:")
        self.stdout.write("=" * 40)
        for name in sorted(CoreExporterRegistry.get_all_model_names()):
            self.stdout.write(f"  - {name}")
        
        self.stdout.write("\nORCD Plugin Models:")
        self.stdout.write("=" * 40)
        for name in sorted(PluginExporterRegistry.get_all_model_names()):
            self.stdout.write(f"  - {name}")

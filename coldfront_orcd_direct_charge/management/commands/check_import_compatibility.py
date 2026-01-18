# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Check if an export is compatible with this instance.

This management command validates an export directory and checks whether
it can be safely imported into the current portal instance.

Supports both v2.0 (two-directory structure) and v1.0 (flat) exports.

Usage:
    coldfront check_import_compatibility /path/to/export/
    coldfront check_import_compatibility /path/to/export/ --verbose

Example:
    coldfront check_import_compatibility /backups/portal/export_20260117/
"""

import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from coldfront_orcd_direct_charge.backup import (
    Manifest,
    RootManifest,
    check_compatibility,
    CompatibilityStatus,
    COMPONENT_COLDFRONT_CORE,
    COMPONENT_ORCD_PLUGIN,
)
from coldfront_orcd_direct_charge.backup.manifest import (
    verify_checksum,
    get_current_schema_version,
    get_software_versions,
    EXPORT_VERSION,
    MANIFEST_FILENAME,
)
from coldfront_orcd_direct_charge.backup.utils import validate_import_directory


class Command(BaseCommand):
    """Check if an export is compatible with this instance."""
    
    help = "Check if an export is compatible with this portal instance"
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "export_path",
            help="Path to export directory containing manifest.json.",
        )
        parser.add_argument(
            "--verbose", "-v",
            action="store_true",
            help="Show detailed information.",
        )
        parser.add_argument(
            "--verify-checksum",
            action="store_true",
            help="Also verify data integrity via checksum.",
        )
    
    def handle(self, *args, **options):
        """Execute the compatibility check."""
        export_path = Path(options["export_path"])
        verbose = options["verbose"]
        
        # Validate export directory
        if not export_path.is_dir():
            raise CommandError(f"Export path does not exist: {export_path}")
        
        manifest_path = export_path / MANIFEST_FILENAME
        if not manifest_path.exists():
            raise CommandError(
                f"Invalid export directory: {export_path}\n"
                "Expected a directory containing manifest.json"
            )
        
        self.stdout.write(f"Checking export: {export_path}\n")
        
        # Detect export format version
        is_v2 = self._is_v2_export(export_path)
        
        if is_v2:
            self._check_v2_export(export_path, verbose, options)
        else:
            self._check_v1_export(export_path, verbose, options)
    
    def _is_v2_export(self, export_path: Path) -> bool:
        """Check if this is a v2.0 export with component subdirectories."""
        core_dir = export_path / COMPONENT_COLDFRONT_CORE
        plugin_dir = export_path / COMPONENT_ORCD_PLUGIN
        return core_dir.is_dir() or plugin_dir.is_dir()
    
    def _check_v2_export(self, export_path: Path, verbose: bool, options: dict):
        """Check v2.0 export with component subdirectories."""
        try:
            root_manifest = RootManifest.from_file(str(export_path))
        except Exception as e:
            raise CommandError(f"Failed to load root manifest: {e}")
        
        # Show export info
        self.stdout.write("=" * 60)
        self.stdout.write("EXPORT INFORMATION (v2.0 Format)")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Export Version:    {root_manifest.export_version}")
        self.stdout.write(f"Export Format:     {root_manifest.export_format}")
        self.stdout.write(f"Created:           {root_manifest.created_at}")
        self.stdout.write(f"Source Portal:     {root_manifest.source_portal.get('name', 'Unknown')}")
        self.stdout.write(f"Source URL:        {root_manifest.source_portal.get('url', 'N/A')}")
        self.stdout.write(f"Components:        {', '.join(root_manifest.get_component_names())}")
        self.stdout.write(f"Total Records:     {root_manifest.total_records}")
        
        if verbose:
            sw = root_manifest.software_versions
            self.stdout.write(f"\nSoftware Versions (Export):")
            self.stdout.write(f"  ColdFront:       {sw.coldfront}")
            self.stdout.write(f"  Plugin:          {sw.coldfront_orcd_direct_charge}")
            self.stdout.write(f"  Django:          {sw.django}")
            self.stdout.write(f"  Python:          {sw.python}")
        
        # Show current instance info
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("CURRENT INSTANCE")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Export Version:    {EXPORT_VERSION}")
        self.stdout.write(f"Schema Version:    {get_current_schema_version()}")
        
        if verbose:
            current_sw = get_software_versions()
            self.stdout.write(f"\nSoftware Versions (Current):")
            self.stdout.write(f"  ColdFront:       {current_sw.coldfront}")
            self.stdout.write(f"  Plugin:          {current_sw.coldfront_orcd_direct_charge}")
            self.stdout.write(f"  Django:          {current_sw.django}")
            self.stdout.write(f"  Python:          {current_sw.python}")
        
        # Check each component
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("COMPONENT STATUS")
        self.stdout.write("=" * 60)
        
        all_warnings = []
        all_errors = []
        overall_status = CompatibilityStatus.COMPATIBLE
        
        for component_name in root_manifest.get_component_names():
            component_dir = export_path / component_name
            component_manifest_path = component_dir / MANIFEST_FILENAME
            
            if component_manifest_path.exists():
                try:
                    component_manifest = Manifest.from_file(str(component_dir))
                    component_info = root_manifest.components.get(component_name, {})
                    record_count = component_info.get("record_count", 0)
                    
                    self.stdout.write(
                        f"\n  {component_name}: {record_count} records"
                    )
                    
                    if verbose:
                        for model, count in component_info.get("data_counts", {}).items():
                            self.stdout.write(f"    - {model}: {count}")
                    
                    # Check component compatibility
                    report = check_compatibility(component_manifest)
                    all_warnings.extend(report.warnings)
                    all_errors.extend(report.errors)
                    
                    if report.status == CompatibilityStatus.INCOMPATIBLE:
                        overall_status = CompatibilityStatus.INCOMPATIBLE
                    elif (report.status == CompatibilityStatus.COMPATIBLE_WITH_WARNINGS 
                          and overall_status == CompatibilityStatus.COMPATIBLE):
                        overall_status = CompatibilityStatus.COMPATIBLE_WITH_WARNINGS
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f"  {component_name}: Could not load manifest - {e}")
                    )
        
        # Verify checksum if requested
        if options["verify_checksum"]:
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write("CHECKSUM VERIFICATION")
            self.stdout.write("=" * 60)
            
            if root_manifest.checksum:
                from coldfront_orcd_direct_charge.backup.manifest import calculate_checksum
                actual = calculate_checksum(str(export_path))
                if actual["value"] == root_manifest.checksum.get("value"):
                    self.stdout.write(self.style.SUCCESS("✓ Checksum verified"))
                else:
                    self.stdout.write(self.style.ERROR("✗ Checksum verification FAILED"))
                    all_errors.append("Checksum mismatch")
            else:
                self.stdout.write(self.style.WARNING("No checksum in manifest"))
        
        # Show warnings and errors
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("COMPATIBILITY CHECK")
        self.stdout.write("=" * 60)
        
        status_style = {
            CompatibilityStatus.COMPATIBLE: self.style.SUCCESS,
            CompatibilityStatus.COMPATIBLE_WITH_WARNINGS: self.style.WARNING,
            CompatibilityStatus.INCOMPATIBLE: self.style.ERROR,
        }
        
        self.stdout.write(
            f"Status: {status_style[overall_status](overall_status.value.upper())}"
        )
        
        if all_warnings:
            self.stdout.write(self.style.WARNING("\nWarnings:"))
            for warning in all_warnings:
                self.stdout.write(self.style.WARNING(f"  ⚠ {warning}"))
        
        if all_errors:
            self.stdout.write(self.style.ERROR("\nErrors:"))
            for error in all_errors:
                self.stdout.write(self.style.ERROR(f"  ✗ {error}"))
        
        # Final recommendation
        self._print_recommendation(overall_status, str(export_path))
    
    def _check_v1_export(self, export_path: Path, verbose: bool, options: dict):
        """Check v1.0 flat export (backward compatibility)."""
        try:
            manifest = Manifest.from_file(str(export_path))
        except Exception as e:
            raise CommandError(f"Failed to load manifest: {e}")
        
        # Show export info
        self.stdout.write("=" * 60)
        self.stdout.write("EXPORT INFORMATION (v1.0 Legacy Format)")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Export Version:    {manifest.export_version}")
        self.stdout.write(f"Export Format:     {manifest.export_format}")
        self.stdout.write(f"Created:           {manifest.created_at}")
        self.stdout.write(f"Source Portal:     {manifest.source_portal.get('name', 'Unknown')}")
        self.stdout.write(f"Source URL:        {manifest.source_portal.get('url', 'N/A')}")
        
        if verbose:
            sw = manifest.software_versions
            self.stdout.write(f"\nSoftware Versions (Export):")
            self.stdout.write(f"  ColdFront:       {sw.coldfront}")
            self.stdout.write(f"  Plugin:          {sw.coldfront_orcd_direct_charge}")
            self.stdout.write(f"  Django:          {sw.django}")
            self.stdout.write(f"  Python:          {sw.python}")
            
            self.stdout.write(f"\nSchema Versions (Export):")
            for app, version in manifest.schema_versions.items():
                self.stdout.write(f"  {app}: {version}")
        
        # Show current instance info
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("CURRENT INSTANCE")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Export Version:    {EXPORT_VERSION}")
        self.stdout.write(f"Schema Version:    {get_current_schema_version()}")
        
        if verbose:
            current_sw = get_software_versions()
            self.stdout.write(f"\nSoftware Versions (Current):")
            self.stdout.write(f"  ColdFront:       {current_sw.coldfront}")
            self.stdout.write(f"  Plugin:          {current_sw.coldfront_orcd_direct_charge}")
            self.stdout.write(f"  Django:          {current_sw.django}")
            self.stdout.write(f"  Python:          {current_sw.python}")
        
        # Check compatibility
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("COMPATIBILITY CHECK")
        self.stdout.write("=" * 60)
        
        report = check_compatibility(manifest)
        
        status_style = {
            CompatibilityStatus.COMPATIBLE: self.style.SUCCESS,
            CompatibilityStatus.COMPATIBLE_WITH_WARNINGS: self.style.WARNING,
            CompatibilityStatus.INCOMPATIBLE: self.style.ERROR,
        }
        
        self.stdout.write(
            f"Status: {status_style[report.status](report.status.value.upper())}"
        )
        
        if report.warnings:
            self.stdout.write(self.style.WARNING("\nWarnings:"))
            for warning in report.warnings:
                self.stdout.write(self.style.WARNING(f"  ⚠ {warning}"))
        
        if report.errors:
            self.stdout.write(self.style.ERROR("\nErrors:"))
            for error in report.errors:
                self.stdout.write(self.style.ERROR(f"  ✗ {error}"))
        
        # Verify checksum if requested
        if options["verify_checksum"]:
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write("CHECKSUM VERIFICATION")
            self.stdout.write("=" * 60)
            
            if verify_checksum(manifest, str(export_path)):
                self.stdout.write(self.style.SUCCESS("✓ Checksum verified"))
            else:
                self.stdout.write(self.style.ERROR("✗ Checksum verification FAILED"))
        
        # Show data summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("DATA SUMMARY")
        self.stdout.write("=" * 60)
        
        total_records = 0
        for model_name, count in sorted(manifest.data_counts.items()):
            self.stdout.write(f"  {model_name:40} {count:>8} records")
            total_records += count
        
        self.stdout.write("-" * 60)
        self.stdout.write(f"  {'TOTAL':40} {total_records:>8} records")
        
        # Final recommendation
        self._print_recommendation(report.status, str(export_path))
    
    def _print_recommendation(self, status: CompatibilityStatus, export_path: str):
        """Print final recommendation."""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("RECOMMENDATION")
        self.stdout.write("=" * 60)
        
        if status == CompatibilityStatus.COMPATIBLE:
            self.stdout.write(
                self.style.SUCCESS("✓ This export is fully compatible and can be imported.")
            )
            self.stdout.write("\nTo import, run:")
            self.stdout.write(f"  coldfront import_portal_data {export_path}")
            sys.exit(0)
            
        elif status == CompatibilityStatus.COMPATIBLE_WITH_WARNINGS:
            self.stdout.write(
                self.style.WARNING(
                    "⚠ This export can be imported, but review the warnings above."
                )
            )
            self.stdout.write("\nTo import with warnings, run:")
            self.stdout.write(f"  coldfront import_portal_data {export_path} --force")
            sys.exit(0)
            
        else:
            self.stdout.write(
                self.style.ERROR("✗ This export CANNOT be imported due to errors above.")
            )
            self.stdout.write("\nResolve the errors before attempting to import.")
            sys.exit(1)

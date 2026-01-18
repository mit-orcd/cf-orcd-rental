# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Check if an export is compatible with this instance.

This management command validates an export directory and checks whether
it can be safely imported into the current portal instance.

Usage:
    coldfront check_import_compatibility /path/to/export/

Example:
    coldfront check_import_compatibility /backups/portal/export_20260117/
"""

import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from coldfront_orcd_direct_charge.backup import (
    Manifest,
    check_compatibility,
    CompatibilityStatus,
)
from coldfront_orcd_direct_charge.backup.manifest import (
    verify_checksum,
    get_current_schema_version,
    get_software_versions,
    EXPORT_VERSION,
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
        export_path = options["export_path"]
        verbose = options["verbose"]
        
        # Validate export directory
        if not validate_import_directory(export_path):
            raise CommandError(
                f"Invalid export directory: {export_path}\n"
                "Expected a directory containing manifest.json"
            )
        
        # Load manifest
        self.stdout.write(f"Checking export: {export_path}\n")
        
        try:
            manifest = Manifest.from_file(export_path)
        except Exception as e:
            raise CommandError(f"Failed to load manifest: {e}")
        
        # Show export info
        self.stdout.write("=" * 60)
        self.stdout.write("EXPORT INFORMATION")
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
            
            if verify_checksum(manifest, export_path):
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
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("RECOMMENDATION")
        self.stdout.write("=" * 60)
        
        if report.status == CompatibilityStatus.COMPATIBLE:
            self.stdout.write(
                self.style.SUCCESS("✓ This export is fully compatible and can be imported.")
            )
            self.stdout.write("\nTo import, run:")
            self.stdout.write(f"  coldfront import_portal_data {export_path}")
            sys.exit(0)
            
        elif report.status == CompatibilityStatus.COMPATIBLE_WITH_WARNINGS:
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

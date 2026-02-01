# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Django management command to create maintenance windows.

Creates a maintenance window with a start datetime, end datetime, and title.
Maintenance windows define periods when node rentals are not billed.

Examples:
    coldfront create_maintenance_window --start "2026-02-15 00:00" --end "2026-02-16 12:00" --title "Scheduled maintenance"
    coldfront create_maintenance_window --start "2026-02-15 00:00" --end "2026-02-16 12:00" --title "Emergency fix" --description "Fixing power issue"
    coldfront create_maintenance_window --start "2026-02-15 00:00" --end "2026-02-16 12:00" --title "Test window" --dry-run
"""

from datetime import datetime

from django.core.management.base import BaseCommand

from coldfront_orcd_direct_charge.models import MaintenanceWindow


class Command(BaseCommand):
    help = "Create a maintenance window"

    def add_arguments(self, parser):
        parser.add_argument(
            "--start",
            type=str,
            required=True,
            help="Start datetime (YYYY-MM-DD HH:MM format)",
        )
        parser.add_argument(
            "--end",
            type=str,
            required=True,
            help="End datetime (YYYY-MM-DD HH:MM format)",
        )
        parser.add_argument(
            "--title",
            type=str,
            required=True,
            help="Title for the maintenance window",
        )
        parser.add_argument(
            "--description",
            type=str,
            default="",
            help="Optional description for the maintenance window",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without making changes",
        )

    def handle(self, *args, **options):
        start_str = options["start"]
        end_str = options["end"]
        title = options["title"]
        description = options["description"]
        dry_run = options["dry_run"]

        # Parse start datetime
        try:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M")
        except ValueError:
            self.stdout.write(
                self.style.ERROR(
                    f"Invalid start datetime format: '{start_str}'. "
                    "Expected YYYY-MM-DD HH:MM (e.g., '2026-02-15 00:00')"
                )
            )
            return

        # Parse end datetime
        try:
            end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M")
        except ValueError:
            self.stdout.write(
                self.style.ERROR(
                    f"Invalid end datetime format: '{end_str}'. "
                    "Expected YYYY-MM-DD HH:MM (e.g., '2026-02-16 12:00')"
                )
            )
            return

        # Validate end > start
        if end_dt <= start_dt:
            self.stdout.write(
                self.style.ERROR("End datetime must be after start datetime")
            )
            return

        # Calculate duration
        duration_hours = (end_dt - start_dt).total_seconds() / 3600

        # Dry-run mode
        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY-RUN] Would create:"))
            self.stdout.write(f"  Title: {title}")
            self.stdout.write(f"  Start: {start_dt.strftime('%Y-%m-%d %H:%M')}")
            self.stdout.write(f"  End: {end_dt.strftime('%Y-%m-%d %H:%M')}")
            self.stdout.write(f"  Duration: {duration_hours:.1f} hours")
            if description:
                self.stdout.write(f"  Description: {description}")
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("[DRY-RUN] No changes made."))
            return

        # Create the maintenance window
        window = MaintenanceWindow.objects.create(
            title=title,
            description=description,
            start_datetime=start_dt,
            end_datetime=end_dt,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created maintenance window #{window.pk}: {window.title}"
            )
        )
        self.stdout.write(f"  Start: {window.start_datetime.strftime('%Y-%m-%d %H:%M')}")
        self.stdout.write(f"  End: {window.end_datetime.strftime('%Y-%m-%d %H:%M')}")
        self.stdout.write(f"  Duration: {window.duration_hours:.1f} hours")

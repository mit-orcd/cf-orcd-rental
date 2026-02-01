# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Django management command to delete maintenance windows.

Deletes a maintenance window by ID. Requires confirmation unless --force is used.

Examples:
    coldfront delete_maintenance_window 1
    coldfront delete_maintenance_window 1 --force
"""

from django.core.management.base import BaseCommand

from coldfront_orcd_direct_charge.models import MaintenanceWindow


class Command(BaseCommand):
    help = "Delete a maintenance window"

    def add_arguments(self, parser):
        parser.add_argument(
            "window_id",
            type=int,
            help="ID of the maintenance window to delete",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip confirmation prompt",
        )

    def handle(self, *args, **options):
        window_id = options["window_id"]
        force = options["force"]

        # Look up the maintenance window
        try:
            window = MaintenanceWindow.objects.get(pk=window_id)
        except MaintenanceWindow.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Maintenance window #{window_id} not found")
            )
            return

        # Display window details
        start_str = window.start_datetime.strftime("%Y-%m-%d %H:%M")
        end_str = window.end_datetime.strftime("%Y-%m-%d %H:%M")

        # Determine status for display
        if window.is_upcoming:
            status = "UPCOMING"
        elif window.is_in_progress:
            status = "IN PROGRESS"
        else:
            status = "COMPLETED"

        if not force:
            self.stdout.write("About to delete maintenance window:")
            self.stdout.write(f"  ID: #{window.pk}")
            self.stdout.write(f"  Title: {window.title}")
            self.stdout.write(f"  Period: {start_str} - {end_str}")
            self.stdout.write(f"  Duration: {window.duration_hours:.1f} hours")
            self.stdout.write(f"  Status: {status}")
            if window.description:
                self.stdout.write(f"  Description: {window.description}")
            self.stdout.write("")

            confirm = input("Type 'yes' to confirm deletion: ")
            if confirm.lower() != "yes":
                self.stdout.write("Cancelled.")
                return

        # Store for message after deletion
        window_title = window.title

        # Delete the window
        window.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted maintenance window #{window_id}: {window_title}"
            )
        )

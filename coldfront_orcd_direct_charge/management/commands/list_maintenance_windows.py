# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Django management command to list maintenance windows.

Lists maintenance windows with their ID, title, dates, duration, and status.
Supports filtering by status (upcoming, in_progress, completed).

Examples:
    coldfront list_maintenance_windows
    coldfront list_maintenance_windows --upcoming
    coldfront list_maintenance_windows --status in_progress
    coldfront list_maintenance_windows --status completed
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from coldfront_orcd_direct_charge.models import MaintenanceWindow


class Command(BaseCommand):
    help = "List maintenance windows"

    def add_arguments(self, parser):
        parser.add_argument(
            "--upcoming",
            action="store_true",
            help="Show only upcoming (future) windows",
        )
        parser.add_argument(
            "--status",
            type=str,
            choices=["upcoming", "in_progress", "completed"],
            help="Filter by status: upcoming, in_progress, or completed",
        )

    def handle(self, *args, **options):
        queryset = MaintenanceWindow.objects.all()
        now = timezone.now()

        # Apply filters
        if options["upcoming"] or options["status"] == "upcoming":
            queryset = queryset.filter(start_datetime__gt=now)
            filter_label = "upcoming"
        elif options["status"] == "in_progress":
            queryset = queryset.filter(start_datetime__lte=now, end_datetime__gt=now)
            filter_label = "in progress"
        elif options["status"] == "completed":
            queryset = queryset.filter(end_datetime__lte=now)
            filter_label = "completed"
        else:
            filter_label = None

        # Order by start datetime (most recent first for completed, earliest first for upcoming)
        if options["status"] == "completed":
            queryset = queryset.order_by("-start_datetime")
        else:
            queryset = queryset.order_by("start_datetime")

        if not queryset.exists():
            if filter_label:
                self.stdout.write(f"No {filter_label} maintenance windows found.")
            else:
                self.stdout.write("No maintenance windows found.")
            return

        # Header
        count = queryset.count()
        if filter_label:
            self.stdout.write(f"Found {count} {filter_label} maintenance window(s):")
        else:
            self.stdout.write(f"Found {count} maintenance window(s):")
        self.stdout.write("")

        # List windows
        for window in queryset:
            # Determine status
            if window.is_upcoming:
                status = "UPCOMING"
                status_style = self.style.SUCCESS
            elif window.is_in_progress:
                status = "IN PROGRESS"
                status_style = self.style.WARNING
            else:
                status = "COMPLETED"
                status_style = lambda x: x  # noqa: E731 - no styling for completed

            start_str = window.start_datetime.strftime("%Y-%m-%d %H:%M")
            end_str = window.end_datetime.strftime("%Y-%m-%d %H:%M")

            self.stdout.write(
                f"#{window.pk}: {window.title}"
            )
            self.stdout.write(
                f"    {start_str} - {end_str} | "
                f"{window.duration_hours:.1f}h | "
                f"{status_style(status)}"
            )
            if window.description:
                # Truncate long descriptions
                desc = window.description[:80]
                if len(window.description) > 80:
                    desc += "..."
                self.stdout.write(f"    {desc}")
            self.stdout.write("")

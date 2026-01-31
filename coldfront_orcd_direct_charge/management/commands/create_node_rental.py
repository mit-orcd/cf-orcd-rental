# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Django management command to create node rental reservations.

Creates a reservation for a GPU node instance, associating it with a project
and requesting user. Supports all reservation parameters including start date,
duration (in 12-hour blocks), status, and notes.

Examples:
    coldfront create_node_rental gpu-h200x8-001 jsmith_group jsmith --start-date 2026-02-15
    coldfront create_node_rental gpu-h200x8-001 jsmith_group jsmith --start-date 2026-02-15 --num-blocks 3
    coldfront create_node_rental gpu-h200x8-001 jsmith_group jsmith --start-date 2026-02-15 --status APPROVED
    coldfront create_node_rental gpu-h200x8-001 jsmith_group jsmith --start-date 2026-02-15 --dry-run
"""

from datetime import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from coldfront.core.project.models import Project

from coldfront_orcd_direct_charge.models import (
    GpuNodeInstance,
    Reservation,
    has_approved_cost_allocation,
    is_included_in_reservations,
)


def parse_date(date_str):
    """Parse a date string in YYYY-MM-DD format.

    Args:
        date_str: Date string in YYYY-MM-DD format

    Returns:
        date object

    Raises:
        ValueError: If the date format is invalid
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(
            f"Invalid date format: '{date_str}'. Expected YYYY-MM-DD (e.g., 2026-02-15)"
        )


class Command(BaseCommand):
    help = "Create a node rental reservation for a GPU node instance"

    def add_arguments(self, parser):
        # Required positional arguments
        parser.add_argument(
            "node_address",
            type=str,
            help="Associated resource address of the GPU node instance (e.g., gpu-h200x8-001)",
        )
        parser.add_argument(
            "project",
            type=str,
            help="Project name (e.g., jsmith_group) or project ID",
        )
        parser.add_argument(
            "username",
            type=str,
            help="Username of the requesting user",
        )

        # Required date argument
        parser.add_argument(
            "--start-date",
            type=str,
            required=True,
            dest="start_date",
            help="Start date in YYYY-MM-DD format (reservation starts at 4:00 PM)",
        )

        # Optional arguments
        parser.add_argument(
            "--num-blocks",
            type=int,
            default=1,
            dest="num_blocks",
            help="Number of 12-hour blocks (default: 1, min: 1, max: 14)",
        )
        parser.add_argument(
            "--status",
            type=str,
            choices=["PENDING", "APPROVED", "DECLINED", "CANCELLED"],
            default="PENDING",
            help="Reservation status (default: PENDING)",
        )
        parser.add_argument(
            "--rental-notes",
            type=str,
            dest="rental_notes",
            default="",
            help="Notes from the requester about this reservation",
        )
        parser.add_argument(
            "--manager-notes",
            type=str,
            dest="manager_notes",
            default="",
            help="Notes from the rental manager (for approved/declined reservations)",
        )
        parser.add_argument(
            "--processed-by",
            type=str,
            dest="processed_by",
            help="Username of the rental manager who processed this reservation (for approved/declined)",
        )
        parser.add_argument(
            "--skip-validation",
            action="store_true",
            dest="skip_validation",
            help="Skip validation checks (cost allocation, user eligibility)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Create reservation even if there are overlapping reservations",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show the Django ORM commands that would be executed without making changes",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress non-essential output",
        )

    def handle(self, *args, **options):
        node_address = options["node_address"]
        project_identifier = options["project"]
        username = options["username"]
        start_date_str = options["start_date"]
        num_blocks = options["num_blocks"]
        status = options["status"]
        rental_notes = options["rental_notes"]
        manager_notes = options["manager_notes"]
        processed_by_username = options.get("processed_by")
        skip_validation = options["skip_validation"]
        force = options["force"]
        dry_run = options["dry_run"]
        quiet = options["quiet"]

        # Parse start date
        try:
            start_date = parse_date(start_date_str)
        except ValueError as e:
            self.stdout.write(self.style.ERROR(str(e)))
            return

        # Validate num_blocks
        if num_blocks < 1 or num_blocks > 14:
            self.stdout.write(self.style.ERROR(
                f"Invalid num_blocks: {num_blocks}. Must be between 1 and 14."
            ))
            return

        # Look up the GPU node instance
        try:
            node_instance = GpuNodeInstance.objects.get(
                associated_resource_address=node_address
            )
        except GpuNodeInstance.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"GPU node instance not found: {node_address}"
            ))
            return

        # Look up the project (by name or ID)
        project = self._find_project(project_identifier)
        if project is None:
            return

        # Look up the requesting user
        try:
            requesting_user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User not found: {username}"))
            return

        # Look up processed_by user if provided
        processed_by = None
        if processed_by_username:
            try:
                processed_by = User.objects.get(username=processed_by_username)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"Processed-by user not found: {processed_by_username}"
                ))
                return

        # Validation checks (unless skipped)
        if not skip_validation:
            # Check if project has approved cost allocation
            if not has_approved_cost_allocation(project):
                self.stdout.write(self.style.ERROR(
                    f"Project '{project.title}' does not have an approved cost allocation. "
                    "Use --skip-validation to bypass this check."
                ))
                return

            # Check if user is eligible to make reservations for this project
            if not is_included_in_reservations(requesting_user, project):
                self.stdout.write(self.style.ERROR(
                    f"User '{username}' is not eligible to make reservations for project "
                    f"'{project.title}'. Only owners, technical admins, and members can "
                    "make reservations. Use --skip-validation to bypass this check."
                ))
                return

            # Check if node is rentable
            if not node_instance.is_rentable:
                self.stdout.write(self.style.ERROR(
                    f"Node '{node_address}' is not rentable. "
                    "Use --skip-validation to bypass this check."
                ))
                return

        # Check for overlapping reservations
        overlapping = self._find_overlapping_reservations(
            node_instance, start_date, num_blocks
        )
        if overlapping and not force:
            self.stdout.write(self.style.ERROR(
                f"Found {len(overlapping)} overlapping reservation(s) for this node and time period:"
            ))
            for res in overlapping:
                self.stdout.write(
                    f"  - Reservation #{res.pk}: {res.start_date} to {res.end_date} "
                    f"({res.get_status_display()})"
                )
            self.stdout.write("Use --force to create the reservation anyway.")
            return

        # Dry-run mode: print commands that would be executed
        if dry_run:
            self._print_dry_run(
                node_instance=node_instance,
                project=project,
                requesting_user=requesting_user,
                start_date=start_date,
                num_blocks=num_blocks,
                status=status,
                rental_notes=rental_notes,
                manager_notes=manager_notes,
                processed_by=processed_by,
                overlapping=overlapping,
            )
            return

        # Create the reservation
        reservation = Reservation.objects.create(
            node_instance=node_instance,
            project=project,
            requesting_user=requesting_user,
            start_date=start_date,
            num_blocks=num_blocks,
            status=status,
            rental_notes=rental_notes,
            manager_notes=manager_notes,
            processed_by=processed_by,
        )

        if not quiet:
            self.stdout.write(self.style.SUCCESS(
                f"Created reservation #{reservation.pk}"
            ))

        # Summary
        if not quiet:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Reservation created successfully."))
            self.stdout.write(f"  Reservation ID: {reservation.pk}")
            self.stdout.write(f"  Node: {node_address} ({node_instance.node_type.name})")
            self.stdout.write(f"  Project: {project.title}")
            self.stdout.write(f"  Requesting User: {username}")
            self.stdout.write(f"  Start: {start_date} at 4:00 PM")
            self.stdout.write(f"  Duration: {num_blocks} block(s) ({num_blocks * 12} hours)")
            self.stdout.write(f"  End: {reservation.end_datetime.strftime('%Y-%m-%d %I:%M %p')}")
            self.stdout.write(f"  Status: {reservation.get_status_display()}")
            if processed_by:
                self.stdout.write(f"  Processed by: {processed_by.username}")
            if overlapping:
                self.stdout.write(self.style.WARNING(
                    f"  Note: Created with {len(overlapping)} overlapping reservation(s)"
                ))

    def _find_project(self, identifier):
        """Find a project by name or ID.

        Args:
            identifier: Project name or numeric ID

        Returns:
            Project object or None if not found
        """
        # Try as numeric ID first
        if identifier.isdigit():
            try:
                return Project.objects.get(pk=int(identifier))
            except Project.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"Project not found with ID: {identifier}"
                ))
                return None

        # Try as project name (title)
        try:
            return Project.objects.get(title=identifier)
        except Project.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"Project not found: {identifier}"
            ))
            return None
        except Project.MultipleObjectsReturned:
            self.stdout.write(self.style.ERROR(
                f"Multiple projects found with name '{identifier}'. Please use project ID."
            ))
            return None

    def _find_overlapping_reservations(self, node_instance, start_date, num_blocks):
        """Find reservations that overlap with the proposed time period.

        Args:
            node_instance: The GpuNodeInstance
            start_date: Proposed start date
            num_blocks: Number of 12-hour blocks

        Returns:
            QuerySet of overlapping Reservation objects
        """
        # Calculate proposed start and end datetimes
        proposed_start = Reservation(
            start_date=start_date, num_blocks=num_blocks
        ).start_datetime
        proposed_end = Reservation.calculate_end_datetime(proposed_start, num_blocks)

        # Find overlapping reservations (excluding cancelled and declined)
        overlapping = []
        existing = Reservation.objects.filter(
            node_instance=node_instance,
            status__in=[
                Reservation.StatusChoices.PENDING,
                Reservation.StatusChoices.APPROVED,
            ],
        )

        for res in existing:
            res_start = res.start_datetime
            res_end = res.end_datetime

            # Check for overlap: not (proposed_end <= res_start or proposed_start >= res_end)
            if not (proposed_end <= res_start or proposed_start >= res_end):
                overlapping.append(res)

        return overlapping

    def _print_dry_run(self, node_instance, project, requesting_user, start_date,
                       num_blocks, status, rental_notes, manager_notes,
                       processed_by, overlapping):
        """Print the Django ORM commands that would be executed."""
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(
            "[DRY-RUN] Would execute the following commands:"
        ))
        self.stdout.write("")

        # Calculate end datetime for display
        temp_reservation = Reservation(start_date=start_date, num_blocks=num_blocks)
        end_dt = Reservation.calculate_end_datetime(
            temp_reservation.start_datetime, num_blocks
        )

        self.stdout.write("# Create reservation")
        self.stdout.write("reservation = Reservation.objects.create(")
        self.stdout.write(f"    node_instance=<GpuNodeInstance: {node_instance.associated_resource_address}>,")
        self.stdout.write(f"    project=<Project: {project.title}>,")
        self.stdout.write(f"    requesting_user=<User: {requesting_user.username}>,")
        self.stdout.write(f"    start_date=date({start_date.year}, {start_date.month}, {start_date.day}),")
        self.stdout.write(f"    num_blocks={num_blocks},")
        self.stdout.write(f"    status='{status}',")
        if rental_notes:
            self.stdout.write(f"    rental_notes='{rental_notes}',")
        if manager_notes:
            self.stdout.write(f"    manager_notes='{manager_notes}',")
        if processed_by:
            self.stdout.write(f"    processed_by=<User: {processed_by.username}>,")
        self.stdout.write(")")

        self.stdout.write("")
        self.stdout.write("# Reservation timing:")
        self.stdout.write(f"#   Start: {start_date} at 4:00 PM")
        self.stdout.write(f"#   Duration: {num_blocks} block(s) = {num_blocks * 12} hours")
        self.stdout.write(f"#   End: {end_dt.strftime('%Y-%m-%d %I:%M %p')}")

        if overlapping:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                f"# WARNING: {len(overlapping)} overlapping reservation(s) exist"
            ))
            for res in overlapping:
                self.stdout.write(
                    f"#   - Reservation #{res.pk}: {res.start_date} to {res.end_date}"
                )

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("[DRY-RUN] No changes made."))

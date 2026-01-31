# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Django management command to update existing node rental reservations.

Updates an existing reservation by its ID. All fields are optional - only
specified fields will be updated.

Duration can be updated in two ways:
- --num-blocks: Number of 12-hour blocks (max: 14)
- --end-date: Calculate duration from start to end (no block limit, supports fractional blocks)

Examples:
    coldfront update_node_rental 42 --status APPROVED --processed-by rental_admin
    coldfront update_node_rental 42 --start-date 2026-02-20 --num-blocks 3
    coldfront update_node_rental 42 --end-date 2026-02-25
    coldfront update_node_rental 42 --manager-notes "Approved for research project"
    coldfront update_node_rental 42 --node-address gpu-h200x8-002
    coldfront update_node_rental 42 --dry-run
"""

import math
from datetime import datetime, time, timedelta

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


def parse_end_datetime(date_str, start_datetime):
    """Parse an end date/datetime string.

    Supports multiple formats:
    - YYYY-MM-DD: Uses 9:00 AM on that date (standard reservation end time)
    - YYYY-MM-DD HH:MM: Uses the specified time

    Args:
        date_str: Date or datetime string
        start_datetime: The reservation start datetime (for validation)

    Returns:
        datetime object

    Raises:
        ValueError: If the format is invalid or end is before start
    """
    # Try datetime format first (YYYY-MM-DD HH:MM)
    for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"]:
        try:
            end_dt = datetime.strptime(date_str, fmt)
            if end_dt <= start_datetime:
                raise ValueError(
                    f"End datetime ({end_dt}) must be after start datetime ({start_datetime})"
                )
            return end_dt
        except ValueError:
            continue

    # Try date-only format (YYYY-MM-DD) - defaults to 9:00 AM
    try:
        end_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        # Default to 9:00 AM (standard reservation end time)
        end_dt = datetime.combine(end_date, time(9, 0))
        if end_dt <= start_datetime:
            raise ValueError(
                f"End datetime ({end_dt}) must be after start datetime ({start_datetime})"
            )
        return end_dt
    except ValueError:
        pass

    raise ValueError(
        f"Invalid end date format: '{date_str}'. "
        "Expected YYYY-MM-DD (e.g., 2026-02-17) or 'YYYY-MM-DD HH:MM' (e.g., '2026-02-17 09:00')"
    )


def calculate_blocks_from_duration(start_datetime, end_datetime):
    """Calculate the number of 12-hour blocks for a duration.

    Returns both the exact fractional blocks and the rounded-up integer value.

    Args:
        start_datetime: Reservation start datetime
        end_datetime: Reservation end datetime

    Returns:
        tuple: (exact_blocks as float, rounded_blocks as int)
    """
    duration = end_datetime - start_datetime
    total_hours = duration.total_seconds() / 3600
    exact_blocks = total_hours / 12
    rounded_blocks = math.ceil(exact_blocks)
    return exact_blocks, max(1, rounded_blocks)


class Command(BaseCommand):
    help = "Update an existing node rental reservation"

    def add_arguments(self, parser):
        # Required positional argument
        parser.add_argument(
            "reservation_id",
            type=int,
            help="ID of the reservation to update",
        )

        # Optional update fields
        parser.add_argument(
            "--node-address",
            type=str,
            dest="node_address",
            help="New GPU node instance resource address (e.g., gpu-h200x8-001)",
        )
        parser.add_argument(
            "--project",
            type=str,
            help="New project name or project ID",
        )
        parser.add_argument(
            "--username",
            type=str,
            help="New requesting user's username",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            dest="start_date",
            help="New start date in YYYY-MM-DD format (reservation starts at 4:00 PM)",
        )
        parser.add_argument(
            "--num-blocks",
            type=int,
            dest="num_blocks",
            help="New number of 12-hour blocks (min: 1, max: 14). Cannot be used with --end-date.",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            dest="end_date",
            help=(
                "New end date/time for the reservation. Calculates duration automatically. "
                "Formats: YYYY-MM-DD (uses 9:00 AM) or 'YYYY-MM-DD HH:MM'. "
                "Allows fractional blocks and durations beyond 14 blocks. "
                "Cannot be used with --num-blocks."
            ),
        )
        parser.add_argument(
            "--status",
            type=str,
            choices=["PENDING", "APPROVED", "DECLINED", "CANCELLED"],
            help="New reservation status",
        )
        parser.add_argument(
            "--rental-notes",
            type=str,
            dest="rental_notes",
            help="New notes from the requester (use empty string to clear)",
        )
        parser.add_argument(
            "--manager-notes",
            type=str,
            dest="manager_notes",
            help="New notes from the rental manager (use empty string to clear)",
        )
        parser.add_argument(
            "--processed-by",
            type=str,
            dest="processed_by",
            help="Username of the rental manager who processed this reservation (use empty string to clear)",
        )
        parser.add_argument(
            "--skip-validation",
            action="store_true",
            dest="skip_validation",
            help="Skip validation checks (cost allocation, user eligibility, node rentability)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Update reservation even if there are overlapping reservations",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without making changes",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress non-essential output",
        )

    def handle(self, *args, **options):
        reservation_id = options["reservation_id"]
        dry_run = options["dry_run"]
        quiet = options["quiet"]
        skip_validation = options["skip_validation"]
        force = options["force"]

        # Look up the reservation
        try:
            reservation = Reservation.objects.get(pk=reservation_id)
        except Reservation.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"Reservation not found with ID: {reservation_id}"
            ))
            return

        # Track changes
        changes = {}
        new_values = {}

        # Process node_address update
        if options.get("node_address") is not None:
            try:
                new_node = GpuNodeInstance.objects.get(
                    associated_resource_address=options["node_address"]
                )
                if new_node != reservation.node_instance:
                    changes["node_instance"] = (
                        reservation.node_instance.associated_resource_address,
                        new_node.associated_resource_address
                    )
                    new_values["node_instance"] = new_node
            except GpuNodeInstance.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"GPU node instance not found: {options['node_address']}"
                ))
                return

        # Process project update
        if options.get("project") is not None:
            new_project = self._find_project(options["project"])
            if new_project is None:
                return
            if new_project != reservation.project:
                changes["project"] = (reservation.project.title, new_project.title)
                new_values["project"] = new_project

        # Process username update
        if options.get("username") is not None:
            try:
                new_user = User.objects.get(username=options["username"])
                if new_user != reservation.requesting_user:
                    changes["requesting_user"] = (
                        reservation.requesting_user.username,
                        new_user.username
                    )
                    new_values["requesting_user"] = new_user
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"User not found: {options['username']}"
                ))
                return

        # Process start_date update
        new_start_date = None
        if options.get("start_date") is not None:
            try:
                new_start_date = parse_date(options["start_date"])
                if new_start_date != reservation.start_date:
                    changes["start_date"] = (
                        str(reservation.start_date),
                        str(new_start_date)
                    )
                    new_values["start_date"] = new_start_date
            except ValueError as e:
                self.stdout.write(self.style.ERROR(str(e)))
                return

        # Check mutual exclusivity of --num-blocks and --end-date
        if options.get("num_blocks") is not None and options.get("end_date") is not None:
            self.stdout.write(self.style.ERROR(
                "Cannot specify both --num-blocks and --end-date. Use one or the other."
            ))
            return

        # Determine the effective start date for end-date calculations
        effective_start_date = new_start_date if new_start_date else reservation.start_date
        start_datetime = datetime.combine(effective_start_date, time(16, 0))

        # Track end-date mode for this update
        using_end_date = False
        exact_blocks = None
        specified_end_datetime = None

        # Process num_blocks update
        if options.get("num_blocks") is not None:
            new_num_blocks = options["num_blocks"]
            if new_num_blocks < 1:
                self.stdout.write(self.style.ERROR(
                    f"Invalid num_blocks: {new_num_blocks}. Must be at least 1."
                ))
                return
            if new_num_blocks > 14:
                self.stdout.write(self.style.ERROR(
                    f"Invalid num_blocks: {new_num_blocks}. Must be between 1 and 14. "
                    "Use --end-date to specify longer durations."
                ))
                return
            if new_num_blocks != reservation.num_blocks:
                changes["num_blocks"] = (reservation.num_blocks, new_num_blocks)
                new_values["num_blocks"] = new_num_blocks

        # Process end_date update
        if options.get("end_date") is not None:
            try:
                specified_end_datetime = parse_end_datetime(
                    options["end_date"], start_datetime
                )
            except ValueError as e:
                self.stdout.write(self.style.ERROR(str(e)))
                return

            exact_blocks, new_num_blocks = calculate_blocks_from_duration(
                start_datetime, specified_end_datetime
            )
            using_end_date = True

            if new_num_blocks != reservation.num_blocks:
                changes["num_blocks"] = (reservation.num_blocks, new_num_blocks)
                new_values["num_blocks"] = new_num_blocks

            if not quiet:
                total_hours = (specified_end_datetime - start_datetime).total_seconds() / 3600
                self.stdout.write(
                    f"Calculated duration: {total_hours:.1f} hours = {exact_blocks:.2f} blocks "
                    f"(stored as {new_num_blocks} blocks)"
                )

        # Process status update
        if options.get("status") is not None:
            if options["status"] != reservation.status:
                changes["status"] = (reservation.status, options["status"])
                new_values["status"] = options["status"]

        # Process rental_notes update
        if options.get("rental_notes") is not None:
            if options["rental_notes"] != reservation.rental_notes:
                old_val = reservation.rental_notes[:50] + "..." if len(reservation.rental_notes) > 50 else reservation.rental_notes
                new_val = options["rental_notes"][:50] + "..." if len(options["rental_notes"]) > 50 else options["rental_notes"]
                changes["rental_notes"] = (f'"{old_val}"', f'"{new_val}"')
                new_values["rental_notes"] = options["rental_notes"]

        # Process manager_notes update
        if options.get("manager_notes") is not None:
            if options["manager_notes"] != reservation.manager_notes:
                old_val = reservation.manager_notes[:50] + "..." if len(reservation.manager_notes) > 50 else reservation.manager_notes
                new_val = options["manager_notes"][:50] + "..." if len(options["manager_notes"]) > 50 else options["manager_notes"]
                changes["manager_notes"] = (f'"{old_val}"', f'"{new_val}"')
                new_values["manager_notes"] = options["manager_notes"]

        # Process processed_by update
        if options.get("processed_by") is not None:
            if options["processed_by"] == "":
                # Clear the processed_by field
                if reservation.processed_by is not None:
                    changes["processed_by"] = (reservation.processed_by.username, None)
                    new_values["processed_by"] = None
            else:
                try:
                    new_processed_by = User.objects.get(username=options["processed_by"])
                    if new_processed_by != reservation.processed_by:
                        old_val = reservation.processed_by.username if reservation.processed_by else None
                        changes["processed_by"] = (old_val, new_processed_by.username)
                        new_values["processed_by"] = new_processed_by
                except User.DoesNotExist:
                    self.stdout.write(self.style.ERROR(
                        f"Processed-by user not found: {options['processed_by']}"
                    ))
                    return

        # Check if there are any changes
        if not changes:
            self.stdout.write(self.style.WARNING(
                "No changes specified. Reservation remains unchanged."
            ))
            return

        # Get effective values for validation
        effective_node = new_values.get("node_instance", reservation.node_instance)
        effective_project = new_values.get("project", reservation.project)
        effective_user = new_values.get("requesting_user", reservation.requesting_user)
        effective_start = new_values.get("start_date", reservation.start_date)
        effective_blocks = new_values.get("num_blocks", reservation.num_blocks)

        # Validation checks (unless skipped)
        if not skip_validation:
            # Check if project has approved cost allocation (if project changed)
            if "project" in new_values:
                if not has_approved_cost_allocation(effective_project):
                    self.stdout.write(self.style.ERROR(
                        f"Project '{effective_project.title}' does not have an approved cost allocation. "
                        "Use --skip-validation to bypass this check."
                    ))
                    return

            # Check if user is eligible for the project (if user or project changed)
            if "requesting_user" in new_values or "project" in new_values:
                if not is_included_in_reservations(effective_user, effective_project):
                    self.stdout.write(self.style.ERROR(
                        f"User '{effective_user.username}' is not eligible to make reservations for project "
                        f"'{effective_project.title}'. Only owners, technical admins, and members can "
                        "make reservations. Use --skip-validation to bypass this check."
                    ))
                    return

            # Check if node is rentable (if node changed)
            if "node_instance" in new_values:
                if not effective_node.is_rentable:
                    self.stdout.write(self.style.ERROR(
                        f"Node '{effective_node.associated_resource_address}' is not rentable. "
                        "Use --skip-validation to bypass this check."
                    ))
                    return

        # Check for overlapping reservations if timing or node changed
        overlapping = []
        if any(k in changes for k in ["node_instance", "start_date", "num_blocks"]):
            overlapping = self._find_overlapping_reservations(
                effective_node, effective_start, effective_blocks, exclude_id=reservation_id
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
                self.stdout.write("Use --force to update the reservation anyway.")
                return

        # Dry-run mode: show what would be updated
        if dry_run:
            self._print_dry_run(reservation, changes, new_values, overlapping,
                               using_end_date, exact_blocks, specified_end_datetime)
            return

        # Apply the changes
        for field, value in new_values.items():
            setattr(reservation, field, value)
        reservation.save()

        if not quiet:
            self.stdout.write(self.style.SUCCESS(
                f"Updated reservation #{reservation_id}"
            ))

        # Summary
        if not quiet:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Reservation updated successfully."))
            self.stdout.write(f"  Reservation ID: {reservation.pk}")
            self.stdout.write("")
            self.stdout.write("  Changes applied:")
            for field, (old_val, new_val) in changes.items():
                self.stdout.write(f"    {field}: {old_val} -> {new_val}")

            if using_end_date and exact_blocks is not None:
                self.stdout.write("")
                if specified_end_datetime:
                    self.stdout.write(
                        f"  Specified End: {specified_end_datetime.strftime('%Y-%m-%d %I:%M %p')}"
                    )

            self.stdout.write("")
            self.stdout.write("  Current values:")
            self.stdout.write(f"    Node: {reservation.node_instance.associated_resource_address}")
            self.stdout.write(f"    Project: {reservation.project.title}")
            self.stdout.write(f"    Requesting User: {reservation.requesting_user.username}")
            self.stdout.write(f"    Start: {reservation.start_date} at 4:00 PM")
            self.stdout.write(f"    Duration: {reservation.num_blocks} block(s) ({reservation.num_blocks * 12} hours)")
            self.stdout.write(f"    End: {reservation.end_datetime.strftime('%Y-%m-%d %I:%M %p')}")
            self.stdout.write(f"    Status: {reservation.get_status_display()}")
            if reservation.processed_by:
                self.stdout.write(f"    Processed by: {reservation.processed_by.username}")

            if overlapping:
                self.stdout.write(self.style.WARNING(
                    f"  Note: Updated with {len(overlapping)} overlapping reservation(s)"
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

    def _find_overlapping_reservations(self, node_instance, start_date, num_blocks, exclude_id=None):
        """Find reservations that overlap with the proposed time period.

        Args:
            node_instance: The GpuNodeInstance
            start_date: Proposed start date
            num_blocks: Number of 12-hour blocks
            exclude_id: Reservation ID to exclude from the check (the one being updated)

        Returns:
            List of overlapping Reservation objects
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

        if exclude_id:
            existing = existing.exclude(pk=exclude_id)

        for res in existing:
            res_start = res.start_datetime
            res_end = res.end_datetime

            # Check for overlap: not (proposed_end <= res_start or proposed_start >= res_end)
            if not (proposed_end <= res_start or proposed_start >= res_end):
                overlapping.append(res)

        return overlapping

    def _print_dry_run(self, reservation, changes, new_values, overlapping,
                       using_end_date=False, exact_blocks=None, specified_end_datetime=None):
        """Print what would be updated."""
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(
            "[DRY-RUN] Would update reservation #{} with the following changes:".format(
                reservation.pk
            )
        ))
        self.stdout.write("")

        self.stdout.write("# Current values:")
        self.stdout.write(f"#   Node: {reservation.node_instance.associated_resource_address}")
        self.stdout.write(f"#   Project: {reservation.project.title}")
        self.stdout.write(f"#   Requesting User: {reservation.requesting_user.username}")
        self.stdout.write(f"#   Start: {reservation.start_date} at 4:00 PM")
        self.stdout.write(f"#   Duration: {reservation.num_blocks} block(s)")
        self.stdout.write(f"#   Status: {reservation.get_status_display()}")

        self.stdout.write("")
        self.stdout.write("# Changes to apply:")
        for field, (old_val, new_val) in changes.items():
            self.stdout.write(f"reservation.{field} = {new_val}  # was: {old_val}")

        if using_end_date and exact_blocks is not None:
            self.stdout.write("")
            total_hours = exact_blocks * 12
            self.stdout.write(
                f"# Duration calculated: {exact_blocks:.2f} blocks ({total_hours:.1f} hours)"
            )
            if specified_end_datetime:
                self.stdout.write(
                    f"# Specified end: {specified_end_datetime.strftime('%Y-%m-%d %I:%M %p')}"
                )

        self.stdout.write("")
        self.stdout.write("reservation.save()")

        if overlapping:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                f"# WARNING: {len(overlapping)} overlapping reservation(s) would exist"
            ))
            for res in overlapping:
                self.stdout.write(
                    f"#   - Reservation #{res.pk}: {res.start_date} to {res.end_date}"
                )

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("[DRY-RUN] No changes made."))

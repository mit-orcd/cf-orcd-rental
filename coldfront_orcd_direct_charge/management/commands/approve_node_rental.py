# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Django management command to approve a node rental reservation.

Approves a PENDING reservation, replicating the approval logic from
the web UI (ReservationApproveView). This includes checking for conflicts
with existing APPROVED reservations on the same node, setting the
processed_by user, and logging the approval activity.

The reservation is identified by its (node_address, project, start_date)
triple, which uniquely identifies a reservation in the test setup workflow.

Examples:
    # Approve a reservation
    coldfront approve_node_rental node2433 orcd_u0_p1 \\
        --start-date 2026-03-02 --processed-by orcd_rem

    # Approve with manager notes
    coldfront approve_node_rental node2433 orcd_u0_p1 \\
        --start-date 2026-03-02 --processed-by orcd_rem \\
        --manager-notes "Approved during test setup"

    # Re-approve an already-approved reservation (idempotent)
    coldfront approve_node_rental node2433 orcd_u0_p1 \\
        --start-date 2026-03-02 --processed-by orcd_rem --force

    # Preview changes
    coldfront approve_node_rental node2433 orcd_u0_p1 \\
        --start-date 2026-03-02 --processed-by orcd_rem --dry-run
"""

from datetime import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from coldfront.core.project.models import Project

from coldfront_orcd_direct_charge.models import (
    ActivityLog,
    GpuNodeInstance,
    Reservation,
    log_activity,
)


# Name of the Rental Manager group
RENTAL_MANAGER_GROUP = "Rental Manager"


class Command(BaseCommand):
    help = "Approve a PENDING node rental reservation"

    def add_arguments(self, parser):
        parser.add_argument(
            "node_address",
            type=str,
            help="Associated resource address of the GPU node instance (e.g., node2433)",
        )
        parser.add_argument(
            "project",
            type=str,
            help="Project name (e.g., 'orcd_u0_p1') or project ID",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            required=True,
            dest="start_date",
            help="Start date of the reservation to approve (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--processed-by",
            type=str,
            required=True,
            dest="processed_by",
            help=(
                "Username of the Rental Manager who approves the reservation. "
                "Must have the can_manage_rentals permission."
            ),
        )
        parser.add_argument(
            "--manager-notes",
            type=str,
            dest="manager_notes",
            default="",
            help="Optional notes from the rental manager about this approval",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Approve even if there are conflicts with existing APPROVED "
                "reservations, or re-approve an already-approved reservation"
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress non-essential output",
        )

    def handle(self, *args, **options):
        node_address = options["node_address"]
        project_identifier = options["project"]
        start_date_str = options["start_date"]
        processed_by_username = options["processed_by"]
        manager_notes = options.get("manager_notes", "")
        force = options["force"]
        dry_run = options["dry_run"]
        quiet = options["quiet"]

        # -----------------------------------------------------------------
        # Parse start date
        # -----------------------------------------------------------------
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except ValueError:
            self.stdout.write(self.style.ERROR(
                f"Invalid date format: '{start_date_str}'. Expected YYYY-MM-DD"
            ))
            return

        # -----------------------------------------------------------------
        # Look up the node instance
        # -----------------------------------------------------------------
        try:
            node_instance = GpuNodeInstance.objects.get(
                associated_resource_address=node_address
            )
        except GpuNodeInstance.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"GPU node instance not found: {node_address}"
            ))
            return

        # -----------------------------------------------------------------
        # Look up the project
        # -----------------------------------------------------------------
        project = self._find_project(project_identifier)
        if project is None:
            return

        # -----------------------------------------------------------------
        # Look up the processed-by user (must be a Rental Manager)
        # -----------------------------------------------------------------
        processor = self._find_rental_manager(processed_by_username)
        if processor is None:
            return

        # -----------------------------------------------------------------
        # Find the reservation
        # -----------------------------------------------------------------
        reservation = self._find_reservation(
            node_instance, project, start_date, force
        )
        if reservation is None:
            return

        # -----------------------------------------------------------------
        # Check status
        # -----------------------------------------------------------------
        if reservation.status != Reservation.StatusChoices.PENDING:
            if not force:
                self.stdout.write(self.style.ERROR(
                    f"Reservation #{reservation.pk} is not PENDING "
                    f"(current status: {reservation.get_status_display()}). "
                    "Use --force to re-approve."
                ))
                return

        # -----------------------------------------------------------------
        # Check for conflicts with existing APPROVED reservations
        # (mirrors ReservationApproveView logic)
        # -----------------------------------------------------------------
        conflicts = self._find_conflicts(reservation)
        if conflicts and not force:
            self.stdout.write(self.style.ERROR(
                f"Cannot approve: {len(conflicts)} conflict(s) with existing "
                "APPROVED reservation(s):"
            ))
            for existing in conflicts:
                self.stdout.write(
                    f"  - Reservation #{existing.pk}: "
                    f"{existing.start_datetime.strftime('%Y-%m-%d %I:%M %p')} to "
                    f"{existing.end_datetime.strftime('%Y-%m-%d %I:%M %p')} "
                    f"(project: {existing.project.title})"
                )
            self.stdout.write("Use --force to approve anyway.")
            return

        # -----------------------------------------------------------------
        # Dry-run mode
        # -----------------------------------------------------------------
        if dry_run:
            self._print_dry_run(
                reservation=reservation,
                processor=processor,
                manager_notes=manager_notes,
                conflicts=conflicts,
            )
            return

        # -----------------------------------------------------------------
        # Approve the reservation
        # -----------------------------------------------------------------
        reservation.status = Reservation.StatusChoices.APPROVED
        reservation.processed_by = processor
        if manager_notes:
            reservation.manager_notes = manager_notes
        reservation.save()

        # Log the approval activity (matches ReservationApproveView)
        log_activity(
            action="reservation.approved",
            category=ActivityLog.ActionCategory.RESERVATION,
            description=(
                f"Reservation #{reservation.pk} approved by "
                f"{processor.username} (via management command)"
            ),
            user=processor,
            target=reservation,
            extra_data={
                "project_id": reservation.project.pk,
                "project_title": reservation.project.title,
                "node": reservation.node_instance.associated_resource_address,
            },
        )

        # -----------------------------------------------------------------
        # Summary
        # -----------------------------------------------------------------
        if not quiet:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS(
                f"Reservation #{reservation.pk} approved."
            ))
            self.stdout.write(
                f"  Node: {node_address} "
                f"({node_instance.node_type.name})"
            )
            self.stdout.write(f"  Project: {project.title}")
            self.stdout.write(
                f"  Requesting user: "
                f"{reservation.requesting_user.username}"
            )
            self.stdout.write(
                f"  Period: {reservation.start_date} at 4:00 PM to "
                f"{reservation.end_datetime.strftime('%Y-%m-%d %I:%M %p')}"
            )
            self.stdout.write(
                f"  Duration: {reservation.num_blocks} block(s) "
                f"({reservation.billable_hours} hours)"
            )
            self.stdout.write(f"  Processed by: {processor.username}")
            if manager_notes:
                self.stdout.write(f"  Manager notes: {manager_notes}")
            if conflicts:
                self.stdout.write(self.style.WARNING(
                    f"  Note: Approved with {len(conflicts)} "
                    "overlapping reservation(s)"
                ))

    def _find_project(self, identifier):
        """Find a project by name or ID."""
        if identifier.isdigit():
            try:
                return Project.objects.get(pk=int(identifier))
            except Project.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"Project with ID {identifier} not found"
                ))
                return None

        try:
            return Project.objects.get(title=identifier)
        except Project.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"Project '{identifier}' not found"
            ))
            return None
        except Project.MultipleObjectsReturned:
            self.stdout.write(self.style.ERROR(
                f"Multiple projects found with title '{identifier}'. "
                "Please use the project ID instead."
            ))
            return None

    def _find_rental_manager(self, identifier):
        """Find a user and verify they have rental management permissions."""
        try:
            user = User.objects.get(username=identifier)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"User '{identifier}' not found"
            ))
            return None

        # Check for can_manage_rentals permission (via group or direct)
        if not (
            user.is_superuser
            or user.has_perm(
                "coldfront_orcd_direct_charge.can_manage_rentals"
            )
        ):
            self.stdout.write(self.style.ERROR(
                f"User '{user.username}' does not have rental management "
                f"permissions. They must be a member of the "
                f"'{RENTAL_MANAGER_GROUP}' group or have the "
                "'can_manage_rentals' permission."
            ))
            return None

        return user

    def _find_reservation(self, node_instance, project, start_date, force):
        """Find a reservation by node, project, and start_date.

        When force is True, also searches for APPROVED reservations
        (for idempotent re-approval).
        """
        # First try to find a PENDING reservation
        try:
            return Reservation.objects.get(
                node_instance=node_instance,
                project=project,
                start_date=start_date,
                status=Reservation.StatusChoices.PENDING,
            )
        except Reservation.DoesNotExist:
            pass
        except Reservation.MultipleObjectsReturned:
            self.stdout.write(self.style.ERROR(
                f"Multiple PENDING reservations found for "
                f"node={node_instance.associated_resource_address}, "
                f"project={project.title}, start_date={start_date}. "
                "Cannot determine which to approve."
            ))
            return None

        # If --force, also check for already-approved reservations
        if force:
            try:
                return Reservation.objects.get(
                    node_instance=node_instance,
                    project=project,
                    start_date=start_date,
                    status=Reservation.StatusChoices.APPROVED,
                )
            except Reservation.DoesNotExist:
                pass
            except Reservation.MultipleObjectsReturned:
                self.stdout.write(self.style.ERROR(
                    f"Multiple APPROVED reservations found for "
                    f"node={node_instance.associated_resource_address}, "
                    f"project={project.title}, start_date={start_date}."
                ))
                return None

        self.stdout.write(self.style.ERROR(
            f"No PENDING reservation found for "
            f"node={node_instance.associated_resource_address}, "
            f"project={project.title}, start_date={start_date}"
        ))
        return None

    def _find_conflicts(self, reservation):
        """Find APPROVED reservations that conflict with this one.

        Mirrors the conflict detection logic in ReservationApproveView.
        """
        new_start = reservation.start_datetime
        new_end = reservation.end_datetime

        approved = Reservation.objects.filter(
            node_instance=reservation.node_instance,
            status=Reservation.StatusChoices.APPROVED,
        ).exclude(pk=reservation.pk)

        conflicts = []
        for existing in approved:
            if (new_start < existing.end_datetime
                    and new_end > existing.start_datetime):
                conflicts.append(existing)

        return conflicts

    def _print_dry_run(self, reservation, processor, manager_notes,
                       conflicts):
        """Print the commands that would be executed."""
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(
            "[DRY-RUN] Would execute the following:"
        ))
        self.stdout.write("")

        self.stdout.write("# Update reservation status")
        self.stdout.write(
            f"reservation = Reservation.objects.get(pk={reservation.pk})"
        )
        self.stdout.write("reservation.status = 'APPROVED'")
        self.stdout.write(
            f"reservation.processed_by = <User: {processor.username}>"
        )
        if manager_notes:
            self.stdout.write(
                f"reservation.manager_notes = '{manager_notes}'"
            )
        self.stdout.write("reservation.save()")

        self.stdout.write("")
        self.stdout.write("# Log activity")
        self.stdout.write(
            f"log_activity(action='reservation.approved', "
            f"user={processor.username}, "
            f"target=Reservation #{reservation.pk})"
        )

        self.stdout.write("")
        self.stdout.write(
            f"# Reservation: {reservation.node_instance.associated_resource_address} "
            f"| {reservation.project.title} | {reservation.start_date}"
        )
        self.stdout.write(
            f"# Period: {reservation.start_date} 4:00 PM to "
            f"{reservation.end_datetime.strftime('%Y-%m-%d %I:%M %p')}"
        )
        self.stdout.write(
            f"# Duration: {reservation.num_blocks} block(s) "
            f"({reservation.billable_hours} hours)"
        )

        if conflicts:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                f"# WARNING: {len(conflicts)} conflicting APPROVED "
                "reservation(s) exist"
            ))
            for existing in conflicts:
                self.stdout.write(
                    f"#   - Reservation #{existing.pk}: "
                    f"{existing.start_date} to {existing.end_date}"
                )

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("[DRY-RUN] No changes made."))

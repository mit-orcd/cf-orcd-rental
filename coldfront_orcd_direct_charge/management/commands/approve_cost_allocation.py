# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Django management command to approve a project's cost allocation.

Approves a PENDING cost allocation, replicating the approval logic from
the web UI (CostAllocationApprovalView). This includes creating a
CostAllocationSnapshot with CostObjectSnapshot records for historical
billing accuracy.

Examples:
    # Approve a project's cost allocation
    coldfront approve_cost_allocation orcd_u0_p1 --reviewed-by orcd_bim

    # Approve with review notes
    coldfront approve_cost_allocation orcd_u0_p1 --reviewed-by orcd_bim \
        --review-notes "Verified cost objects for Q1 2026"

    # Re-approve an already-approved allocation
    coldfront approve_cost_allocation orcd_u0_p1 --reviewed-by orcd_bim --force

    # Preview changes
    coldfront approve_cost_allocation orcd_u0_p1 --reviewed-by orcd_bim --dry-run
"""

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from coldfront.core.project.models import Project

from coldfront_orcd_direct_charge.models import (
    CostAllocationSnapshot,
    CostObjectSnapshot,
    ProjectCostAllocation,
)


# Name of the Billing Manager group
BILLING_MANAGER_GROUP = "Billing Manager"


class Command(BaseCommand):
    help = "Approve a project's PENDING cost allocation"

    def add_arguments(self, parser):
        parser.add_argument(
            "project",
            type=str,
            help="Project name (e.g., 'orcd_u0_p1') or project ID",
        )
        parser.add_argument(
            "--reviewed-by",
            type=str,
            dest="reviewed_by",
            required=True,
            help=(
                "Username of the Billing Manager who approves the allocation. "
                "Must be a member of the Billing Manager group."
            ),
        )
        parser.add_argument(
            "--review-notes",
            type=str,
            dest="review_notes",
            default="",
            help="Optional notes from the reviewer about the approval",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Approve even if the allocation is not PENDING (re-approve)",
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
        project_identifier = options["project"]
        reviewed_by_identifier = options["reviewed_by"]
        review_notes = options.get("review_notes", "")
        force = options["force"]
        dry_run = options["dry_run"]
        quiet = options["quiet"]

        # -----------------------------------------------------------------
        # Look up the project
        # -----------------------------------------------------------------
        project = self._find_project(project_identifier)
        if not project:
            return

        # -----------------------------------------------------------------
        # Look up the reviewer (must be a Billing Manager)
        # -----------------------------------------------------------------
        reviewer = self._find_billing_manager(reviewed_by_identifier)
        if not reviewer:
            return

        # -----------------------------------------------------------------
        # Find the cost allocation
        # -----------------------------------------------------------------
        try:
            allocation = ProjectCostAllocation.objects.get(project=project)
        except ProjectCostAllocation.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"No cost allocation found for project '{project.title}'. "
                "Create one first with 'set_project_cost_allocation'."
            ))
            return

        # -----------------------------------------------------------------
        # Check status
        # -----------------------------------------------------------------
        if allocation.status != ProjectCostAllocation.StatusChoices.PENDING:
            if not force:
                self.stdout.write(self.style.ERROR(
                    f"Cost allocation for '{project.title}' is not PENDING "
                    f"(current status: {allocation.status}). "
                    "Use --force to re-approve."
                ))
                return

        # Verify there are cost objects to approve
        cost_objects = list(allocation.cost_objects.all())
        if not cost_objects:
            self.stdout.write(self.style.ERROR(
                f"Cost allocation for '{project.title}' has no cost objects. "
                "Cannot approve an empty allocation."
            ))
            return

        # -----------------------------------------------------------------
        # Dry-run mode
        # -----------------------------------------------------------------
        if dry_run:
            self._print_dry_run(
                project=project,
                allocation=allocation,
                reviewer=reviewer,
                review_notes=review_notes,
                cost_objects=cost_objects,
            )
            return

        # -----------------------------------------------------------------
        # Approve the allocation (replicates CostAllocationApprovalView)
        # -----------------------------------------------------------------
        approval_time = timezone.now()

        with transaction.atomic():
            # Mark any existing current snapshots as superseded
            superseded_count = CostAllocationSnapshot.objects.filter(
                allocation=allocation,
                superseded_at__isnull=True,
            ).update(superseded_at=approval_time)

            # Create a new snapshot of the current cost objects
            snapshot = CostAllocationSnapshot.objects.create(
                allocation=allocation,
                approved_at=approval_time,
                approved_by=reviewer,
                superseded_at=None,
            )

            # Copy all current cost objects to the snapshot
            for co in cost_objects:
                CostObjectSnapshot.objects.create(
                    snapshot=snapshot,
                    cost_object=co.cost_object,
                    percentage=co.percentage,
                )

            # Update the allocation status
            allocation.status = ProjectCostAllocation.StatusChoices.APPROVED
            allocation.reviewed_by = reviewer
            allocation.reviewed_at = approval_time
            allocation.review_notes = review_notes
            allocation.save()

        # -----------------------------------------------------------------
        # Summary
        # -----------------------------------------------------------------
        if not quiet:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Cost allocation approved."))
            self.stdout.write(f"  Project: {project.title}")
            self.stdout.write(f"  Reviewed by: {reviewer.username}")
            self.stdout.write(f"  Snapshot ID: {snapshot.pk}")
            self.stdout.write(f"  Cost objects: {len(cost_objects)}")
            for co in cost_objects:
                self.stdout.write(f"    - {co.cost_object}: {co.percentage}%")
            if review_notes:
                self.stdout.write(f"  Review notes: {review_notes}")
            if superseded_count:
                self.stdout.write(f"  Superseded snapshots: {superseded_count}")

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

    def _find_billing_manager(self, identifier):
        """Find a user and verify they are a Billing Manager."""
        if identifier.isdigit():
            try:
                user = User.objects.get(pk=int(identifier))
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"User with ID {identifier} not found"
                ))
                return None
        else:
            try:
                user = User.objects.get(username=identifier)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"User '{identifier}' not found"
                ))
                return None

        try:
            billing_manager_group = Group.objects.get(name=BILLING_MANAGER_GROUP)
        except Group.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"'{BILLING_MANAGER_GROUP}' group not found. "
                "Run 'coldfront setup_billing_manager --create-group' first."
            ))
            return None

        if not user.groups.filter(pk=billing_manager_group.pk).exists():
            if not (user.is_superuser or
                    user.has_perm("coldfront_orcd_direct_charge.can_manage_billing")):
                self.stdout.write(self.style.ERROR(
                    f"User '{user.username}' is not a Billing Manager. "
                    f"They must be a member of the '{BILLING_MANAGER_GROUP}' group "
                    "or have the 'can_manage_billing' permission."
                ))
                return None

        return user

    def _print_dry_run(self, project, allocation, reviewer, review_notes,
                       cost_objects):
        """Print the Django ORM commands that would be executed."""
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(
            "[DRY-RUN] Would execute the following commands:"
        ))
        self.stdout.write("")

        self.stdout.write("# Supersede existing snapshots")
        self.stdout.write(
            f"CostAllocationSnapshot.objects.filter("
            f"allocation=<Allocation: {project.title}>, "
            f"superseded_at=None).update(superseded_at=now)"
        )

        self.stdout.write("")
        self.stdout.write("# Create approval snapshot")
        self.stdout.write("snapshot = CostAllocationSnapshot.objects.create(")
        self.stdout.write(f"    allocation=<Allocation: {project.title}>,")
        self.stdout.write("    approved_at=timezone.now(),")
        self.stdout.write(f"    approved_by=<User: {reviewer.username}>,")
        self.stdout.write(")")

        self.stdout.write("")
        self.stdout.write("# Copy cost objects to snapshot")
        for co in cost_objects:
            self.stdout.write("CostObjectSnapshot.objects.create(")
            self.stdout.write("    snapshot=snapshot,")
            self.stdout.write(f"    cost_object='{co.cost_object}',")
            self.stdout.write(f"    percentage=Decimal('{co.percentage}'),")
            self.stdout.write(")")

        self.stdout.write("")
        self.stdout.write("# Update allocation status")
        self.stdout.write(f"allocation.status = 'APPROVED'")
        self.stdout.write(f"allocation.reviewed_by = <User: {reviewer.username}>")
        self.stdout.write(f"allocation.reviewed_at = timezone.now()")
        self.stdout.write(f"allocation.review_notes = '{review_notes}'")
        self.stdout.write("allocation.save()")

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("[DRY-RUN] No changes made."))

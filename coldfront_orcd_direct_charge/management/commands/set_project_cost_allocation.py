# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Django management command to set cost allocation for ORCD projects.

Sets the cost objects and their percentage allocations for a project.
Cost allocations are required before a project can be used for reservations.

Cost object format: CO:NNN where:
    - CO is the cost object identifier (alphanumeric and hyphens)
    - NNN is the percentage (0-100, must sum to 100 across all cost objects)

Examples:
    # Set a single cost object (100%)
    coldfront set_project_cost_allocation jsmith_group ABC-123:100

    # Split between multiple cost objects
    coldfront set_project_cost_allocation jsmith_group ABC-123:50 DEF-456:30 GHI-789:20

    # Replace existing allocation
    coldfront set_project_cost_allocation jsmith_group ABC-123:100 --force

    # Set with notes
    coldfront set_project_cost_allocation jsmith_group ABC-123:100 --notes "Q1 2026 allocation"

    # Preview changes
    coldfront set_project_cost_allocation jsmith_group ABC-123:50 DEF-456:50 --dry-run
"""

import re
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand

from coldfront.core.project.models import Project

from coldfront_orcd_direct_charge.models import (
    ProjectCostAllocation,
    ProjectCostObject,
)


# Regex pattern for cost object identifiers (alphanumeric and hyphens)
COST_OBJECT_PATTERN = re.compile(r'^[A-Za-z0-9-]+$')


def parse_allocation_arg(allocation_arg):
    """Parse an allocation argument in format 'CO:NNN'.

    Args:
        allocation_arg: String in format "COST_OBJECT:PERCENTAGE"

    Returns:
        Tuple of (cost_object, percentage_decimal) or raises ValueError.
    """
    if ":" not in allocation_arg:
        raise ValueError(
            f"Invalid format '{allocation_arg}'. Expected 'COST_OBJECT:PERCENTAGE' "
            "(e.g., 'ABC-123:50')"
        )

    parts = allocation_arg.split(":", 1)
    cost_object = parts[0].strip()
    percentage_str = parts[1].strip()

    if not cost_object:
        raise ValueError("Cost object identifier cannot be empty")

    if not COST_OBJECT_PATTERN.match(cost_object):
        raise ValueError(
            f"Invalid cost object '{cost_object}'. "
            "Must contain only letters, numbers, and hyphens."
        )

    try:
        percentage = Decimal(percentage_str)
    except InvalidOperation:
        raise ValueError(
            f"Invalid percentage '{percentage_str}'. Must be a number."
        )

    if percentage <= 0:
        raise ValueError(
            f"Percentage must be positive, got {percentage} for '{cost_object}'"
        )

    if percentage > 100:
        raise ValueError(
            f"Percentage cannot exceed 100, got {percentage} for '{cost_object}'"
        )

    return cost_object, percentage


class Command(BaseCommand):
    help = "Set cost allocation for an ORCD project"

    def add_arguments(self, parser):
        # Required positional argument
        parser.add_argument(
            "project",
            type=str,
            help="Project name (e.g., 'jsmith_group') or project ID",
        )

        # Variable number of allocation arguments
        parser.add_argument(
            "allocations",
            nargs="+",
            type=str,
            metavar="CO:PERCENT",
            help=(
                "Cost object allocations in format 'COST_OBJECT:PERCENTAGE'. "
                "Multiple allocations can be specified and must sum to 100. "
                "Example: ABC-123:50 DEF-456:50"
            ),
        )

        # Optional arguments
        parser.add_argument(
            "--notes",
            type=str,
            default="",
            help="Notes about the cost allocation",
        )
        parser.add_argument(
            "--status",
            type=str,
            choices=["PENDING", "APPROVED", "REJECTED"],
            default="PENDING",
            help="Initial status of the cost allocation (default: PENDING)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Replace existing cost allocation instead of reporting error",
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
        project_identifier = options["project"]
        allocation_args = options["allocations"]
        notes = options["notes"]
        status = options["status"]
        force = options["force"]
        dry_run = options["dry_run"]
        quiet = options["quiet"]

        # Look up the project
        project = self._find_project(project_identifier)
        if not project:
            return

        # Parse allocation arguments
        parsed_allocations = []
        seen_cost_objects = set()

        for alloc_arg in allocation_args:
            try:
                cost_object, percentage = parse_allocation_arg(alloc_arg)

                # Check for duplicate cost objects
                if cost_object in seen_cost_objects:
                    self.stdout.write(self.style.ERROR(
                        f"Duplicate cost object '{cost_object}' specified"
                    ))
                    return

                seen_cost_objects.add(cost_object)
                parsed_allocations.append((cost_object, percentage))

            except ValueError as e:
                self.stdout.write(self.style.ERROR(str(e)))
                return

        # Validate percentages sum to 100
        total_percentage = sum(p for _, p in parsed_allocations)
        if total_percentage != Decimal("100"):
            self.stdout.write(self.style.ERROR(
                f"Percentages must sum to 100, got {total_percentage}"
            ))
            return

        # Check if allocation already exists
        allocation_exists = ProjectCostAllocation.objects.filter(project=project).exists()
        if allocation_exists and not force:
            self.stdout.write(self.style.ERROR(
                f"Cost allocation already exists for project '{project.title}'. "
                "Use --force to replace."
            ))
            return

        # Dry-run mode: print commands that would be executed
        if dry_run:
            self._print_dry_run(
                project=project,
                parsed_allocations=parsed_allocations,
                notes=notes,
                status=status,
                allocation_exists=allocation_exists,
            )
            return

        # Execute the commands
        self._set_cost_allocation(
            project=project,
            parsed_allocations=parsed_allocations,
            notes=notes,
            status=status,
            allocation_exists=allocation_exists,
            quiet=quiet,
        )

        # Summary
        if not quiet:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Cost allocation set successfully."))
            self.stdout.write(f"  Project: {project.title}")
            self.stdout.write(f"  Status: {status}")
            self.stdout.write(f"  Cost objects: {len(parsed_allocations)}")
            for co, pct in parsed_allocations:
                self.stdout.write(f"    - {co}: {pct}%")
            if notes:
                self.stdout.write(f"  Notes: {notes}")

    def _find_project(self, identifier):
        """Find a project by name or ID.

        Args:
            identifier: Project title (e.g., 'jsmith_group') or numeric ID

        Returns:
            Project instance or None if not found
        """
        # Try as numeric ID first
        if identifier.isdigit():
            try:
                return Project.objects.get(pk=int(identifier))
            except Project.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"Project with ID {identifier} not found"
                ))
                return None

        # Try as project title
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

    def _print_dry_run(self, project, parsed_allocations, notes, status, allocation_exists):
        """Print the Django ORM commands that would be executed."""
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("[DRY-RUN] Would execute the following commands:"))
        self.stdout.write("")

        if allocation_exists:
            self.stdout.write("# Delete existing cost objects")
            self.stdout.write(f"allocation = ProjectCostAllocation.objects.get(project=<Project: {project.title}>)")
            self.stdout.write("allocation.cost_objects.all().delete()")
            self.stdout.write("")
            self.stdout.write("# Update allocation")
            self.stdout.write(f"allocation.notes = '{notes}'")
            self.stdout.write(f"allocation.status = '{status}'")
            self.stdout.write("allocation.reviewed_by = None")
            self.stdout.write("allocation.reviewed_at = None")
            self.stdout.write("allocation.review_notes = ''")
            self.stdout.write("allocation.save()")
        else:
            self.stdout.write("# Create cost allocation")
            self.stdout.write("allocation = ProjectCostAllocation.objects.create(")
            self.stdout.write(f"    project=<Project: {project.title}>,")
            self.stdout.write(f"    notes='{notes}',")
            self.stdout.write(f"    status='{status}',")
            self.stdout.write(")")

        self.stdout.write("")
        self.stdout.write("# Create cost objects")
        for cost_object, percentage in parsed_allocations:
            self.stdout.write("ProjectCostObject.objects.create(")
            self.stdout.write("    allocation=allocation,")
            self.stdout.write(f"    cost_object='{cost_object}',")
            self.stdout.write(f"    percentage=Decimal('{percentage}'),")
            self.stdout.write(")")

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("[DRY-RUN] No changes made."))

    def _set_cost_allocation(self, project, parsed_allocations, notes, status, allocation_exists, quiet):
        """Set the cost allocation for a project.

        Args:
            project: Project instance
            parsed_allocations: List of (cost_object, percentage) tuples
            notes: Notes about the allocation
            status: Status string (PENDING, APPROVED, REJECTED)
            allocation_exists: Whether an allocation already exists
            quiet: Suppress output if True
        """
        if allocation_exists:
            # Update existing allocation
            allocation = ProjectCostAllocation.objects.get(project=project)

            # Delete existing cost objects
            old_count = allocation.cost_objects.count()
            allocation.cost_objects.all().delete()

            # Update allocation fields
            allocation.notes = notes
            allocation.status = status
            # Reset review status when allocation is modified
            allocation.reviewed_by = None
            allocation.reviewed_at = None
            allocation.review_notes = ""
            allocation.save()

            if not quiet:
                self.stdout.write(self.style.SUCCESS(
                    f"Updated existing cost allocation (removed {old_count} old cost objects)"
                ))
        else:
            # Create new allocation
            allocation = ProjectCostAllocation.objects.create(
                project=project,
                notes=notes,
                status=status,
            )
            if not quiet:
                self.stdout.write(self.style.SUCCESS(
                    f"Created new cost allocation for project '{project.title}'"
                ))

        # Create cost objects
        for cost_object, percentage in parsed_allocations:
            ProjectCostObject.objects.create(
                allocation=allocation,
                cost_object=cost_object,
                percentage=percentage,
            )
            if not quiet:
                self.stdout.write(self.style.SUCCESS(
                    f"  Added cost object '{cost_object}' at {percentage}%"
                ))

# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Django management command to set account maintenance fee (AMF) status for users.

Sets the maintenance status and billing project for a user account. The AMF
determines what level of account maintenance services the user receives and
which project is charged for those services.

Status levels:
    - inactive: No account maintenance fees (default for new accounts)
    - basic: Basic maintenance level (requires billing project)
    - advanced: Advanced maintenance level (requires billing project)

Billing project requirements:
    - The user must have an eligible role in the project (owner, technical_admin,
      or member). Financial admins cannot use a project for maintenance fees.
    - The project should have an approved cost allocation for billing to work.

Examples:
    # Set a user to inactive (no maintenance fee)
    coldfront set_user_amf jsmith inactive

    # Set a user to basic maintenance with a billing project
    coldfront set_user_amf jsmith basic --project jsmith_group

    # Set a user to advanced maintenance with a billing project
    coldfront set_user_amf jsmith advanced --project research_lab

    # Update an existing configuration (requires --force)
    coldfront set_user_amf jsmith basic --project new_project --force

    # Preview changes without applying
    coldfront set_user_amf jsmith advanced --project jsmith_group --dry-run

    # Override timestamps
    coldfront set_user_amf jsmith basic --project jsmith_group --created 2024-11-15
    coldfront set_user_amf jsmith basic --project jsmith_group --modified 2025-02-01T09:00:00
"""

from datetime import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from coldfront.core.project.models import Project

from coldfront_orcd_direct_charge.models import (
    UserMaintenanceStatus,
    can_use_for_maintenance_fee,
    has_approved_cost_allocation,
)


class Command(BaseCommand):
    help = "Set account maintenance fee (AMF) status for a user"

    def add_arguments(self, parser):
        # Required positional arguments
        parser.add_argument(
            "username",
            type=str,
            help="Username of the user to configure",
        )
        parser.add_argument(
            "status",
            type=str,
            choices=["inactive", "basic", "advanced"],
            help="Maintenance status level: inactive, basic, or advanced",
        )

        # Optional arguments
        parser.add_argument(
            "--project",
            type=str,
            help=(
                "Project name (e.g., 'jsmith_group') or project ID to charge "
                "maintenance fees to. Required for basic and advanced status."
            ),
        )
        parser.add_argument(
            "--created",
            type=str,
            help="Override creation date (YYYY-MM-DD or ISO 8601 datetime)",
        )
        parser.add_argument(
            "--modified",
            type=str,
            help="Override last-modified date (YYYY-MM-DD or ISO 8601 datetime)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Update existing maintenance configuration instead of reporting error",
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
        username = options["username"]
        status = options["status"]
        project_identifier = options.get("project")
        force = options["force"]
        dry_run = options["dry_run"]
        quiet = options["quiet"]

        # Parse optional date overrides
        created_dt = self._parse_datetime(options.get("created"), "created")
        modified_dt = self._parse_datetime(options.get("modified"), "modified")

        # Look up the user
        user = self._find_user(username)
        if not user:
            return

        # Validate status/project combination
        if status in ["basic", "advanced"] and not project_identifier:
            self.stdout.write(self.style.ERROR(
                f"The '{status}' status requires a billing project. "
                "Use --project to specify one."
            ))
            return

        # Look up the project if specified
        project = None
        if project_identifier:
            project = self._find_project(project_identifier)
            if not project:
                return

            # Validate user can use this project for maintenance fees
            if not can_use_for_maintenance_fee(user, project):
                self.stdout.write(self.style.ERROR(
                    f"User '{username}' cannot use project '{project.title}' for "
                    "maintenance fees. The user must have an owner, technical_admin, "
                    "or member role in the project."
                ))
                return

            # Warn if project doesn't have approved cost allocation
            if not has_approved_cost_allocation(project):
                self.stdout.write(self.style.WARNING(
                    f"Warning: Project '{project.title}' does not have an approved "
                    "cost allocation. Maintenance fees cannot be billed until the "
                    "cost allocation is approved."
                ))

        # Check if user already has a non-default maintenance status
        existing_status = self._get_existing_status(user)
        if existing_status and existing_status.status != UserMaintenanceStatus.StatusChoices.INACTIVE:
            if not force:
                current_project = (
                    existing_status.billing_project.title
                    if existing_status.billing_project else "none"
                )
                self.stdout.write(self.style.ERROR(
                    f"User '{username}' already has maintenance status "
                    f"'{existing_status.get_status_display()}' (project: {current_project}). "
                    "Use --force to update."
                ))
                return

        # Dry-run mode: print commands that would be executed
        if dry_run:
            self._print_dry_run(
                user=user,
                status=status,
                project=project,
                existing_status=existing_status,
                created_dt=created_dt,
                modified_dt=modified_dt,
            )
            return

        # Execute the update
        self._set_maintenance_status(
            user=user,
            status=status,
            project=project,
            existing_status=existing_status,
            quiet=quiet,
            created_dt=created_dt,
            modified_dt=modified_dt,
        )

        # Summary
        if not quiet:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Account maintenance fee configured successfully."))
            self.stdout.write(f"  User: {username}")
            self.stdout.write(f"  Status: {status}")
            if project:
                self.stdout.write(f"  Billing project: {project.title}")

    @staticmethod
    def _parse_datetime(value, flag_name):
        """Parse a date or datetime string into a timezone-aware datetime.

        Accepts ``YYYY-MM-DD`` (interpreted as midnight UTC) or any ISO 8601
        datetime string.  Returns ``None`` when *value* is ``None`` or empty.
        """
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            try:
                dt = datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                raise ValueError(
                    f"Invalid --{flag_name} value '{value}'. "
                    "Use YYYY-MM-DD or ISO 8601 datetime format."
                )
        if dt.tzinfo is None:
            dt = timezone.make_aware(dt)
        return dt

    def _find_user(self, username):
        """Find a user by username.

        Args:
            username: Username to look up

        Returns:
            User instance or None if not found
        """
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"User '{username}' not found"
            ))
            return None

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

    def _get_existing_status(self, user):
        """Get the user's existing maintenance status if any.

        Args:
            user: User instance

        Returns:
            UserMaintenanceStatus instance or None
        """
        try:
            return UserMaintenanceStatus.objects.get(user=user)
        except UserMaintenanceStatus.DoesNotExist:
            return None

    def _print_dry_run(self, user, status, project, existing_status,
                       created_dt=None, modified_dt=None):
        """Print the Django ORM commands that would be executed."""
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("[DRY-RUN] Would execute the following commands:"))
        self.stdout.write("")

        project_repr = f"<Project: {project.title}>" if project else "None"

        if existing_status:
            self.stdout.write("# Update existing maintenance status")
            self.stdout.write(f"maintenance_status = UserMaintenanceStatus.objects.get(user=<User: {user.username}>)")
            self.stdout.write(f"maintenance_status.status = '{status}'")
            self.stdout.write(f"maintenance_status.billing_project = {project_repr}")
            self.stdout.write("maintenance_status.save()")
        else:
            self.stdout.write("# Create new maintenance status")
            self.stdout.write("UserMaintenanceStatus.objects.create(")
            self.stdout.write(f"    user=<User: {user.username}>,")
            self.stdout.write(f"    status='{status}',")
            self.stdout.write(f"    billing_project={project_repr},")
            self.stdout.write(")")

        if created_dt is not None or modified_dt is not None:
            self.stdout.write("")
            self.stdout.write("# Override timestamps (bypass auto_now)")
            parts = []
            if created_dt is not None:
                parts.append(f"created='{created_dt.isoformat()}'")
            if modified_dt is not None:
                parts.append(f"modified='{modified_dt.isoformat()}'")
            self.stdout.write(
                f"UserMaintenanceStatus.objects.filter(pk=ms.pk).update({', '.join(parts)})"
            )

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("[DRY-RUN] No changes made."))

    def _set_maintenance_status(self, user, status, project, existing_status, quiet,
                               created_dt=None, modified_dt=None):
        """Set the maintenance status for a user.

        Args:
            user: User instance
            status: Status string (inactive, basic, advanced)
            project: Project instance or None
            existing_status: Existing UserMaintenanceStatus or None
            quiet: Suppress output if True
            created_dt: Optional datetime override for created timestamp
            modified_dt: Optional datetime override for modified timestamp
        """
        if existing_status:
            # Update existing record
            old_status = existing_status.get_status_display()
            old_project = (
                existing_status.billing_project.title
                if existing_status.billing_project else "none"
            )

            existing_status.status = status
            existing_status.billing_project = project
            existing_status.save()

            if not quiet:
                self.stdout.write(self.style.SUCCESS(
                    f"Updated maintenance status for '{user.username}' "
                    f"(was: {old_status}, project: {old_project})"
                ))

            record = existing_status
        else:
            # Create new record
            record = UserMaintenanceStatus.objects.create(
                user=user,
                status=status,
                billing_project=project,
            )
            if not quiet:
                self.stdout.write(self.style.SUCCESS(
                    f"Created maintenance status for '{user.username}'"
                ))

        # Override timestamps if specified (uses queryset.update to bypass auto_now)
        update_fields = {}
        if created_dt is not None:
            update_fields["created"] = created_dt
        if modified_dt is not None:
            update_fields["modified"] = modified_dt
        if update_fields:
            UserMaintenanceStatus.objects.filter(pk=record.pk).update(**update_fields)
            if not quiet:
                for field_name, value in update_fields.items():
                    self.stdout.write(self.style.SUCCESS(
                        f"Set {field_name} to {value.isoformat()}"
                    ))

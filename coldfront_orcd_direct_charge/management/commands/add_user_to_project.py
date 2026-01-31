# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Django management command to add a user to an ORCD project.

Adds a user to an existing ORCD project with a specified role. The user
will be assigned both a ColdFront ProjectUser record and an ORCD-specific
ProjectMemberRole record.

ORCD Member Roles:
    - financial_admin: Can manage cost allocations, manage all roles, create reservations.
                       NOT included in reservations or maintenance fee billing.
    - technical_admin: Can manage members and technical admins, create reservations.
                       Included in reservations and maintenance fee billing.
    - member: Can create reservations only.
              Included in reservations and maintenance fee billing.

Examples:
    # Add a user as a member
    coldfront add_user_to_project jsmith research_lab --role member

    # Add a user as financial admin
    coldfront add_user_to_project jsmith research_lab --role financial_admin

    # Add a user as technical admin with project ID
    coldfront add_user_to_project jsmith 42 --role technical_admin

    # Preview changes without making them
    coldfront add_user_to_project jsmith research_lab --role member --dry-run

    # Update existing role (requires --force)
    coldfront add_user_to_project jsmith research_lab --role technical_admin --force
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from coldfront.core.project.models import (
    Project,
    ProjectUser,
    ProjectUserRoleChoice,
    ProjectUserStatusChoice,
)

from coldfront_orcd_direct_charge.models import ProjectMemberRole


# Valid ORCD roles
VALID_ROLES = {
    "financial_admin": ProjectMemberRole.RoleChoices.FINANCIAL_ADMIN,
    "technical_admin": ProjectMemberRole.RoleChoices.TECHNICAL_ADMIN,
    "member": ProjectMemberRole.RoleChoices.MEMBER,
}


class Command(BaseCommand):
    help = "Add a user to an ORCD project with a specified role"

    def add_arguments(self, parser):
        # Required positional arguments
        parser.add_argument(
            "username",
            type=str,
            help="Username of the user to add to the project",
        )
        parser.add_argument(
            "project",
            type=str,
            help="Project name (e.g., 'jsmith_group') or project ID",
        )

        # Required role option
        parser.add_argument(
            "--role",
            type=str,
            required=True,
            choices=list(VALID_ROLES.keys()),
            help="ORCD role to assign: financial_admin, technical_admin, or member",
        )

        # Optional flags
        parser.add_argument(
            "--force",
            action="store_true",
            help="Update existing role assignment instead of reporting error",
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
        project_identifier = options["project"]
        role_name = options["role"]
        force = options["force"]
        dry_run = options["dry_run"]
        quiet = options["quiet"]

        # Look up the user
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User not found: {username}"))
            return

        # Look up the project
        project = self._find_project(project_identifier)
        if not project:
            return

        # Get the role choice
        role_choice = VALID_ROLES[role_name]

        # Check if user is the project owner (PI)
        if project.pi == user:
            self.stdout.write(self.style.ERROR(
                f"User '{username}' is the project owner (PI). "
                "The owner role is implicit and cannot be assigned additional roles."
            ))
            return

        # Check if role already exists
        existing_role = ProjectMemberRole.objects.filter(
            project=project,
            user=user,
            role=role_choice,
        ).first()

        if existing_role and not force:
            self.stdout.write(self.style.ERROR(
                f"User '{username}' already has role '{role_name}' in project '{project.title}'. "
                "Use --force to update."
            ))
            return

        # Check for other existing roles (user may have a different role)
        other_roles = ProjectMemberRole.objects.filter(
            project=project,
            user=user,
        ).exclude(role=role_choice)

        # Dry-run mode: print commands that would be executed
        if dry_run:
            self._print_dry_run(
                username=username,
                project=project,
                role_name=role_name,
                role_choice=role_choice,
                existing_role=existing_role,
                other_roles=other_roles,
            )
            return

        # Execute the commands
        if existing_role:
            # Role already exists with same value, nothing to update
            if not quiet:
                self.stdout.write(self.style.WARNING(
                    f"User '{username}' already has role '{role_name}' in project '{project.title}' (no changes made)"
                ))
        else:
            # Create the ORCD member role
            ProjectMemberRole.objects.create(
                project=project,
                user=user,
                role=role_choice,
            )
            if not quiet:
                role_display = dict(ProjectMemberRole.RoleChoices.choices).get(role_choice, role_name)
                self.stdout.write(self.style.SUCCESS(
                    f"Added role '{role_display}' for user '{username}' in project '{project.title}'"
                ))

        # Ensure user has a ProjectUser record (ColdFront requirement)
        project_user, created = ProjectUser.objects.get_or_create(
            project=project,
            user=user,
            defaults={
                "role": ProjectUserRoleChoice.objects.get(name="User"),
                "status": ProjectUserStatusChoice.objects.get(name="Active"),
            }
        )

        if created and not quiet:
            self.stdout.write(self.style.SUCCESS(
                f"Created ColdFront ProjectUser record for '{username}'"
            ))

        # Summary
        if not quiet:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("User added to project."))
            self.stdout.write(f"  User: {username}")
            self.stdout.write(f"  Project: {project.title}")
            self.stdout.write(f"  Role: {role_name}")

            # List all current roles for this user in the project
            all_roles = ProjectMemberRole.objects.filter(
                project=project,
                user=user,
            ).values_list("role", flat=True)
            if all_roles:
                role_displays = [
                    dict(ProjectMemberRole.RoleChoices.choices).get(r, r)
                    for r in all_roles
                ]
                self.stdout.write(f"  All roles: {', '.join(role_displays)}")

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

    def _print_dry_run(self, username, project, role_name, role_choice,
                       existing_role, other_roles):
        """Print the Django ORM commands that would be executed."""
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("[DRY-RUN] Would execute the following commands:"))
        self.stdout.write("")

        if existing_role:
            self.stdout.write("# Role already exists - no changes needed")
            self.stdout.write(f"# User '{username}' already has role '{role_name}' in project '{project.title}'")
        else:
            self.stdout.write("# Create ORCD member role")
            self.stdout.write("ProjectMemberRole.objects.create(")
            self.stdout.write(f"    project=<Project: {project.title}>,")
            self.stdout.write(f"    user=<User: {username}>,")
            self.stdout.write(f"    role='{role_choice}',  # {role_name}")
            self.stdout.write(")")

        self.stdout.write("")
        self.stdout.write("# Ensure ColdFront ProjectUser record exists")
        self.stdout.write("ProjectUser.objects.get_or_create(")
        self.stdout.write(f"    project=<Project: {project.title}>,")
        self.stdout.write(f"    user=<User: {username}>,")
        self.stdout.write("    defaults={")
        self.stdout.write("        'role': ProjectUserRoleChoice.objects.get(name='User'),")
        self.stdout.write("        'status': ProjectUserStatusChoice.objects.get(name='Active'),")
        self.stdout.write("    }")
        self.stdout.write(")")

        if other_roles:
            self.stdout.write("")
            self.stdout.write("# Note: User has other existing roles in this project:")
            for role in other_roles:
                role_display = dict(ProjectMemberRole.RoleChoices.choices).get(role.role, role.role)
                self.stdout.write(f"#   - {role_display}")

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("[DRY-RUN] No changes made."))

# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Django management command to create ORCD projects.

Creates projects with ORCD-specific features including member roles.
Follows the USERNAME_group naming convention by default.

Examples:
    coldfront create_orcd_project jsmith
    coldfront create_orcd_project jsmith --project-name "Research Lab"
    coldfront create_orcd_project jsmith --add-member auser:financial_admin
    coldfront create_orcd_project jsmith --add-member buser:technical_admin --add-member cuser:member
    coldfront create_orcd_project jsmith --dry-run
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from coldfront.core.project.models import (
    Project,
    ProjectStatusChoice,
    ProjectUser,
    ProjectUserRoleChoice,
    ProjectUserStatusChoice,
)

from coldfront_orcd_direct_charge.models import ProjectMemberRole


# Valid ORCD roles for --add-member
VALID_ROLES = {
    "financial_admin": ProjectMemberRole.RoleChoices.FINANCIAL_ADMIN,
    "technical_admin": ProjectMemberRole.RoleChoices.TECHNICAL_ADMIN,
    "member": ProjectMemberRole.RoleChoices.MEMBER,
}


def parse_member_arg(member_arg):
    """Parse a member argument in format 'username:role'.
    
    Returns:
        Tuple of (username, role_choice) or raises ValueError.
    """
    if ":" not in member_arg:
        raise ValueError(
            f"Invalid format '{member_arg}'. Expected 'username:role' "
            f"where role is one of: {', '.join(VALID_ROLES.keys())}"
        )
    
    username, role = member_arg.split(":", 1)
    username = username.strip()
    role = role.strip().lower()
    
    if not username:
        raise ValueError("Username cannot be empty")
    
    if role not in VALID_ROLES:
        raise ValueError(
            f"Invalid role '{role}'. Must be one of: {', '.join(VALID_ROLES.keys())}"
        )
    
    return username, VALID_ROLES[role]


class Command(BaseCommand):
    help = "Create an ORCD project with optional member roles"

    def add_arguments(self, parser):
        # Required positional argument
        parser.add_argument(
            "username",
            type=str,
            help="Username of the project owner (PI)",
        )

        # Optional arguments
        parser.add_argument(
            "--project-name",
            type=str,
            dest="project_name",
            help="Project name/title (defaults to USERNAME_group)",
        )
        parser.add_argument(
            "--description",
            type=str,
            help="Project description (defaults to 'Group project for USERNAME')",
        )
        parser.add_argument(
            "--status",
            type=str,
            choices=["New", "Active", "Archived"],
            default="Active",
            help="Project status (default: Active)",
        )
        parser.add_argument(
            "--add-member",
            type=str,
            action="append",
            metavar="USER:ROLE",
            help=(
                "Add a member with an ORCD role. Format: username:role where role is "
                "financial_admin, technical_admin, or member. Can be specified multiple times."
            ),
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Update existing project instead of reporting error",
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
        dry_run = options["dry_run"]
        quiet = options["quiet"]
        force = options["force"]

        # Look up the owner user
        try:
            owner = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User not found: {username}"))
            return

        # Determine project name and description
        title = options.get("project_name") or f"{username}_group"
        description = options.get("description") or f"Group project for {username}"
        status_name = options["status"]

        # Parse member arguments
        members_to_add = []
        member_args = options.get("add_member") or []
        for member_arg in member_args:
            try:
                member_username, role_choice = parse_member_arg(member_arg)
                members_to_add.append((member_username, role_choice))
            except ValueError as e:
                self.stdout.write(self.style.ERROR(str(e)))
                return

        # Validate member users exist
        member_users = {}
        for member_username, role_choice in members_to_add:
            if member_username == username:
                self.stdout.write(self.style.ERROR(
                    f"Cannot add owner '{username}' as a member. "
                    "The owner role is implicit."
                ))
                return
            try:
                member_users[member_username] = User.objects.get(username=member_username)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"Member user not found: {member_username}"
                ))
                return

        # Check if project already exists
        project_exists = Project.objects.filter(title=title, pi=owner).exists()
        if project_exists and not force:
            self.stdout.write(self.style.ERROR(
                f"Project '{title}' already exists for user '{username}'. "
                "Use --force to update."
            ))
            return

        # Dry-run mode: print commands that would be executed
        if dry_run:
            self._print_dry_run(
                username=username,
                title=title,
                description=description,
                status_name=status_name,
                project_exists=project_exists,
                members_to_add=members_to_add,
            )
            return

        # Get status choice
        try:
            status = ProjectStatusChoice.objects.get(name=status_name)
        except ProjectStatusChoice.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"Project status not found: {status_name}"
            ))
            return

        # Execute the commands
        if project_exists:
            project = Project.objects.get(title=title, pi=owner)
            project.description = description
            project.status = status
            project.save()
            if not quiet:
                self.stdout.write(self.style.SUCCESS(
                    f"Updated existing project '{title}'"
                ))
        else:
            # Create the project
            project = Project.objects.create(
                title=title,
                pi=owner,
                status=status,
                description=description,
            )

            # Add owner as Manager (ColdFront role - required)
            ProjectUser.objects.create(
                project=project,
                user=owner,
                role=ProjectUserRoleChoice.objects.get(name="Manager"),
                status=ProjectUserStatusChoice.objects.get(name="Active"),
            )

            if not quiet:
                self.stdout.write(self.style.SUCCESS(
                    f"Created project '{title}' with owner '{username}'"
                ))

        # Add members with ORCD roles
        for member_username, role_choice in members_to_add:
            member_user = member_users[member_username]
            self._add_member(project, member_user, role_choice, quiet)

        # Summary
        if not quiet:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Project setup complete."))
            self.stdout.write(f"  Title: {title}")
            self.stdout.write(f"  Owner: {username}")
            self.stdout.write(f"  Status: {status_name}")
            if members_to_add:
                self.stdout.write(f"  Members added: {len(members_to_add)}")

    def _print_dry_run(self, username, title, description, status_name,
                       project_exists, members_to_add):
        """Print the Django ORM commands that would be executed."""
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("[DRY-RUN] Would execute the following commands:"))
        self.stdout.write("")

        if project_exists:
            self.stdout.write("# Update existing project")
            self.stdout.write(f"project = Project.objects.get(title='{title}', pi=<User: {username}>)")
            self.stdout.write(f"project.description = '{description}'")
            self.stdout.write(f"project.status = ProjectStatusChoice.objects.get(name='{status_name}')")
            self.stdout.write("project.save()")
        else:
            self.stdout.write("# Create project")
            self.stdout.write("project = Project.objects.create(")
            self.stdout.write(f"    title='{title}',")
            self.stdout.write(f"    pi=<User: {username}>,")
            self.stdout.write(f"    status=ProjectStatusChoice.objects.get(name='{status_name}'),")
            self.stdout.write(f"    description='{description}',")
            self.stdout.write(")")
            self.stdout.write("")
            self.stdout.write("# Add owner as Manager")
            self.stdout.write("ProjectUser.objects.create(")
            self.stdout.write("    project=project,")
            self.stdout.write(f"    user=<User: {username}>,")
            self.stdout.write("    role=ProjectUserRoleChoice.objects.get(name='Manager'),")
            self.stdout.write("    status=ProjectUserStatusChoice.objects.get(name='Active'),")
            self.stdout.write(")")

        for member_username, role_choice in members_to_add:
            self.stdout.write("")
            self.stdout.write(f"# Add member with ORCD role")
            self.stdout.write("ProjectMemberRole.objects.get_or_create(")
            self.stdout.write("    project=project,")
            self.stdout.write(f"    user=<User: {member_username}>,")
            self.stdout.write(f"    role='{role_choice}',")
            self.stdout.write(")")

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("[DRY-RUN] No changes made."))

    def _add_member(self, project, user, role_choice, quiet):
        """Add a member with an ORCD role to the project."""
        # Check if member role already exists
        existing_role = ProjectMemberRole.objects.filter(
            project=project,
            user=user,
            role=role_choice,
        ).first()

        if existing_role:
            if not quiet:
                self.stdout.write(self.style.WARNING(
                    f"User '{user.username}' already has role '{role_choice}' in this project"
                ))
            return

        # Create the ORCD member role
        ProjectMemberRole.objects.create(
            project=project,
            user=user,
            role=role_choice,
        )

        # Also ensure user has a ProjectUser record (ColdFront requirement)
        project_user, created = ProjectUser.objects.get_or_create(
            project=project,
            user=user,
            defaults={
                "role": ProjectUserRoleChoice.objects.get(name="User"),
                "status": ProjectUserStatusChoice.objects.get(name="Active"),
            }
        )

        if not quiet:
            role_display = dict(ProjectMemberRole.RoleChoices.choices).get(role_choice, role_choice)
            self.stdout.write(self.style.SUCCESS(
                f"Added '{user.username}' as {role_display}"
            ))

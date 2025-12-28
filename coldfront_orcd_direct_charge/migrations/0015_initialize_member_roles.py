# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Data migration to initialize ProjectMemberRole for existing project members.

Migration logic:
- Skip project PIs (they are owners implicitly via project.pi)
- Existing ProjectUser with Manager role become Technical Admin
- Existing ProjectUser with User role become Member

This ensures existing projects continue to function with the new role system.
"""

from django.db import migrations


def initialize_member_roles(apps, schema_editor):
    """Create ProjectMemberRole entries for existing ProjectUser records."""
    ProjectUser = apps.get_model("project", "ProjectUser")
    ProjectMemberRole = apps.get_model("coldfront_orcd_direct_charge", "ProjectMemberRole")

    # Role mapping from ColdFront roles to ORCD roles
    role_mapping = {
        "Manager": "technical_admin",
        "User": "member",
    }

    # Get all active project users
    project_users = ProjectUser.objects.select_related(
        "project", "user", "role", "status"
    ).filter(status__name="Active")

    created_count = 0
    skipped_pi_count = 0
    skipped_existing_count = 0

    for pu in project_users:
        # Skip if user is the project PI (they are owners implicitly)
        if pu.project.pi_id == pu.user_id:
            skipped_pi_count += 1
            continue

        # Map the role
        orcd_role = role_mapping.get(pu.role.name)
        if not orcd_role:
            # Unknown role, skip
            continue

        # Check if role already exists (idempotency)
        if ProjectMemberRole.objects.filter(project=pu.project, user=pu.user).exists():
            skipped_existing_count += 1
            continue

        # Create the ProjectMemberRole
        ProjectMemberRole.objects.create(
            project=pu.project,
            user=pu.user,
            role=orcd_role,
        )
        created_count += 1

    print(f"\nProjectMemberRole initialization complete:")
    print(f"  - Created: {created_count} role assignments")
    print(f"  - Skipped (PI/Owner): {skipped_pi_count}")
    print(f"  - Skipped (already exists): {skipped_existing_count}")


def reverse_member_roles(apps, schema_editor):
    """Remove all ProjectMemberRole entries (reverse migration)."""
    ProjectMemberRole = apps.get_model("coldfront_orcd_direct_charge", "ProjectMemberRole")
    count = ProjectMemberRole.objects.count()
    ProjectMemberRole.objects.all().delete()
    print(f"\nRemoved {count} ProjectMemberRole entries")


class Migration(migrations.Migration):

    dependencies = [
        ("coldfront_orcd_direct_charge", "0014_projectmemberrole"),
        ("project", "0006_historicalproject_institution_project_institution"),
    ]

    operations = [
        migrations.RunPython(initialize_member_roles, reverse_member_roles),
    ]


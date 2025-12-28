# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Data migration to create USERNAME_group projects for existing users.

Creates a group project for all users who have a USERNAME_personal project
(indicating they were set up with auto-configuration enabled).
"""

from django.db import migrations


def create_group_projects(apps, schema_editor):
    """Create USERNAME_group projects for users with _personal projects."""
    User = apps.get_model("auth", "User")
    Project = apps.get_model("project", "Project")
    ProjectStatusChoice = apps.get_model("project", "ProjectStatusChoice")
    ProjectUser = apps.get_model("project", "ProjectUser")
    ProjectUserRoleChoice = apps.get_model("project", "ProjectUserRoleChoice")
    ProjectUserStatusChoice = apps.get_model("project", "ProjectUserStatusChoice")

    # Get required status/role objects
    try:
        active_status = ProjectStatusChoice.objects.get(name="Active")
        manager_role = ProjectUserRoleChoice.objects.get(name="Manager")
        active_user_status = ProjectUserStatusChoice.objects.get(name="Active")
    except (ProjectStatusChoice.DoesNotExist, ProjectUserRoleChoice.DoesNotExist, ProjectUserStatusChoice.DoesNotExist):
        # Required choices don't exist yet - skip migration
        return

    created_count = 0
    for user in User.objects.all():
        personal_title = f"{user.username}_personal"
        group_title = f"{user.username}_group"

        # Only create group project if user has a personal project
        # (indicating auto-config was enabled for them)
        has_personal = Project.objects.filter(title=personal_title, pi=user).exists()
        has_group = Project.objects.filter(title=group_title, pi=user).exists()

        if has_personal and not has_group:
            # Create the group project
            project = Project.objects.create(
                title=group_title,
                pi=user,
                status=active_status,
                description=f"Group project for {user.username}",
            )

            # Add user as Manager
            ProjectUser.objects.create(
                project=project,
                user=user,
                role=manager_role,
                status=active_user_status,
            )
            created_count += 1

    if created_count:
        print(f"  Created {created_count} group project(s)")


def delete_group_projects(apps, schema_editor):
    """Delete USERNAME_group projects (reverse migration)."""
    Project = apps.get_model("project", "Project")
    deleted_count, _ = Project.objects.filter(title__endswith="_group").delete()
    if deleted_count:
        print(f"  Deleted {deleted_count} group project(s)")


class Migration(migrations.Migration):

    dependencies = [
        ("coldfront_orcd_direct_charge", "0008_delete_old_default_projects"),
        ("project", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_group_projects, delete_group_projects),
    ]


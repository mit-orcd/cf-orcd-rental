# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Signal handlers for auto-configuration features.

When AUTO_PI_ENABLE is True, new users automatically get is_pi=True.
When AUTO_DEFAULT_PROJECT_ENABLE is True, new users get USERNAME_personal and USERNAME_group projects.

These features are IRREVERSIBLE - once applied, changes persist even if features are disabled.
"""

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings


@receiver(post_save, sender=User)
def auto_configure_user(sender, instance, created, **kwargs):
    """Apply auto-PI and auto-default-project to new users."""
    if not created:
        return

    # Auto-PI: set is_pi=True if enabled
    if getattr(settings, "AUTO_PI_ENABLE", False):
        if hasattr(instance, "userprofile"):
            instance.userprofile.is_pi = True
            instance.userprofile.save()

    # Auto Default Projects: create USERNAME_personal and USERNAME_group
    if getattr(settings, "AUTO_DEFAULT_PROJECT_ENABLE", False):
        create_default_project_for_user(instance)
        create_group_project_for_user(instance)


def create_default_project_for_user(user):
    """
    Create the default project for a user if it doesn't exist.

    The project is named USERNAME_personal.
    The user is set as PI and added as Manager with Active status.
    """
    from coldfront.core.project.models import (
        Project,
        ProjectStatusChoice,
        ProjectUser,
        ProjectUserRoleChoice,
        ProjectUserStatusChoice,
    )

    project_title = f"{user.username}_personal"

    # Check if project already exists
    if Project.objects.filter(title=project_title, pi=user).exists():
        return

    # User must be PI to own a project
    if hasattr(user, "userprofile"):
        user.userprofile.is_pi = True
        user.userprofile.save()

    # Create the project
    status = ProjectStatusChoice.objects.get(name="Active")
    project = Project.objects.create(
        title=project_title,
        pi=user,
        status=status,
        description=f"Personal project for {user.username}",
    )

    # Add user as Manager on their own project
    ProjectUser.objects.create(
        project=project,
        user=user,
        role=ProjectUserRoleChoice.objects.get(name="Manager"),
        status=ProjectUserStatusChoice.objects.get(name="Active"),
    )


def create_group_project_for_user(user):
    """
    Create the group project for a user if it doesn't exist.

    The project is named USERNAME_group.
    The user is set as PI and added as Manager with Active status.
    """
    from coldfront.core.project.models import (
        Project,
        ProjectStatusChoice,
        ProjectUser,
        ProjectUserRoleChoice,
        ProjectUserStatusChoice,
    )

    project_title = f"{user.username}_group"

    # Check if project already exists
    if Project.objects.filter(title=project_title, pi=user).exists():
        return

    # User must be PI to own a project
    if hasattr(user, "userprofile"):
        user.userprofile.is_pi = True
        user.userprofile.save()

    # Create the project
    status = ProjectStatusChoice.objects.get(name="Active")
    project = Project.objects.create(
        title=project_title,
        pi=user,
        status=status,
        description=f"Group project for {user.username}",
    )

    # Add user as Manager on their own project
    ProjectUser.objects.create(
        project=project,
        user=user,
        role=ProjectUserRoleChoice.objects.get(name="Manager"),
        status=ProjectUserStatusChoice.objects.get(name="Active"),
    )

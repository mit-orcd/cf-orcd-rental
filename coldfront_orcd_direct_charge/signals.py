# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Signal handlers for auto-configuration features.

When AUTO_PI_ENABLE is True, new users automatically get is_pi=True.
When AUTO_DEFAULT_PROJECT_ENABLE is True, new users get USERNAME_personal and USERNAME_group projects.
New users always get a UserMaintenanceStatus record with 'inactive' default.

When a user is removed from a project that is their billing project for maintenance fees,
their maintenance status is automatically reset to 'inactive'.

These features are IRREVERSIBLE - once applied, changes persist even if features are disabled.
"""

from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings

from coldfront.core.project.models import ProjectUser


@receiver(post_save, sender=User)
def auto_configure_user(sender, instance, created, **kwargs):
    """Apply auto-PI, auto-default-project, and maintenance status to new users."""
    if not created:
        return

    # Always create maintenance status for new users
    create_maintenance_status_for_user(instance)

    # Auto-PI: set is_pi=True if enabled
    if getattr(settings, "AUTO_PI_ENABLE", False):
        if hasattr(instance, "userprofile"):
            instance.userprofile.is_pi = True
            instance.userprofile.save()

    # Auto Default Projects: create USERNAME_personal and USERNAME_group
    if getattr(settings, "AUTO_DEFAULT_PROJECT_ENABLE", False):
        create_default_project_for_user(instance)
        create_group_project_for_user(instance)


def create_maintenance_status_for_user(user):
    """
    Create UserMaintenanceStatus for a user if it doesn't exist.

    Default status is 'inactive'.
    """
    from coldfront_orcd_direct_charge.models import UserMaintenanceStatus

    UserMaintenanceStatus.objects.get_or_create(
        user=user,
        defaults={"status": UserMaintenanceStatus.StatusChoices.INACTIVE},
    )


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


# =============================================================================
# Project Membership Change Handlers
# Reset maintenance status when user loses access to their billing project
# =============================================================================


@receiver(post_save, sender=ProjectUser)
def check_maintenance_status_on_project_user_change(sender, instance, **kwargs):
    """Reset maintenance status if user's billing project membership becomes inactive."""
    # Only act if status is not Active
    if instance.status.name == "Active":
        return

    reset_maintenance_if_billing_project(instance.user, instance.project)


@receiver(post_delete, sender=ProjectUser)
def check_maintenance_status_on_project_user_delete(sender, instance, **kwargs):
    """Reset maintenance status if user is deleted from their billing project."""
    reset_maintenance_if_billing_project(instance.user, instance.project)


def reset_maintenance_if_billing_project(user, project):
    """
    Reset user's maintenance status to inactive if project is their billing project.

    Called when a user is removed from a project (either by deletion or status change).
    If the project was being used as their billing project for maintenance fees,
    their status is reset to 'inactive' and the billing project is cleared.
    """
    from coldfront_orcd_direct_charge.models import UserMaintenanceStatus

    try:
        maintenance_status = UserMaintenanceStatus.objects.get(
            user=user,
            billing_project=project,
        )
        maintenance_status.status = UserMaintenanceStatus.StatusChoices.INACTIVE
        maintenance_status.billing_project = None
        maintenance_status.save()
    except UserMaintenanceStatus.DoesNotExist:
        pass  # No matching maintenance status, nothing to reset

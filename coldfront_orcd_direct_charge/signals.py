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

import logging

from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings

from coldfront.core.project.models import Project, ProjectUser

logger = logging.getLogger(__name__)


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


@receiver(post_save, sender=Project)
def auto_activate_project(sender, instance, created, **kwargs):
    """Automatically activate newly created projects.
    
    The rental portal doesn't require project approval, so new projects
    are immediately set to Active status.
    """
    if not created:
        return
    
    if instance.status.name == "New":
        from coldfront.core.project.models import ProjectStatusChoice
        active_status = ProjectStatusChoice.objects.get(name="Active")
        instance.status = active_status
        instance.save(update_fields=["status"])


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
    Reset user's maintenance status to inactive if project is their billing project
    and the user can no longer use it for maintenance fees.

    Called when a user is removed from a project or their role changes.
    Checks the user's current ORCD role to determine if they can still use
    the project for maintenance fees (owner, technical_admin, or member can;
    financial_admin and None cannot).
    """
    from coldfront_orcd_direct_charge.models import (
        UserMaintenanceStatus,
        can_use_for_maintenance_fee,
    )

    try:
        maintenance_status = UserMaintenanceStatus.objects.get(
            user=user,
            billing_project=project,
        )

        # Check if user can still use this project for maintenance fees
        if not can_use_for_maintenance_fee(user, project):
            logger.info(
                "Resetting maintenance status: user=%s lost eligibility for project=%s, "
                "status reset to inactive",
                user.username, project.title
            )
            maintenance_status.status = UserMaintenanceStatus.StatusChoices.INACTIVE
            maintenance_status.billing_project = None
            maintenance_status.save()
    except UserMaintenanceStatus.DoesNotExist:
        pass  # No matching maintenance status, nothing to reset


# =============================================================================
# ProjectMemberRole Change Handlers
# Reset maintenance status when user's ORCD role changes to financial_admin
# or when they are removed from the project
# =============================================================================


def connect_member_role_signals():
    """
    Connect signal handlers for ProjectMemberRole.
    
    This is called from apps.py to avoid circular imports.
    """
    from coldfront_orcd_direct_charge.models import ProjectMemberRole

    post_save.connect(check_maintenance_on_role_change, sender=ProjectMemberRole)
    post_delete.connect(check_maintenance_on_role_delete, sender=ProjectMemberRole)


def check_maintenance_on_role_change(sender, instance, **kwargs):
    """Reset maintenance status if user's role changes to financial_admin."""
    from coldfront_orcd_direct_charge.models import ProjectMemberRole

    # If user is now a financial admin, they can't use this project for maintenance fees
    if instance.role == ProjectMemberRole.RoleChoices.FINANCIAL_ADMIN:
        logger.debug(
            "Member role changed to financial_admin: user=%s, project=%s, checking maintenance status",
            instance.user.username, instance.project.title
        )
        reset_maintenance_if_billing_project(instance.user, instance.project)


def check_maintenance_on_role_delete(sender, instance, **kwargs):
    """Reset maintenance status if user is removed from project."""
    logger.debug(
        "Member role deleted: user=%s, project=%s, checking maintenance status",
        instance.user.username, instance.project.title
    )
    reset_maintenance_if_billing_project(instance.user, instance.project)


# =============================================================================
# Authentication Signal Handlers
# Log user login, logout, and failed login attempts
# =============================================================================

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Log successful user login."""
    from coldfront_orcd_direct_charge.models import ActivityLog, log_activity

    log_activity(
        action="auth.login",
        category=ActivityLog.ActionCategory.AUTH,
        description=f"User {user.username} logged in",
        user=user,
        request=request,
        extra_data={"username": user.username},
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Log user logout."""
    from coldfront_orcd_direct_charge.models import ActivityLog, log_activity

    if user:
        log_activity(
            action="auth.logout",
            category=ActivityLog.ActionCategory.AUTH,
            description=f"User {user.username} logged out",
            user=user,
            request=request,
            extra_data={"username": user.username},
        )


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    """Log failed login attempts."""
    from coldfront_orcd_direct_charge.models import ActivityLog, log_activity

    username = credentials.get("username", "unknown")
    log_activity(
        action="auth.login_failed",
        category=ActivityLog.ActionCategory.AUTH,
        description=f"Failed login attempt for {username}",
        request=request,
        extra_data={"attempted_username": username},
    )


# =============================================================================
# Activity Logging Signal Handlers
# Log key model changes for audit trail
# =============================================================================


def connect_activity_log_signals():
    """
    Connect signal handlers for activity logging.

    This is called from apps.py to avoid circular imports.
    """
    from coldfront_orcd_direct_charge.models import (
        Reservation,
        ProjectMemberRole,
        ProjectCostAllocation,
        UserMaintenanceStatus,
        RentalRate,
    )

    post_save.connect(log_reservation_change, sender=Reservation)
    post_save.connect(log_member_role_change, sender=ProjectMemberRole)
    post_delete.connect(log_member_role_delete, sender=ProjectMemberRole)
    post_save.connect(log_cost_allocation_change, sender=ProjectCostAllocation)
    post_save.connect(log_maintenance_status_change, sender=UserMaintenanceStatus)
    post_save.connect(log_rate_change, sender=RentalRate)


def log_reservation_change(sender, instance, created, **kwargs):
    """Log reservation creation and status changes."""
    from coldfront_orcd_direct_charge.models import ActivityLog, log_activity

    if created:
        log_activity(
            action="reservation.created",
            category=ActivityLog.ActionCategory.RESERVATION,
            description=f"Reservation #{instance.pk} created for project {instance.project.title}",
            user=instance.requesting_user,
            target=instance,
            extra_data={
                "status": instance.status,
                "project_id": instance.project.pk,
                "project_title": instance.project.title,
                "node": instance.node_instance.associated_resource_address,
                "start_date": str(instance.start_date),
                "num_blocks": instance.num_blocks,
            },
        )
    else:
        # Log status changes - these are also handled in views for more context
        # This catches any other updates
        log_activity(
            action="reservation.updated",
            category=ActivityLog.ActionCategory.RESERVATION,
            description=f"Reservation #{instance.pk} updated (status: {instance.get_status_display()})",
            target=instance,
            extra_data={
                "status": instance.status,
                "project_id": instance.project.pk,
            },
        )


def log_member_role_change(sender, instance, created, **kwargs):
    """Log member role additions."""
    from coldfront_orcd_direct_charge.models import ActivityLog, log_activity

    if created:
        log_activity(
            action="member.role_added",
            category=ActivityLog.ActionCategory.MEMBER,
            description=f"Role {instance.get_role_display()} added for {instance.user.username} in {instance.project.title}",
            target=instance,
            extra_data={
                "user_id": instance.user.pk,
                "username": instance.user.username,
                "project_id": instance.project.pk,
                "project_title": instance.project.title,
                "role": instance.role,
            },
        )


def log_member_role_delete(sender, instance, **kwargs):
    """Log member role removals."""
    from coldfront_orcd_direct_charge.models import ActivityLog, log_activity

    log_activity(
        action="member.role_removed",
        category=ActivityLog.ActionCategory.MEMBER,
        description=f"Role {instance.get_role_display()} removed for {instance.user.username} from {instance.project.title}",
        target=instance.project,
        extra_data={
            "user_id": instance.user.pk,
            "username": instance.user.username,
            "project_id": instance.project.pk,
            "project_title": instance.project.title,
            "role": instance.role,
        },
    )


def log_cost_allocation_change(sender, instance, created, **kwargs):
    """Log cost allocation changes."""
    from coldfront_orcd_direct_charge.models import ActivityLog, log_activity

    if created:
        log_activity(
            action="cost_allocation.created",
            category=ActivityLog.ActionCategory.COST_ALLOCATION,
            description=f"Cost allocation created for project {instance.project.title}",
            target=instance,
            extra_data={
                "project_id": instance.project.pk,
                "project_title": instance.project.title,
                "status": instance.status,
            },
        )
    else:
        log_activity(
            action="cost_allocation.updated",
            category=ActivityLog.ActionCategory.COST_ALLOCATION,
            description=f"Cost allocation updated for project {instance.project.title} (status: {instance.get_status_display()})",
            target=instance,
            extra_data={
                "project_id": instance.project.pk,
                "project_title": instance.project.title,
                "status": instance.status,
            },
        )


def log_maintenance_status_change(sender, instance, created, **kwargs):
    """Log maintenance status changes."""
    from coldfront_orcd_direct_charge.models import ActivityLog, log_activity

    if created:
        log_activity(
            action="maintenance.created",
            category=ActivityLog.ActionCategory.MAINTENANCE,
            description=f"Maintenance status created for {instance.user.username}",
            user=instance.user,
            target=instance,
            extra_data={
                "status": instance.status,
            },
        )
    else:
        billing_project = instance.billing_project.title if instance.billing_project else None
        log_activity(
            action="maintenance.updated",
            category=ActivityLog.ActionCategory.MAINTENANCE,
            description=f"Maintenance status updated for {instance.user.username}: {instance.get_status_display()}",
            user=instance.user,
            target=instance,
            extra_data={
                "status": instance.status,
                "billing_project": billing_project,
            },
        )


def log_rate_change(sender, instance, created, **kwargs):
    """Log rate creation and updates."""
    from coldfront_orcd_direct_charge.models import ActivityLog, log_activity

    action = "rate.created" if created else "rate.updated"
    description = (
        f"Rate for {instance.sku.name}: ${instance.rate}/{instance.sku.get_billing_unit_display()} "
        f"effective {instance.effective_date}"
    )

    log_activity(
        action=action,
        category=ActivityLog.ActionCategory.RATE,
        description=description,
        user=instance.set_by,
        target=instance,
        extra_data={
            "sku_code": instance.sku.sku_code,
            "sku_name": instance.sku.name,
            "rate": str(instance.rate),
            "effective_date": str(instance.effective_date),
            "billing_unit": instance.sku.billing_unit,
        },
    )

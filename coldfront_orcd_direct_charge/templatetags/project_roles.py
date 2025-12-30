# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Template tags for project member roles.

Supports multi-role: users can have multiple roles (e.g., Financial Admin AND Technical Admin).
"""

from collections import OrderedDict

from django import template

from coldfront_orcd_direct_charge.models import (
    ProjectCostAllocation,
    ProjectMemberRole,
    get_user_project_roles,
    can_edit_cost_allocation,
    can_manage_members,
    can_manage_financial_admins,
    has_approved_cost_allocation,
)

register = template.Library()

# Role display names and badge classes
ROLE_DISPLAY = {
    "owner": ("Owner", "badge-primary"),
    "financial_admin": ("Financial Admin", "badge-warning"),
    "technical_admin": ("Technical Admin", "badge-info"),
    "member": ("Member", "badge-secondary"),
}


@register.simple_tag
def get_project_members(project):
    """Get all members of a project with their ORCD roles.

    Users can have multiple roles. Returns a list of dictionaries with:
    - 'user': the User object
    - 'roles': list of role strings (e.g., ["owner", "financial_admin"])
    - 'roles_display': list of dicts with 'name' and 'badge_class' for each role
    - 'is_owner': True if user is the project owner

    The owner is included first, followed by other members sorted by username.

    Args:
        project: The ColdFront Project object

    Returns:
        List of member dictionaries
    """
    # Use OrderedDict to group roles by user while maintaining order
    members_dict = OrderedDict()

    # Add owner first (with owner role)
    owner = project.pi
    members_dict[owner.pk] = {
        "user": owner,
        "roles": ["owner"],
        "roles_display": [{"name": "Owner", "badge_class": "badge-primary"}],
        "is_owner": True,
    }

    # Get all role assignments for this project
    member_roles = ProjectMemberRole.objects.filter(
        project=project
    ).select_related("user").order_by("user__username", "role")

    for mr in member_roles:
        user_pk = mr.user.pk
        role_info = ROLE_DISPLAY.get(mr.role, (mr.get_role_display(), "badge-secondary"))

        if user_pk in members_dict:
            # User already exists (e.g., owner with additional roles)
            members_dict[user_pk]["roles"].append(mr.role)
            members_dict[user_pk]["roles_display"].append({
                "name": role_info[0],
                "badge_class": role_info[1],
            })
        else:
            # New user
            members_dict[user_pk] = {
                "user": mr.user,
                "roles": [mr.role],
                "roles_display": [{"name": role_info[0], "badge_class": role_info[1]}],
                "is_owner": False,
            }

    return list(members_dict.values())


@register.simple_tag
def get_project_member_count(project):
    """Get the total count of unique project members including owner.

    Args:
        project: The ColdFront Project object

    Returns:
        Integer count of unique members
    """
    # Count unique users with roles
    unique_users = set(
        ProjectMemberRole.objects.filter(project=project).values_list("user_id", flat=True)
    )
    # Add owner if not already counted
    unique_users.add(project.pi_id)
    return len(unique_users)


@register.simple_tag
def user_project_roles(user, project):
    """Get all of the user's roles in a project.

    Args:
        user: The Django User object
        project: The ColdFront Project object

    Returns:
        List of role strings, e.g., ["owner", "financial_admin"]
    """
    return get_user_project_roles(user, project)


@register.simple_tag
def user_can_edit_cost_allocation(user, project):
    """Check if user can edit cost allocation for a project.

    Args:
        user: The Django User object
        project: The ColdFront Project object

    Returns:
        Boolean
    """
    return can_edit_cost_allocation(user, project)


@register.simple_tag
def user_can_manage_members(user, project):
    """Check if user can manage members for a project.

    Args:
        user: The Django User object
        project: The ColdFront Project object

    Returns:
        Boolean
    """
    return can_manage_members(user, project)


@register.simple_tag
def user_can_manage_financial_admins(user, project):
    """Check if user can manage financial admins for a project.

    Args:
        user: The Django User object
        project: The ColdFront Project object

    Returns:
        Boolean
    """
    return can_manage_financial_admins(user, project)


@register.simple_tag
def cost_allocation_status(project):
    """Get the cost allocation status for a project.

    Args:
        project: The ColdFront Project object

    Returns:
        String status ('PENDING', 'APPROVED', 'REJECTED') or None if no allocation exists
    """
    try:
        return project.cost_allocation.status
    except ProjectCostAllocation.DoesNotExist:
        return None


@register.simple_tag
def project_has_approved_cost_allocation(project):
    """Check if project has an approved cost allocation.

    Args:
        project: The ColdFront Project object

    Returns:
        Boolean
    """
    return has_approved_cost_allocation(project)


@register.simple_tag
def user_can_manage_billing(user):
    """Check if user has billing manager permission.

    Args:
        user: The Django User object

    Returns:
        Boolean
    """
    return user.has_perm("coldfront_orcd_direct_charge.can_manage_billing")


@register.simple_tag
def get_user_roles(user, project):
    """Get user's roles in a project for display.

    Returns a list of human-readable role names for the user in the given project.
    Owner role is implicit via project.pi, other roles are from ProjectMemberRole.

    Args:
        user: The Django User object
        project: The ColdFront Project object

    Returns:
        list: List of role display names (e.g., ["Owner", "Financial Admin"])
    """
    roles = get_user_project_roles(user, project)

    # Convert to display names
    display_names = []
    for role in roles:
        if role in ROLE_DISPLAY:
            display_names.append(ROLE_DISPLAY[role][0])
        else:
            # Fallback: convert underscores to spaces and title case
            display_names.append(role.replace("_", " ").title())

    return display_names


@register.simple_tag
def get_projects_for_maintenance_fee(user):
    """Get projects user can use for maintenance fees with approved cost allocation.

    Returns projects where:
    1. User can use for maintenance fee (owner, technical admin, or member - NOT financial admin only)
    2. Project has an approved cost allocation

    Args:
        user: The Django User object

    Returns:
        list: List of Project objects eligible for maintenance fee billing
    """
    from coldfront.core.project.models import Project
    from coldfront_orcd_direct_charge.models import can_use_for_maintenance_fee

    eligible_projects = []

    # Get all active projects where user is a member
    projects = Project.objects.filter(
        projectuser__user=user,
        projectuser__status__name="Active",
        status__name__in=["Active", "New"],
    ).distinct()

    for project in projects:
        # Check both conditions: user can use for maintenance AND has approved allocation
        if can_use_for_maintenance_fee(user, project) and has_approved_cost_allocation(project):
            eligible_projects.append(project)

    return eligible_projects


@register.simple_tag
def get_dashboard_data(user):
    """Get all dashboard data for the home page.

    Collects summaries of projects, cost allocations, maintenance status,
    and reservations for display on the dashboard.

    Args:
        user: The Django User object

    Returns:
        dict: Dashboard context data
    """
    from datetime import date
    from coldfront.core.project.models import Project
    from coldfront_orcd_direct_charge.models import (
        Reservation,
        UserMaintenanceStatus,
    )

    data = {}

    # =========================================================================
    # Projects Summary
    # =========================================================================
    # Projects where user is owner
    owned_projects = Project.objects.filter(
        pi=user,
        status__name__in=["Active", "New"],
    ).order_by("-created")

    # Projects where user has a member role (but not owner)
    member_project_ids = (
        ProjectMemberRole.objects.filter(user=user)
        .values_list("project_id", flat=True)
        .distinct()
    )
    member_projects = Project.objects.filter(
        pk__in=member_project_ids,
        status__name__in=["Active", "New"],
    ).exclude(pi=user).order_by("-created")

    all_projects = list(owned_projects) + list(member_projects)
    all_project_ids = [p.pk for p in all_projects]

    data["owned_projects"] = owned_projects
    data["member_projects"] = member_projects
    data["owned_count"] = owned_projects.count()
    data["member_count"] = member_projects.count()
    data["total_projects"] = len(all_projects)
    data["recent_projects"] = all_projects[:5]
    data["is_pi"] = user.userprofile.is_pi if hasattr(user, "userprofile") else False

    # =========================================================================
    # Cost Allocation Summary
    # =========================================================================
    approved_count = 0
    pending_count = 0
    rejected_count = 0
    not_configured_count = 0
    projects_needing_attention = []

    for project in all_projects:
        try:
            allocation = project.cost_allocation
            if allocation.status == ProjectCostAllocation.StatusChoices.APPROVED:
                approved_count += 1
            elif allocation.status == ProjectCostAllocation.StatusChoices.PENDING:
                pending_count += 1
                projects_needing_attention.append({
                    "project": project,
                    "status": "pending",
                    "status_display": "Pending Approval",
                })
            else:  # REJECTED
                rejected_count += 1
                projects_needing_attention.append({
                    "project": project,
                    "status": "rejected",
                    "status_display": "Rejected",
                })
        except ProjectCostAllocation.DoesNotExist:
            not_configured_count += 1
            projects_needing_attention.append({
                "project": project,
                "status": "not_configured",
                "status_display": "Not Configured",
            })

    data["cost_approved_count"] = approved_count
    data["cost_pending_count"] = pending_count
    data["cost_rejected_count"] = rejected_count
    data["cost_not_configured_count"] = not_configured_count
    data["projects_needing_attention"] = projects_needing_attention[:5]

    # =========================================================================
    # Account Maintenance Status
    # =========================================================================
    try:
        maintenance_status = user.maintenance_status
        data["maintenance_status"] = maintenance_status.get_status_display()
        data["maintenance_status_raw"] = maintenance_status.status
        data["maintenance_billing_project"] = maintenance_status.billing_project
    except UserMaintenanceStatus.DoesNotExist:
        data["maintenance_status"] = "Inactive"
        data["maintenance_status_raw"] = "inactive"
        data["maintenance_billing_project"] = None

    # =========================================================================
    # Reservations Summary
    # =========================================================================
    today = date.today()

    # Get reservations for all user's projects
    reservations = (
        Reservation.objects.filter(project_id__in=all_project_ids)
        .select_related("project", "node_instance", "requesting_user")
        .order_by("start_date")
    )

    # Categorize reservations
    upcoming = [
        r
        for r in reservations
        if r.status == Reservation.StatusChoices.APPROVED and r.end_date >= today
    ]
    pending = [
        r for r in reservations if r.status == Reservation.StatusChoices.PENDING
    ]
    past = [
        r
        for r in reservations
        if r.status == Reservation.StatusChoices.APPROVED and r.end_date < today
    ]

    data["upcoming_reservations"] = upcoming[:3]
    data["upcoming_count"] = len(upcoming)
    data["pending_reservation_count"] = len(pending)
    data["past_count"] = len(past)
    data["total_reservations"] = len(reservations)

    return data



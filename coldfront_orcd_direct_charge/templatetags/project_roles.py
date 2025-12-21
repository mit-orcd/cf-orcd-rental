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

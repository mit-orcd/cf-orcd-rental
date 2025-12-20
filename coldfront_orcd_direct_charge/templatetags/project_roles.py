# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Template tags for project member roles."""

from django import template

from coldfront_orcd_direct_charge.models import (
    ProjectMemberRole,
    get_user_project_role,
    can_edit_cost_allocation,
    can_manage_members,
    can_manage_financial_admins,
)

register = template.Library()


@register.simple_tag
def get_project_members(project):
    """Get all members of a project with their ORCD roles.

    Returns a list of dictionaries with 'user', 'role', and 'role_display' keys.
    The owner is included first, followed by other members sorted by role.

    Args:
        project: The ColdFront Project object

    Returns:
        List of member dictionaries
    """
    members = []

    # Add owner first
    members.append({
        "user": project.pi,
        "role": "owner",
        "role_display": "Owner",
        "is_owner": True,
    })

    # Add other members
    member_roles = ProjectMemberRole.objects.filter(
        project=project
    ).select_related("user").order_by("role", "user__username")

    for mr in member_roles:
        members.append({
            "user": mr.user,
            "role": mr.role,
            "role_display": mr.get_role_display(),
            "is_owner": False,
        })

    return members


@register.simple_tag
def get_project_member_count(project):
    """Get the total count of project members including owner.

    Args:
        project: The ColdFront Project object

    Returns:
        Integer count of members
    """
    return ProjectMemberRole.objects.filter(project=project).count() + 1  # +1 for owner


@register.simple_tag
def user_project_role(user, project):
    """Get the user's role in a project.

    Args:
        user: The Django User object
        project: The ColdFront Project object

    Returns:
        String role name or None
    """
    return get_user_project_role(user, project)


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

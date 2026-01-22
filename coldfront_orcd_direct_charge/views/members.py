# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Project member management views.

Includes member listing, adding/removing members, role management,
and project reservations view.
"""

import logging
from collections import OrderedDict
from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.forms import formset_factory
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import TemplateView, View

from coldfront.core.user.utils import CombinedUserSearch

from coldfront_orcd_direct_charge.forms import (
    AddMemberForm,
    UpdateMemberRoleForm,
    ProjectAddUserWithRoleForm,
)
from coldfront_orcd_direct_charge.models import (
    ProjectMemberRole,
    Reservation,
    UserMaintenanceStatus,
    ActivityLog,
    get_user_project_role,
    can_manage_members,
    can_manage_financial_admins,
    log_activity,
)

logger = logging.getLogger(__name__)


class ProjectMembersView(LoginRequiredMixin, TemplateView):
    """View for listing and managing project members."""

    template_name = "coldfront_orcd_direct_charge/project_members.html"

    def dispatch(self, request, *args, **kwargs):
        """Check user has permission to view project members."""
        from coldfront.core.project.models import Project

        self.project = get_object_or_404(Project, pk=kwargs.get("pk"))

        # Any member of the project can view the members list
        user_role = get_user_project_role(request.user, self.project)
        if user_role is None and not request.user.is_superuser:
            messages.error(request, "You do not have access to this project.")
            return redirect("project-list")

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project"] = self.project

        # Role display names and badge classes
        ROLE_DISPLAY = {
            "owner": ("Owner", "badge-primary"),
            "financial_admin": ("Financial Admin", "badge-warning"),
            "technical_admin": ("Technical Admin", "badge-info"),
            "member": ("Member", "badge-secondary"),
        }

        # Get all member roles for this project
        member_roles = ProjectMemberRole.objects.filter(
            project=self.project
        ).select_related("user").order_by("user__username", "role")

        # Build dict of members grouped by user
        members_dict = OrderedDict()

        # Add owner first
        owner = self.project.pi
        members_dict[owner.pk] = {
            "user": owner,
            "roles": ["owner"],
            "roles_display": [{"name": "Owner", "badge_class": "badge-primary"}],
            "is_owner": True,
        }

        # Add other members, grouping roles by user
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

        # Add maintenance status for each member
        for member_data in members_dict.values():
            user = member_data["user"]
            try:
                status = user.maintenance_status
                member_data["maintenance_status"] = status.get_status_display()
                member_data["maintenance_status_raw"] = status.status
            except UserMaintenanceStatus.DoesNotExist:
                member_data["maintenance_status"] = "Not Set"
                member_data["maintenance_status_raw"] = None

        context["members"] = list(members_dict.values())
        context["can_manage_members"] = can_manage_members(self.request.user, self.project)
        context["can_manage_financial_admins"] = can_manage_financial_admins(self.request.user, self.project)
        context["current_user_role"] = get_user_project_role(self.request.user, self.project)

        return context


class AddMemberView(LoginRequiredMixin, TemplateView):
    """View for adding a new member to a project."""

    template_name = "coldfront_orcd_direct_charge/add_member.html"

    def dispatch(self, request, *args, **kwargs):
        """Check user has permission to add members."""
        from coldfront.core.project.models import Project

        self.project = get_object_or_404(Project, pk=kwargs.get("pk"))

        if not can_manage_members(request.user, self.project):
            messages.error(request, "You do not have permission to add members to this project.")
            return redirect("coldfront_orcd_direct_charge:project-members", pk=self.project.pk)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project"] = self.project
        context["can_add_financial_admin"] = can_manage_financial_admins(
            self.request.user, self.project
        )

        if self.request.method == "POST":
            context["form"] = AddMemberForm(
                self.request.POST,
                project=self.project,
                current_user=self.request.user,
                can_add_financial_admin=context["can_add_financial_admin"],
            )
        else:
            context["form"] = AddMemberForm(
                project=self.project,
                current_user=self.request.user,
                can_add_financial_admin=context["can_add_financial_admin"],
            )

        return context

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        form = context["form"]

        if form.is_valid():
            username = form.cleaned_data["username"]
            roles = form.cleaned_data["roles"]  # Now a list of roles

            user = User.objects.get(username=username)

            logger.info(
                "Adding member to project: user=%s, project=%s, roles=%s, added_by=%s",
                username, self.project.title, roles, request.user.username
            )

            # Check role permission: only owner/financial admin can add financial admins
            if ProjectMemberRole.RoleChoices.FINANCIAL_ADMIN in roles:
                if not can_manage_financial_admins(request.user, self.project):
                    messages.error(request, "You do not have permission to add financial admins.")
                    return self.render_to_response(context)

            # Create the member roles (one record per role)
            for role in roles:
                ProjectMemberRole.objects.get_or_create(
                    project=self.project,
                    user=user,
                    role=role,
                )

            # Also add to ColdFront's ProjectUser if not already there
            from coldfront.core.project.models import (
                ProjectUser,
                ProjectUserRoleChoice,
                ProjectUserStatusChoice,
            )

            if not ProjectUser.objects.filter(project=self.project, user=user).exists():
                # Map our roles to ColdFront role: Manager if any admin role, else User
                cf_role_name = "Manager" if any(r in [
                    ProjectMemberRole.RoleChoices.FINANCIAL_ADMIN,
                    ProjectMemberRole.RoleChoices.TECHNICAL_ADMIN,
                ] for r in roles) else "User"

                ProjectUser.objects.create(
                    project=self.project,
                    user=user,
                    role=ProjectUserRoleChoice.objects.get(name=cf_role_name),
                    status=ProjectUserStatusChoice.objects.get(name="Active"),
                )

            # Build role display names for message
            role_names = [
                dict(form.fields["roles"].choices).get(r, r) for r in roles
            ]

            # Log to activity log
            log_activity(
                action="member.added",
                category=ActivityLog.ActionCategory.MEMBER,
                description=f"User {username} added to {self.project.title} with roles: {', '.join(role_names)}",
                request=request,
                target=self.project,
                extra_data={
                    "project_id": self.project.pk,
                    "project_title": self.project.title,
                    "user_id": user.pk,
                    "username": username,
                    "roles": list(roles),
                },
            )

            messages.success(
                request,
                f"Added {username} with role(s): {', '.join(role_names)}"
            )
            return redirect("coldfront_orcd_direct_charge:project-members", pk=self.project.pk)

        return self.render_to_response(context)


class UpdateMemberRoleView(LoginRequiredMixin, TemplateView):
    """View for managing a member's roles (add/remove multiple roles)."""

    template_name = "coldfront_orcd_direct_charge/update_member_role.html"

    def dispatch(self, request, *args, **kwargs):
        """Check user has permission to update member roles."""
        from coldfront.core.project.models import Project

        self.project = get_object_or_404(Project, pk=kwargs.get("pk"))
        self.target_user = get_object_or_404(User, pk=kwargs.get("user_pk"))

        # Can't change owner's explicit roles if they're the owner
        # (but owner CAN have additional explicit roles)
        self.is_owner = self.project.pi == self.target_user

        # Get all member roles for this user
        self.member_roles = list(
            ProjectMemberRole.objects.filter(
                project=self.project, user=self.target_user
            ).values_list("role", flat=True)
        )

        # If not owner and has no roles, redirect
        if not self.is_owner and not self.member_roles:
            messages.error(request, "This user is not a member of the project.")
            return redirect("coldfront_orcd_direct_charge:project-members", pk=self.project.pk)

        if not can_manage_members(request.user, self.project):
            messages.error(request, "You do not have permission to update member roles.")
            return redirect("coldfront_orcd_direct_charge:project-members", pk=self.project.pk)

        # Technical admins can only change members and technical admins, not financial admins
        if not can_manage_financial_admins(request.user, self.project):
            if ProjectMemberRole.RoleChoices.FINANCIAL_ADMIN in self.member_roles:
                messages.error(request, "You do not have permission to change a financial admin's roles.")
                return redirect("coldfront_orcd_direct_charge:project-members", pk=self.project.pk)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project"] = self.project
        context["target_user"] = self.target_user
        context["is_owner"] = self.is_owner
        context["current_roles"] = self.member_roles
        context["can_set_financial_admin"] = can_manage_financial_admins(
            self.request.user, self.project
        )

        if self.request.method == "POST":
            context["form"] = UpdateMemberRoleForm(
                self.request.POST,
                can_set_financial_admin=context["can_set_financial_admin"],
                current_roles=self.member_roles,
            )
        else:
            context["form"] = UpdateMemberRoleForm(
                can_set_financial_admin=context["can_set_financial_admin"],
                current_roles=self.member_roles,
            )

        return context

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        form = context["form"]

        if form.is_valid():
            new_roles = set(form.cleaned_data["roles"])
            old_roles = set(self.member_roles)

            # Check permission to set financial admin
            if ProjectMemberRole.RoleChoices.FINANCIAL_ADMIN in new_roles:
                if not can_manage_financial_admins(request.user, self.project):
                    messages.error(request, "You do not have permission to set financial admin role.")
                    return self.render_to_response(context)

            logger.info(
                "Updating member roles: user=%s, project=%s, old_roles=%s, new_roles=%s, updated_by=%s",
                self.target_user.username, self.project.title, old_roles, new_roles, request.user.username
            )

            # Remove roles that were unchecked
            roles_to_remove = old_roles - new_roles
            if roles_to_remove:
                ProjectMemberRole.objects.filter(
                    project=self.project,
                    user=self.target_user,
                    role__in=roles_to_remove,
                ).delete()

            # Add roles that were newly checked
            roles_to_add = new_roles - old_roles
            for role in roles_to_add:
                ProjectMemberRole.objects.get_or_create(
                    project=self.project,
                    user=self.target_user,
                    role=role,
                )

            # Update ColdFront ProjectUser role
            from coldfront.core.project.models import ProjectUser, ProjectUserRoleChoice

            try:
                cf_project_user = ProjectUser.objects.get(
                    project=self.project, user=self.target_user
                )
                # Manager if any admin role, else User
                cf_role_name = "Manager" if any(r in [
                    ProjectMemberRole.RoleChoices.FINANCIAL_ADMIN,
                    ProjectMemberRole.RoleChoices.TECHNICAL_ADMIN,
                ] for r in new_roles) else "User"
                cf_project_user.role = ProjectUserRoleChoice.objects.get(name=cf_role_name)
                cf_project_user.save()
            except ProjectUser.DoesNotExist:
                pass  # No ColdFront ProjectUser record

            # Log to activity log
            log_activity(
                action="member.roles_updated",
                category=ActivityLog.ActionCategory.MEMBER,
                description=f"Roles updated for {self.target_user.username} in {self.project.title}",
                request=request,
                target=self.project,
                extra_data={
                    "project_id": self.project.pk,
                    "project_title": self.project.title,
                    "user_id": self.target_user.pk,
                    "username": self.target_user.username,
                    "new_roles": list(new_roles),
                },
            )

            # Build message
            if not new_roles and not self.is_owner:
                messages.success(
                    request,
                    f"Removed all roles from {self.target_user.username}. They are no longer a project member."
                )
            else:
                role_names = [
                    dict(form.fields["roles"].choices).get(r, r) for r in new_roles
                ]
                messages.success(
                    request,
                    f"Updated {self.target_user.username}'s roles to: {', '.join(role_names) if role_names else 'None'}"
                )
            return redirect("coldfront_orcd_direct_charge:project-members", pk=self.project.pk)

        return self.render_to_response(context)


class RemoveMemberView(LoginRequiredMixin, View):
    """View for removing a member (and all their roles) from a project."""

    def post(self, request, pk, user_pk):
        from coldfront.core.project.models import Project, ProjectUser

        project = get_object_or_404(Project, pk=pk)
        target_user = get_object_or_404(User, pk=user_pk)

        # Can't remove owner
        if project.pi == target_user:
            messages.error(request, "Cannot remove the project owner.")
            return redirect("coldfront_orcd_direct_charge:project-members", pk=project.pk)

        # Check permission
        if not can_manage_members(request.user, project):
            messages.error(request, "You do not have permission to remove members.")
            return redirect("coldfront_orcd_direct_charge:project-members", pk=project.pk)

        # Get all member roles for this user
        member_roles = ProjectMemberRole.objects.filter(project=project, user=target_user)
        if not member_roles.exists():
            messages.error(request, "This user is not a member of the project.")
            return redirect("coldfront_orcd_direct_charge:project-members", pk=project.pk)

        # Technical admins cannot remove users who have financial admin role
        if not can_manage_financial_admins(request.user, project):
            if member_roles.filter(role=ProjectMemberRole.RoleChoices.FINANCIAL_ADMIN).exists():
                messages.error(request, "You do not have permission to remove a financial admin.")
                return redirect("coldfront_orcd_direct_charge:project-members", pk=project.pk)

        roles_list = list(member_roles.values_list("role", flat=True))
        
        # Get optional removal notes from form
        removal_notes = request.POST.get("notes", "").strip()
        
        logger.info(
            "Removing member from project: user=%s, project=%s, roles=%s, removed_by=%s, notes=%s",
            target_user.username, project.title, roles_list, request.user.username,
            removal_notes[:100] if removal_notes else "(none)"
        )

        # Remove all member roles
        member_roles.delete()

        # Also remove from ColdFront's ProjectUser
        ProjectUser.objects.filter(project=project, user=target_user).delete()

        # Log to activity log
        extra_data = {
            "project_id": project.pk,
            "project_title": project.title,
            "user_id": target_user.pk,
            "username": target_user.username,
            "removed_roles": roles_list,
        }
        if removal_notes:
            extra_data["removal_notes"] = removal_notes
        
        log_activity(
            action="member.removed",
            category=ActivityLog.ActionCategory.MEMBER,
            description=f"User {target_user.username} removed from {project.title}",
            request=request,
            target=project,
            extra_data=extra_data,
        )

        messages.success(request, f"Removed {target_user.username} from the project.")
        return redirect("coldfront_orcd_direct_charge:project-members", pk=project.pk)


# =============================================================================
# Add Users Search Views (Override ColdFront's add-users flow)
# =============================================================================


class ProjectAddUsersSearchView(LoginRequiredMixin, TemplateView):
    """View for the autocomplete add-users interface.

    This renders the project_add_users.html template which provides an
    autocomplete search interface for finding and adding users to a project.
    The template uses JavaScript to call the user-search API endpoint.
    """

    template_name = "project/project_add_users.html"

    def dispatch(self, request, *args, **kwargs):
        """Check user has permission to add members and project is active."""
        from coldfront.core.project.models import Project

        self.project = get_object_or_404(Project, pk=self.kwargs.get("pk"))

        if self.project.status.name not in ["Active", "New"]:
            messages.error(request, "You cannot add members to an archived project.")
            return HttpResponseRedirect(
                reverse("project-detail", kwargs={"pk": self.project.pk})
            )

        if not can_manage_members(request.user, self.project):
            messages.error(
                request, "You do not have permission to add members to this project."
            )
            return HttpResponseRedirect(
                reverse("project-detail", kwargs={"pk": self.project.pk})
            )

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project"] = self.project
        return context


class ProjectAddUsersSearchResultsView(LoginRequiredMixin, TemplateView):
    """Override ColdFront's view to use ORCD roles and remove allocations."""

    template_name = "project/add_user_search_results.html"

    def test_func(self):
        """Check user can add members to this project."""
        if self.request.user.is_superuser:
            return True

        project_obj = get_object_or_404(
            __import__("coldfront.core.project.models", fromlist=["Project"]).Project,
            pk=self.kwargs.get("pk")
        )

        if project_obj.pi == self.request.user:
            return True

        # Check ORCD roles - owner, financial admin, or technical admin can add members
        if can_manage_members(self.request.user, project_obj):
            return True

        return False

    def dispatch(self, request, *args, **kwargs):
        from coldfront.core.project.models import Project

        project_obj = get_object_or_404(Project, pk=self.kwargs.get("pk"))
        if project_obj.status.name not in ["Active", "New"]:
            messages.error(request, "You cannot add members to an archived project.")
            return HttpResponseRedirect(reverse("project-detail", kwargs={"pk": project_obj.pk}))

        if not can_manage_members(request.user, project_obj):
            messages.error(request, "You do not have permission to add members to this project.")
            return HttpResponseRedirect(reverse("project-detail", kwargs={"pk": project_obj.pk}))

        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        from coldfront.core.project.models import Project

        user_search_string = request.POST.get("q")
        search_by = request.POST.get("search_by")
        pk = self.kwargs.get("pk")

        project_obj = get_object_or_404(Project, pk=pk)

        # Validate search string is provided
        if not user_search_string:
            messages.error(request, "Please enter a search term to find users.")
            return HttpResponseRedirect(
                reverse("coldfront_orcd_direct_charge:project-add-users-search", kwargs={"pk": pk})
            )

        # Get users already in project (either as owner or via ProjectMemberRole)
        users_to_exclude = [project_obj.pi.username]
        users_to_exclude.extend([
            mr.user.username for mr in ProjectMemberRole.objects.filter(project=project_obj)
        ])

        combined_user_search_obj = CombinedUserSearch(user_search_string, search_by, users_to_exclude)
        context = combined_user_search_obj.search()

        matches = context.get("matches")
        # Set default role to Member for all matches
        for match in matches:
            match.update({"role": ProjectMemberRole.RoleChoices.MEMBER})

        if matches:
            formset = formset_factory(ProjectAddUserWithRoleForm, max_num=len(matches))
            formset = formset(initial=matches, prefix="userform")
            context["formset"] = formset
            context["user_search_string"] = user_search_string
            context["search_by"] = search_by

        # Check for multiple usernames in search (guard against None already handled above)
        if user_search_string and len(user_search_string.split()) > 1:
            users_already_in_project = []
            for ele in user_search_string.split():
                if ele in users_to_exclude:
                    users_already_in_project.append(ele)
            context["users_already_in_project"] = users_already_in_project

        context["pk"] = pk
        return render(request, self.template_name, context)


class ProjectAddUsersView(LoginRequiredMixin, View):
    """Handle form submission to add users with ORCD roles."""

    def dispatch(self, request, *args, **kwargs):
        from coldfront.core.project.models import Project

        project_obj = get_object_or_404(Project, pk=self.kwargs.get("pk"))

        if not can_manage_members(request.user, project_obj):
            messages.error(request, "You do not have permission to add members to this project.")
            return HttpResponseRedirect(reverse("project-detail", kwargs={"pk": project_obj.pk}))

        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        from coldfront.core.project.models import (
            Project,
            ProjectUser,
            ProjectUserRoleChoice,
            ProjectUserStatusChoice,
        )

        pk = self.kwargs.get("pk")
        project_obj = get_object_or_404(Project, pk=pk)

        # Parse the formset data - handle multiple roles per user (checkboxes)
        formset_data = {}
        for key, value in request.POST.items():
            if key.startswith("userform-"):
                parts = key.split("-")
                if len(parts) >= 3:
                    index = int(parts[1])
                    field = parts[2]
                    if index not in formset_data:
                        formset_data[index] = {"roles": []}
                    if field == "roles":
                        # Multiple checkboxes with same name
                        formset_data[index]["roles"].append(value)
                    else:
                        formset_data[index][field] = value

        # Also get roles from getlist for proper multi-value handling
        for index in formset_data.keys():
            roles_key = f"userform-{index}-roles"
            roles = request.POST.getlist(roles_key)
            if roles:
                formset_data[index]["roles"] = roles

        added_count = 0
        for index, data in formset_data.items():
            # Check if this user was selected
            if data.get("selected") != "on":
                continue

            username = data.get("username")
            roles = data.get("roles", [])

            if not username or not roles:
                continue

            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                messages.warning(request, f"User '{username}' not found.")
                continue

            # Skip if user is project owner
            if project_obj.pi == user:
                messages.warning(request, f"'{username}' is the project owner.")
                continue

            # Check permission to add financial admins
            if ProjectMemberRole.RoleChoices.FINANCIAL_ADMIN in roles:
                if not can_manage_financial_admins(request.user, project_obj):
                    messages.warning(request, f"You don't have permission to add '{username}' as Financial Admin.")
                    # Remove financial admin from the roles list
                    roles = [r for r in roles if r != ProjectMemberRole.RoleChoices.FINANCIAL_ADMIN]
                    if not roles:
                        continue

            logger.info(
                "Adding member to project via search: user=%s, project=%s, roles=%s, added_by=%s",
                username, project_obj.title, roles, request.user.username
            )

            # Create ProjectMemberRole for each role
            for role in roles:
                ProjectMemberRole.objects.get_or_create(
                    project=project_obj,
                    user=user,
                    role=role,
                )

            # Also create ColdFront ProjectUser for compatibility
            cf_role_name = "Manager" if any(r in [
                ProjectMemberRole.RoleChoices.FINANCIAL_ADMIN,
                ProjectMemberRole.RoleChoices.TECHNICAL_ADMIN,
            ] for r in roles) else "User"

            if not ProjectUser.objects.filter(project=project_obj, user=user).exists():
                ProjectUser.objects.create(
                    project=project_obj,
                    user=user,
                    role=ProjectUserRoleChoice.objects.get(name=cf_role_name),
                    status=ProjectUserStatusChoice.objects.get(name="Active"),
                )

            added_count += 1

        if added_count > 0:
            messages.success(request, f"Added {added_count} member(s) to the project.")
        else:
            messages.info(request, "No members were added.")

        return redirect("coldfront_orcd_direct_charge:project-members", pk=pk)


# =============================================================================
# Project Reservations View
# =============================================================================


class ProjectReservationsView(LoginRequiredMixin, TemplateView):
    """Display all reservations for a specific project.

    Shows reservations split into:
    - Future: start_date >= today, sorted ascending (next to later)
    - Past: start_date < today, sorted descending (most recent to oldest)

    Access is restricted to project members (owner, any role).
    """

    template_name = "coldfront_orcd_direct_charge/project_reservations.html"

    def dispatch(self, request, *args, **kwargs):
        """Check user has access to this project."""
        from coldfront.core.project.models import Project

        self.project = get_object_or_404(Project, pk=kwargs.get("pk"))

        # Allow superusers
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)

        # Allow project owner
        if self.project.pi == request.user:
            return super().dispatch(request, *args, **kwargs)

        # Allow users with any ORCD role in the project
        if ProjectMemberRole.objects.filter(
            project=self.project, user=request.user
        ).exists():
            return super().dispatch(request, *args, **kwargs)

        messages.error(request, "You do not have permission to view reservations for this project.")
        return redirect("project-detail", pk=self.project.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project"] = self.project

        today = date.today()

        # Get all reservations for this project
        all_reservations = Reservation.objects.filter(
            project=self.project
        ).select_related("node_instance", "requesting_user").order_by("start_date")

        # Split into future and past
        future_reservations = [
            r for r in all_reservations if r.start_date >= today
        ]
        past_reservations = [
            r for r in all_reservations if r.start_date < today
        ]

        # Future: already sorted ascending by query
        context["future_reservations"] = future_reservations

        # Past: reverse to get descending (most recent first)
        context["past_reservations"] = list(reversed(past_reservations))

        context["future_count"] = len(future_reservations)
        context["past_count"] = len(past_reservations)
        context["total_count"] = len(all_reservations)

        return context


# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Dashboard and activity log views.

Includes the home page dashboard and activity log viewer.
"""

from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.views.generic import TemplateView

from coldfront_orcd_direct_charge.models import (
    ProjectCostAllocation,
    Reservation,
    UserMaintenanceStatus,
    ActivityLog,
    ProjectMemberRole,
    can_view_activity_log,
)


class ActivityLogView(LoginRequiredMixin, TemplateView):
    """View activity logs. Restricted to Billing/Rental Managers and superusers."""

    template_name = "coldfront_orcd_direct_charge/activity_log.html"

    def dispatch(self, request, *args, **kwargs):
        if not can_view_activity_log(request.user):
            raise PermissionDenied("You do not have permission to view activity logs.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Filter parameters
        category = self.request.GET.get("category", "")
        user_filter = self.request.GET.get("user", "")
        action_filter = self.request.GET.get("action", "")
        date_from = self.request.GET.get("date_from", "")
        date_to = self.request.GET.get("date_to", "")

        logs = ActivityLog.objects.select_related("user").all()

        if category:
            logs = logs.filter(category=category)
        if user_filter:
            logs = logs.filter(user__username__icontains=user_filter)
        if action_filter:
            logs = logs.filter(action__icontains=action_filter)
        if date_from:
            logs = logs.filter(timestamp__date__gte=date_from)
        if date_to:
            logs = logs.filter(timestamp__date__lte=date_to)

        # Paginate (50 per page)
        paginator = Paginator(logs, 50)
        page = self.request.GET.get("page", 1)
        context["logs"] = paginator.get_page(page)
        context["categories"] = ActivityLog.ActionCategory.choices
        context["filters"] = {
            "category": category,
            "user": user_filter,
            "action": action_filter,
            "date_from": date_from,
            "date_to": date_to,
        }
        return context


class Home2View(LoginRequiredMixin, TemplateView):
    """New dashboard home page with summary cards.

    Displays user-centric summaries of:
    - Projects (owned and member)
    - Cost allocation status
    - Account maintenance status
    - Reservations (upcoming, pending, past)
    """

    template_name = "coldfront_orcd_direct_charge/home2.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # =====================================================================
        # Projects Summary
        # =====================================================================
        from coldfront.core.project.models import Project

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

        context["owned_projects"] = owned_projects
        context["member_projects"] = member_projects
        context["owned_count"] = owned_projects.count()
        context["member_count"] = member_projects.count()
        context["total_projects"] = len(all_projects)
        # Top 5 projects for quick list (owned first, then member)
        context["recent_projects"] = all_projects[:5]
        context["is_pi"] = user.userprofile.is_pi if hasattr(user, "userprofile") else False

        # =====================================================================
        # Cost Allocation Summary
        # =====================================================================
        # Count projects by cost allocation status
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

        context["cost_approved_count"] = approved_count
        context["cost_pending_count"] = pending_count
        context["cost_rejected_count"] = rejected_count
        context["cost_not_configured_count"] = not_configured_count
        context["projects_needing_attention"] = projects_needing_attention[:5]

        # =====================================================================
        # Account Maintenance Status
        # =====================================================================
        try:
            maintenance_status = user.maintenance_status
            context["maintenance_status"] = maintenance_status.get_status_display()
            context["maintenance_status_raw"] = maintenance_status.status
            context["maintenance_billing_project"] = maintenance_status.billing_project
        except UserMaintenanceStatus.DoesNotExist:
            context["maintenance_status"] = "Inactive"
            context["maintenance_status_raw"] = "inactive"
            context["maintenance_billing_project"] = None

        # =====================================================================
        # Reservations Summary
        # =====================================================================
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

        context["upcoming_reservations"] = upcoming[:3]  # Next 3 for quick view
        context["upcoming_count"] = len(upcoming)
        context["pending_reservation_count"] = len(pending)
        context["past_count"] = len(past)
        context["total_reservations"] = len(reservations)

        return context


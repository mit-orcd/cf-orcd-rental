# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Rental and reservation management views.

Includes calendar view, reservation requests, rental manager approval workflow,
and user-facing reservation lists.
"""

import calendar
import logging
from datetime import date, datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.views.generic import (
    TemplateView,
    CreateView,
    DetailView,
    View,
    ListView,
    UpdateView,
    DeleteView,
)

from coldfront_orcd_direct_charge.forms import (
    ReservationRequestForm,
    ReservationDeclineForm,
)
from coldfront_orcd_direct_charge.models import (
    GpuNodeInstance,
    MaintenanceWindow,
    Reservation,
    ReservationMetadataEntry,
    UserMaintenanceStatus,
    ActivityLog,
    ProjectMemberRole,
    can_use_for_maintenance_fee,
    has_approved_cost_allocation,
    log_activity,
)

logger = logging.getLogger(__name__)


class RentingCalendarView(LoginRequiredMixin, TemplateView):
    """Calendar view showing H200x8 node availability for renting."""

    template_name = "coldfront_orcd_direct_charge/renting_calendar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get year and month from query params, default to current
        today = date.today()
        
        # Earliest bookable date is 7 days from today
        earliest_bookable = today + timedelta(days=7)
        
        # Default to the month containing the earliest bookable date
        default_year = earliest_bookable.year
        default_month = earliest_bookable.month
        
        year = int(self.request.GET.get("year", default_year))
        month = int(self.request.GET.get("month", default_month))

        # Calculate the maximum allowed month (3 months from current)
        max_month = today.month + 3
        max_year = today.year
        if max_month > 12:
            max_month = max_month - 12
            max_year = today.year + 1

        # Calculate the minimum allowed month (month containing earliest bookable date)
        min_month = earliest_bookable.month
        min_year = earliest_bookable.year

        # Clamp the requested month to the allowed range
        min_month_date = date(min_year, min_month, 1)
        max_month_date = date(max_year, max_month, 1)
        requested_month_date = date(year, month, 1)

        if requested_month_date < min_month_date:
            year, month = min_year, min_month
        elif requested_month_date > max_month_date:
            year, month = max_year, max_month

        # Get rentable H200x8 nodes
        h200x8_nodes = GpuNodeInstance.objects.filter(
            is_rentable=True,
            node_type__name="H200x8",
        ).order_by("associated_resource_address")

        # Build calendar data
        cal = calendar.Calendar(firstweekday=6)  # Start on Sunday
        month_days = list(cal.itermonthdays(year, month))
        
        # Determine the first day to show in the calendar
        if year == today.year and month == today.month:
            # For current month, start from today
            first_day = today.day
        else:
            # For future months, show all days
            first_day = 1

        days_in_month = [d for d in range(first_day, calendar.monthrange(year, month)[1] + 1)]

        # Get approved reservations for this month
        month_start = date(year, month, 1)
        month_end = date(year, month, calendar.monthrange(year, month)[1])
        
        approved_reservations = Reservation.objects.filter(
            status=Reservation.StatusChoices.APPROVED,
            node_instance__in=h200x8_nodes,
        ).select_related("project")

        # Get pending reservations to show "P" indicator
        pending_reservations = Reservation.objects.filter(
            status=Reservation.StatusChoices.PENDING,
            node_instance__in=h200x8_nodes,
        ).select_related("project")

        # Get user's project IDs to identify "my" reservations
        from coldfront.core.project.models import Project
        user_project_ids = set(
            Project.objects.filter(
                projectuser__user=self.request.user,
                projectuser__status__name="Active",
            ).values_list("id", flat=True)
        )

        # Build availability matrix: {node_id: {day: {rental_type, am_is_mine, pm_is_mine, is_bookable}}}
        availability = {}
        for node in h200x8_nodes:
            availability[node.id] = {}
            for day in days_in_month:
                current_date = date(year, month, day)
                # Check if date is before earliest bookable date
                is_bookable = current_date >= earliest_bookable
                
                # Define time periods for this day
                day_4am = datetime.combine(current_date, time(4, 0))
                day_4pm = datetime.combine(current_date, time(16, 0))
                next_day_4am = day_4am + timedelta(days=1)
                
                # Track AM (4 AM - 4 PM) and PM (4 PM - 4 AM next day) separately
                am_booked = False
                pm_booked = False
                am_is_mine = False
                pm_is_mine = False
                am_pending = False
                pm_pending = False
                
                for res in approved_reservations.filter(node_instance=node):
                    # AM period: check if reservation overlaps [4 AM, 4 PM)
                    # Interval overlap: [start, end) overlaps [4AM, 4PM) iff start < 4PM and end > 4AM
                    if res.start_datetime < day_4pm and res.end_datetime > day_4am:
                        am_booked = True
                        if res.project_id in user_project_ids:
                            am_is_mine = True
                    
                    # PM period: check if reservation overlaps [4 PM, 4 AM next day)
                    # Interval overlap: [start, end) overlaps [4PM, 4AM-next) iff start < 4AM-next and end > 4PM
                    if res.start_datetime < next_day_4am and res.end_datetime > day_4pm:
                        pm_booked = True
                        if res.project_id in user_project_ids:
                            pm_is_mine = True
                
                # Check for pending reservations
                for res in pending_reservations.filter(node_instance=node):
                    if res.start_datetime < day_4pm and res.end_datetime > day_4am:
                        am_pending = True
                    if res.start_datetime < next_day_4am and res.end_datetime > day_4pm:
                        pm_pending = True
                
                # Determine rental type based on AM/PM status
                if am_booked and pm_booked:
                    rental_type = "full"
                elif am_booked:
                    rental_type = "am_only"
                elif pm_booked:
                    rental_type = "pm_only"
                else:
                    rental_type = "available"
                
                availability[node.id][day] = {
                    "rental_type": rental_type,
                    "am_is_mine": am_is_mine,
                    "pm_is_mine": pm_is_mine,
                    "is_bookable": is_bookable,
                    "has_pending": am_pending or pm_pending,
                }

        # Calculate prev/next month
        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1

        if month == 12:
            next_year, next_month = year + 1, 1
        else:
            next_year, next_month = year, month + 1

        # Determine if prev/next buttons should be shown
        prev_month_date = date(prev_year, prev_month, 1)
        next_month_date = date(next_year, next_month, 1)

        show_prev = prev_month_date >= min_month_date
        show_next = next_month_date <= max_month_date

        context.update({
            "nodes": h200x8_nodes,
            "days": days_in_month,
            "availability": availability,
            "year": year,
            "month": month,
            "month_name": calendar.month_name[month],
            "prev_year": prev_year,
            "prev_month": prev_month,
            "next_year": next_year,
            "next_month": next_month,
            "show_prev": show_prev,
            "show_next": show_next,
            "today": today,
            "earliest_bookable": earliest_bookable,
            "max_month_name": calendar.month_name[max_month],
            "max_year": max_year,
        })

        return context


class ReservationRequestView(LoginRequiredMixin, CreateView):
    """View for submitting a reservation request."""

    model = Reservation
    form_class = ReservationRequestForm
    template_name = "coldfront_orcd_direct_charge/reservation_request.html"
    success_url = reverse_lazy("coldfront_orcd_direct_charge:renting-calendar")

    def dispatch(self, request, *args, **kwargs):
        """Check if user has active maintenance subscription before allowing access."""
        if request.user.is_authenticated:
            try:
                status = request.user.maintenance_status
                if status.status == UserMaintenanceStatus.StatusChoices.INACTIVE:
                    messages.error(
                        request,
                        "You must have an active account maintenance fee subscription to make reservations. "
                        "Please update your subscription status in your profile."
                    )
                    return redirect("coldfront_orcd_direct_charge:renting-calendar")
            except UserMaintenanceStatus.DoesNotExist:
                messages.error(
                    request,
                    "You must have an active account maintenance fee subscription to make reservations. "
                    "Please update your subscription status in your profile."
                )
                return redirect("coldfront_orcd_direct_charge:renting-calendar")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(
            self.request,
            "Your reservation request has been submitted and is pending approval."
        )
        return super().form_valid(form)


class RentalManagerView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """View for rental managers to review and approve/decline reservation requests."""

    template_name = "coldfront_orcd_direct_charge/rental_manager.html"
    permission_required = "coldfront_orcd_direct_charge.can_manage_rentals"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get pending reservations
        pending_reservations = Reservation.objects.filter(
            status=Reservation.StatusChoices.PENDING
        ).select_related("node_instance", "project", "requesting_user")

        # Get recently processed reservations (last 30 days)
        thirty_days_ago = date.today() - timedelta(days=30)
        recent_reservations = Reservation.objects.filter(
            status__in=[
                Reservation.StatusChoices.APPROVED,
                Reservation.StatusChoices.DECLINED,
            ],
            modified__date__gte=thirty_days_ago,
        ).select_related("node_instance", "project", "requesting_user")

        context.update({
            "pending_reservations": pending_reservations,
            "recent_reservations": recent_reservations,
            "decline_form": ReservationDeclineForm(),
        })

        return context


class ReservationApproveView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """View to approve a reservation request."""

    permission_required = "coldfront_orcd_direct_charge.can_manage_rentals"

    def post(self, request, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        
        if reservation.status != Reservation.StatusChoices.PENDING:
            messages.error(request, "This reservation has already been processed.")
            return redirect("coldfront_orcd_direct_charge:rental-manager")

        # Check for conflicts with other approved reservations
        new_start = reservation.start_datetime
        new_end = reservation.end_datetime

        conflicts = Reservation.objects.filter(
            node_instance=reservation.node_instance,
            status=Reservation.StatusChoices.APPROVED,
        ).exclude(pk=pk)

        for existing in conflicts:
            if new_start < existing.end_datetime and new_end > existing.start_datetime:
                messages.error(
                    request,
                    f"Cannot approve: conflicts with existing reservation from "
                    f"{existing.start_datetime.strftime('%b %d %I:%M %p')} to "
                    f"{existing.end_datetime.strftime('%b %d %I:%M %p')}."
                )
                return redirect("coldfront_orcd_direct_charge:rental-manager")

        reservation.status = Reservation.StatusChoices.APPROVED
        reservation.processed_by = request.user
        reservation.save()

        # Log the approval action
        log_activity(
            action="reservation.approved",
            category=ActivityLog.ActionCategory.RESERVATION,
            description=f"Reservation #{reservation.pk} approved by {request.user.username}",
            request=request,
            target=reservation,
            extra_data={
                "project_id": reservation.project.pk,
                "project_title": reservation.project.title,
                "node": reservation.node_instance.associated_resource_address,
            },
        )

        messages.success(
            request,
            f"Reservation for {reservation.node_instance.associated_resource_address} approved."
        )
        return redirect("coldfront_orcd_direct_charge:rental-manager")


class ReservationDeclineView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """View to decline a reservation request."""

    permission_required = "coldfront_orcd_direct_charge.can_manage_rentals"

    def post(self, request, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        
        if reservation.status != Reservation.StatusChoices.PENDING:
            messages.error(request, "This reservation has already been processed.")
            return redirect("coldfront_orcd_direct_charge:rental-manager")

        form = ReservationDeclineForm(request.POST)
        if form.is_valid():
            reservation.status = Reservation.StatusChoices.DECLINED
            reservation.manager_notes = form.cleaned_data.get("manager_notes", "")
            reservation.processed_by = request.user
            reservation.save()

            # Log the decline action
            log_activity(
                action="reservation.declined",
                category=ActivityLog.ActionCategory.RESERVATION,
                description=f"Reservation #{reservation.pk} declined by {request.user.username}",
                request=request,
                target=reservation,
                extra_data={
                    "project_id": reservation.project.pk,
                    "project_title": reservation.project.title,
                    "node": reservation.node_instance.associated_resource_address,
                    "manager_notes": reservation.manager_notes,
                },
            )

            messages.success(
                request,
                f"Reservation for {reservation.node_instance.associated_resource_address} declined."
            )
        else:
            messages.error(request, "Invalid form submission.")

        return redirect("coldfront_orcd_direct_charge:rental-manager")


class ReservationMetadataView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """View to add metadata entries to a reservation."""

    permission_required = "coldfront_orcd_direct_charge.can_manage_rentals"

    def post(self, request, pk):
        reservation = get_object_or_404(Reservation, pk=pk)

        # Get all new entry contents from POST data
        # The template sends them as new_entry_0, new_entry_1, etc.
        entries_added = 0
        for key, value in request.POST.items():
            if key.startswith("new_entry_") and value.strip():
                ReservationMetadataEntry.objects.create(
                    reservation=reservation,
                    content=value.strip(),
                )
                entries_added += 1

        if entries_added > 0:
            messages.success(
                request,
                f"Added {entries_added} metadata {'entry' if entries_added == 1 else 'entries'} "
                f"for reservation {reservation.node_instance.associated_resource_address}."
            )
        else:
            messages.info(request, "No new metadata entries were added.")

        return redirect("coldfront_orcd_direct_charge:rental-manager")


class ReservationDetailView(LoginRequiredMixin, DetailView):
    """Detail view showing comprehensive information about a single reservation.

    Access is restricted to:
    - Project members (owner, any ORCD role)
    - The requesting user who made the reservation
    - Rental managers
    """

    model = Reservation
    template_name = "coldfront_orcd_direct_charge/reservation_detail.html"
    context_object_name = "reservation"

    def dispatch(self, request, *args, **kwargs):
        """Check user has permission to view this reservation."""
        self.object = self.get_object()
        reservation = self.object

        # Allow rental managers
        if request.user.has_perm("coldfront_orcd_direct_charge.can_manage_rentals"):
            return super().dispatch(request, *args, **kwargs)

        # Allow superusers
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)

        # Allow the user who requested the reservation
        if reservation.requesting_user == request.user:
            return super().dispatch(request, *args, **kwargs)

        # Allow project owner
        if reservation.project.pi == request.user:
            return super().dispatch(request, *args, **kwargs)

        # Allow users with any ORCD role in the project
        if ProjectMemberRole.objects.filter(
            project=reservation.project, user=request.user
        ).exists():
            return super().dispatch(request, *args, **kwargs)

        messages.error(request, "You do not have permission to view this reservation.")
        return redirect("coldfront_orcd_direct_charge:my-reservations")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reservation = self.object

        # Add additional context for display
        context["project"] = reservation.project
        context["node_instance"] = reservation.node_instance
        context["is_rental_manager"] = self.request.user.has_perm(
            "coldfront_orcd_direct_charge.can_manage_rentals"
        )

        # Get metadata entries (only for rental managers)
        if context["is_rental_manager"]:
            context["metadata_entries"] = reservation.metadata_entries.all().order_by("-created")

        return context


@login_required
@require_POST
def update_maintenance_status(request):
    """Update the current user's account maintenance status via AJAX."""
    from coldfront.core.project.models import Project

    new_status = request.POST.get("status")
    project_id = request.POST.get("project_id")

    # Validate the status value
    valid_statuses = [choice[0] for choice in UserMaintenanceStatus.StatusChoices.choices]
    if new_status not in valid_statuses:
        return JsonResponse(
            {"success": False, "error": "Invalid status value"},
            status=400,
        )

    # For basic/advanced, require a billing project
    billing_project = None
    if new_status != UserMaintenanceStatus.StatusChoices.INACTIVE:
        if not project_id:
            return JsonResponse(
                {"success": False, "error": "Please select a project for fee billing"},
                status=400,
            )

        # Validate that project exists and user can use it for maintenance fees
        # (must be owner, technical admin, or member - NOT financial admin)
        try:
            billing_project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Invalid project"},
                status=400,
            )

        if not can_use_for_maintenance_fee(request.user, billing_project):
            return JsonResponse(
                {"success": False, "error": "You cannot use this project for maintenance fee billing"},
                status=400,
            )

        # Check that project has an approved cost allocation
        if not has_approved_cost_allocation(billing_project):
            return JsonResponse(
                {"success": False, "error": "This project does not have an approved cost allocation"},
                status=400,
            )

    # Get or create the user's maintenance status
    maintenance_status, _ = UserMaintenanceStatus.objects.get_or_create(
        user=request.user,
        defaults={"status": UserMaintenanceStatus.StatusChoices.INACTIVE},
    )

    # Update the status and billing project
    maintenance_status.status = new_status
    maintenance_status.billing_project = billing_project
    maintenance_status.save()

    # Build the display value
    display_value = maintenance_status.get_status_display()

    return JsonResponse({
        "success": True,
        "status": new_status,
        "display": display_value,
        "project_id": billing_project.pk if billing_project else None,
        "project_title": billing_project.title if billing_project else None,
    })


class MyReservationsView(LoginRequiredMixin, TemplateView):
    """Display reservations for projects where the user has a role.

    Shows all reservations from projects where the logged-in user is:
    - Owner (project.pi)
    - Financial Admin
    - Technical Admin
    - Member

    Reservations are categorized into:
    - Upcoming: Confirmed, end date >= today
    - Pending: Awaiting approval
    - Past: Confirmed, already completed
    - Declined/Cancelled: Rejected or cancelled reservations
    """

    template_name = "coldfront_orcd_direct_charge/my_reservations.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Get projects where user is owner
        from coldfront.core.project.models import Project

        owned_projects = Project.objects.filter(pi=user)

        # Get projects where user has explicit role
        member_projects = Project.objects.filter(
            member_roles__user=user
        ).distinct()

        # Combine all projects
        all_project_ids = set(owned_projects.values_list("pk", flat=True)) | set(
            member_projects.values_list("pk", flat=True)
        )

        # Get reservations for these projects
        reservations = (
            Reservation.objects.filter(project_id__in=all_project_ids)
            .select_related("project", "project__pi", "node_instance", "requesting_user")
            .order_by("-start_date")
        )

        today = date.today()

        # Categorize by status
        context["upcoming"] = [
            r
            for r in reservations
            if r.status == Reservation.StatusChoices.APPROVED and r.end_date >= today
        ]
        context["pending"] = [
            r for r in reservations if r.status == Reservation.StatusChoices.PENDING
        ]
        context["past"] = [
            r
            for r in reservations
            if r.status == Reservation.StatusChoices.APPROVED and r.end_date < today
        ]
        context["declined_cancelled"] = [
            r
            for r in reservations
            if r.status
            in [Reservation.StatusChoices.DECLINED, Reservation.StatusChoices.CANCELLED]
        ]

        # Store total counts
        context["total_reservations"] = len(reservations)
        context["upcoming_count"] = len(context["upcoming"])
        context["pending_count"] = len(context["pending"])
        context["past_count"] = len(context["past"])
        context["declined_cancelled_count"] = len(context["declined_cancelled"])

        # Check maintenance status for warning banner
        try:
            maintenance_status = user.maintenance_status
            context["maintenance_status_raw"] = maintenance_status.status
        except UserMaintenanceStatus.DoesNotExist:
            context["maintenance_status_raw"] = "inactive"

        # Check if user has any resource-using role in projects with upcoming/pending reservations
        # Financial admins don't need a maintenance fee since they only manage billing
        has_resource_role = False
        active_project_ids = set()
        for r in context["upcoming"] + context["pending"]:
            active_project_ids.add(r.project_id)

        for project_id in active_project_ids:
            project = Project.objects.get(pk=project_id)
            # Owner always has resource role
            if project.pi == user:
                has_resource_role = True
                break
            # Check ORCD roles - technical_admin and member are resource roles
            roles = ProjectMemberRole.objects.filter(project_id=project_id, user=user)
            for role in roles:
                if role.role in [ProjectMemberRole.RoleChoices.TECHNICAL_ADMIN,
                                 ProjectMemberRole.RoleChoices.MEMBER]:
                    has_resource_role = True
                    break
            if has_resource_role:
                break

        # Show warning if inactive, has upcoming/pending reservations, AND has resource role
        context["show_maintenance_warning"] = (
            context["maintenance_status_raw"] == "inactive"
            and (context["upcoming_count"] > 0 or context["pending_count"] > 0)
            and has_resource_role
        )

        return context


# =============================================================================
# Maintenance Window Views
# =============================================================================


class MaintenanceWindowListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """List all maintenance windows with management controls."""

    model = MaintenanceWindow
    template_name = "coldfront_orcd_direct_charge/maintenance_window/list.html"
    context_object_name = "windows"
    permission_required = "coldfront_orcd_direct_charge.can_manage_rentals"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        return context


class MaintenanceWindowCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create a new maintenance window."""

    model = MaintenanceWindow
    template_name = "coldfront_orcd_direct_charge/maintenance_window/form.html"
    fields = ["title", "start_datetime", "end_datetime", "description"]
    permission_required = "coldfront_orcd_direct_charge.can_manage_rentals"
    success_url = reverse_lazy("coldfront_orcd_direct_charge:maintenance-window-list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)

        log_activity(
            action="maintenance_window.created",
            category=ActivityLog.ActionCategory.MAINTENANCE,
            description=f"Created maintenance window: {self.object.title}",
            request=self.request,
            target=self.object,
            extra_data={
                "window_id": self.object.pk,
                "start_datetime": self.object.start_datetime.isoformat(),
                "end_datetime": self.object.end_datetime.isoformat(),
                "duration_hours": self.object.duration_hours,
            },
        )

        messages.success(
            self.request, f"Maintenance window '{self.object.title}' created successfully."
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["action"] = "Create"
        return context


class MaintenanceWindowUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Edit an existing maintenance window (future windows only)."""

    model = MaintenanceWindow
    template_name = "coldfront_orcd_direct_charge/maintenance_window/form.html"
    fields = ["title", "start_datetime", "end_datetime", "description"]
    permission_required = "coldfront_orcd_direct_charge.can_manage_rentals"
    success_url = reverse_lazy("coldfront_orcd_direct_charge:maintenance-window-list")

    def get_queryset(self):
        """Only allow editing windows that haven't started yet."""
        return MaintenanceWindow.objects.filter(start_datetime__gt=timezone.now())

    def get(self, request, *args, **kwargs):
        """Handle case where window is not editable."""
        try:
            self.object = self.get_object()
        except Http404:
            messages.error(
                request,
                "This maintenance window has already started or passed and cannot be "
                "modified through the web interface.",
            )
            return redirect("coldfront_orcd_direct_charge:maintenance-window-list")
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Handle case where window is not editable."""
        try:
            self.object = self.get_object()
        except Http404:
            messages.error(
                request,
                "This maintenance window has already started or passed and cannot be "
                "modified through the web interface.",
            )
            return redirect("coldfront_orcd_direct_charge:maintenance-window-list")
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["action"] = "Edit"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)

        log_activity(
            action="maintenance_window.updated",
            category=ActivityLog.ActionCategory.MAINTENANCE,
            description=f"Updated maintenance window: {self.object.title}",
            request=self.request,
            target=self.object,
            extra_data={
                "window_id": self.object.pk,
                "start_datetime": self.object.start_datetime.isoformat(),
                "end_datetime": self.object.end_datetime.isoformat(),
                "duration_hours": self.object.duration_hours,
            },
        )

        messages.success(
            self.request, f"Maintenance window '{self.object.title}' updated successfully."
        )
        return response


class MaintenanceWindowDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Delete a maintenance window (future windows only)."""

    model = MaintenanceWindow
    template_name = "coldfront_orcd_direct_charge/maintenance_window/delete.html"
    permission_required = "coldfront_orcd_direct_charge.can_manage_rentals"
    success_url = reverse_lazy("coldfront_orcd_direct_charge:maintenance-window-list")

    def get_queryset(self):
        """Only allow deleting windows that haven't started yet."""
        return MaintenanceWindow.objects.filter(start_datetime__gt=timezone.now())

    def get(self, request, *args, **kwargs):
        """Handle case where window is not deletable."""
        try:
            self.object = self.get_object()
        except Http404:
            messages.error(
                request,
                "This maintenance window has already started or passed and cannot be "
                "deleted through the web interface.",
            )
            return redirect("coldfront_orcd_direct_charge:maintenance-window-list")
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Handle case where window is not deletable."""
        try:
            self.object = self.get_object()
        except Http404:
            messages.error(
                request,
                "This maintenance window has already started or passed and cannot be "
                "deleted through the web interface.",
            )
            return redirect("coldfront_orcd_direct_charge:maintenance-window-list")
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        # Capture details before deletion
        window_id = self.object.pk
        window_title = self.object.title
        start_datetime = self.object.start_datetime.isoformat()
        end_datetime = self.object.end_datetime.isoformat()
        duration_hours = self.object.duration_hours

        # Log activity before deletion (object will be gone after super())
        log_activity(
            action="maintenance_window.deleted",
            category=ActivityLog.ActionCategory.MAINTENANCE,
            description=f"Deleted maintenance window: {window_title}",
            request=self.request,
            target=None,  # Object is being deleted
            extra_data={
                "window_id": window_id,
                "window_title": window_title,
                "start_datetime": start_datetime,
                "end_datetime": end_datetime,
                "duration_hours": duration_hours,
            },
        )

        response = super().form_valid(form)
        messages.success(
            self.request, f"Maintenance window '{window_title}' deleted successfully."
        )
        return response


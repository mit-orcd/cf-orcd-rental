# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

import calendar
from datetime import date, datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView, DetailView, CreateView, View

from coldfront_orcd_direct_charge.forms import (
    ProjectCostAllocationForm,
    ProjectCostObjectFormSet,
    ReservationRequestForm,
    ReservationDeclineForm,
    ReservationMetadataEntryForm,
)
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from coldfront_orcd_direct_charge.models import (
    GpuNodeInstance,
    CpuNodeInstance,
    ProjectCostAllocation,
    Reservation,
    ReservationMetadataEntry,
    UserMaintenanceStatus,
)


class NodeInstanceListView(LoginRequiredMixin, TemplateView):
    """List view showing all GPU and CPU node instances."""

    template_name = "coldfront_orcd_direct_charge/node_instance_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["gpu_nodes"] = GpuNodeInstance.objects.all()
        context["cpu_nodes"] = CpuNodeInstance.objects.all()
        context["gpu_count"] = GpuNodeInstance.objects.count()
        context["cpu_count"] = CpuNodeInstance.objects.count()
        return context


class GpuNodeInstanceDetailView(LoginRequiredMixin, DetailView):
    """Detail view for a single GPU node instance."""

    model = GpuNodeInstance
    template_name = "coldfront_orcd_direct_charge/gpu_node_detail.html"
    context_object_name = "node"


class CpuNodeInstanceDetailView(LoginRequiredMixin, DetailView):
    """Detail view for a single CPU node instance."""

    model = CpuNodeInstance
    template_name = "coldfront_orcd_direct_charge/cpu_node_detail.html"
    context_object_name = "node"


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
        reservation.save()

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
            reservation.save()

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

        # Validate that project exists and user is an active member
        try:
            billing_project = Project.objects.get(
                pk=project_id,
                projectuser__user=request.user,
                projectuser__status__name="Active",
            )
        except Project.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Invalid project or you are not an active member"},
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
    if billing_project:
        display_value = f"{display_value} (charged to: {billing_project.title})"

    return JsonResponse({
        "success": True,
        "status": new_status,
        "display": display_value,
        "project_id": billing_project.pk if billing_project else None,
        "project_title": billing_project.title if billing_project else None,
    })


class ProjectCostAllocationView(LoginRequiredMixin, TemplateView):
    """View for managing cost allocation for a project."""

    template_name = "coldfront_orcd_direct_charge/project_cost_allocation.html"

    def dispatch(self, request, *args, **kwargs):
        """Check user has permission to manage this project."""
        from coldfront.core.project.models import Project

        self.project = get_object_or_404(Project, pk=kwargs.get("pk"))

        # Check if user is PI, manager, or superuser
        is_pi = self.project.pi == request.user
        is_manager = self.project.projectuser_set.filter(
            user=request.user,
            role__name="Manager",
            status__name="Active",
        ).exists()
        is_superuser = request.user.is_superuser

        if not (is_pi or is_manager or is_superuser):
            messages.error(request, "You do not have permission to manage cost allocation for this project.")
            return redirect("project-detail", pk=self.project.pk)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project"] = self.project

        # Get or create the cost allocation for this project
        allocation, _ = ProjectCostAllocation.objects.get_or_create(
            project=self.project,
            defaults={"notes": ""},
        )
        context["allocation"] = allocation

        if self.request.method == "POST":
            context["form"] = ProjectCostAllocationForm(
                self.request.POST, instance=allocation
            )
            context["formset"] = ProjectCostObjectFormSet(
                self.request.POST, instance=allocation
            )
        else:
            context["form"] = ProjectCostAllocationForm(instance=allocation)
            context["formset"] = ProjectCostObjectFormSet(instance=allocation)

        return context

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        form = context["form"]
        formset = context["formset"]

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Cost allocation updated successfully.")
            return redirect("project-detail", pk=self.project.pk)

        # Re-render with errors
        return self.render_to_response(context)

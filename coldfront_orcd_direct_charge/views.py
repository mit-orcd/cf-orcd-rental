# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

import calendar
import logging
from datetime import date, datetime, time, timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView, DetailView, CreateView, View

from coldfront_orcd_direct_charge.forms import (
    ProjectCostAllocationForm,
    ProjectCostObjectFormSet,
    ReservationRequestForm,
    ReservationDeclineForm,
    ReservationMetadataEntryForm,
    RateForm,
    SKUForm,
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
    CostAllocationSnapshot,
    CostObjectSnapshot,
    InvoicePeriod,
    InvoiceLineOverride,
    ActivityLog,
    RentalSKU,
    RentalRate,
    can_edit_cost_allocation,
    can_use_for_maintenance_fee,
    can_view_activity_log,
    has_approved_cost_allocation,
    log_activity,
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


class ProjectCostAllocationView(LoginRequiredMixin, TemplateView):
    """View for managing cost allocation for a project."""

    template_name = "coldfront_orcd_direct_charge/project_cost_allocation.html"

    def dispatch(self, request, *args, **kwargs):
        """Check user has permission to manage this project's cost allocation."""
        from coldfront.core.project.models import Project

        self.project = get_object_or_404(Project, pk=kwargs.get("pk"))

        # Check if user can edit cost allocation (owner, financial admin, or superuser)
        if not can_edit_cost_allocation(request.user, self.project):
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
            # Save allocation and reset status to PENDING for approval
            allocation = form.save(commit=False)
            allocation.status = ProjectCostAllocation.StatusChoices.PENDING
            allocation.reviewed_by = None
            allocation.reviewed_at = None
            allocation.review_notes = ""
            allocation.save()
            formset.save()
            logger.info(
                f"Cost allocation submitted for approval: project={self.project.pk}, "
                f"submitted_by={request.user.username}"
            )
            messages.info(
                request,
                "Cost allocation submitted for approval. "
                "A Billing Manager will review your submission."
            )
            return redirect("project-detail", pk=self.project.pk)

        # Re-render with errors
        return self.render_to_response(context)


# =============================================================================
# Billing Manager Views
# =============================================================================


class PendingCostAllocationsView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """List all cost allocations pending approval.

    Only accessible to users with can_manage_billing permission (Billing Managers).
    """

    template_name = "coldfront_orcd_direct_charge/pending_cost_allocations.html"
    permission_required = "coldfront_orcd_direct_charge.can_manage_billing"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get pending allocations with related data
        pending_allocations = ProjectCostAllocation.objects.filter(
            status=ProjectCostAllocation.StatusChoices.PENDING
        ).select_related("project", "project__pi").prefetch_related("cost_objects").order_by("-modified")

        context["pending_allocations"] = pending_allocations
        context["pending_count"] = pending_allocations.count()

        return context


class CostAllocationApprovalView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Review and approve/reject a cost allocation.

    Only accessible to users with can_manage_billing permission (Billing Managers).
    """

    template_name = "coldfront_orcd_direct_charge/cost_allocation_review.html"
    permission_required = "coldfront_orcd_direct_charge.can_manage_billing"

    def dispatch(self, request, *args, **kwargs):
        self.allocation = get_object_or_404(ProjectCostAllocation, pk=kwargs.get("pk"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["allocation"] = self.allocation
        context["project"] = self.allocation.project
        context["cost_objects"] = self.allocation.cost_objects.all()
        context["total_percentage"] = self.allocation.total_percentage()
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        review_notes = request.POST.get("review_notes", "").strip()

        if action == "approve":
            approval_time = timezone.now()

            # Mark any existing current snapshots as superseded
            CostAllocationSnapshot.objects.filter(
                allocation=self.allocation,
                superseded_at__isnull=True,
            ).update(superseded_at=approval_time)

            # Create a new snapshot of the current cost objects
            snapshot = CostAllocationSnapshot.objects.create(
                allocation=self.allocation,
                approved_at=approval_time,
                approved_by=request.user,
                superseded_at=None,
            )

            # Copy all current cost objects to the snapshot
            for cost_object in self.allocation.cost_objects.all():
                CostObjectSnapshot.objects.create(
                    snapshot=snapshot,
                    cost_object=cost_object.cost_object,
                    percentage=cost_object.percentage,
                )

            self.allocation.status = ProjectCostAllocation.StatusChoices.APPROVED
            self.allocation.reviewed_by = request.user
            self.allocation.reviewed_at = approval_time
            self.allocation.review_notes = review_notes
            self.allocation.save()
            logger.info(
                f"Cost allocation approved: project={self.allocation.project.pk}, "
                f"approved_by={request.user.username}, snapshot_id={snapshot.pk}"
            )

            # Log to activity log
            log_activity(
                action="cost_allocation.approved",
                category=ActivityLog.ActionCategory.COST_ALLOCATION,
                description=f"Cost allocation approved for {self.allocation.project.title}",
                request=request,
                target=self.allocation,
                extra_data={
                    "project_id": self.allocation.project.pk,
                    "project_title": self.allocation.project.title,
                    "snapshot_id": snapshot.pk,
                },
            )

            messages.success(
                request,
                f"Cost allocation for '{self.allocation.project.title}' has been approved."
            )
        elif action == "reject":
            if not review_notes:
                messages.error(request, "Please provide a reason for rejection.")
                return self.render_to_response(self.get_context_data(**kwargs))

            self.allocation.status = ProjectCostAllocation.StatusChoices.REJECTED
            self.allocation.reviewed_by = request.user
            self.allocation.reviewed_at = timezone.now()
            self.allocation.review_notes = review_notes
            self.allocation.save()
            logger.info(
                f"Cost allocation rejected: project={self.allocation.project.pk}, "
                f"rejected_by={request.user.username}, reason={review_notes}"
            )

            # Log to activity log
            log_activity(
                action="cost_allocation.rejected",
                category=ActivityLog.ActionCategory.COST_ALLOCATION,
                description=f"Cost allocation rejected for {self.allocation.project.title}",
                request=request,
                target=self.allocation,
                extra_data={
                    "project_id": self.allocation.project.pk,
                    "project_title": self.allocation.project.title,
                    "review_notes": review_notes,
                },
            )

            messages.warning(
                request,
                f"Cost allocation for '{self.allocation.project.title}' has been rejected."
            )
        else:
            messages.error(request, "Invalid action.")
            return self.render_to_response(self.get_context_data(**kwargs))

        return redirect("coldfront_orcd_direct_charge:pending-cost-allocations")


# =============================================================================
# Invoice Preparation Views
# =============================================================================


class InvoicePreparationView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Month selector for invoice preparation.

    Shows a list of months with completed reservations and their invoice status.
    Only accessible to users with can_manage_billing permission.
    """

    template_name = "coldfront_orcd_direct_charge/invoice_preparation.html"
    permission_required = "coldfront_orcd_direct_charge.can_manage_billing"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all months with approved reservations (including future)
        approved_reservations = Reservation.objects.filter(
            status=Reservation.StatusChoices.APPROVED,
        ).select_related("project")

        # Find unique year/month combinations from all approved reservations
        months_with_reservations = set()
        for res in approved_reservations:
            # Add each day of the reservation to find all months it spans
            current = res.start_date
            while current <= res.end_date:
                months_with_reservations.add((current.year, current.month))
                # Move to next month
                if current.month == 12:
                    current = date(current.year + 1, 1, 1)
                else:
                    current = date(current.year, current.month + 1, 1)

        # Build list of months with invoice status
        invoice_months = []
        for year, month in sorted(months_with_reservations, reverse=True):
            invoice_period = InvoicePeriod.objects.filter(year=year, month=month).first()
            override_count = 0
            if invoice_period:
                override_count = invoice_period.overrides.count()

            invoice_months.append({
                "year": year,
                "month": month,
                "month_name": calendar.month_name[month],
                "invoice_period": invoice_period,
                "status": invoice_period.get_status_display() if invoice_period else "Not Started",
                "override_count": override_count,
            })

        context["invoice_months"] = invoice_months

        return context


class InvoiceDetailView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Display invoice report for a specific month.

    Shows all completed reservations for the month with cost object breakdowns.
    Only accessible to users with can_manage_billing permission.
    """

    template_name = "coldfront_orcd_direct_charge/invoice_detail.html"
    permission_required = "coldfront_orcd_direct_charge.can_manage_billing"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        year = int(self.kwargs.get("year"))
        month = int(self.kwargs.get("month"))

        context["year"] = year
        context["month"] = month
        context["month_name"] = calendar.month_name[month]

        # Get or create invoice period
        invoice_period, _ = InvoicePeriod.objects.get_or_create(
            year=year,
            month=month,
            defaults={"status": InvoicePeriod.StatusChoices.DRAFT},
        )
        context["invoice_period"] = invoice_period

        # Get all approved reservations that overlap with this month
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        # Get filter parameters
        owner_filter = self.request.GET.get("owner", "")
        title_filter = self.request.GET.get("title", "")

        # Get distinct owners for dropdown (before filtering)
        all_owners = Reservation.objects.filter(
            status=Reservation.StatusChoices.APPROVED
        ).values_list("project__pi__username", flat=True).distinct().order_by("project__pi__username")
        context["owners"] = list(all_owners)
        context["owner_filter"] = owner_filter
        context["title_filter"] = title_filter

        # Get all approved reservations that overlap this month (including future)
        all_reservations = Reservation.objects.filter(
            status=Reservation.StatusChoices.APPROVED,
        ).select_related("project", "project__pi", "node_instance")

        # Apply filters
        if owner_filter:
            all_reservations = all_reservations.filter(project__pi__username=owner_filter)
        if title_filter:
            all_reservations = all_reservations.filter(project__title__icontains=title_filter)

        # Filter to reservations that overlap with this month
        reservations = []
        for res in all_reservations:
            # Check if reservation overlaps this month
            if res.start_date <= month_end and res.end_date >= month_start:
                reservations.append(res)

        # Get overrides for this period
        overrides = {
            o.reservation_id: o
            for o in invoice_period.overrides.select_related("created_by")
        }

        # Calculate billing details for each reservation
        invoice_lines = []
        for res in reservations:
            override = overrides.get(res.pk)

            # If excluded via override, mark it
            if override and override.override_type == InvoiceLineOverride.OverrideTypeChoices.EXCLUDE:
                invoice_lines.append({
                    "reservation": res,
                    "excluded": True,
                    "override": override,
                    "hours_in_month": 0,
                    "cost_breakdown": [],
                })
                continue

            # Calculate hours for this month
            hours_data = self._calculate_hours_for_month(res, year, month)

            # Check for hours override
            if override and override.override_type == InvoiceLineOverride.OverrideTypeChoices.HOURS:
                hours_in_month = override.override_value.get("hours", hours_data["hours"])
            else:
                hours_in_month = hours_data["hours"]

            # Calculate cost breakdown using snapshots
            if override and override.override_type == InvoiceLineOverride.OverrideTypeChoices.COST_SPLIT:
                cost_breakdown = override.override_value.get("cost_breakdown", [])
            else:
                cost_breakdown = self._calculate_cost_breakdown(
                    res, year, month, hours_in_month
                )

            invoice_lines.append({
                "reservation": res,
                "excluded": False,
                "override": override,
                "hours_in_month": hours_in_month,
                "cost_breakdown": cost_breakdown,
                "daily_breakdown": hours_data.get("daily_breakdown", []),
            })

        # Group by project
        projects = {}
        for line in invoice_lines:
            project = line["reservation"].project
            if project.pk not in projects:
                projects[project.pk] = {
                    "project": project,
                    "lines": [],
                    "total_hours": 0,
                    "cost_totals": {},
                }
            projects[project.pk]["lines"].append(line)
            if not line["excluded"]:
                projects[project.pk]["total_hours"] += line["hours_in_month"]
                for co in line["cost_breakdown"]:
                    if co["cost_object"] not in projects[project.pk]["cost_totals"]:
                        projects[project.pk]["cost_totals"][co["cost_object"]] = 0
                    projects[project.pk]["cost_totals"][co["cost_object"]] += co["hours"]

        context["projects"] = list(projects.values())
        context["total_reservations"] = len(invoice_lines)
        context["excluded_count"] = sum(1 for l in invoice_lines if l["excluded"])

        return context

    def _calculate_hours_for_month(self, reservation, year, month):
        """Calculate how many hours of a reservation fall within a specific month."""
        # Use naive datetimes to match Reservation.start_datetime/end_datetime
        month_start = datetime.combine(date(year, month, 1), time(0, 0))
        if month == 12:
            month_end = datetime.combine(date(year + 1, 1, 1), time(0, 0))
        else:
            month_end = datetime.combine(date(year, month + 1, 1), time(0, 0))

        # Clip reservation to month boundaries (all naive datetimes)
        effective_start = max(reservation.start_datetime, month_start)
        effective_end = min(reservation.end_datetime, month_end)

        if effective_end <= effective_start:
            return {"hours": 0, "daily_breakdown": []}

        # Calculate total hours in this month
        delta = effective_end - effective_start
        hours = delta.total_seconds() / 3600

        return {
            "hours": round(hours, 2),
            "effective_start": effective_start,
            "effective_end": effective_end,
        }

    def _calculate_cost_breakdown(self, reservation, year, month, total_hours):
        """Calculate cost object breakdown using historical snapshots.

        For each day of the reservation in this month, find the active snapshot
        and allocate that day's hours according to the snapshot's percentages.
        """
        from decimal import Decimal

        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        # Track hours by cost object
        cost_hours = {}

        # Iterate through each day of the reservation in this month
        current_date = max(reservation.start_date, month_start)
        end_date = min(reservation.end_date, month_end)

        while current_date <= end_date:
            # Get hours for this day
            day_hours = self._get_hours_for_day(reservation, current_date, year, month)

            if day_hours > 0:
                # Get the active snapshot for this day
                # Cost object changes take effect the day AFTER approval
                snapshot = CostAllocationSnapshot.get_active_snapshot_for_date(
                    reservation.project, current_date
                )

                if snapshot:
                    # Allocate hours according to snapshot percentages
                    for co_snap in snapshot.cost_objects.all():
                        co_id = co_snap.cost_object
                        pct = float(co_snap.percentage) / 100.0
                        hours_for_co = day_hours * pct

                        if co_id not in cost_hours:
                            cost_hours[co_id] = 0
                        cost_hours[co_id] += hours_for_co
                else:
                    # No snapshot available - log and add to "Unknown"
                    if "UNKNOWN" not in cost_hours:
                        cost_hours["UNKNOWN"] = 0
                    cost_hours["UNKNOWN"] += day_hours

            current_date += timedelta(days=1)

        # Convert to list format
        breakdown = [
            {"cost_object": co, "hours": round(hours, 2)}
            for co, hours in sorted(cost_hours.items())
        ]

        return breakdown

    def _get_hours_for_day(self, reservation, target_date, year, month):
        """Calculate hours for a specific day of a reservation."""
        # Define the day boundaries (naive datetimes to match Reservation)
        day_start = datetime.combine(target_date, time(0, 0))
        day_end = datetime.combine(target_date + timedelta(days=1), time(0, 0))

        # Clip to reservation boundaries (all naive datetimes)
        effective_start = max(reservation.start_datetime, day_start)
        effective_end = min(reservation.end_datetime, day_end)

        if effective_end <= effective_start:
            return 0

        delta = effective_end - effective_start
        return delta.total_seconds() / 3600

    def post(self, request, *args, **kwargs):
        """Handle finalize/unfinalize actions."""
        year = int(self.kwargs.get("year"))
        month = int(self.kwargs.get("month"))

        invoice_period, _ = InvoicePeriod.objects.get_or_create(
            year=year,
            month=month,
            defaults={"status": InvoicePeriod.StatusChoices.DRAFT},
        )

        action = request.POST.get("action")

        if action == "finalize":
            invoice_period.status = InvoicePeriod.StatusChoices.FINALIZED
            invoice_period.finalized_by = request.user
            invoice_period.finalized_at = timezone.now()
            invoice_period.save()
            logger.info(
                f"Invoice period finalized: {year}/{month}, by={request.user.username}"
            )

            # Log to activity log
            log_activity(
                action="invoice.finalized",
                category=ActivityLog.ActionCategory.INVOICE,
                description=f"Invoice {calendar.month_name[month]} {year} finalized",
                request=request,
                target=invoice_period,
                extra_data={"year": year, "month": month},
            )

            messages.success(request, f"Invoice for {calendar.month_name[month]} {year} has been finalized.")
        elif action == "unfinalize":
            invoice_period.status = InvoicePeriod.StatusChoices.DRAFT
            invoice_period.finalized_by = None
            invoice_period.finalized_at = None
            invoice_period.save()
            logger.info(
                f"Invoice period unfinalized: {year}/{month}, by={request.user.username}"
            )

            # Log to activity log
            log_activity(
                action="invoice.reopened",
                category=ActivityLog.ActionCategory.INVOICE,
                description=f"Invoice {calendar.month_name[month]} {year} reopened for editing",
                request=request,
                target=invoice_period,
                extra_data={"year": year, "month": month},
            )

            messages.info(request, f"Invoice for {calendar.month_name[month]} {year} has been reopened for editing.")

        return redirect("coldfront_orcd_direct_charge:invoice-detail", year=year, month=month)


class InvoiceEditView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Edit view for adding/modifying invoice line overrides.

    Allows Billing Managers to override hours, cost splits, or exclude reservations.
    Only accessible when the invoice is not finalized.
    """

    template_name = "coldfront_orcd_direct_charge/invoice_edit.html"
    permission_required = "coldfront_orcd_direct_charge.can_manage_billing"

    def dispatch(self, request, *args, **kwargs):
        year = int(kwargs.get("year"))
        month = int(kwargs.get("month"))

        self.invoice_period = InvoicePeriod.objects.filter(year=year, month=month).first()

        if self.invoice_period and self.invoice_period.is_finalized:
            messages.error(request, "Cannot edit a finalized invoice.")
            return redirect("coldfront_orcd_direct_charge:invoice-detail", year=year, month=month)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        year = int(self.kwargs.get("year"))
        month = int(self.kwargs.get("month"))
        reservation_id = self.request.GET.get("reservation")

        context["year"] = year
        context["month"] = month
        context["month_name"] = calendar.month_name[month]

        # Get or create invoice period
        invoice_period, _ = InvoicePeriod.objects.get_or_create(
            year=year,
            month=month,
            defaults={"status": InvoicePeriod.StatusChoices.DRAFT},
        )
        context["invoice_period"] = invoice_period

        if reservation_id:
            reservation = get_object_or_404(Reservation, pk=reservation_id)
            context["reservation"] = reservation

            # Get existing override if any
            existing_override = InvoiceLineOverride.objects.filter(
                invoice_period=invoice_period,
                reservation=reservation,
            ).first()
            context["existing_override"] = existing_override

            # Calculate original values
            month_start = date(year, month, 1)
            if month == 12:
                month_end = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = date(year, month + 1, 1) - timedelta(days=1)

            # Calculate hours
            hours_data = InvoiceDetailView._calculate_hours_for_month(
                InvoiceDetailView(), reservation, year, month
            )
            context["original_hours"] = hours_data["hours"]

            # Get current cost objects for the project
            try:
                allocation = reservation.project.cost_allocation
                context["cost_objects"] = list(allocation.cost_objects.values("cost_object", "percentage"))
            except ProjectCostAllocation.DoesNotExist:
                context["cost_objects"] = []

        return context

    def post(self, request, *args, **kwargs):
        year = int(self.kwargs.get("year"))
        month = int(self.kwargs.get("month"))
        reservation_id = request.POST.get("reservation_id")
        override_type = request.POST.get("override_type")
        notes = request.POST.get("notes", "").strip()

        if not notes:
            messages.error(request, "Notes are required for any override.")
            return redirect(
                f"{request.path}?reservation={reservation_id}"
            )

        reservation = get_object_or_404(Reservation, pk=reservation_id)

        invoice_period, _ = InvoicePeriod.objects.get_or_create(
            year=year,
            month=month,
            defaults={"status": InvoicePeriod.StatusChoices.DRAFT},
        )

        # Calculate original values for audit
        hours_data = InvoiceDetailView._calculate_hours_for_month(
            InvoiceDetailView(), reservation, year, month
        )
        original_cost_breakdown = InvoiceDetailView._calculate_cost_breakdown(
            InvoiceDetailView(), reservation, year, month, hours_data["hours"]
        )

        original_value = {
            "hours": hours_data["hours"],
            "cost_breakdown": original_cost_breakdown,
        }

        # Build override value based on type
        if override_type == InvoiceLineOverride.OverrideTypeChoices.EXCLUDE:
            override_value = {"excluded": True}
        elif override_type == InvoiceLineOverride.OverrideTypeChoices.HOURS:
            new_hours = float(request.POST.get("override_hours", hours_data["hours"]))
            override_value = {"hours": new_hours}
        elif override_type == InvoiceLineOverride.OverrideTypeChoices.COST_SPLIT:
            # Parse custom cost split from form
            cost_breakdown = []
            for key, value in request.POST.items():
                if key.startswith("cost_object_"):
                    co_id = key.replace("cost_object_", "")
                    hours = float(value) if value else 0
                    cost_breakdown.append({"cost_object": co_id, "hours": hours})
            override_value = {"cost_breakdown": cost_breakdown}
        else:
            messages.error(request, "Invalid override type.")
            return redirect(
                f"{request.path}?reservation={reservation_id}"
            )

        # Create or update override
        override, created = InvoiceLineOverride.objects.update_or_create(
            invoice_period=invoice_period,
            reservation=reservation,
            defaults={
                "override_type": override_type,
                "original_value": original_value,
                "override_value": override_value,
                "notes": notes,
                "created_by": request.user,
            },
        )

        action_str = "created" if created else "updated"
        logger.info(
            f"Invoice override {action_str}: reservation={reservation.pk}, "
            f"type={override_type}, by={request.user.username}"
        )

        # Log to activity log
        log_activity(
            action=f"invoice.override_{action_str}",
            category=ActivityLog.ActionCategory.INVOICE,
            description=f"Override {action_str} for reservation #{reservation.pk}",
            request=request,
            target=override,
            extra_data={
                "year": year,
                "month": month,
                "reservation_id": reservation.pk,
                "override_type": override_type,
            },
        )

        messages.success(request, f"Override {action_str} successfully.")

        return redirect("coldfront_orcd_direct_charge:invoice-detail", year=year, month=month)


class InvoiceExportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Export invoice data as JSON.

    Generates a JSON file containing all invoice line items with audit metadata.
    """

    permission_required = "coldfront_orcd_direct_charge.can_manage_billing"

    def get(self, request, *args, **kwargs):
        from django.http import JsonResponse
        import json

        year = int(self.kwargs.get("year"))
        month = int(self.kwargs.get("month"))

        # Get invoice detail data
        detail_view = InvoiceDetailView()
        detail_view.request = request
        detail_view.kwargs = self.kwargs
        context = detail_view.get_context_data()

        # Build export data
        export_data = {
            "metadata": {
                "year": year,
                "month": month,
                "month_name": calendar.month_name[month],
                "generated_at": timezone.now().isoformat(),
                "generated_by": request.user.username,
                "invoice_status": context["invoice_period"].get_status_display(),
                "total_reservations": context["total_reservations"],
                "excluded_count": context["excluded_count"],
            },
            "projects": [],
        }

        for proj_data in context["projects"]:
            project_export = {
                "project_id": proj_data["project"].pk,
                "project_title": proj_data["project"].title,
                "project_owner": proj_data["project"].pi.username,
                "total_hours": proj_data["total_hours"],
                "cost_totals": proj_data["cost_totals"],
                "reservations": [],
            }

            for line in proj_data["lines"]:
                res = line["reservation"]
                override = line["override"]

                res_export = {
                    "reservation_id": res.pk,
                    "node": res.node_instance.associated_resource_address,
                    "start_date": res.start_date.isoformat(),
                    "start_datetime": res.start_datetime.isoformat(),
                    "end_date": res.end_date.isoformat(),
                    "end_datetime": res.end_datetime.isoformat(),
                    "billable_hours": res.billable_hours,
                    "hours_in_month": line["hours_in_month"],
                    "excluded": line["excluded"],
                    "cost_breakdown": line["cost_breakdown"],
                }

                if override:
                    res_export["override"] = {
                        "type": override.get_override_type_display(),
                        "notes": override.notes,
                        "created_by": override.created_by.username if override.created_by else None,
                        "created_at": override.created.isoformat(),
                        "original_value": override.original_value,
                        "override_value": override.override_value,
                    }

                project_export["reservations"].append(res_export)

            export_data["projects"].append(project_export)

        # Log the export action
        log_activity(
            action="invoice.exported",
            category=ActivityLog.ActionCategory.INVOICE,
            description=f"Invoice {calendar.month_name[month]} {year} exported as JSON",
            request=request,
            target=context["invoice_period"],
            extra_data={
                "year": year,
                "month": month,
                "total_reservations": context["total_reservations"],
            },
        )

        response = JsonResponse(export_data, json_dumps_params={"indent": 2})
        response["Content-Disposition"] = f'attachment; filename="invoice_{year}_{month:02d}.json"'
        return response


class InvoiceDeleteOverrideView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Delete an invoice line override."""

    permission_required = "coldfront_orcd_direct_charge.can_manage_billing"

    def post(self, request, *args, **kwargs):
        year = int(self.kwargs.get("year"))
        month = int(self.kwargs.get("month"))
        override_id = self.kwargs.get("override_id")

        override = get_object_or_404(InvoiceLineOverride, pk=override_id)

        # Check invoice is not finalized
        if override.invoice_period.is_finalized:
            messages.error(request, "Cannot delete override from a finalized invoice.")
            return redirect("coldfront_orcd_direct_charge:invoice-detail", year=year, month=month)

        reservation_id = override.reservation_id
        override_type = override.override_type
        override.delete()

        logger.info(
            f"Invoice override deleted: reservation={reservation_id}, "
            f"by={request.user.username}"
        )

        # Log to activity log
        log_activity(
            action="invoice.override_deleted",
            category=ActivityLog.ActionCategory.INVOICE,
            description=f"Override deleted for reservation #{reservation_id}",
            request=request,
            extra_data={
                "year": year,
                "month": month,
                "reservation_id": reservation_id,
                "override_type": override_type,
            },
        )

        messages.success(request, "Override deleted successfully.")

        return redirect("coldfront_orcd_direct_charge:invoice-detail", year=year, month=month)


# =============================================================================
# Member Management Views
# =============================================================================

from django.contrib.auth.models import User

from coldfront_orcd_direct_charge.forms import AddMemberForm, UpdateMemberRoleForm
from coldfront_orcd_direct_charge.models import (
    ProjectMemberRole,
    get_user_project_role,
    can_manage_members,
    can_manage_financial_admins,
)


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
        from collections import OrderedDict

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
# Add Users Search Results Views (Override ColdFront's add-users flow)
# =============================================================================

from django.forms import formset_factory
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.urls import reverse

from coldfront.core.user.utils import CombinedUserSearch

from coldfront_orcd_direct_charge.forms import ProjectAddUserWithRoleForm


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

        if len(user_search_string.split()) > 1:
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
# Activity Log View
# =============================================================================


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


# =============================================================================
# My Reservations View
# =============================================================================


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
        from coldfront_orcd_direct_charge.models import ProjectMemberRole

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


# =============================================================================
# Home2 Dashboard View
# =============================================================================


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
        from datetime import date

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


# =============================================================================
# Rate Management Views
# =============================================================================


class RateManagementView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Rate management dashboard showing all SKUs grouped by type.

    Only accessible to users with can_manage_rates permission (Rate Managers).
    """

    template_name = "coldfront_orcd_direct_charge/rate_management.html"
    permission_required = "coldfront_orcd_direct_charge.can_manage_rates"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all SKUs grouped by type
        all_skus = RentalSKU.objects.prefetch_related("rates").order_by("name")

        # Group by SKU type
        node_skus = []
        maintenance_skus = []
        qos_skus = []

        for sku in all_skus:
            current_rate = sku.current_rate
            sku_data = {
                "sku": sku,
                "current_rate": current_rate,
                "rate_count": sku.rates.count(),
            }

            if sku.sku_type == RentalSKU.SKUType.NODE:
                node_skus.append(sku_data)
            elif sku.sku_type == RentalSKU.SKUType.MAINTENANCE:
                maintenance_skus.append(sku_data)
            else:  # QOS
                qos_skus.append(sku_data)

        context["node_skus"] = node_skus
        context["maintenance_skus"] = maintenance_skus
        context["qos_skus"] = qos_skus

        return context


class SKURateDetailView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Detail view for a single SKU with rate history.

    Only accessible to users with can_manage_rates permission (Rate Managers).
    """

    template_name = "coldfront_orcd_direct_charge/sku_rate_detail.html"
    permission_required = "coldfront_orcd_direct_charge.can_manage_rates"

    def dispatch(self, request, *args, **kwargs):
        self.sku = get_object_or_404(RentalSKU, pk=kwargs.get("pk"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sku"] = self.sku
        context["current_rate"] = self.sku.current_rate
        context["rates"] = self.sku.rates.select_related("set_by").order_by("-effective_date")
        return context


class AddRateView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Add a new rate to an existing SKU.

    Only accessible to users with can_manage_rates permission (Rate Managers).
    """

    template_name = "coldfront_orcd_direct_charge/add_rate_form.html"
    permission_required = "coldfront_orcd_direct_charge.can_manage_rates"

    def dispatch(self, request, *args, **kwargs):
        self.sku = get_object_or_404(RentalSKU, pk=kwargs.get("pk"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sku"] = self.sku
        context["current_rate"] = self.sku.current_rate
        context["form"] = RateForm(sku=self.sku)
        return context

    def post(self, request, *args, **kwargs):
        form = RateForm(request.POST, sku=self.sku)

        if form.is_valid():
            # Create the new rate
            rate = RentalRate.objects.create(
                sku=self.sku,
                rate=form.cleaned_data["rate"],
                effective_date=form.cleaned_data["effective_date"],
                notes=form.cleaned_data.get("notes", ""),
                set_by=request.user,
            )

            messages.success(
                request,
                f"Rate of ${rate.rate}/{self.sku.get_billing_unit_display()} "
                f"added for {self.sku.name}, effective {rate.effective_date}."
            )

            logger.info(
                f"Rate added: sku={self.sku.sku_code}, rate={rate.rate}, "
                f"effective={rate.effective_date}, user={request.user.username}"
            )

            return redirect("coldfront_orcd_direct_charge:sku-rate-detail", pk=self.sku.pk)

        # Form invalid - re-render with errors
        context = self.get_context_data(**kwargs)
        context["form"] = form
        return self.render_to_response(context)


class CreateSKUView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Create a new custom SKU (primarily for QoS).

    Only accessible to users with can_manage_rates permission (Rate Managers).
    """

    template_name = "coldfront_orcd_direct_charge/create_sku_form.html"
    permission_required = "coldfront_orcd_direct_charge.can_manage_rates"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = SKUForm()
        return context

    def post(self, request, *args, **kwargs):
        form = SKUForm(request.POST)

        if form.is_valid():
            # Create the SKU
            sku = RentalSKU.objects.create(
                sku_code=form.cleaned_data["sku_code"],
                name=form.cleaned_data["name"],
                description=form.cleaned_data.get("description", ""),
                sku_type=form.cleaned_data["sku_type"],
                billing_unit=RentalSKU.BillingUnit.MONTHLY,  # QoS and Maintenance are always monthly
                is_active=True,
            )

            # Create initial rate
            rate = RentalRate.objects.create(
                sku=sku,
                rate=form.cleaned_data["initial_rate"],
                effective_date=date.today(),
                notes="Initial rate",
                set_by=request.user,
            )

            messages.success(
                request,
                f"SKU '{sku.name}' created with initial rate of "
                f"${rate.rate}/{sku.get_billing_unit_display()}."
            )

            logger.info(
                f"SKU created: code={sku.sku_code}, name={sku.name}, "
                f"type={sku.sku_type}, rate={rate.rate}, user={request.user.username}"
            )

            # Log activity
            log_activity(
                action="sku.created",
                category=ActivityLog.ActionCategory.RATE,
                description=f"SKU '{sku.name}' ({sku.sku_code}) created",
                user=request.user,
                request=request,
                target=sku,
                extra_data={
                    "sku_code": sku.sku_code,
                    "sku_type": sku.sku_type,
                    "initial_rate": str(rate.rate),
                },
            )

            return redirect("coldfront_orcd_direct_charge:sku-rate-detail", pk=sku.pk)

        # Form invalid - re-render with errors
        context = self.get_context_data(**kwargs)
        context["form"] = form
        return self.render_to_response(context)

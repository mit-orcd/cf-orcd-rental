# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Billing and cost allocation views.

Includes cost allocation management, billing manager approval workflow,
and invoice preparation/export functionality.
"""

import calendar
import logging
from datetime import date, datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import TemplateView, View

from coldfront_orcd_direct_charge.forms import (
    ProjectCostAllocationForm,
    ProjectCostObjectFormSet,
)
from coldfront_orcd_direct_charge.models import (
    ProjectCostAllocation,
    Reservation,
    CostAllocationSnapshot,
    CostObjectSnapshot,
    InvoicePeriod,
    InvoiceLineOverride,
    ActivityLog,
    can_edit_cost_allocation,
    get_sku_for_reservation,
    log_activity,
)

logger = logging.getLogger(__name__)


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

        # Try to get existing allocation, but don't create one just for viewing
        # This prevents creating a PENDING allocation when user just views then cancels
        allocation = ProjectCostAllocation.objects.filter(
            project=self.project
        ).first()

        # If no allocation exists, create an unsaved instance for form display only
        if allocation is None:
            allocation = ProjectCostAllocation(project=self.project)
            context["is_new_allocation"] = True
        else:
            context["is_new_allocation"] = False

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
        is_new_allocation = context.get("is_new_allocation", False)

        if form.is_valid() and formset.is_valid():
            # Wrap all database operations in a transaction for atomicity
            # If formset save fails, allocation save will be rolled back
            with transaction.atomic():
                # Save allocation and reset status to PENDING for approval
                allocation = form.save(commit=False)
                allocation.status = ProjectCostAllocation.StatusChoices.PENDING
                allocation.reviewed_by = None
                allocation.reviewed_at = None
                allocation.review_notes = ""
                allocation.save()

                # For new allocations, we need to set the formset's instance
                # to the now-saved allocation before saving the formset
                if is_new_allocation:
                    formset.instance = allocation

                formset.save()

            # Logging and messages outside transaction
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

            # Wrap all database operations in a transaction for atomicity
            # If any operation fails, all changes will be rolled back
            with transaction.atomic():
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

            # Logging and messages outside transaction
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

            # Wrap database operations in a transaction for atomicity
            with transaction.atomic():
                self.allocation.status = ProjectCostAllocation.StatusChoices.REJECTED
                self.allocation.reviewed_by = request.user
                self.allocation.reviewed_at = timezone.now()
                self.allocation.review_notes = review_notes
                self.allocation.save()

            # Logging and messages outside transaction
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

            # Get SKU for this reservation
            sku = get_sku_for_reservation(res)

            # If excluded via override, mark it
            if override and override.override_type == InvoiceLineOverride.OverrideTypeChoices.EXCLUDE:
                invoice_lines.append({
                    "reservation": res,
                    "excluded": True,
                    "override": override,
                    "hours_in_month": 0,
                    "maintenance_deduction": 0,
                    "cost_breakdown": [],
                    "sku": sku,
                })
                continue

            # Calculate hours for this month
            hours_data = self._calculate_hours_for_month(res, year, month)

            # Check for hours override
            if override and override.override_type == InvoiceLineOverride.OverrideTypeChoices.HOURS:
                hours_in_month = override.override_value.get("hours", hours_data["hours"])
            else:
                hours_in_month = hours_data["hours"]

            # Determine the effective project for cost breakdown
            # (may differ from reservation project if CHARGE_PROJECT override)
            charge_redirected = False
            original_project = None
            effective_project = res.project

            if override and override.override_type == InvoiceLineOverride.OverrideTypeChoices.CHARGE_PROJECT:
                from coldfront.core.project.models import Project

                target_id = override.override_value.get("target_project_id")
                if target_id:
                    try:
                        target_project = Project.objects.select_related("pi").get(pk=target_id)
                        original_project = res.project
                        effective_project = target_project
                        charge_redirected = True
                    except Project.DoesNotExist:
                        pass  # Fall back to original project

            # Calculate cost breakdown using snapshots
            if override and override.override_type == InvoiceLineOverride.OverrideTypeChoices.COST_SPLIT:
                cost_breakdown = override.override_value.get("cost_breakdown", [])
            elif charge_redirected:
                # Use target project's cost allocation for the breakdown
                cost_breakdown = self._calculate_cost_breakdown_for_project(
                    effective_project, res, year, month, hours_in_month
                )
            else:
                cost_breakdown = self._calculate_cost_breakdown(
                    res, year, month, hours_in_month
                )

            # Calculate maintenance deduction for this reservation in this month
            maintenance_deduction = self._get_maintenance_deduction_for_reservation(
                res, year, month
            )

            line_data = {
                "reservation": res,
                "excluded": False,
                "override": override,
                "hours_in_month": hours_in_month,
                "maintenance_deduction": round(maintenance_deduction, 2),
                "cost_breakdown": cost_breakdown,
                "daily_breakdown": hours_data.get("daily_breakdown", []),
                "sku": sku,
            }

            if charge_redirected:
                line_data["charge_redirected"] = True
                line_data["original_project"] = original_project
                line_data["effective_project"] = effective_project

            invoice_lines.append(line_data)

        # Group by project (use effective_project for charge-redirected lines)
        projects = {}
        for line in invoice_lines:
            project = line.get("effective_project", line["reservation"].project)
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

    def _calculate_cost_breakdown_for_project(self, project, reservation, year, month, total_hours):
        """Calculate cost object breakdown using a specific project's snapshots.

        Similar to _calculate_cost_breakdown, but uses the given project's cost
        allocation snapshots instead of the reservation's project. Used when a
        CHARGE_PROJECT override redirects charges to a different project.
        """
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        cost_hours = {}

        current_date = max(reservation.start_date, month_start)
        end_date = min(reservation.end_date, month_end)

        while current_date <= end_date:
            day_hours = self._get_hours_for_day(reservation, current_date, year, month)

            if day_hours > 0:
                # Use the TARGET project's snapshot instead of the reservation's project
                snapshot = CostAllocationSnapshot.get_active_snapshot_for_date(
                    project, current_date
                )

                if snapshot:
                    for co_snap in snapshot.cost_objects.all():
                        co_id = co_snap.cost_object
                        pct = float(co_snap.percentage) / 100.0
                        hours_for_co = day_hours * pct

                        if co_id not in cost_hours:
                            cost_hours[co_id] = 0
                        cost_hours[co_id] += hours_for_co
                else:
                    # No snapshot; fall back to current cost allocation
                    try:
                        allocation = project.cost_allocation
                        for co in allocation.cost_objects.all():
                            co_id = co.cost_object
                            pct = float(co.percentage) / 100.0
                            hours_for_co = day_hours * pct

                            if co_id not in cost_hours:
                                cost_hours[co_id] = 0
                            cost_hours[co_id] += hours_for_co
                    except ProjectCostAllocation.DoesNotExist:
                        if "UNKNOWN" not in cost_hours:
                            cost_hours["UNKNOWN"] = 0
                        cost_hours["UNKNOWN"] += day_hours

            current_date += timedelta(days=1)

        breakdown = [
            {"cost_object": co, "hours": round(hours, 2)}
            for co, hours in sorted(cost_hours.items())
        ]

        return breakdown

    def _get_maintenance_hours_for_period(self, start_dt, end_dt):
        """Calculate total maintenance hours overlapping a time period.
        
        Args:
            start_dt: Period start datetime (naive)
            end_dt: Period end datetime (naive)
            
        Returns:
            float: Total hours of maintenance window overlap
        """
        from coldfront_orcd_direct_charge.models import MaintenanceWindow
        
        # Find all maintenance windows that overlap with this period
        # Note: MaintenanceWindow uses timezone-aware datetimes, but we compare with naive
        # datetimes from Reservation. We need to handle this carefully.
        windows = MaintenanceWindow.objects.filter(
            start_datetime__lt=end_dt,
            end_datetime__gt=start_dt
        )
        
        total_hours = 0
        for window in windows:
            # Convert maintenance window times to naive for comparison
            # (assuming they're stored in the same timezone as reservations)
            window_start = window.start_datetime
            window_end = window.end_datetime
            
            # Make naive if timezone-aware
            if hasattr(window_start, 'tzinfo') and window_start.tzinfo is not None:
                window_start = window_start.replace(tzinfo=None)
            if hasattr(window_end, 'tzinfo') and window_end.tzinfo is not None:
                window_end = window_end.replace(tzinfo=None)
            
            # Calculate the overlap
            overlap_start = max(window_start, start_dt)
            overlap_end = min(window_end, end_dt)
            if overlap_end > overlap_start:
                delta = overlap_end - overlap_start
                total_hours += delta.total_seconds() / 3600
        
        return total_hours

    def _get_maintenance_deduction_for_reservation(self, reservation, year, month):
        """Calculate total maintenance hours for a reservation in a given month.
        
        Args:
            reservation: The Reservation object
            year: Invoice year
            month: Invoice month
            
        Returns:
            float: Total hours of maintenance window overlap for this reservation in this month
        """
        # Get month boundaries
        month_start = datetime.combine(date(year, month, 1), time(0, 0))
        if month == 12:
            month_end = datetime.combine(date(year + 1, 1, 1), time(0, 0))
        else:
            month_end = datetime.combine(date(year, month + 1, 1), time(0, 0))
        
        # Clip reservation to month
        effective_start = max(reservation.start_datetime, month_start)
        effective_end = min(reservation.end_datetime, month_end)
        
        if effective_end <= effective_start:
            return 0
        
        return self._get_maintenance_hours_for_period(effective_start, effective_end)

    def _get_hours_for_day(self, reservation, target_date, year, month):
        """Calculate hours for a specific day of a reservation, excluding maintenance windows."""
        # Define the day boundaries (naive datetimes to match Reservation)
        day_start = datetime.combine(target_date, time(0, 0))
        day_end = datetime.combine(target_date + timedelta(days=1), time(0, 0))

        # Clip to reservation boundaries (all naive datetimes)
        effective_start = max(reservation.start_datetime, day_start)
        effective_end = min(reservation.end_datetime, day_end)

        if effective_end <= effective_start:
            return 0

        delta = effective_end - effective_start
        raw_hours = delta.total_seconds() / 3600
        
        # Subtract any maintenance window overlap
        maintenance_hours = self._get_maintenance_hours_for_period(
            effective_start, effective_end
        )
        
        return max(0, raw_hours - maintenance_hours)

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
            
            # Calculate maintenance deduction
            context["maintenance_deduction"] = round(
                InvoiceDetailView._get_maintenance_deduction_for_reservation(
                    InvoiceDetailView(), reservation, year, month
                ), 2
            )

            # Get current cost objects for the project
            try:
                allocation = reservation.project.cost_allocation
                context["cost_objects"] = list(allocation.cost_objects.values("cost_object", "percentage"))
            except ProjectCostAllocation.DoesNotExist:
                context["cost_objects"] = []

            # --- Charge to Different Project: build eligible and all project lists ---
            from coldfront.core.project.models import Project
            from coldfront_orcd_direct_charge.models import ProjectMemberRole

            current_project = reservation.project

            # Eligible projects: same PI OR shared financial admin
            current_fin_admin_user_ids = list(
                ProjectMemberRole.objects.filter(
                    project=current_project,
                    role=ProjectMemberRole.RoleChoices.FINANCIAL_ADMIN,
                ).values_list("user_id", flat=True)
            )

            from django.db.models import Q

            eligible_qs = Project.objects.filter(
                status__name="Active",
            ).exclude(pk=current_project.pk)

            if current_fin_admin_user_ids:
                eligible_qs = eligible_qs.filter(
                    Q(pi=current_project.pi)
                    | Q(
                        member_roles__user_id__in=current_fin_admin_user_ids,
                        member_roles__role=ProjectMemberRole.RoleChoices.FINANCIAL_ADMIN,
                    )
                    | Q(pi_id__in=current_fin_admin_user_ids)
                ).distinct()
            else:
                eligible_qs = eligible_qs.filter(pi=current_project.pi)

            eligible_projects = list(
                eligible_qs.select_related("pi").order_by("pi__username", "title")
            )
            import json

            context["eligible_projects_json"] = json.dumps([
                {"id": p.pk, "label": f"{p.pi.username} - {p.title}"}
                for p in eligible_projects
            ])

            # All active projects (for "any project" option, billing managers only)
            all_projects = list(
                Project.objects.filter(status__name="Active")
                .exclude(pk=current_project.pk)
                .select_related("pi")
                .order_by("pi__username", "title")
            )
            context["all_projects_json"] = json.dumps([
                {"id": p.pk, "label": f"{p.pi.username} - {p.title}"}
                for p in all_projects
            ])

            context["is_billing_manager"] = self.request.user.has_perm(
                "coldfront_orcd_direct_charge.can_manage_billing"
            )

            # If editing an existing CHARGE_PROJECT override, include target project info
            if (
                existing_override
                and existing_override.override_type
                == InvoiceLineOverride.OverrideTypeChoices.CHARGE_PROJECT
            ):
                target_id = existing_override.override_value.get("target_project_id")
                if target_id:
                    try:
                        target_project = Project.objects.select_related("pi").get(pk=target_id)
                        context["existing_target_project_id"] = target_project.pk
                        context["existing_target_project_label"] = (
                            f"{target_project.pi.username} - {target_project.title}"
                        )
                    except Project.DoesNotExist:
                        context["existing_target_project_id"] = None

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
        elif override_type == InvoiceLineOverride.OverrideTypeChoices.CHARGE_PROJECT:
            from coldfront.core.project.models import Project

            target_project_id = request.POST.get("target_project_id")
            if not target_project_id:
                messages.error(request, "Please select a target project.")
                return redirect(f"{request.path}?reservation={reservation_id}")

            try:
                target_project = Project.objects.get(pk=int(target_project_id))
            except (Project.DoesNotExist, ValueError, TypeError):
                messages.error(request, "Selected project does not exist.")
                return redirect(f"{request.path}?reservation={reservation_id}")

            if target_project.pk == reservation.project.pk:
                messages.error(request, "Target project must be different from the current project.")
                return redirect(f"{request.path}?reservation={reservation_id}")

            # Verify the target project has an approved cost allocation
            try:
                target_allocation = target_project.cost_allocation
                if not target_allocation.is_approved():
                    messages.error(
                        request,
                        f"Project \"{target_project.title}\" does not have an approved cost allocation.",
                    )
                    return redirect(f"{request.path}?reservation={reservation_id}")
            except ProjectCostAllocation.DoesNotExist:
                messages.error(
                    request,
                    f"Project \"{target_project.title}\" does not have a cost allocation configured.",
                )
                return redirect(f"{request.path}?reservation={reservation_id}")

            override_value = {"target_project_id": target_project.pk}
            # Also record the original project id for audit trail
            original_value["original_project_id"] = reservation.project.pk
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
                sku = line.get("sku")

                res_export = {
                    "reservation_id": res.pk,
                    "node": res.node_instance.associated_resource_address,
                    "sku_code": sku.sku_code if sku else None,
                    "sku_name": sku.name if sku else None,
                    "start_date": res.start_date.isoformat(),
                    "start_datetime": res.start_datetime.isoformat(),
                    "end_date": res.end_date.isoformat(),
                    "end_datetime": res.end_datetime.isoformat(),
                    "billable_hours": res.billable_hours,
                    "hours_in_month": line["hours_in_month"],
                    "maintenance_deduction": line.get("maintenance_deduction", 0),
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

                # Include charge redirect metadata
                if line.get("charge_redirected"):
                    original_proj = line["original_project"]
                    res_export["charge_redirect"] = {
                        "original_project_id": original_proj.pk,
                        "original_project_title": original_proj.title,
                        "original_project_owner": original_proj.pi.username,
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


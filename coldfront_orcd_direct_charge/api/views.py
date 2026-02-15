# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

import calendar
from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from django_filters import rest_framework as filters
from rest_framework import permissions, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from coldfront_orcd_direct_charge.api.serializers import (
    MaintenanceSubscriptionSerializer,
    MaintenanceWindowSerializer,
    ProjectCostAllocationSerializer,
    QoSSubscriptionSerializer,
    ReservationSerializer,
    SKUSerializer,
)
from coldfront_orcd_direct_charge.models import (
    ActivityLog,
    CostAllocationSnapshot,
    GpuNodeInstance,
    InvoiceLineOverride,
    InvoicePeriod,
    MaintenanceWindow,
    ProjectCostAllocation,
    ProjectMemberRole,
    RentalSKU,
    Reservation,
    UserMaintenanceStatus,
    UserQoSSubscription,
    can_view_activity_log,
    get_sku_for_reservation,
    log_activity,
)


class HasManageRentalsPermission(permissions.BasePermission):
    """Permission check for can_manage_rentals."""

    def has_permission(self, request, view):
        return request.user.has_perm("coldfront_orcd_direct_charge.can_manage_rentals")


class HasManageBillingPermission(permissions.BasePermission):
    """Permission check for can_manage_billing."""

    def has_permission(self, request, view):
        return request.user.has_perm("coldfront_orcd_direct_charge.can_manage_billing")


class ReservationFilter(filters.FilterSet):
    """Filters for ReservationViewSet."""

    status = filters.ChoiceFilter(choices=Reservation.StatusChoices.choices)
    node = filters.CharFilter(field_name="node_instance__associated_resource_address")
    node_type = filters.CharFilter(field_name="node_instance__node_type__name")
    project = filters.CharFilter(field_name="project__title", lookup_expr="icontains")
    requesting_user = filters.CharFilter(field_name="requesting_user__username")
    start_date = filters.DateFromToRangeFilter()

    class Meta:
        model = Reservation
        fields = [
            "status",
            "node",
            "node_type",
            "project",
            "requesting_user",
            "start_date",
        ]


class CostAllocationFilter(filters.FilterSet):
    """Filters for CostAllocationViewSet."""

    status = filters.ChoiceFilter(choices=ProjectCostAllocation.StatusChoices.choices)
    project = filters.CharFilter(field_name="project__title", lookup_expr="icontains")
    project_pi = filters.CharFilter(field_name="project__pi__username")
    created = filters.DateTimeFromToRangeFilter()
    modified = filters.DateTimeFromToRangeFilter()
    reviewed_by = filters.CharFilter(field_name="reviewed_by__username")

    class Meta:
        model = ProjectCostAllocation
        fields = [
            "status",
            "project",
            "project_pi",
            "created",
            "modified",
            "reviewed_by",
        ]


class ReservationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing reservations.

    Requires authentication and can_manage_rentals permission.

    Filters:
    - status: Filter by reservation status (PENDING, APPROVED, DECLINED, CANCELLED)
    - node: Filter by node address (exact match)
    - node_type: Filter by node type name (exact match)
    - project: Filter by project title (case-insensitive contains)
    - requesting_user: Filter by username (exact match)
    - start_date_after / start_date_before: Filter by date range
    """

    serializer_class = ReservationSerializer
    permission_classes = [IsAuthenticated, HasManageRentalsPermission]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = ReservationFilter

    def get_queryset(self):
        return Reservation.objects.select_related(
            "node_instance",
            "node_instance__node_type",
            "project",
            "requesting_user",
        ).order_by("-created")


class CostAllocationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing cost allocations.

    Requires authentication and can_manage_billing permission.

    Filters:
    - status: Filter by status (PENDING, APPROVED, REJECTED)
    - project: Filter by project title (case-insensitive contains)
    - project_pi: Filter by project PI username (exact match)
    - created_after / created_before: Filter by created date range
    - modified_after / modified_before: Filter by modified date range
    - reviewed_by: Filter by reviewer username (exact match)
    """

    serializer_class = ProjectCostAllocationSerializer
    permission_classes = [IsAuthenticated, HasManageBillingPermission]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = CostAllocationFilter

    def get_queryset(self):
        return ProjectCostAllocation.objects.select_related(
            "project",
            "project__pi",
            "reviewed_by",
        ).prefetch_related("cost_objects").order_by("-modified")


class MaintenanceWindowViewSet(viewsets.ModelViewSet):
    """ViewSet for MaintenanceWindow CRUD operations.

    Provides list, create, retrieve, update, and delete actions.
    Requires can_manage_rentals permission.

    Query Parameters:
    - status: Filter by window status (upcoming, in_progress, completed)
    """

    queryset = MaintenanceWindow.objects.all()
    serializer_class = MaintenanceWindowSerializer
    permission_classes = [IsAuthenticated, HasManageRentalsPermission]

    def perform_create(self, serializer):
        """Set created_by to the current user."""
        serializer.save(created_by=self.request.user)

    def get_queryset(self):
        """Optionally filter by upcoming/in_progress/completed windows."""
        queryset = MaintenanceWindow.objects.select_related("created_by").all()

        # Filter by status
        status_filter = self.request.query_params.get("status")
        if status_filter == "upcoming":
            queryset = queryset.filter(start_datetime__gt=timezone.now())
        elif status_filter == "in_progress":
            now = timezone.now()
            queryset = queryset.filter(start_datetime__lte=now, end_datetime__gt=now)
        elif status_filter == "completed":
            queryset = queryset.filter(end_datetime__lte=timezone.now())

        return queryset


class UserSearchView(APIView):
    """Search users by username, first name, last name, or email.

    Used for autocomplete in the Add Member form.

    Query parameters:
    - q: Search query (minimum 2 characters)
    - project_id: Optional project ID to exclude owner and existing members
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.GET.get("q", "").strip()
        project_id = request.GET.get("project_id")

        # Require at least 2 characters
        if len(query) < 2:
            return Response([])

        # Search users by username, first name, last name, or email
        users = User.objects.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query),
            is_active=True,
        )

        # Optionally exclude users already in the project
        if project_id:
            try:
                from coldfront.core.project.models import Project

                project = Project.objects.get(pk=project_id)
                exclude_ids = [project.pi_id]  # Exclude owner
                # Exclude users who already have any role
                exclude_ids.extend(
                    ProjectMemberRole.objects.filter(project=project)
                    .values_list("user_id", flat=True)
                    .distinct()
                )
                users = users.exclude(id__in=exclude_ids)
            except Project.DoesNotExist:
                pass

        # Limit results
        users = users[:10]

        return Response(
            [
                {
                    "username": u.username,
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                    "email": u.email,
                    "display": f"{u.username} - {u.first_name} {u.last_name}",
                }
                for u in users
            ]
        )


class InvoiceListView(APIView):
    """List months with billable activity and their invoice status.

    GET /api/invoice/

    Requires authentication and can_manage_billing permission.

    Returns a list of months with:
    - year, month, month_name
    - status (Draft, Finalized, or Not Started)
    - override_count

    Months are included if they have approved reservations, active AMF
    entries, or active QoS subscriptions.
    """

    permission_classes = [IsAuthenticated, HasManageBillingPermission]

    def get(self, request):
        billable_months = set()

        # Months with approved reservations
        approved_reservations = Reservation.objects.filter(
            status=Reservation.StatusChoices.APPROVED,
        ).select_related("project")

        for res in approved_reservations:
            current = res.start_date
            while current <= res.end_date:
                billable_months.add((current.year, current.month))
                if current.month == 12:
                    current = date(current.year + 1, 1, 1)
                else:
                    current = date(current.year, current.month + 1, 1)

        # Months with active AMF entries (basic or advanced with a billing project)
        active_amf = UserMaintenanceStatus.objects.filter(
            status__in=[
                UserMaintenanceStatus.StatusChoices.BASIC,
                UserMaintenanceStatus.StatusChoices.ADVANCED,
            ],
            billing_project__isnull=False,
        )
        for amf in active_amf:
            # The AMF is billable from its created month up to the earlier
            # of end_date or today
            created_date = amf.created.date() if amf.created else None
            if created_date:
                current = date(created_date.year, created_date.month, 1)
                today = date.today()
                cap_date = min(amf.end_date, today) if amf.end_date else today
                end_month = date(cap_date.year, cap_date.month, 1)
                while current <= end_month:
                    billable_months.add((current.year, current.month))
                    if current.month == 12:
                        current = date(current.year + 1, 1, 1)
                    else:
                        current = date(current.year, current.month + 1, 1)

        # Months with active QoS subscriptions
        active_qos = UserQoSSubscription.objects.filter(
            is_active=True,
            billing_project__isnull=False,
        )
        for qos in active_qos:
            current = date(qos.start_date.year, qos.start_date.month, 1)
            end_limit = qos.end_date or date.today()
            end_month = date(end_limit.year, end_limit.month, 1)
            while current <= end_month:
                billable_months.add((current.year, current.month))
                if current.month == 12:
                    current = date(current.year + 1, 1, 1)
                else:
                    current = date(current.year, current.month + 1, 1)

        # Build list of months with invoice status
        invoice_months = []
        for year, month in sorted(billable_months, reverse=True):
            invoice_period = InvoicePeriod.objects.filter(year=year, month=month).first()
            override_count = 0
            if invoice_period:
                override_count = invoice_period.overrides.count()

            invoice_months.append({
                "year": year,
                "month": month,
                "month_name": calendar.month_name[month],
                "status": invoice_period.get_status_display() if invoice_period else "Not Started",
                "is_finalized": invoice_period.is_finalized if invoice_period else False,
                "override_count": override_count,
            })

        # Log the API access
        log_activity(
            action="api.invoice_list",
            category=ActivityLog.ActionCategory.API,
            description="API: Invoice list retrieved",
            request=request,
            extra_data={"result_count": len(invoice_months)},
        )

        return Response(invoice_months)


class InvoiceReportView(APIView):
    """Get full invoice report for a specific month.

    GET /api/invoice/YYYY/MM/

    Requires authentication and can_manage_billing permission.

    Returns a combined report including reservations, account maintenance
    fees (AMF), and QoS subscriptions, grouped by project.
    """

    permission_classes = [IsAuthenticated, HasManageBillingPermission]

    # Map maintenance status to SKU code
    STATUS_TO_SKU = {
        "basic": "MAINT_STANDARD",
        "advanced": "MAINT_ADVANCED",
    }

    def get(self, request, year, month):
        # Validate month
        if not 1 <= month <= 12:
            return Response(
                {"error": "Month must be between 1 and 12"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get or create invoice period
        invoice_period, _ = InvoicePeriod.objects.get_or_create(
            year=year,
            month=month,
            defaults={"status": InvoicePeriod.StatusChoices.DRAFT},
        )

        # Build all three line-item types
        reservation_lines = self._build_reservation_lines(year, month, invoice_period)
        amf_lines = self._build_amf_lines(year, month)
        qos_lines = self._build_qos_lines(year, month)

        # Merge into project-grouped response
        export_data = self._build_combined_response(
            request, year, month, invoice_period,
            reservation_lines, amf_lines, qos_lines,
        )

        # Log the API access
        log_activity(
            action="api.invoice_report",
            category=ActivityLog.ActionCategory.API,
            description=f"API: Invoice {calendar.month_name[month]} {year} retrieved",
            request=request,
            extra_data={
                "year": year,
                "month": month,
                "total_reservations": len(reservation_lines),
                "total_amf_entries": len(amf_lines),
                "total_qos_entries": len(qos_lines),
            },
        )

        return Response(export_data)

    # =====================================================================
    # Reservation line-item builder (existing logic, extracted)
    # =====================================================================

    def _build_reservation_lines(self, year, month, invoice_period):
        """Build reservation billing line items for the given month."""
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        all_reservations = Reservation.objects.filter(
            status=Reservation.StatusChoices.APPROVED,
        ).select_related("project", "project__pi", "node_instance")

        reservations = [
            res for res in all_reservations
            if res.start_date <= month_end and res.end_date >= month_start
        ]

        overrides = {
            o.reservation_id: o
            for o in invoice_period.overrides.select_related("created_by")
        }

        lines = []
        for res in reservations:
            override = overrides.get(res.pk)
            sku = get_sku_for_reservation(res)

            if override and override.override_type == InvoiceLineOverride.OverrideTypeChoices.EXCLUDE:
                lines.append({
                    "reservation": res,
                    "excluded": True,
                    "override": override,
                    "hours_in_month": 0,
                    "cost_breakdown": [],
                    "sku": sku,
                })
                continue

            hours_data = self._calculate_hours_for_month(res, year, month)

            if override and override.override_type == InvoiceLineOverride.OverrideTypeChoices.HOURS:
                hours_in_month = override.override_value.get("hours", hours_data["hours"])
            else:
                hours_in_month = hours_data["hours"]

            if override and override.override_type == InvoiceLineOverride.OverrideTypeChoices.COST_SPLIT:
                cost_breakdown = override.override_value.get("cost_breakdown", [])
            else:
                cost_breakdown = self._calculate_cost_breakdown(res, year, month, hours_in_month)

            lines.append({
                "reservation": res,
                "excluded": False,
                "override": override,
                "hours_in_month": hours_in_month,
                "cost_breakdown": cost_breakdown,
                "sku": sku,
            })

        return lines

    # =====================================================================
    # AMF line-item builder
    # =====================================================================

    def _build_amf_lines(self, year, month):
        """Build AMF billing line items for the given month.

        Returns a list of dicts, each representing one user's maintenance
        fee for the month.  Includes the ``activated_at`` timestamp from
        ``UserMaintenanceStatus.created`` so callers can compute partial-
        month fractions.
        """
        month_start = date(year, month, 1)
        if month == 12:
            next_month_start = date(year + 1, 1, 1)
        else:
            next_month_start = date(year, month + 1, 1)
        month_end = next_month_start - timedelta(days=1)
        days_in_month = (next_month_start - month_start).days

        # Find users with active AMF whose created date is before the end of month
        active_amf = UserMaintenanceStatus.objects.filter(
            status__in=[
                UserMaintenanceStatus.StatusChoices.BASIC,
                UserMaintenanceStatus.StatusChoices.ADVANCED,
            ],
            billing_project__isnull=False,
        ).select_related("user", "billing_project", "billing_project__pi")

        # Pre-fetch SKUs for maintenance
        sku_cache = {
            sku.sku_code: sku
            for sku in RentalSKU.objects.filter(
                sku_code__in=list(self.STATUS_TO_SKU.values())
            )
        }

        lines = []
        for amf in active_amf:
            activated_date = amf.created.date() if amf.created else month_start

            # Skip if activated after this month ends
            if activated_date > month_end:
                continue

            # Skip if subscription ended before this month starts
            if amf.end_date < month_start:
                continue

            # Effective end: the earlier of next_month_start or end_date + 1 day
            # (end_date is inclusive, so billing includes that day)
            effective_end = min(next_month_start, amf.end_date + timedelta(days=1))

            # Calculate billable days (partial month if activated mid-month
            # or if subscription ends mid-month)
            effective_start = max(activated_date, month_start)
            billable_days = (effective_end - effective_start).days
            fraction = round(billable_days / days_in_month, 6)

            # Look up SKU and rate
            sku_code = self.STATUS_TO_SKU.get(amf.status)
            sku = sku_cache.get(sku_code)
            rate_obj = sku.get_rate_for_date(month_start) if sku else None

            # Cost object breakdown from billing project's snapshot
            cost_breakdown = self._get_project_cost_breakdown(amf.billing_project, month_start)

            lines.append({
                "project": amf.billing_project,
                "username": amf.user.username,
                "status": amf.status,
                "sku_code": sku_code,
                "sku_name": sku.name if sku else None,
                "rate": str(rate_obj.rate) if rate_obj else None,
                "billing_unit": "MONTHLY",
                "activated_at": amf.created.isoformat() if amf.created else None,
                "end_date": amf.end_date.isoformat(),
                "days_in_month": days_in_month,
                "billable_days": billable_days,
                "fraction": fraction,
                "cost_breakdown": cost_breakdown,
            })

        return lines

    # =====================================================================
    # QoS line-item builder
    # =====================================================================

    def _build_qos_lines(self, year, month):
        """Build QoS subscription billing line items for the given month.

        Returns a list of dicts, each representing one user's QoS
        subscription for the month.  Includes ``start_date`` so callers
        can compute partial-month fractions.
        """
        month_start = date(year, month, 1)
        if month == 12:
            next_month_start = date(year + 1, 1, 1)
        else:
            next_month_start = date(year, month + 1, 1)
        month_end = next_month_start - timedelta(days=1)
        days_in_month = (next_month_start - month_start).days

        # Find QoS subscriptions active during this month
        active_qos = UserQoSSubscription.objects.filter(
            is_active=True,
            billing_project__isnull=False,
            start_date__lte=month_end,
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=month_start)
        ).select_related("user", "sku", "billing_project", "billing_project__pi")

        lines = []
        for qos in active_qos:
            # Calculate billable days (partial month for start/end mid-month)
            effective_start = max(qos.start_date, month_start)
            effective_end = min(qos.end_date, month_end) if qos.end_date else month_end
            billable_days = (effective_end - effective_start).days + 1
            fraction = round(billable_days / days_in_month, 6)

            # Look up rate
            rate_obj = qos.sku.get_rate_for_date(month_start) if qos.sku else None

            # Cost object breakdown from billing project's snapshot
            cost_breakdown = self._get_project_cost_breakdown(qos.billing_project, month_start)

            lines.append({
                "project": qos.billing_project,
                "username": qos.user.username,
                "sku_code": qos.sku.sku_code if qos.sku else None,
                "sku_name": qos.sku.name if qos.sku else None,
                "rate": str(rate_obj.rate) if rate_obj else None,
                "billing_unit": "MONTHLY",
                "start_date": qos.start_date.isoformat(),
                "end_date": qos.end_date.isoformat() if qos.end_date else None,
                "days_in_month": days_in_month,
                "billable_days": billable_days,
                "fraction": fraction,
                "cost_breakdown": cost_breakdown,
            })

        return lines

    # =====================================================================
    # Combined response builder
    # =====================================================================

    def _build_combined_response(self, request, year, month, invoice_period,
                                 reservation_lines, amf_lines, qos_lines):
        """Merge reservation, AMF, and QoS lines into a project-grouped response."""
        total_reservations = len(reservation_lines)
        excluded_count = sum(1 for l in reservation_lines if l["excluded"])

        # Seed projects dict from reservation lines
        projects = {}

        def _ensure_project(proj):
            if proj.pk not in projects:
                projects[proj.pk] = {
                    "project": proj,
                    "reservation_lines": [],
                    "amf_lines": [],
                    "qos_lines": [],
                    "total_hours": 0,
                    "cost_totals": {},
                }

        for line in reservation_lines:
            proj = line["reservation"].project
            _ensure_project(proj)
            projects[proj.pk]["reservation_lines"].append(line)
            if not line["excluded"]:
                projects[proj.pk]["total_hours"] += line["hours_in_month"]
                for co in line["cost_breakdown"]:
                    if co["cost_object"] not in projects[proj.pk]["cost_totals"]:
                        projects[proj.pk]["cost_totals"][co["cost_object"]] = 0
                    projects[proj.pk]["cost_totals"][co["cost_object"]] += co["hours"]

        for line in amf_lines:
            proj = line["project"]
            _ensure_project(proj)
            projects[proj.pk]["amf_lines"].append(line)

        for line in qos_lines:
            proj = line["project"]
            _ensure_project(proj)
            projects[proj.pk]["qos_lines"].append(line)

        # Build export data
        export_data = {
            "metadata": {
                "year": year,
                "month": month,
                "month_name": calendar.month_name[month],
                "generated_at": timezone.now().isoformat(),
                "generated_by": request.user.username,
                "invoice_status": invoice_period.get_status_display(),
                "total_reservations": total_reservations,
                "excluded_count": excluded_count,
                "total_amf_entries": len(amf_lines),
                "total_qos_entries": len(qos_lines),
            },
            "projects": [],
        }

        for proj_data in projects.values():
            project_export = {
                "project_id": proj_data["project"].pk,
                "project_title": proj_data["project"].title,
                "project_owner": proj_data["project"].pi.username,
                "total_hours": proj_data["total_hours"],
                "cost_totals": proj_data["cost_totals"],
                "reservations": [],
                "amf_entries": [],
                "qos_entries": [],
            }

            # Serialize reservation lines
            for line in proj_data["reservation_lines"]:
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

            # Serialize AMF lines (drop internal 'project' key)
            for line in proj_data["amf_lines"]:
                project_export["amf_entries"].append({
                    k: v for k, v in line.items() if k != "project"
                })

            # Serialize QoS lines (drop internal 'project' key)
            for line in proj_data["qos_lines"]:
                project_export["qos_entries"].append({
                    k: v for k, v in line.items() if k != "project"
                })

            export_data["projects"].append(project_export)

        return export_data

    # =====================================================================
    # Shared helpers
    # =====================================================================

    @staticmethod
    def _get_project_cost_breakdown(project, reference_date):
        """Get cost object percentage breakdown for a project.

        Uses the active CostAllocationSnapshot for the given date.
        Returns a list of ``{"cost_object": ..., "percentage": ...}`` dicts.
        """
        snapshot = CostAllocationSnapshot.get_active_snapshot_for_date(
            project, reference_date
        )
        if not snapshot:
            return [{"cost_object": "UNKNOWN", "percentage": 100.0}]

        return [
            {
                "cost_object": co_snap.cost_object,
                "percentage": float(co_snap.percentage),
            }
            for co_snap in snapshot.cost_objects.all()
        ]

    def _calculate_hours_for_month(self, reservation, year, month):
        """Calculate how many hours of a reservation fall within a specific month."""
        month_start = datetime.combine(date(year, month, 1), time(0, 0))
        if month == 12:
            month_end = datetime.combine(date(year + 1, 1, 1), time(0, 0))
        else:
            month_end = datetime.combine(date(year, month + 1, 1), time(0, 0))

        effective_start = max(reservation.start_datetime, month_start)
        effective_end = min(reservation.end_datetime, month_end)

        if effective_end <= effective_start:
            return {"hours": 0}

        delta = effective_end - effective_start
        hours = delta.total_seconds() / 3600

        return {"hours": round(hours, 2)}

    def _calculate_cost_breakdown(self, reservation, year, month, total_hours):
        """Calculate cost object breakdown using historical snapshots."""
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        cost_hours = {}

        current_date = max(reservation.start_date, month_start)
        end_date = min(reservation.end_date, month_end)

        while current_date <= end_date:
            day_hours = self._get_hours_for_day(reservation, current_date)

            if day_hours > 0:
                snapshot = CostAllocationSnapshot.get_active_snapshot_for_date(
                    reservation.project, current_date
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
                    if "UNKNOWN" not in cost_hours:
                        cost_hours["UNKNOWN"] = 0
                    cost_hours["UNKNOWN"] += day_hours

            current_date += timedelta(days=1)

        breakdown = [
            {"cost_object": co, "hours": round(hours, 2)}
            for co, hours in sorted(cost_hours.items())
        ]

        return breakdown

    def _get_hours_for_day(self, reservation, target_date):
        """Calculate hours for a specific day of a reservation."""
        day_start = datetime.combine(target_date, time(0, 0))
        day_end = datetime.combine(target_date + timedelta(days=1), time(0, 0))

        effective_start = max(reservation.start_datetime, day_start)
        effective_end = min(reservation.end_datetime, day_end)

        if effective_end <= effective_start:
            return 0

        delta = effective_end - effective_start
        return delta.total_seconds() / 3600


# =========================================================================
# Focused invoice sub-endpoints
# =========================================================================


class InvoiceReservationsView(InvoiceReportView):
    """Get reservation-only invoice report for a specific month.

    GET /api/invoice/reservations/YYYY/MM/
    """

    def get(self, request, year, month):
        if not 1 <= month <= 12:
            return Response(
                {"error": "Month must be between 1 and 12"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice_period, _ = InvoicePeriod.objects.get_or_create(
            year=year, month=month,
            defaults={"status": InvoicePeriod.StatusChoices.DRAFT},
        )

        reservation_lines = self._build_reservation_lines(year, month, invoice_period)
        export_data = self._build_combined_response(
            request, year, month, invoice_period,
            reservation_lines=reservation_lines,
            amf_lines=[],
            qos_lines=[],
        )

        log_activity(
            action="api.invoice_reservations",
            category=ActivityLog.ActionCategory.API,
            description=f"API: Invoice reservations {calendar.month_name[month]} {year}",
            request=request,
            extra_data={"year": year, "month": month},
        )

        return Response(export_data)


class InvoiceAMFView(InvoiceReportView):
    """Get AMF-only invoice report for a specific month.

    GET /api/invoice/amf/YYYY/MM/
    """

    def get(self, request, year, month):
        if not 1 <= month <= 12:
            return Response(
                {"error": "Month must be between 1 and 12"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice_period, _ = InvoicePeriod.objects.get_or_create(
            year=year, month=month,
            defaults={"status": InvoicePeriod.StatusChoices.DRAFT},
        )

        amf_lines = self._build_amf_lines(year, month)
        export_data = self._build_combined_response(
            request, year, month, invoice_period,
            reservation_lines=[],
            amf_lines=amf_lines,
            qos_lines=[],
        )

        log_activity(
            action="api.invoice_amf",
            category=ActivityLog.ActionCategory.API,
            description=f"API: Invoice AMF {calendar.month_name[month]} {year}",
            request=request,
            extra_data={"year": year, "month": month},
        )

        return Response(export_data)


class InvoiceQoSView(InvoiceReportView):
    """Get QoS-only invoice report for a specific month.

    GET /api/invoice/qos/YYYY/MM/
    """

    def get(self, request, year, month):
        if not 1 <= month <= 12:
            return Response(
                {"error": "Month must be between 1 and 12"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice_period, _ = InvoicePeriod.objects.get_or_create(
            year=year, month=month,
            defaults={"status": InvoicePeriod.StatusChoices.DRAFT},
        )

        qos_lines = self._build_qos_lines(year, month)
        export_data = self._build_combined_response(
            request, year, month, invoice_period,
            reservation_lines=[],
            amf_lines=[],
            qos_lines=qos_lines,
        )

        log_activity(
            action="api.invoice_qos",
            category=ActivityLog.ActionCategory.API,
            description=f"API: Invoice QoS {calendar.month_name[month]} {year}",
            request=request,
            extra_data={"year": year, "month": month},
        )

        return Response(export_data)


class HasActivityLogPermission(permissions.BasePermission):
    """Permission check for viewing activity logs."""

    def has_permission(self, request, view):
        return can_view_activity_log(request.user)


class ActivityLogAPIView(APIView):
    """API endpoint for querying activity logs.

    GET /api/activity-log/

    Query parameters:
    - category: Filter by action category
    - user: Filter by username (exact match)
    - action: Filter by action (contains)
    - date_from: Filter by start date (YYYY-MM-DD)
    - date_to: Filter by end date (YYYY-MM-DD)
    - limit: Maximum number of results (default 100, max 1000)

    Requires authentication and Billing/Rental Manager permission.
    """

    permission_classes = [IsAuthenticated, HasActivityLogPermission]

    def get(self, request):
        logs = ActivityLog.objects.select_related("user").all()

        # Apply filters from query params
        category = request.GET.get("category")
        user = request.GET.get("user")
        action = request.GET.get("action")
        date_from = request.GET.get("date_from")
        date_to = request.GET.get("date_to")
        limit = min(int(request.GET.get("limit", 100)), 1000)

        if category:
            logs = logs.filter(category=category)
        if user:
            logs = logs.filter(user__username=user)
        if action:
            logs = logs.filter(action__icontains=action)
        if date_from:
            logs = logs.filter(timestamp__date__gte=date_from)
        if date_to:
            logs = logs.filter(timestamp__date__lte=date_to)

        logs = logs[:limit]

        # Log the API access
        log_activity(
            action="api.activity_log",
            category=ActivityLog.ActionCategory.API,
            description="API: Activity log retrieved",
            request=request,
            extra_data={
                "filters": {
                    "category": category,
                    "user": user,
                    "action": action,
                    "date_from": date_from,
                    "date_to": date_to,
                    "limit": limit,
                },
                "result_count": len(logs),
            },
        )

        return Response([{
            "timestamp": log.timestamp.isoformat(),
            "user": log.user.username if log.user else None,
            "action": log.action,
            "category": log.category,
            "description": log.description,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "target_repr": log.target_repr,
            "ip_address": log.ip_address,
            "extra_data": log.extra_data,
        } for log in logs])


class MaintenanceSubscriptionListView(APIView):
    """List maintenance fee subscriptions.

    GET /api/maintenance-subscriptions/

    Managers see all, regular users see only their own.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        is_manager = user.has_perm(
            "coldfront_orcd_direct_charge.can_manage_rentals"
        ) or user.has_perm("coldfront_orcd_direct_charge.can_manage_billing")

        if is_manager:
            queryset = UserMaintenanceStatus.objects.select_related(
                "user", "billing_project"
            ).all()
        else:
            queryset = UserMaintenanceStatus.objects.select_related(
                "user", "billing_project"
            ).filter(user=user)

        # Prefetch maintenance SKUs to avoid N+1 queries in serializer
        maintenance_skus = {
            sku.sku_code: sku
            for sku in RentalSKU.objects.filter(
                sku_code__in=["MAINT_STANDARD", "MAINT_ADVANCED"]
            )
        }

        serializer = MaintenanceSubscriptionSerializer(
            queryset, many=True, context={"maintenance_skus": maintenance_skus}
        )
        return Response(serializer.data)


class QoSSubscriptionListView(APIView):
    """List QoS subscriptions.

    GET /api/qos-subscriptions/

    Managers see all, regular users see only their own.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        is_manager = user.has_perm(
            "coldfront_orcd_direct_charge.can_manage_rentals"
        ) or user.has_perm("coldfront_orcd_direct_charge.can_manage_billing")

        if is_manager:
            queryset = UserQoSSubscription.objects.select_related(
                "user", "sku", "billing_project"
            ).all()
        else:
            queryset = UserQoSSubscription.objects.select_related(
                "user", "sku", "billing_project"
            ).filter(user=user)

        serializer = QoSSubscriptionSerializer(queryset, many=True)
        return Response(serializer.data)


class SKUListView(APIView):
    """List available SKUs with current rates.

    GET /api/skus/
    GET /api/skus/?type=MAINTENANCE
    GET /api/skus/?type=QOS
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = RentalSKU.objects.filter(is_active=True)

        sku_type = request.GET.get("type")
        if sku_type:
            queryset = queryset.filter(sku_type=sku_type)

        serializer = SKUSerializer(queryset, many=True)
        return Response(serializer.data)


class NodeAvailabilityView(APIView):
    """Return booked periods for a GPU node to support availability checks.

    GET /api/node-availability/?node_id=<id>

    Requires authentication (any logged-in user).

    Returns all APPROVED and PENDING reservation time intervals for the
    specified node within the bookable window (today+7 days through
    today+3 months).  Does NOT expose project names, user names, or
    reservation IDs -- only time intervals and status.

    Response shape:
    {
      "node_id": 1,
      "node_name": "node2433",
      "booked_periods": [
        {
          "start_datetime": "2026-02-13T16:00:00",
          "end_datetime": "2026-02-14T04:00:00",
          "status": "approved",
          "is_mine": false
        }
      ]
    }
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        node_id = request.GET.get("node_id")
        if not node_id:
            return Response(
                {"error": "node_id query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            node = GpuNodeInstance.objects.get(pk=node_id, is_rentable=True)
        except GpuNodeInstance.DoesNotExist:
            return Response(
                {"error": "Node not found or not rentable"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Bookable window: today + 7 days through today + 3 months
        today = date.today()
        window_start = today + timedelta(days=7)
        max_month = today.month + 3
        max_year = today.year
        if max_month > 12:
            max_month = max_month - 12
            max_year += 1
        import calendar as cal_module
        window_end = date(
            max_year, max_month, cal_module.monthrange(max_year, max_month)[1]
        )

        # Convert to datetimes for overlap comparison
        window_start_dt = datetime.combine(window_start, time(0, 0))
        window_end_dt = datetime.combine(window_end + timedelta(days=1), time(0, 0))

        # Get user's project IDs to determine "is_mine"
        from coldfront.core.project.models import Project

        user_project_ids = set(
            Project.objects.filter(
                projectuser__user=request.user,
                projectuser__status__name="Active",
            ).values_list("id", flat=True)
        )

        # Query APPROVED and PENDING reservations that overlap the bookable window
        reservations = Reservation.objects.filter(
            node_instance=node,
            status__in=[
                Reservation.StatusChoices.APPROVED,
                Reservation.StatusChoices.PENDING,
            ],
        ).select_related("project")

        booked_periods = []
        for res in reservations:
            # Check if reservation overlaps with the bookable window
            if res.start_datetime < window_end_dt and res.end_datetime > window_start_dt:
                booked_periods.append({
                    "start_datetime": res.start_datetime.isoformat(),
                    "end_datetime": res.end_datetime.isoformat(),
                    "status": res.status.lower(),
                    "is_mine": res.project_id in user_project_ids,
                })

        return Response({
            "node_id": node.pk,
            "node_name": node.associated_resource_address,
            "booked_periods": booked_periods,
        })

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

from coldfront_orcd_direct_charge.api.serializers import ReservationSerializer
from coldfront_orcd_direct_charge.models import (
    ActivityLog,
    CostAllocationSnapshot,
    InvoiceLineOverride,
    InvoicePeriod,
    ProjectCostAllocation,
    ProjectMemberRole,
    Reservation,
    can_view_activity_log,
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
    """List months with approved reservations and their invoice status.

    GET /api/invoice/

    Requires authentication and can_manage_billing permission.

    Returns a list of months with:
    - year, month, month_name
    - status (Draft, Finalized, or Not Started)
    - override_count
    """

    permission_classes = [IsAuthenticated, HasManageBillingPermission]

    def get(self, request):
        # Get all months with approved reservations
        approved_reservations = Reservation.objects.filter(
            status=Reservation.StatusChoices.APPROVED,
        ).select_related("project")

        # Find unique year/month combinations
        months_with_reservations = set()
        for res in approved_reservations:
            current = res.start_date
            while current <= res.end_date:
                months_with_reservations.add((current.year, current.month))
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

    Returns the same JSON structure as the web export endpoint.
    """

    permission_classes = [IsAuthenticated, HasManageBillingPermission]

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

        # Get all approved reservations that overlap with this month
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        all_reservations = Reservation.objects.filter(
            status=Reservation.StatusChoices.APPROVED,
        ).select_related("project", "project__pi", "node_instance")

        # Filter to reservations that overlap with this month
        reservations = []
        for res in all_reservations:
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
                cost_breakdown = self._calculate_cost_breakdown(res, year, month, hours_in_month)

            invoice_lines.append({
                "reservation": res,
                "excluded": False,
                "override": override,
                "hours_in_month": hours_in_month,
                "cost_breakdown": cost_breakdown,
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

        # Build export data
        total_reservations = len(invoice_lines)
        excluded_count = sum(1 for l in invoice_lines if l["excluded"])

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

        # Log the API access
        log_activity(
            action="api.invoice_report",
            category=ActivityLog.ActionCategory.API,
            description=f"API: Invoice {calendar.month_name[month]} {year} retrieved",
            request=request,
            extra_data={
                "year": year,
                "month": month,
                "total_reservations": total_reservations,
            },
        )

        return Response(export_data)

    def _calculate_hours_for_month(self, reservation, year, month):
        """Calculate how many hours of a reservation fall within a specific month."""
        month_start = datetime.combine(date(year, month, 1), time(0, 0))
        if month == 12:
            month_end = datetime.combine(date(year + 1, 1, 1), time(0, 0))
        else:
            month_end = datetime.combine(date(year, month + 1, 1), time(0, 0))

        # Clip reservation to month boundaries (all naive datetimes)
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

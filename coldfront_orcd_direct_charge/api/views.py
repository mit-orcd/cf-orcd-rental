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
    compute_effective_billing_end,
    get_sku_for_reservation,
    log_activity,
)
from coldfront_orcd_direct_charge.utils.invoice_builders import (
    build_amf_lines,
    build_combined_response,
    build_qos_lines,
    build_reservation_lines,
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
            # of effective_billing_end or today
            created_date = amf.created.date() if amf.created else None
            if created_date:
                eff_billing_end = compute_effective_billing_end(created_date, amf.end_date)
                current = date(created_date.year, created_date.month, 1)
                today = date.today()
                cap_date = min(eff_billing_end, today)
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

    All billing logic is in ``utils.invoice_builders`` so the web-portal
    views produce identical data.
    """

    permission_classes = [IsAuthenticated, HasManageBillingPermission]

    def get(self, request, year, month):
        if not 1 <= month <= 12:
            return Response(
                {"error": "Month must be between 1 and 12"},
                status=status.HTTP_400_BAD_REQUEST
            )

        invoice_period, _ = InvoicePeriod.objects.get_or_create(
            year=year,
            month=month,
            defaults={"status": InvoicePeriod.StatusChoices.DRAFT},
        )

        reservation_lines = build_reservation_lines(year, month, invoice_period)
        amf_lines = build_amf_lines(year, month)
        qos_lines = build_qos_lines(year, month)

        export_data = build_combined_response(
            request, year, month, invoice_period,
            reservation_lines, amf_lines, qos_lines,
        )

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


# =========================================================================
# Focused invoice sub-endpoints
# =========================================================================


class InvoiceReservationsView(APIView):
    """Get reservation-only invoice report for a specific month.

    GET /api/invoice/reservations/YYYY/MM/
    """

    permission_classes = [IsAuthenticated, HasManageBillingPermission]

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

        reservation_lines = build_reservation_lines(year, month, invoice_period)
        export_data = build_combined_response(
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


class InvoiceAMFView(APIView):
    """Get AMF-only invoice report for a specific month.

    GET /api/invoice/amf/YYYY/MM/
    """

    permission_classes = [IsAuthenticated, HasManageBillingPermission]

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

        amf_lines = build_amf_lines(year, month)
        export_data = build_combined_response(
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


class InvoiceQoSView(APIView):
    """Get QoS-only invoice report for a specific month.

    GET /api/invoice/qos/YYYY/MM/
    """

    permission_classes = [IsAuthenticated, HasManageBillingPermission]

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

        qos_lines = build_qos_lines(year, month)
        export_data = build_combined_response(
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

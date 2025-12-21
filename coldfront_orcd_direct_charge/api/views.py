# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from django.contrib.auth.models import User
from django.db.models import Q
from django_filters import rest_framework as filters
from rest_framework import permissions, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from coldfront_orcd_direct_charge.api.serializers import ReservationSerializer
from coldfront_orcd_direct_charge.models import ProjectMemberRole, Reservation


class HasManageRentalsPermission(permissions.BasePermission):
    """Permission check for can_manage_rentals."""

    def has_permission(self, request, view):
        return request.user.has_perm("coldfront_orcd_direct_charge.can_manage_rentals")


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

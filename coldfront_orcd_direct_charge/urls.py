# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from django.urls import include, path

from coldfront_orcd_direct_charge import views

app_name = "coldfront_orcd_direct_charge"

urlpatterns = [
    path("", views.NodeInstanceListView.as_view(), name="node-instance-list"),
    path("gpu/<int:pk>/", views.GpuNodeInstanceDetailView.as_view(), name="gpu-node-detail"),
    path("cpu/<int:pk>/", views.CpuNodeInstanceDetailView.as_view(), name="cpu-node-detail"),
    # Renting views
    path("renting/", views.RentingCalendarView.as_view(), name="renting-calendar"),
    path("renting/request/", views.ReservationRequestView.as_view(), name="reservation-request"),
    path("renting/manage/", views.RentalManagerView.as_view(), name="rental-manager"),
    path("renting/manage/<int:pk>/approve/", views.ReservationApproveView.as_view(), name="reservation-approve"),
    path("renting/manage/<int:pk>/decline/", views.ReservationDeclineView.as_view(), name="reservation-decline"),
    path("renting/manage/<int:pk>/metadata/", views.ReservationMetadataView.as_view(), name="reservation-metadata"),
    # User profile
    path("user/update-maintenance-status/", views.update_maintenance_status, name="update-maintenance-status"),
    # Project cost allocation
    path("project/<int:pk>/cost-allocation/", views.ProjectCostAllocationView.as_view(), name="project-cost-allocation"),
    # Project member management
    path("project/<int:pk>/members/", views.ProjectMembersView.as_view(), name="project-members"),
    path("project/<int:pk>/members/add/", views.AddMemberView.as_view(), name="add-member"),
    path("project/<int:pk>/members/<int:user_pk>/update/", views.UpdateMemberRoleView.as_view(), name="update-member-role"),
    path("project/<int:pk>/members/<int:user_pk>/remove/", views.RemoveMemberView.as_view(), name="remove-member"),
    # API
    path("api/", include("coldfront_orcd_direct_charge.api.urls")),
]



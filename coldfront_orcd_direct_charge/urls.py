# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from django.urls import include, path

from coldfront_orcd_direct_charge import views
from coldfront_orcd_direct_charge.views.auth import PasswordLoginView

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
    # Reservation detail
    path("reservation/<int:pk>/", views.ReservationDetailView.as_view(), name="reservation-detail"),
    # User profile
    path("user/login", PasswordLoginView.as_view(), name="password-login"),
    path("user/update-maintenance-status/", views.update_maintenance_status, name="update-maintenance-status"),
    # Project cost allocation (use orcd-project/ prefix to avoid conflict with ColdFront core URLs)
    path("orcd-project/<int:pk>/cost-allocation/", views.ProjectCostAllocationView.as_view(), name="project-cost-allocation"),
    path("orcd-project/<int:pk>/reservations/", views.ProjectReservationsView.as_view(), name="project-reservations"),
    # Billing Manager views
    path("billing/pending/", views.PendingCostAllocationsView.as_view(), name="pending-cost-allocations"),
    path("billing/allocation/<int:pk>/review/", views.CostAllocationApprovalView.as_view(), name="cost-allocation-review"),
    # Invoice Preparation views
    path("billing/invoice/", views.InvoicePreparationView.as_view(), name="invoice-preparation"),
    path("billing/invoice/<int:year>/<int:month>/", views.InvoiceDetailView.as_view(), name="invoice-detail"),
    path("billing/invoice/<int:year>/<int:month>/edit/", views.InvoiceEditView.as_view(), name="invoice-edit"),
    path("billing/invoice/<int:year>/<int:month>/export/", views.InvoiceExportView.as_view(), name="invoice-export"),
    path("billing/invoice/<int:year>/<int:month>/override/<int:override_id>/delete/", views.InvoiceDeleteOverrideView.as_view(), name="invoice-delete-override"),
    # Activity Log
    path("activity-log/", views.ActivityLogView.as_view(), name="activity-log"),
    # Project member management (use orcd-project/ prefix to avoid conflict with ColdFront core URLs)
    path("orcd-project/<int:pk>/members/", views.ProjectMembersView.as_view(), name="project-members"),
    path("orcd-project/<int:pk>/members/add/", views.AddMemberView.as_view(), name="add-member"),
    path("orcd-project/<int:pk>/members/<int:user_pk>/update/", views.UpdateMemberRoleView.as_view(), name="update-member-role"),
    path("orcd-project/<int:pk>/members/<int:user_pk>/remove/", views.RemoveMemberView.as_view(), name="remove-member"),
    # Project add users search (use orcd-project/ prefix to avoid conflict with ColdFront's add-users flow)
    path("orcd-project/<int:pk>/add-users-search/", views.ProjectAddUsersSearchView.as_view(), name="project-add-users-search"),
    path("orcd-project/<int:pk>/add-users-search-results/", views.ProjectAddUsersSearchResultsView.as_view(), name="project-add-users-search-results"),
    path("orcd-project/<int:pk>/add-users/", views.ProjectAddUsersView.as_view(), name="project-add-users"),
    # User's personal views
    path("my/reservations/", views.MyReservationsView.as_view(), name="my-reservations"),
    # Rate Management views (Rate Managers only)
    path("rates/", views.RateManagementView.as_view(), name="rate-management"),
    path("rates/sku/<int:pk>/", views.SKURateDetailView.as_view(), name="sku-rate-detail"),
    path("rates/sku/<int:pk>/add/", views.AddRateView.as_view(), name="add-rate"),
    path("rates/sku/<int:pk>/visibility/", views.ToggleSKUVisibilityView.as_view(), name="toggle-sku-visibility"),
    path("rates/sku/create/", views.CreateSKUView.as_view(), name="create-sku"),
    # Public Current Rates views (all logged-in users)
    path("rates/current/", views.CurrentRatesView.as_view(), name="current-rates"),
    path("rates/current/<int:pk>/", views.SKUPublicDetailView.as_view(), name="sku-public-detail"),
    # API
    path("api/", include("coldfront_orcd_direct_charge.api.urls")),
    # Maintenance Windows
    path("maintenance-windows/", views.MaintenanceWindowListView.as_view(), name="maintenance-window-list"),
    path("maintenance-windows/create/", views.MaintenanceWindowCreateView.as_view(), name="maintenance-window-create"),
    path("maintenance-windows/<int:pk>/edit/", views.MaintenanceWindowUpdateView.as_view(), name="maintenance-window-update"),
    path("maintenance-windows/<int:pk>/delete/", views.MaintenanceWindowDeleteView.as_view(), name="maintenance-window-delete"),
]



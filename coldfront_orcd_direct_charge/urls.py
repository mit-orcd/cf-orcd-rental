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
    # API
    path("api/", include("coldfront_orcd_direct_charge.api.urls")),
]



# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from django.urls import path
from rest_framework import routers

from coldfront_orcd_direct_charge.api import views

router = routers.DefaultRouter()
router.register(r"rentals", views.ReservationViewSet, basename="rentals")
router.register(r"cost-allocations", views.CostAllocationViewSet, basename="cost-allocations")

urlpatterns = router.urls + [
    path("user-search/", views.UserSearchView.as_view(), name="user-search"),
    # Invoice API endpoints
    path("invoice/", views.InvoiceListView.as_view(), name="invoice-list"),
    path("invoice/<int:year>/<int:month>/", views.InvoiceReportView.as_view(), name="invoice-report"),
    # Activity log API endpoint
    path("activity-log/", views.ActivityLogAPIView.as_view(), name="api-activity-log"),
    # Subscription API endpoints
    path("maintenance-subscriptions/", views.MaintenanceSubscriptionListView.as_view(),
         name="maintenance-subscriptions"),
    path("qos-subscriptions/", views.QoSSubscriptionListView.as_view(),
         name="qos-subscriptions"),
    path("skus/", views.SKUListView.as_view(), name="sku-list"),
]

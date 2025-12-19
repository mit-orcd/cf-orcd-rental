# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from rest_framework import routers

from coldfront_orcd_direct_charge.api import views

router = routers.DefaultRouter()
router.register(r"rentals", views.ReservationViewSet, basename="rentals")

urlpatterns = router.urls

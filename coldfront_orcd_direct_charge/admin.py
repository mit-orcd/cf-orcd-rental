# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from django.contrib import admin
from coldfront_orcd_direct_charge.models import GpuNodeInstance, CpuNodeInstance


@admin.register(GpuNodeInstance)
class GpuNodeInstanceAdmin(admin.ModelAdmin):
    list_display = ("name", "is_rentable", "status", "associated_resource_address", "modified")
    list_filter = ("is_rentable", "status", "name")
    search_fields = ("name", "associated_resource_address")
    ordering = ("name", "associated_resource_address")


@admin.register(CpuNodeInstance)
class CpuNodeInstanceAdmin(admin.ModelAdmin):
    list_display = ("name", "is_rentable", "status", "associated_resource_address", "modified")
    list_filter = ("is_rentable", "status", "name")
    search_fields = ("name", "associated_resource_address")
    ordering = ("name", "associated_resource_address")


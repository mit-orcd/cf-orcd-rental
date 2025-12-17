# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from django.contrib import admin
from coldfront_orcd_direct_charge.models import NodeType, GpuNodeInstance, CpuNodeInstance


@admin.register(NodeType)
class NodeTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "description", "is_active", "modified")
    list_filter = ("category", "is_active")
    search_fields = ("name", "description")
    ordering = ("category", "name")


@admin.register(GpuNodeInstance)
class GpuNodeInstanceAdmin(admin.ModelAdmin):
    list_display = ("node_type_name", "is_rentable", "status", "associated_resource_address", "modified")
    list_filter = ("is_rentable", "status", "node_type")
    search_fields = ("node_type__name", "associated_resource_address")
    ordering = ("node_type__name", "associated_resource_address")

    @admin.display(description="Node Type")
    def node_type_name(self, obj):
        return obj.node_type.name


@admin.register(CpuNodeInstance)
class CpuNodeInstanceAdmin(admin.ModelAdmin):
    list_display = ("node_type_name", "is_rentable", "status", "associated_resource_address", "modified")
    list_filter = ("is_rentable", "status", "node_type")
    search_fields = ("node_type__name", "associated_resource_address")
    ordering = ("node_type__name", "associated_resource_address")

    @admin.display(description="Node Type")
    def node_type_name(self, obj):
        return obj.node_type.name

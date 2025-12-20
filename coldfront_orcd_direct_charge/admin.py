# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from django.contrib import admin
from coldfront_orcd_direct_charge.models import (
    NodeType,
    GpuNodeInstance,
    CpuNodeInstance,
    ProjectMemberRole,
    Reservation,
    ReservationMetadataEntry,
)


@admin.register(NodeType)
class NodeTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "description", "is_active", "modified")
    list_filter = ("category", "is_active")
    search_fields = ("name", "description")
    ordering = ("category", "name")


@admin.register(ProjectMemberRole)
class ProjectMemberRoleAdmin(admin.ModelAdmin):
    list_display = ("user_username", "project_title", "role", "created", "modified")
    list_filter = ("role", "project")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "project__title",
    )
    ordering = ("project__title", "role", "user__username")
    raw_id_fields = ("user", "project")
    readonly_fields = ("created", "modified")

    @admin.display(description="Username")
    def user_username(self, obj):
        return obj.user.username

    @admin.display(description="Project")
    def project_title(self, obj):
        return obj.project.title


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


class ReservationMetadataEntryInline(admin.TabularInline):
    """Inline admin for metadata entries on Reservation."""
    model = ReservationMetadataEntry
    extra = 1
    readonly_fields = ("created",)
    fields = ("content", "created")


@admin.register(ReservationMetadataEntry)
class ReservationMetadataEntryAdmin(admin.ModelAdmin):
    """Admin for ReservationMetadataEntry model."""
    list_display = ("reservation", "content_preview", "created")
    list_filter = ("created",)
    search_fields = ("content", "reservation__node_instance__associated_resource_address")
    ordering = ("-created",)
    readonly_fields = ("created", "modified")

    @admin.display(description="Content")
    def content_preview(self, obj):
        if len(obj.content) > 50:
            return obj.content[:50] + "..."
        return obj.content


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "node_instance_address",
        "project",
        "requesting_user",
        "start_date",
        "num_blocks",
        "get_billable_hours",
        "get_end_datetime",
        "status",
        "metadata_count",
        "created",
    )
    list_filter = ("status", "node_instance__node_type", "start_date")
    search_fields = (
        "node_instance__associated_resource_address",
        "project__title",
        "requesting_user__username",
        "requesting_user__first_name",
        "requesting_user__last_name",
    )
    readonly_fields = ("get_billable_hours", "get_end_datetime", "get_start_datetime", "created", "modified")
    ordering = ("-created",)
    actions = ["approve_reservations", "decline_reservations"]
    inlines = [ReservationMetadataEntryInline]

    fieldsets = (
        (None, {
            "fields": ("node_instance", "project", "requesting_user", "status")
        }),
        ("Timing", {
            "fields": ("start_date", "num_blocks", "get_start_datetime", "get_end_datetime", "get_billable_hours")
        }),
        ("Notes", {
            "fields": ("manager_notes",)
        }),
        ("Timestamps", {
            "fields": ("created", "modified"),
            "classes": ("collapse",)
        }),
    )

    @admin.display(description="Node")
    def node_instance_address(self, obj):
        return obj.node_instance.associated_resource_address

    @admin.display(description="Metadata")
    def metadata_count(self, obj):
        count = obj.metadata_entries.count()
        return count if count > 0 else "-"

    @admin.display(description="Billable Hours")
    def get_billable_hours(self, obj):
        return obj.billable_hours

    @admin.display(description="End Time")
    def get_end_datetime(self, obj):
        return obj.end_datetime.strftime("%b %d, %Y %I:%M %p")

    @admin.display(description="Start Time")
    def get_start_datetime(self, obj):
        return obj.start_datetime.strftime("%b %d, %Y %I:%M %p")

    @admin.action(description="Approve selected reservations")
    def approve_reservations(self, request, queryset):
        count = queryset.filter(status=Reservation.StatusChoices.PENDING).update(
            status=Reservation.StatusChoices.APPROVED
        )
        self.message_user(request, f"{count} reservation(s) approved.")

    @admin.action(description="Decline selected reservations")
    def decline_reservations(self, request, queryset):
        count = queryset.filter(status=Reservation.StatusChoices.PENDING).update(
            status=Reservation.StatusChoices.DECLINED
        )
        self.message_user(request, f"{count} reservation(s) declined.")

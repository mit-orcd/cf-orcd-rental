# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from django.contrib import admin
from coldfront_orcd_direct_charge.models import (
    ActivityLog,
    NodeType,
    GpuNodeInstance,
    CpuNodeInstance,
    MaintenanceWindow,
    ProjectMemberRole,
    Reservation,
    ReservationMetadataEntry,
    RentalSKU,
    RentalRate,
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


class RentalRateInline(admin.TabularInline):
    """Inline admin for rates on RentalSKU."""
    model = RentalRate
    extra = 0
    readonly_fields = ("created", "set_by")
    fields = ("rate", "effective_date", "set_by", "notes", "created")
    ordering = ("-effective_date",)


@admin.register(RentalSKU)
class RentalSKUAdmin(admin.ModelAdmin):
    """Admin for RentalSKU model."""
    list_display = (
        "sku_code",
        "name",
        "sku_type",
        "billing_unit",
        "is_active",
        "is_public",
        "current_rate_display",
        "rate_count",
        "modified",
    )
    list_filter = ("sku_type", "billing_unit", "is_active", "is_public")
    search_fields = ("sku_code", "name", "description", "linked_model")
    ordering = ("sku_type", "name")
    readonly_fields = ("created", "modified")
    inlines = [RentalRateInline]

    fieldsets = (
        (None, {
            "fields": ("sku_code", "name", "description")
        }),
        ("Configuration", {
            "fields": ("sku_type", "billing_unit", "is_active", "is_public", "linked_model")
        }),
        ("Metadata", {
            "fields": ("metadata",),
            "classes": ("collapse",),
            "description": "Flexible attributes for filtering (GPU type, memory, etc.)"
        }),
        ("Timestamps", {
            "fields": ("created", "modified"),
            "classes": ("collapse",)
        }),
    )

    @admin.display(description="Current Rate")
    def current_rate_display(self, obj):
        rate = obj.current_rate
        if rate:
            unit = "hr" if obj.billing_unit == "HOURLY" else "mo"
            return f"${rate.rate}/{unit}"
        return "-"

    @admin.display(description="Rates")
    def rate_count(self, obj):
        return obj.rates.count()

    @admin.display(description="Public", boolean=True)
    def is_public_display(self, obj):
        return obj.is_public


@admin.register(RentalRate)
class RentalRateAdmin(admin.ModelAdmin):
    """Admin for RentalRate model."""
    list_display = (
        "sku",
        "rate",
        "effective_date",
        "set_by",
        "created",
    )
    list_filter = ("sku__sku_type", "effective_date", "sku")
    search_fields = ("sku__sku_code", "sku__name", "notes", "set_by__username")
    ordering = ("-effective_date",)
    readonly_fields = ("created", "modified")
    raw_id_fields = ("sku", "set_by")

    fieldsets = (
        (None, {
            "fields": ("sku", "rate", "effective_date")
        }),
        ("Details", {
            "fields": ("set_by", "notes")
        }),
        ("Timestamps", {
            "fields": ("created", "modified"),
            "classes": ("collapse",)
        }),
    )


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """Admin for viewing activity logs (read-only)."""

    list_display = (
        "timestamp",
        "user_display",
        "action",
        "category",
        "target_repr",
        "ip_address",
    )
    list_filter = ("category", "action", "timestamp")
    search_fields = ("user__username", "description", "target_repr", "action")
    readonly_fields = (
        "timestamp",
        "user",
        "action",
        "category",
        "description",
        "target_type",
        "target_id",
        "target_repr",
        "ip_address",
        "user_agent",
        "extra_data",
    )
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)

    fieldsets = (
        ("Action", {
            "fields": ("timestamp", "user", "action", "category", "description")
        }),
        ("Target", {
            "fields": ("target_type", "target_id", "target_repr")
        }),
        ("Request Context", {
            "fields": ("ip_address", "user_agent"),
            "classes": ("collapse",)
        }),
        ("Extra Data", {
            "fields": ("extra_data",),
            "classes": ("collapse",)
        }),
    )

    @admin.display(description="User")
    def user_display(self, obj):
        return obj.user.username if obj.user else "System"

    def has_add_permission(self, request):
        """Logs are created programmatically only."""
        return False

    def has_change_permission(self, request, obj=None):
        """Logs are immutable."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete logs."""
        return request.user.is_superuser


@admin.register(MaintenanceWindow)
class MaintenanceWindowAdmin(admin.ModelAdmin):
    """Admin interface for MaintenanceWindow model."""

    list_display = (
        "title",
        "start_datetime",
        "end_datetime",
        "duration_hours_display",
        "status_display",
        "created_by",
        "created",
    )
    list_filter = ("start_datetime", "created")
    search_fields = ("title", "description")
    readonly_fields = ("created", "modified", "duration_hours_display", "status_display")
    ordering = ("-start_datetime",)

    fieldsets = (
        (None, {
            "fields": ("title", "description")
        }),
        ("Schedule", {
            "fields": ("start_datetime", "end_datetime", "duration_hours_display")
        }),
        ("Metadata", {
            "fields": ("created_by", "created", "modified", "status_display"),
            "classes": ("collapse",)
        }),
    )

    @admin.display(description="Duration")
    def duration_hours_display(self, obj):
        """Display duration in hours."""
        return f"{obj.duration_hours:.1f} hours"

    @admin.display(description="Status")
    def status_display(self, obj):
        """Display current status."""
        if obj.is_upcoming:
            return "Upcoming"
        elif obj.is_in_progress:
            return "In Progress"
        else:
            return "Completed"

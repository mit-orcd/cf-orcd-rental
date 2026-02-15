# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from rest_framework import serializers

from coldfront_orcd_direct_charge.models import (
    MaintenanceWindow,
    ProjectCostAllocation,
    ProjectCostObject,
    RentalSKU,
    Reservation,
    ReservationMetadataEntry,
    UserMaintenanceStatus,
    UserQoSSubscription,
)


class ReservationMetadataEntrySerializer(serializers.ModelSerializer):
    """Serializer for individual metadata entries."""

    class Meta:
        model = ReservationMetadataEntry
        fields = (
            "id",
            "content",
            "created",
            "modified",
        )


class ReservationSerializer(serializers.ModelSerializer):
    """Serializer for Reservation model with computed fields."""

    node = serializers.CharField(
        source="node_instance.associated_resource_address",
        read_only=True,
    )
    node_type = serializers.CharField(
        source="node_instance.node_type.name",
        read_only=True,
    )
    project_id = serializers.IntegerField(source="project.id", read_only=True)
    project_title = serializers.SlugRelatedField(
        slug_field="title",
        read_only=True,
        source="project",
    )
    requesting_user = serializers.SlugRelatedField(
        slug_field="username",
        read_only=True,
    )
    start_datetime = serializers.DateTimeField(read_only=True)
    end_datetime = serializers.DateTimeField(read_only=True)
    billable_hours = serializers.IntegerField(read_only=True)
    rental_metadata_entries = ReservationMetadataEntrySerializer(
        source="metadata_entries", many=True, read_only=True
    )

    class Meta:
        model = Reservation
        fields = (
            "id",
            "node",
            "node_type",
            "project_id",
            "project_title",
            "requesting_user",
            "start_date",
            "start_datetime",
            "end_datetime",
            "num_blocks",
            "billable_hours",
            "status",
            "manager_notes",
            "rental_notes",
            "rental_metadata_entries",
            "created",
            "modified",
        )


class MaintenanceSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for UserMaintenanceStatus model (maintenance fee subscriptions).

    This serializer provides a schema compatible with QoSSubscriptionSerializer,
    deriving SKU-related fields from the maintenance status.
    """

    subscription_type = serializers.SerializerMethodField()
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    is_active = serializers.SerializerMethodField()
    sku_code = serializers.SerializerMethodField()
    sku_name = serializers.SerializerMethodField()
    start_date = serializers.SerializerMethodField()
    end_date = serializers.SerializerMethodField()
    effective_billing_end = serializers.SerializerMethodField()
    billing_project_id = serializers.IntegerField(
        source="billing_project.id", allow_null=True, read_only=True
    )
    billing_project_title = serializers.CharField(
        source="billing_project.title", allow_null=True, read_only=True
    )
    current_rate = serializers.SerializerMethodField()

    # Map maintenance status to corresponding SKU codes
    STATUS_TO_SKU = {
        "basic": "MAINT_STANDARD",
        "advanced": "MAINT_ADVANCED",
    }

    class Meta:
        model = UserMaintenanceStatus
        fields = (
            "id",
            "subscription_type",
            "user_id",
            "username",
            "user_email",
            "status",
            "is_active",
            "sku_code",
            "sku_name",
            "start_date",
            "end_date",
            "effective_billing_end",
            "billing_project_id",
            "billing_project_title",
            "current_rate",
            "created",
            "modified",
        )

    def _get_maintenance_sku(self, status):
        """Map maintenance status to the corresponding MAINTENANCE SKU.

        Uses cached SKUs from context if available to avoid N+1 queries.
        Falls back to database query if context is not provided.
        """
        sku_code = self.STATUS_TO_SKU.get(status)
        if not sku_code:
            return None

        # Use cached SKUs from context if available
        maintenance_skus = self.context.get("maintenance_skus", {})
        if maintenance_skus:
            return maintenance_skus.get(sku_code)

        # Fallback to database query
        return RentalSKU.objects.filter(sku_code=sku_code).first()

    def get_subscription_type(self, obj):
        """Return the subscription type identifier."""
        return "maintenance"

    def get_is_active(self, obj):
        """Return whether the maintenance subscription is currently billable.

        Uses the ``is_billing_active`` model property which checks status,
        billing project, and effective billing end date.
        """
        return obj.is_billing_active

    def get_sku_code(self, obj):
        """Return the SKU code for the maintenance status."""
        return self.STATUS_TO_SKU.get(obj.status)

    def get_sku_name(self, obj):
        """Return the SKU name for the maintenance status."""
        sku = self._get_maintenance_sku(obj.status)
        return sku.name if sku else None

    def get_start_date(self, obj):
        """Return the start date (approximated from created timestamp)."""
        return obj.created.date().isoformat() if obj.created else None

    def get_end_date(self, obj):
        """Return the nominal end date of the maintenance subscription."""
        return obj.end_date.isoformat() if obj.end_date else None

    def get_effective_billing_end(self, obj):
        """Return the effective billing end date (rounded to whole subscription month)."""
        ebe = obj.effective_billing_end
        return ebe.isoformat() if ebe else None

    def get_current_rate(self, obj):
        """Return the current rate for the maintenance SKU."""
        from coldfront_orcd_direct_charge.templatetags.rate_filters import format_rate_value

        sku = self._get_maintenance_sku(obj.status)
        if sku:
            rate = sku.current_rate
            return format_rate_value(rate.rate) if rate else None
        return None


class QoSSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for UserQoSSubscription model."""

    subscription_type = serializers.SerializerMethodField()
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    sku_code = serializers.CharField(source="sku.sku_code", read_only=True)
    sku_name = serializers.CharField(source="sku.name", read_only=True)
    billing_project_id = serializers.IntegerField(
        source="billing_project.id", allow_null=True, read_only=True
    )
    billing_project_title = serializers.CharField(
        source="billing_project.title", allow_null=True, read_only=True
    )
    current_rate = serializers.SerializerMethodField()

    class Meta:
        model = UserQoSSubscription
        fields = (
            "id",
            "subscription_type",
            "user_id",
            "username",
            "user_email",
            "sku_code",
            "sku_name",
            "is_active",
            "start_date",
            "end_date",
            "billing_project_id",
            "billing_project_title",
            "current_rate",
            "created",
            "modified",
        )

    def get_subscription_type(self, obj):
        """Return the subscription type identifier."""
        return "qos"

    def get_current_rate(self, obj):
        """Return the current rate for the subscription's SKU."""
        from coldfront_orcd_direct_charge.templatetags.rate_filters import format_rate_value

        rate = obj.sku.current_rate
        return format_rate_value(rate.rate) if rate else None


class SKUSerializer(serializers.ModelSerializer):
    """Serializer for RentalSKU model with current rate."""

    current_rate = serializers.SerializerMethodField()

    class Meta:
        model = RentalSKU
        fields = (
            "id",
            "sku_code",
            "name",
            "description",
            "sku_type",
            "billing_unit",
            "is_active",
            "current_rate",
            "metadata",
        )

    def get_current_rate(self, obj):
        """Return the current rate for the SKU."""
        from coldfront_orcd_direct_charge.templatetags.rate_filters import format_rate_value

        rate = obj.current_rate
        return format_rate_value(rate.rate) if rate else None


class ProjectCostObjectSerializer(serializers.ModelSerializer):
    """Serializer for individual cost objects within a cost allocation."""

    class Meta:
        model = ProjectCostObject
        fields = (
            "id",
            "cost_object",
            "percentage",
        )


class ProjectCostAllocationSerializer(serializers.ModelSerializer):
    """Serializer for ProjectCostAllocation model with nested cost objects."""

    project_id = serializers.IntegerField(source="project.id", read_only=True)
    project_title = serializers.CharField(source="project.title", read_only=True)
    reviewed_by = serializers.SlugRelatedField(
        slug_field="username",
        read_only=True,
    )
    cost_objects = ProjectCostObjectSerializer(many=True, read_only=True)
    total_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = ProjectCostAllocation
        fields = (
            "id",
            "project_id",
            "project_title",
            "notes",
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_notes",
            "cost_objects",
            "total_percentage",
            "created",
            "modified",
        )


class MaintenanceWindowSerializer(serializers.ModelSerializer):
    """Serializer for MaintenanceWindow model."""

    created_by_username = serializers.CharField(
        source="created_by.username",
        read_only=True,
        allow_null=True,
    )
    duration_hours = serializers.FloatField(read_only=True)
    is_upcoming = serializers.BooleanField(read_only=True)
    is_in_progress = serializers.BooleanField(read_only=True)
    is_completed = serializers.BooleanField(read_only=True)

    class Meta:
        model = MaintenanceWindow
        fields = (
            "id",
            "title",
            "description",
            "start_datetime",
            "end_datetime",
            "duration_hours",
            "is_upcoming",
            "is_in_progress",
            "is_completed",
            "created_by_username",
            "created",
            "modified",
        )
        read_only_fields = ("created", "modified")

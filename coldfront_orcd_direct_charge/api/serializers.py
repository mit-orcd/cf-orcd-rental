# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from rest_framework import serializers

from coldfront_orcd_direct_charge.models import (
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
    """Serializer for UserMaintenanceStatus model (maintenance fee subscriptions)."""

    username = serializers.CharField(source="user.username", read_only=True)
    billing_project_id = serializers.IntegerField(
        source="billing_project.id", allow_null=True, read_only=True
    )
    billing_project_title = serializers.CharField(
        source="billing_project.title", allow_null=True, read_only=True
    )

    class Meta:
        model = UserMaintenanceStatus
        fields = (
            "id",
            "username",
            "status",
            "billing_project_id",
            "billing_project_title",
            "created",
            "modified",
        )


class QoSSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for UserQoSSubscription model."""

    username = serializers.CharField(source="user.username", read_only=True)
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
            "username",
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

    def get_current_rate(self, obj):
        """Return the current rate for the subscription's SKU."""
        rate = obj.sku.current_rate
        return str(rate.rate) if rate else None


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
        rate = obj.current_rate
        return str(rate.rate) if rate else None

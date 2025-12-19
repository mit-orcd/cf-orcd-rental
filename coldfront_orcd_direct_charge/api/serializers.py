# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from rest_framework import serializers

from coldfront_orcd_direct_charge.models import Reservation, ReservationMetadataEntry


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

# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Exporters for reservation-related models.

Models exported:
    - Reservation: GPU node reservation requests
    - ReservationMetadataEntry: Metadata notes for reservations
"""

from typing import Any, Dict

from ..base import BaseExporter
from ..registry import ExporterRegistry
from ..utils import serialize_datetime, serialize_date
from ...models import Reservation, ReservationMetadataEntry


@ExporterRegistry.register
class ReservationExporter(BaseExporter):
    """Exporter for Reservation model.
    
    Reservations reference GpuNodeInstance, Project, and User.
    Uses composite key of node address + start_date for identification.
    """
    
    model_name = "reservations"
    dependencies = ["gpu_node_instances"]
    
    def get_queryset(self):
        """Return all reservations with related objects."""
        return Reservation.objects.select_related(
            "node_instance",
            "project",
            "requesting_user",
            "processed_by",
        ).order_by("-created")
    
    def serialize_record(self, instance: Reservation) -> Dict[str, Any]:
        """Serialize Reservation to dict.
        
        Uses pk as identifier since there's no natural key defined.
        References related objects by their natural keys or usernames.
        """
        return {
            "natural_key": (instance.pk,),
            "fields": {
                "node_instance": instance.node_instance.natural_key(),
                "project_title": instance.project.title if instance.project else None,
                "requesting_user_username": (
                    instance.requesting_user.username 
                    if instance.requesting_user else None
                ),
                "start_date": serialize_date(instance.start_date),
                "num_blocks": instance.num_blocks,
                "status": instance.status,
                "manager_notes": instance.manager_notes,
                "processed_by_username": (
                    instance.processed_by.username 
                    if instance.processed_by else None
                ),
                "rental_notes": instance.rental_notes,
                "rental_management_metadata": instance.rental_management_metadata,
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }


@ExporterRegistry.register
class ReservationMetadataEntryExporter(BaseExporter):
    """Exporter for ReservationMetadataEntry model.
    
    Metadata entries belong to reservations and must be exported after.
    """
    
    model_name = "reservation_metadata_entries"
    dependencies = ["reservations"]
    
    def get_queryset(self):
        """Return all metadata entries with related reservation."""
        return ReservationMetadataEntry.objects.select_related(
            "reservation"
        ).order_by("reservation_id", "created")
    
    def serialize_record(self, instance: ReservationMetadataEntry) -> Dict[str, Any]:
        """Serialize ReservationMetadataEntry to dict.
        
        References reservation by its pk since no natural key.
        """
        return {
            "natural_key": (instance.pk,),
            "fields": {
                "reservation_pk": instance.reservation.pk,
                "content": instance.content,
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }

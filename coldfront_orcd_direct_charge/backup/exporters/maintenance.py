# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Exporters for maintenance-related models.

Models exported:
    - MaintenanceWindow: Scheduled maintenance periods
"""

from typing import Any, Dict

from ..base import BaseExporter
from ..registry import ExporterRegistry
from ..utils import serialize_datetime
from ...models import MaintenanceWindow


@ExporterRegistry.register
class MaintenanceWindowExporter(BaseExporter):
    """Exporter for MaintenanceWindow model.
    
    MaintenanceWindow defines scheduled maintenance periods during which
    rentals are not billed. Uses a composite natural key of title and
    start_datetime for uniqueness.
    """
    
    model_name = "maintenance_windows"
    dependencies = []
    
    def get_queryset(self):
        """Return all maintenance windows ordered by start datetime."""
        return MaintenanceWindow.objects.select_related(
            "created_by"
        ).order_by("-start_datetime")
    
    def serialize_record(self, instance: MaintenanceWindow) -> Dict[str, Any]:
        """Serialize MaintenanceWindow to dict.
        
        Uses a tuple of (title, start_datetime ISO string) as natural key
        since the combination is typically unique.
        """
        return {
            "natural_key": (
                instance.title,
                serialize_datetime(instance.start_datetime),
            ),
            "fields": {
                "title": instance.title,
                "description": instance.description,
                "start_datetime": serialize_datetime(instance.start_datetime),
                "end_datetime": serialize_datetime(instance.end_datetime),
                "created_by_username": (
                    instance.created_by.username if instance.created_by else None
                ),
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }

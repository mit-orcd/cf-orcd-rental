# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Importers for maintenance-related models.

Models imported:
    - MaintenanceWindow: Scheduled maintenance periods
"""

from typing import Any, Dict, Optional
import logging

from ..base import BaseImporter
from ..registry import ImporterRegistry
from ..utils import deserialize_datetime, get_user_by_username
from ...models import MaintenanceWindow

logger = logging.getLogger(__name__)


@ImporterRegistry.register
class MaintenanceWindowImporter(BaseImporter):
    """Importer for MaintenanceWindow model.
    
    Uses a composite natural key of (title, start_datetime) for matching.
    The created_by field is resolved by username if provided.
    """
    
    model_name = "maintenance_windows"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[MaintenanceWindow]:
        """Find existing MaintenanceWindow by title and start_datetime.
        
        The natural key is a tuple of (title, start_datetime ISO string).
        """
        if natural_key is None:
            return None
        
        if isinstance(natural_key, (list, tuple)) and len(natural_key) >= 2:
            title = natural_key[0]
            start_datetime_str = natural_key[1]
            start_datetime = deserialize_datetime(start_datetime_str)
            
            if title and start_datetime:
                try:
                    return MaintenanceWindow.objects.get(
                        title=title,
                        start_datetime=start_datetime,
                    )
                except MaintenanceWindow.DoesNotExist:
                    return None
        
        return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> MaintenanceWindow:
        """Create unsaved MaintenanceWindow from data."""
        fields = data.get("fields", {})
        
        # Resolve created_by foreign key by username
        created_by = None
        created_by_username = fields.get("created_by_username")
        if created_by_username:
            created_by = get_user_by_username(created_by_username)
        
        return MaintenanceWindow(
            title=fields["title"],
            description=fields.get("description", ""),
            start_datetime=deserialize_datetime(fields["start_datetime"]),
            end_datetime=deserialize_datetime(fields["end_datetime"]),
            created_by=created_by,
        )
    
    def create_record(self, data: Dict[str, Any]) -> MaintenanceWindow:
        """Create and save new MaintenanceWindow."""
        instance = self.deserialize_record(data)
        instance.save()
        logger.debug(f"Created MaintenanceWindow: {instance.title}")
        return instance
    
    def update_record(
        self, existing: MaintenanceWindow, data: Dict[str, Any]
    ) -> MaintenanceWindow:
        """Update existing MaintenanceWindow."""
        fields = data.get("fields", {})
        
        existing.title = fields.get("title", existing.title)
        existing.description = fields.get("description", existing.description)
        
        start_datetime = deserialize_datetime(fields.get("start_datetime"))
        if start_datetime:
            existing.start_datetime = start_datetime
        
        end_datetime = deserialize_datetime(fields.get("end_datetime"))
        if end_datetime:
            existing.end_datetime = end_datetime
        
        # Update created_by if username is provided
        created_by_username = fields.get("created_by_username")
        if created_by_username:
            created_by = get_user_by_username(created_by_username)
            if created_by:
                existing.created_by = created_by
        
        existing.save()
        
        logger.debug(f"Updated MaintenanceWindow: {existing.title}")
        return existing

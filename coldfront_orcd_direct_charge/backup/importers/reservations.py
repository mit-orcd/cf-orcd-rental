# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Importers for reservation-related models.

Models imported:
    - Reservation: GPU node reservation requests
    - ReservationMetadataEntry: Metadata notes for reservations

Note: Reservations reference ColdFront core models (Project, User) which
must exist in the target database. The importer will skip records if
referenced users or projects are not found.
"""

from typing import Any, Dict, Optional
import logging

from django.contrib.auth.models import User

from ..base import BaseImporter
from ..registry import ImporterRegistry
from ..utils import deserialize_date
from ...models import Reservation, ReservationMetadataEntry, GpuNodeInstance

logger = logging.getLogger(__name__)


def get_project_by_title(title: str):
    """Get ColdFront project by title.
    
    Args:
        title: Project title to look up
        
    Returns:
        Project instance or None
    """
    if not title:
        return None
    
    try:
        from coldfront.core.project.models import Project
        return Project.objects.get(title=title)
    except Exception:
        return None


def get_user_by_username(username: str) -> Optional[User]:
    """Get user by username.
    
    Args:
        username: Username to look up
        
    Returns:
        User instance or None
    """
    if not username:
        return None
    
    try:
        return User.objects.get(username=username)
    except User.DoesNotExist:
        return None


@ImporterRegistry.register
class ReservationImporter(BaseImporter):
    """Importer for Reservation model.
    
    Reservations are imported by pk since they don't have a natural key.
    References to Project and User are resolved by title/username.
    
    Note: This importer may skip records if referenced projects or users
    don't exist in the target database.
    """
    
    model_name = "reservations"
    dependencies = ["gpu_node_instances"]
    
    # Track pk mapping from export to import
    _pk_mapping: Dict[int, int] = {}
    
    def get_existing(self, natural_key) -> Optional[Reservation]:
        """Find existing Reservation by pk.
        
        Note: Since reservations use pk as key, we can't reliably
        find existing records. Returns None to always create new.
        """
        return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Reservation:
        """Create unsaved Reservation from data."""
        fields = data.get("fields", {})
        
        # Resolve node_instance
        node_key = fields.get("node_instance")
        node_instance = None
        if node_key:
            address = node_key[0] if isinstance(node_key, (list, tuple)) else node_key
            try:
                node_instance = GpuNodeInstance.objects.get_by_natural_key(address)
            except GpuNodeInstance.DoesNotExist:
                raise ValueError(f"GpuNodeInstance not found: {address}")
        
        if not node_instance:
            raise ValueError("node_instance is required")
        
        # Resolve project
        project = get_project_by_title(fields.get("project_title"))
        if not project:
            raise ValueError(f"Project not found: {fields.get('project_title')}")
        
        # Resolve users
        requesting_user = get_user_by_username(fields.get("requesting_user_username"))
        if not requesting_user:
            raise ValueError(f"User not found: {fields.get('requesting_user_username')}")
        
        processed_by = get_user_by_username(fields.get("processed_by_username"))
        
        return Reservation(
            node_instance=node_instance,
            project=project,
            requesting_user=requesting_user,
            start_date=deserialize_date(fields.get("start_date")),
            num_blocks=fields.get("num_blocks", 1),
            status=fields.get("status", Reservation.StatusChoices.PENDING),
            manager_notes=fields.get("manager_notes", ""),
            processed_by=processed_by,
            rental_notes=fields.get("rental_notes", ""),
            rental_management_metadata=fields.get("rental_management_metadata", ""),
        )
    
    def create_record(self, data: Dict[str, Any]) -> Reservation:
        """Create and save new Reservation."""
        original_pk = data.get("natural_key", (None,))[0]
        
        instance = self.deserialize_record(data)
        instance.save()
        
        # Store pk mapping for metadata entries
        if original_pk:
            self._pk_mapping[original_pk] = instance.pk
        
        logger.debug(f"Created Reservation: {instance.pk}")
        return instance
    
    def update_record(self, existing: Reservation, data: Dict[str, Any]) -> Reservation:
        """Update existing Reservation."""
        fields = data.get("fields", {})
        
        existing.status = fields.get("status", existing.status)
        existing.manager_notes = fields.get("manager_notes", existing.manager_notes)
        existing.rental_notes = fields.get("rental_notes", existing.rental_notes)
        existing.rental_management_metadata = fields.get(
            "rental_management_metadata", existing.rental_management_metadata
        )
        
        processed_by = get_user_by_username(fields.get("processed_by_username"))
        if processed_by:
            existing.processed_by = processed_by
        
        existing.save()
        
        logger.debug(f"Updated Reservation: {existing.pk}")
        return existing
    
    @classmethod
    def get_new_pk(cls, original_pk: int) -> Optional[int]:
        """Get new pk for an original pk after import.
        
        Args:
            original_pk: Original pk from export
            
        Returns:
            New pk in current database or None
        """
        return cls._pk_mapping.get(original_pk)


@ImporterRegistry.register
class ReservationMetadataEntryImporter(BaseImporter):
    """Importer for ReservationMetadataEntry model.
    
    Metadata entries reference reservations by pk.
    Requires the ReservationImporter pk mapping to be available.
    """
    
    model_name = "reservation_metadata_entries"
    dependencies = ["reservations"]
    
    def get_existing(self, natural_key) -> Optional[ReservationMetadataEntry]:
        """Find existing entry by pk."""
        return None  # Always create new
    
    def deserialize_record(self, data: Dict[str, Any]) -> ReservationMetadataEntry:
        """Create unsaved ReservationMetadataEntry from data."""
        fields = data.get("fields", {})
        
        # Resolve reservation using pk mapping
        original_reservation_pk = fields.get("reservation_pk")
        new_pk = ReservationImporter.get_new_pk(original_reservation_pk)
        
        if not new_pk:
            # Try to find by original pk as fallback
            try:
                reservation = Reservation.objects.get(pk=original_reservation_pk)
            except Reservation.DoesNotExist:
                raise ValueError(f"Reservation not found: {original_reservation_pk}")
        else:
            reservation = Reservation.objects.get(pk=new_pk)
        
        return ReservationMetadataEntry(
            reservation=reservation,
            content=fields.get("content", ""),
        )
    
    def create_record(self, data: Dict[str, Any]) -> ReservationMetadataEntry:
        """Create and save new ReservationMetadataEntry."""
        instance = self.deserialize_record(data)
        instance.save()
        logger.debug(f"Created ReservationMetadataEntry: {instance.pk}")
        return instance
    
    def update_record(
        self, existing: ReservationMetadataEntry, data: Dict[str, Any]
    ) -> ReservationMetadataEntry:
        """Update existing ReservationMetadataEntry."""
        fields = data.get("fields", {})
        existing.content = fields.get("content", existing.content)
        existing.save()
        logger.debug(f"Updated ReservationMetadataEntry: {existing.pk}")
        return existing

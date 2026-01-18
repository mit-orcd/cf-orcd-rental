# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Importers for billing-related models.

Models imported:
    - ProjectCostAllocation: Cost allocation settings for projects
    - ProjectCostObject: Individual cost objects within allocations
    - CostAllocationSnapshot: Historical snapshots of approved allocations
    - CostObjectSnapshot: Cost objects within snapshots
    - InvoicePeriod: Monthly invoice tracking
    - InvoiceLineOverride: Manual invoice adjustments
"""

from decimal import Decimal
from typing import Any, Dict, Optional
import logging

from django.contrib.auth.models import User

from ..base import BaseImporter
from ..registry import ImporterRegistry
from ..utils import deserialize_datetime, deserialize_decimal
from ...models import (
    ProjectCostAllocation,
    ProjectCostObject,
    CostAllocationSnapshot,
    CostObjectSnapshot,
    InvoicePeriod,
    InvoiceLineOverride,
    Reservation,
)

logger = logging.getLogger(__name__)


def get_project_by_title(title: str):
    """Get ColdFront project by title."""
    if not title:
        return None
    try:
        from coldfront.core.project.models import Project
        return Project.objects.get(title=title)
    except Exception:
        return None


def get_user_by_username(username: str) -> Optional[User]:
    """Get user by username."""
    if not username:
        return None
    try:
        return User.objects.get(username=username)
    except User.DoesNotExist:
        return None


@ImporterRegistry.register
class ProjectCostAllocationImporter(BaseImporter):
    """Importer for ProjectCostAllocation model."""
    
    model_name = "project_cost_allocations"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[ProjectCostAllocation]:
        """Find existing allocation by project title."""
        if not natural_key:
            return None
        
        title = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
        project = get_project_by_title(title)
        
        if not project:
            return None
        
        try:
            return ProjectCostAllocation.objects.get(project=project)
        except ProjectCostAllocation.DoesNotExist:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> ProjectCostAllocation:
        """Create unsaved ProjectCostAllocation from data."""
        fields = data.get("fields", {})
        
        project = get_project_by_title(fields.get("project_title"))
        if not project:
            raise ValueError(f"Project not found: {fields.get('project_title')}")
        
        reviewed_by = get_user_by_username(fields.get("reviewed_by_username"))
        
        return ProjectCostAllocation(
            project=project,
            notes=fields.get("notes", ""),
            status=fields.get("status", ProjectCostAllocation.StatusChoices.PENDING),
            reviewed_by=reviewed_by,
            reviewed_at=deserialize_datetime(fields.get("reviewed_at")),
            review_notes=fields.get("review_notes", ""),
        )
    
    def create_record(self, data: Dict[str, Any]) -> ProjectCostAllocation:
        """Create and save new ProjectCostAllocation."""
        instance = self.deserialize_record(data)
        instance.save()
        logger.debug(f"Created ProjectCostAllocation for: {instance.project.title}")
        return instance
    
    def update_record(
        self, existing: ProjectCostAllocation, data: Dict[str, Any]
    ) -> ProjectCostAllocation:
        """Update existing ProjectCostAllocation."""
        fields = data.get("fields", {})
        
        existing.notes = fields.get("notes", existing.notes)
        existing.status = fields.get("status", existing.status)
        existing.review_notes = fields.get("review_notes", existing.review_notes)
        
        reviewed_by = get_user_by_username(fields.get("reviewed_by_username"))
        if reviewed_by:
            existing.reviewed_by = reviewed_by
        
        reviewed_at = deserialize_datetime(fields.get("reviewed_at"))
        if reviewed_at:
            existing.reviewed_at = reviewed_at
        
        existing.save()
        logger.debug(f"Updated ProjectCostAllocation for: {existing.project.title}")
        return existing


@ImporterRegistry.register
class ProjectCostObjectImporter(BaseImporter):
    """Importer for ProjectCostObject model."""
    
    model_name = "project_cost_objects"
    dependencies = ["project_cost_allocations"]
    
    def get_existing(self, natural_key) -> Optional[ProjectCostObject]:
        """Cost objects don't have natural keys, always create new."""
        return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> ProjectCostObject:
        """Create unsaved ProjectCostObject from data."""
        fields = data.get("fields", {})
        
        project_title = fields.get("allocation_project_title")
        project = get_project_by_title(project_title)
        
        if not project:
            raise ValueError(f"Project not found: {project_title}")
        
        try:
            allocation = ProjectCostAllocation.objects.get(project=project)
        except ProjectCostAllocation.DoesNotExist:
            raise ValueError(f"CostAllocation not found for project: {project_title}")
        
        percentage = deserialize_decimal(fields.get("percentage"))
        if percentage is None:
            percentage = Decimal("0")
        
        return ProjectCostObject(
            allocation=allocation,
            cost_object=fields.get("cost_object", ""),
            percentage=percentage,
        )
    
    def create_record(self, data: Dict[str, Any]) -> ProjectCostObject:
        """Create and save new ProjectCostObject."""
        instance = self.deserialize_record(data)
        instance.save()
        logger.debug(f"Created ProjectCostObject: {instance.cost_object}")
        return instance
    
    def update_record(
        self, existing: ProjectCostObject, data: Dict[str, Any]
    ) -> ProjectCostObject:
        """Update existing ProjectCostObject."""
        fields = data.get("fields", {})
        
        existing.cost_object = fields.get("cost_object", existing.cost_object)
        
        percentage = deserialize_decimal(fields.get("percentage"))
        if percentage is not None:
            existing.percentage = percentage
        
        existing.save()
        logger.debug(f"Updated ProjectCostObject: {existing.cost_object}")
        return existing


@ImporterRegistry.register
class CostAllocationSnapshotImporter(BaseImporter):
    """Importer for CostAllocationSnapshot model."""
    
    model_name = "cost_allocation_snapshots"
    dependencies = ["project_cost_allocations"]
    
    # Track pk mapping
    _pk_mapping: Dict[int, int] = {}
    
    def get_existing(self, natural_key) -> Optional[CostAllocationSnapshot]:
        """Snapshots don't have natural keys, always create new."""
        return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> CostAllocationSnapshot:
        """Create unsaved CostAllocationSnapshot from data."""
        fields = data.get("fields", {})
        
        project_title = fields.get("allocation_project_title")
        project = get_project_by_title(project_title)
        
        if not project:
            raise ValueError(f"Project not found: {project_title}")
        
        try:
            allocation = ProjectCostAllocation.objects.get(project=project)
        except ProjectCostAllocation.DoesNotExist:
            raise ValueError(f"CostAllocation not found for project: {project_title}")
        
        approved_by = get_user_by_username(fields.get("approved_by_username"))
        
        return CostAllocationSnapshot(
            allocation=allocation,
            approved_at=deserialize_datetime(fields.get("approved_at")),
            approved_by=approved_by,
            superseded_at=deserialize_datetime(fields.get("superseded_at")),
        )
    
    def create_record(self, data: Dict[str, Any]) -> CostAllocationSnapshot:
        """Create and save new CostAllocationSnapshot."""
        original_pk = data.get("natural_key", (None,))[0]
        
        instance = self.deserialize_record(data)
        instance.save()
        
        if original_pk:
            self._pk_mapping[original_pk] = instance.pk
        
        logger.debug(f"Created CostAllocationSnapshot: {instance.pk}")
        return instance
    
    def update_record(
        self, existing: CostAllocationSnapshot, data: Dict[str, Any]
    ) -> CostAllocationSnapshot:
        """Update existing CostAllocationSnapshot."""
        fields = data.get("fields", {})
        
        superseded_at = deserialize_datetime(fields.get("superseded_at"))
        if superseded_at:
            existing.superseded_at = superseded_at
        
        existing.save()
        logger.debug(f"Updated CostAllocationSnapshot: {existing.pk}")
        return existing
    
    @classmethod
    def get_new_pk(cls, original_pk: int) -> Optional[int]:
        """Get new pk for an original pk after import."""
        return cls._pk_mapping.get(original_pk)


@ImporterRegistry.register
class CostObjectSnapshotImporter(BaseImporter):
    """Importer for CostObjectSnapshot model."""
    
    model_name = "cost_object_snapshots"
    dependencies = ["cost_allocation_snapshots"]
    
    def get_existing(self, natural_key) -> Optional[CostObjectSnapshot]:
        """Cost object snapshots don't have natural keys."""
        return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> CostObjectSnapshot:
        """Create unsaved CostObjectSnapshot from data."""
        fields = data.get("fields", {})
        
        original_snapshot_pk = fields.get("snapshot_pk")
        new_pk = CostAllocationSnapshotImporter.get_new_pk(original_snapshot_pk)
        
        if new_pk:
            snapshot = CostAllocationSnapshot.objects.get(pk=new_pk)
        else:
            try:
                snapshot = CostAllocationSnapshot.objects.get(pk=original_snapshot_pk)
            except CostAllocationSnapshot.DoesNotExist:
                raise ValueError(f"CostAllocationSnapshot not found: {original_snapshot_pk}")
        
        percentage = deserialize_decimal(fields.get("percentage"))
        if percentage is None:
            percentage = Decimal("0")
        
        return CostObjectSnapshot(
            snapshot=snapshot,
            cost_object=fields.get("cost_object", ""),
            percentage=percentage,
        )
    
    def create_record(self, data: Dict[str, Any]) -> CostObjectSnapshot:
        """Create and save new CostObjectSnapshot."""
        instance = self.deserialize_record(data)
        instance.save()
        logger.debug(f"Created CostObjectSnapshot: {instance.pk}")
        return instance
    
    def update_record(
        self, existing: CostObjectSnapshot, data: Dict[str, Any]
    ) -> CostObjectSnapshot:
        """Update existing CostObjectSnapshot."""
        fields = data.get("fields", {})
        
        existing.cost_object = fields.get("cost_object", existing.cost_object)
        
        percentage = deserialize_decimal(fields.get("percentage"))
        if percentage is not None:
            existing.percentage = percentage
        
        existing.save()
        logger.debug(f"Updated CostObjectSnapshot: {existing.pk}")
        return existing


@ImporterRegistry.register
class InvoicePeriodImporter(BaseImporter):
    """Importer for InvoicePeriod model."""
    
    model_name = "invoice_periods"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[InvoicePeriod]:
        """Find existing InvoicePeriod by year/month."""
        if not natural_key or len(natural_key) < 2:
            return None
        
        year, month = natural_key[0], natural_key[1]
        
        try:
            return InvoicePeriod.objects.get(year=year, month=month)
        except InvoicePeriod.DoesNotExist:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> InvoicePeriod:
        """Create unsaved InvoicePeriod from data."""
        fields = data.get("fields", {})
        
        finalized_by = get_user_by_username(fields.get("finalized_by_username"))
        
        return InvoicePeriod(
            year=fields.get("year"),
            month=fields.get("month"),
            status=fields.get("status", InvoicePeriod.StatusChoices.DRAFT),
            finalized_by=finalized_by,
            finalized_at=deserialize_datetime(fields.get("finalized_at")),
            notes=fields.get("notes", ""),
        )
    
    def create_record(self, data: Dict[str, Any]) -> InvoicePeriod:
        """Create and save new InvoicePeriod."""
        instance = self.deserialize_record(data)
        instance.save()
        logger.debug(f"Created InvoicePeriod: {instance.year}-{instance.month:02d}")
        return instance
    
    def update_record(
        self, existing: InvoicePeriod, data: Dict[str, Any]
    ) -> InvoicePeriod:
        """Update existing InvoicePeriod."""
        fields = data.get("fields", {})
        
        existing.status = fields.get("status", existing.status)
        existing.notes = fields.get("notes", existing.notes)
        
        finalized_by = get_user_by_username(fields.get("finalized_by_username"))
        if finalized_by:
            existing.finalized_by = finalized_by
        
        finalized_at = deserialize_datetime(fields.get("finalized_at"))
        if finalized_at:
            existing.finalized_at = finalized_at
        
        existing.save()
        logger.debug(f"Updated InvoicePeriod: {existing.year}-{existing.month:02d}")
        return existing


@ImporterRegistry.register
class InvoiceLineOverrideImporter(BaseImporter):
    """Importer for InvoiceLineOverride model."""
    
    model_name = "invoice_line_overrides"
    dependencies = ["invoice_periods", "reservations"]
    
    def get_existing(self, natural_key) -> Optional[InvoiceLineOverride]:
        """Overrides don't have natural keys."""
        return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> InvoiceLineOverride:
        """Create unsaved InvoiceLineOverride from data."""
        fields = data.get("fields", {})
        
        # Resolve invoice period
        year = fields.get("invoice_period_year")
        month = fields.get("invoice_period_month")
        
        try:
            invoice_period = InvoicePeriod.objects.get(year=year, month=month)
        except InvoicePeriod.DoesNotExist:
            raise ValueError(f"InvoicePeriod not found: {year}-{month:02d}")
        
        # Resolve reservation
        reservation_pk = fields.get("reservation_pk")
        try:
            reservation = Reservation.objects.get(pk=reservation_pk)
        except Reservation.DoesNotExist:
            raise ValueError(f"Reservation not found: {reservation_pk}")
        
        created_by = get_user_by_username(fields.get("created_by_username"))
        
        return InvoiceLineOverride(
            invoice_period=invoice_period,
            reservation=reservation,
            override_type=fields.get("override_type"),
            original_value=fields.get("original_value", {}),
            override_value=fields.get("override_value", {}),
            notes=fields.get("notes", ""),
            created_by=created_by,
        )
    
    def create_record(self, data: Dict[str, Any]) -> InvoiceLineOverride:
        """Create and save new InvoiceLineOverride."""
        instance = self.deserialize_record(data)
        instance.save()
        logger.debug(f"Created InvoiceLineOverride: {instance.pk}")
        return instance
    
    def update_record(
        self, existing: InvoiceLineOverride, data: Dict[str, Any]
    ) -> InvoiceLineOverride:
        """Update existing InvoiceLineOverride."""
        fields = data.get("fields", {})
        
        existing.override_type = fields.get("override_type", existing.override_type)
        existing.original_value = fields.get("original_value", existing.original_value)
        existing.override_value = fields.get("override_value", existing.override_value)
        existing.notes = fields.get("notes", existing.notes)
        
        existing.save()
        logger.debug(f"Updated InvoiceLineOverride: {existing.pk}")
        return existing

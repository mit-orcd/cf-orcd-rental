# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Exporters for billing-related models.

Models exported:
    - ProjectCostAllocation: Cost allocation settings for projects
    - ProjectCostObject: Individual cost objects within allocations
    - CostAllocationSnapshot: Historical snapshots of approved allocations
    - CostObjectSnapshot: Cost objects within snapshots
    - InvoicePeriod: Monthly invoice tracking
    - InvoiceLineOverride: Manual invoice adjustments
"""

from typing import Any, Dict

from ..base import BaseExporter
from ..registry import ExporterRegistry
from ..utils import serialize_datetime, serialize_decimal
from ...models import (
    ProjectCostAllocation,
    ProjectCostObject,
    CostAllocationSnapshot,
    CostObjectSnapshot,
    InvoicePeriod,
    InvoiceLineOverride,
)


@ExporterRegistry.register
class ProjectCostAllocationExporter(BaseExporter):
    """Exporter for ProjectCostAllocation model.
    
    Cost allocations are linked to projects by the project title.
    """
    
    model_name = "project_cost_allocations"
    dependencies = []
    
    def get_queryset(self):
        """Return all cost allocations with related project."""
        return ProjectCostAllocation.objects.select_related(
            "project",
            "reviewed_by",
        ).order_by("project__title")
    
    def serialize_record(self, instance: ProjectCostAllocation) -> Dict[str, Any]:
        """Serialize ProjectCostAllocation to dict."""
        return {
            "natural_key": (instance.project.title,),
            "fields": {
                "project_title": instance.project.title,
                "notes": instance.notes,
                "status": instance.status,
                "reviewed_by_username": (
                    instance.reviewed_by.username 
                    if instance.reviewed_by else None
                ),
                "reviewed_at": serialize_datetime(instance.reviewed_at),
                "review_notes": instance.review_notes,
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }


@ExporterRegistry.register
class ProjectCostObjectExporter(BaseExporter):
    """Exporter for ProjectCostObject model.
    
    Cost objects belong to cost allocations.
    """
    
    model_name = "project_cost_objects"
    dependencies = ["project_cost_allocations"]
    
    def get_queryset(self):
        """Return all cost objects with related allocation."""
        return ProjectCostObject.objects.select_related(
            "allocation__project"
        ).order_by("allocation__project__title", "-percentage")
    
    def serialize_record(self, instance: ProjectCostObject) -> Dict[str, Any]:
        """Serialize ProjectCostObject to dict."""
        return {
            "natural_key": (instance.pk,),
            "fields": {
                "allocation_project_title": instance.allocation.project.title,
                "cost_object": instance.cost_object,
                "percentage": serialize_decimal(instance.percentage),
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }


@ExporterRegistry.register
class CostAllocationSnapshotExporter(BaseExporter):
    """Exporter for CostAllocationSnapshot model.
    
    Snapshots capture cost allocation state at approval time.
    """
    
    model_name = "cost_allocation_snapshots"
    dependencies = ["project_cost_allocations"]
    
    def get_queryset(self):
        """Return all snapshots with related allocation."""
        return CostAllocationSnapshot.objects.select_related(
            "allocation__project",
            "approved_by",
        ).order_by("allocation__project__title", "-approved_at")
    
    def serialize_record(self, instance: CostAllocationSnapshot) -> Dict[str, Any]:
        """Serialize CostAllocationSnapshot to dict."""
        return {
            "natural_key": (instance.pk,),
            "fields": {
                "allocation_project_title": instance.allocation.project.title,
                "approved_at": serialize_datetime(instance.approved_at),
                "approved_by_username": (
                    instance.approved_by.username 
                    if instance.approved_by else None
                ),
                "superseded_at": serialize_datetime(instance.superseded_at),
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }


@ExporterRegistry.register
class CostObjectSnapshotExporter(BaseExporter):
    """Exporter for CostObjectSnapshot model.
    
    Cost object snapshots belong to allocation snapshots.
    """
    
    model_name = "cost_object_snapshots"
    dependencies = ["cost_allocation_snapshots"]
    
    def get_queryset(self):
        """Return all cost object snapshots."""
        return CostObjectSnapshot.objects.select_related(
            "snapshot__allocation__project"
        ).order_by("snapshot_id", "-percentage")
    
    def serialize_record(self, instance: CostObjectSnapshot) -> Dict[str, Any]:
        """Serialize CostObjectSnapshot to dict."""
        return {
            "natural_key": (instance.pk,),
            "fields": {
                "snapshot_pk": instance.snapshot.pk,
                "cost_object": instance.cost_object,
                "percentage": serialize_decimal(instance.percentage),
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }


@ExporterRegistry.register
class InvoicePeriodExporter(BaseExporter):
    """Exporter for InvoicePeriod model.
    
    Invoice periods track billing months.
    """
    
    model_name = "invoice_periods"
    dependencies = []
    
    def get_queryset(self):
        """Return all invoice periods."""
        return InvoicePeriod.objects.select_related(
            "finalized_by"
        ).order_by("-year", "-month")
    
    def serialize_record(self, instance: InvoicePeriod) -> Dict[str, Any]:
        """Serialize InvoicePeriod to dict.
        
        Uses year/month as natural key since they're unique together.
        """
        return {
            "natural_key": (instance.year, instance.month),
            "fields": {
                "year": instance.year,
                "month": instance.month,
                "status": instance.status,
                "finalized_by_username": (
                    instance.finalized_by.username 
                    if instance.finalized_by else None
                ),
                "finalized_at": serialize_datetime(instance.finalized_at),
                "notes": instance.notes,
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }


@ExporterRegistry.register
class InvoiceLineOverrideExporter(BaseExporter):
    """Exporter for InvoiceLineOverride model.
    
    Overrides belong to invoice periods and reservations.
    """
    
    model_name = "invoice_line_overrides"
    dependencies = ["invoice_periods", "reservations"]
    
    def get_queryset(self):
        """Return all invoice line overrides."""
        return InvoiceLineOverride.objects.select_related(
            "invoice_period",
            "reservation",
            "created_by",
        ).order_by("-created")
    
    def serialize_record(self, instance: InvoiceLineOverride) -> Dict[str, Any]:
        """Serialize InvoiceLineOverride to dict."""
        return {
            "natural_key": (instance.pk,),
            "fields": {
                "invoice_period_year": instance.invoice_period.year,
                "invoice_period_month": instance.invoice_period.month,
                "reservation_pk": instance.reservation.pk,
                "override_type": instance.override_type,
                "original_value": instance.original_value,
                "override_value": instance.override_value,
                "notes": instance.notes,
                "created_by_username": (
                    instance.created_by.username 
                    if instance.created_by else None
                ),
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }

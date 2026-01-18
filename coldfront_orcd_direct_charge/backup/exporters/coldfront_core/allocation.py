# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Exporters for ColdFront allocation models.

Models exported:
    - AllocationStatusChoice: Allocation status options
    - Allocation: Resource allocations
    - AllocationAttributeType: Allocation attribute types
    - AllocationAttribute: Allocation attributes
    - AllocationUser: Allocation user memberships
    - AllocationUserStatusChoice: Allocation user status options
"""

from typing import Any, Dict

from ...base import BaseExporter
from ...registry import CoreExporterRegistry
from ...utils import serialize_datetime, serialize_date


@CoreExporterRegistry.register
class AllocationStatusExporter(BaseExporter):
    """Exporter for AllocationStatusChoice model."""
    
    model_name = "allocation_statuses"
    dependencies = []
    
    def get_queryset(self):
        """Return all allocation statuses."""
        try:
            from coldfront.core.allocation.models import AllocationStatusChoice
            return AllocationStatusChoice.objects.all().order_by("name")
        except ImportError:
            from django.db.models import QuerySet
            return QuerySet().none()
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize AllocationStatusChoice to dict."""
        return {
            "natural_key": (instance.name,),
            "fields": {
                "name": instance.name,
            }
        }


@CoreExporterRegistry.register
class AllocationExporter(BaseExporter):
    """Exporter for Allocation model."""
    
    model_name = "allocations"
    dependencies = ["projects", "resources", "allocation_statuses"]
    
    def get_queryset(self):
        """Return all allocations with related data."""
        try:
            from coldfront.core.allocation.models import Allocation
            return Allocation.objects.select_related(
                "project",
                "status",
            ).prefetch_related(
                "resources",
            ).order_by("project__title", "pk")
        except ImportError:
            from django.db.models import QuerySet
            return QuerySet().none()
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize Allocation to dict."""
        return {
            "natural_key": (instance.pk,),
            "fields": {
                "pk": instance.pk,
                "project_title": instance.project.title,
                "resources": [r.name for r in instance.resources.all()],
                "status": instance.status.name if instance.status else None,
                "quantity": getattr(instance, "quantity", 1),
                "start_date": serialize_date(
                    getattr(instance, "start_date", None)
                ),
                "end_date": serialize_date(
                    getattr(instance, "end_date", None)
                ),
                "justification": getattr(instance, "justification", ""),
                "description": getattr(instance, "description", ""),
                "is_locked": getattr(instance, "is_locked", False),
                "is_changeable": getattr(instance, "is_changeable", True),
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }


@CoreExporterRegistry.register
class AllocationAttributeTypeExporter(BaseExporter):
    """Exporter for AllocationAttributeType model."""
    
    model_name = "allocation_attribute_types"
    dependencies = []
    
    def get_queryset(self):
        """Return all allocation attribute types."""
        try:
            from coldfront.core.allocation.models import AllocationAttributeType
            return AllocationAttributeType.objects.all().order_by("name")
        except ImportError:
            from django.db.models import QuerySet
            return QuerySet().none()
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize AllocationAttributeType to dict."""
        return {
            "natural_key": (instance.name,),
            "fields": {
                "name": instance.name,
                "attribute_type": getattr(instance, "attribute_type", "Text"),
                "has_usage": getattr(instance, "has_usage", False),
                "is_required": getattr(instance, "is_required", False),
                "is_unique": getattr(instance, "is_unique", False),
                "is_private": getattr(instance, "is_private", True),
                "is_changeable": getattr(instance, "is_changeable", False),
            }
        }


@CoreExporterRegistry.register
class AllocationAttributeExporter(BaseExporter):
    """Exporter for AllocationAttribute model."""
    
    model_name = "allocation_attributes"
    dependencies = ["allocations", "allocation_attribute_types"]
    
    def get_queryset(self):
        """Return all allocation attributes."""
        try:
            from coldfront.core.allocation.models import AllocationAttribute
            return AllocationAttribute.objects.select_related(
                "allocation",
                "allocation_attribute_type",
            ).order_by("allocation__pk", "allocation_attribute_type__name")
        except ImportError:
            from django.db.models import QuerySet
            return QuerySet().none()
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize AllocationAttribute to dict."""
        return {
            "natural_key": (
                instance.allocation.pk,
                instance.allocation_attribute_type.name,
            ),
            "fields": {
                "allocation_pk": instance.allocation.pk,
                "attribute_type": instance.allocation_attribute_type.name,
                "value": instance.value,
            }
        }


@CoreExporterRegistry.register
class AllocationUserStatusExporter(BaseExporter):
    """Exporter for AllocationUserStatusChoice model."""
    
    model_name = "allocation_user_statuses"
    dependencies = []
    
    def get_queryset(self):
        """Return all allocation user statuses."""
        try:
            from coldfront.core.allocation.models import AllocationUserStatusChoice
            return AllocationUserStatusChoice.objects.all().order_by("name")
        except ImportError:
            from django.db.models import QuerySet
            return QuerySet().none()
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize AllocationUserStatusChoice to dict."""
        return {
            "natural_key": (instance.name,),
            "fields": {
                "name": instance.name,
            }
        }


@CoreExporterRegistry.register
class AllocationUserExporter(BaseExporter):
    """Exporter for AllocationUser model."""
    
    model_name = "allocation_users"
    dependencies = ["allocations", "users", "allocation_user_statuses"]
    
    def get_queryset(self):
        """Return all allocation users."""
        try:
            from coldfront.core.allocation.models import AllocationUser
            return AllocationUser.objects.select_related(
                "allocation",
                "user",
                "status",
            ).order_by("allocation__pk", "user__username")
        except ImportError:
            from django.db.models import QuerySet
            return QuerySet().none()
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize AllocationUser to dict."""
        return {
            "natural_key": (instance.allocation.pk, instance.user.username),
            "fields": {
                "allocation_pk": instance.allocation.pk,
                "username": instance.user.username,
                "status": instance.status.name if instance.status else None,
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }

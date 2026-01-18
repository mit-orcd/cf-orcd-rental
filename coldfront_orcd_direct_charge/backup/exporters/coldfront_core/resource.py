# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Exporters for ColdFront resource models.

Models exported:
    - ResourceType: Resource type definitions
    - Resource: Resource definitions
    - ResourceAttributeType: Attribute type definitions
    - ResourceAttribute: Resource attributes
"""

from typing import Any, Dict

from ...base import BaseExporter
from ...registry import CoreExporterRegistry
from ...utils import serialize_datetime


@CoreExporterRegistry.register
class ResourceTypeExporter(BaseExporter):
    """Exporter for ResourceType model."""
    
    model_name = "resource_types"
    dependencies = []
    
    def get_queryset(self):
        """Return all resource types."""
        try:
            from coldfront.core.resource.models import ResourceType
            return ResourceType.objects.all().order_by("name")
        except ImportError:
            return []
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize ResourceType to dict."""
        return {
            "natural_key": (instance.name,),
            "fields": {
                "name": instance.name,
                "description": getattr(instance, "description", ""),
            }
        }


@CoreExporterRegistry.register
class ResourceExporter(BaseExporter):
    """Exporter for Resource model."""
    
    model_name = "resources"
    dependencies = ["resource_types"]
    
    def get_queryset(self):
        """Return all resources with related data."""
        try:
            from coldfront.core.resource.models import Resource
            return Resource.objects.select_related(
                "resource_type",
            ).prefetch_related(
                "allowed_groups",
                "allowed_users",
            ).order_by("name")
        except ImportError:
            return []
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize Resource to dict."""
        return {
            "natural_key": (instance.name,),
            "fields": {
                "name": instance.name,
                "description": getattr(instance, "description", ""),
                "resource_type": (
                    instance.resource_type.name 
                    if instance.resource_type else None
                ),
                "is_available": getattr(instance, "is_available", True),
                "is_public": getattr(instance, "is_public", True),
                "is_allocatable": getattr(instance, "is_allocatable", True),
                "requires_payment": getattr(instance, "requires_payment", False),
                "allowed_groups": [
                    g.name for g in instance.allowed_groups.all()
                ],
                "allowed_users": [
                    u.username for u in instance.allowed_users.all()
                ],
            }
        }


@CoreExporterRegistry.register
class ResourceAttributeTypeExporter(BaseExporter):
    """Exporter for ResourceAttributeType model."""
    
    model_name = "resource_attribute_types"
    dependencies = []
    
    def get_queryset(self):
        """Return all resource attribute types."""
        try:
            from coldfront.core.resource.models import ResourceAttributeType
            return ResourceAttributeType.objects.all().order_by("name")
        except ImportError:
            return []
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize ResourceAttributeType to dict."""
        return {
            "natural_key": (instance.name,),
            "fields": {
                "name": instance.name,
                "attribute_type": getattr(instance, "attribute_type", "Text"),
                "is_required": getattr(instance, "is_required", False),
                "is_unique_per_resource": getattr(
                    instance, "is_unique_per_resource", False
                ),
                "is_value_unique": getattr(instance, "is_value_unique", False),
            }
        }


@CoreExporterRegistry.register
class ResourceAttributeExporter(BaseExporter):
    """Exporter for ResourceAttribute model."""
    
    model_name = "resource_attributes"
    dependencies = ["resources", "resource_attribute_types"]
    
    def get_queryset(self):
        """Return all resource attributes."""
        try:
            from coldfront.core.resource.models import ResourceAttribute
            return ResourceAttribute.objects.select_related(
                "resource",
                "resource_attribute_type",
            ).order_by("resource__name", "resource_attribute_type__name")
        except ImportError:
            return []
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize ResourceAttribute to dict."""
        return {
            "natural_key": (
                instance.resource.name,
                instance.resource_attribute_type.name,
            ),
            "fields": {
                "resource_name": instance.resource.name,
                "attribute_type": instance.resource_attribute_type.name,
                "value": instance.value,
                "is_private": getattr(instance, "is_private", False),
            }
        }

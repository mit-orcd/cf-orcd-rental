# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Exporters for node-related models.

Models exported:
    - NodeType: Node type definitions (GPU, CPU categories)
    - GpuNodeInstance: GPU node instances
    - CpuNodeInstance: CPU node instances
"""

from typing import Any, Dict

from ..base import BaseExporter
from ..registry import ExporterRegistry
from ..utils import serialize_datetime
from ...models import NodeType, GpuNodeInstance, CpuNodeInstance


@ExporterRegistry.register
class NodeTypeExporter(BaseExporter):
    """Exporter for NodeType model.
    
    NodeType is the base model for node categorization and must be
    exported first before any node instances.
    """
    
    model_name = "node_types"
    dependencies = []
    
    def get_queryset(self):
        """Return all node types ordered by category and name."""
        return NodeType.objects.all().order_by("category", "name")
    
    def serialize_record(self, instance: NodeType) -> Dict[str, Any]:
        """Serialize NodeType to dict.
        
        Uses name as natural key since it's unique.
        """
        return {
            "natural_key": instance.natural_key(),
            "fields": {
                "name": instance.name,
                "category": instance.category,
                "description": instance.description,
                "is_active": instance.is_active,
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }


@ExporterRegistry.register
class GpuNodeInstanceExporter(BaseExporter):
    """Exporter for GpuNodeInstance model.
    
    GPU node instances reference NodeType and must be exported after it.
    """
    
    model_name = "gpu_node_instances"
    dependencies = ["node_types"]
    
    def get_queryset(self):
        """Return all GPU node instances with related node type."""
        return GpuNodeInstance.objects.select_related("node_type").order_by(
            "node_type__name", "associated_resource_address"
        )
    
    def serialize_record(self, instance: GpuNodeInstance) -> Dict[str, Any]:
        """Serialize GpuNodeInstance to dict.
        
        Uses associated_resource_address as natural key.
        References node_type by its natural key.
        """
        return {
            "natural_key": instance.natural_key(),
            "fields": {
                "node_type": instance.node_type.natural_key(),
                "is_rentable": instance.is_rentable,
                "status": instance.status,
                "associated_resource_address": instance.associated_resource_address,
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }


@ExporterRegistry.register
class CpuNodeInstanceExporter(BaseExporter):
    """Exporter for CpuNodeInstance model.
    
    CPU node instances reference NodeType and must be exported after it.
    """
    
    model_name = "cpu_node_instances"
    dependencies = ["node_types"]
    
    def get_queryset(self):
        """Return all CPU node instances with related node type."""
        return CpuNodeInstance.objects.select_related("node_type").order_by(
            "node_type__name", "associated_resource_address"
        )
    
    def serialize_record(self, instance: CpuNodeInstance) -> Dict[str, Any]:
        """Serialize CpuNodeInstance to dict.
        
        Uses associated_resource_address as natural key.
        References node_type by its natural key.
        """
        return {
            "natural_key": instance.natural_key(),
            "fields": {
                "node_type": instance.node_type.natural_key(),
                "is_rentable": instance.is_rentable,
                "status": instance.status,
                "associated_resource_address": instance.associated_resource_address,
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }

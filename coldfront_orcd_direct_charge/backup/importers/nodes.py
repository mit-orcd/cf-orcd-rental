# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Importers for node-related models.

Models imported:
    - NodeType: Node type definitions (GPU, CPU categories)
    - GpuNodeInstance: GPU node instances
    - CpuNodeInstance: CPU node instances
"""

from typing import Any, Dict, Optional
import logging

from ..base import BaseImporter
from ..registry import ImporterRegistry
from ..utils import resolve_foreign_key
from ...models import NodeType, GpuNodeInstance, CpuNodeInstance

logger = logging.getLogger(__name__)


@ImporterRegistry.register
class NodeTypeImporter(BaseImporter):
    """Importer for NodeType model.
    
    NodeType uses name as natural key.
    """
    
    model_name = "node_types"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[NodeType]:
        """Find existing NodeType by name."""
        if natural_key is None:
            return None
        
        name = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
        
        try:
            return NodeType.objects.get_by_natural_key(name)
        except NodeType.DoesNotExist:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> NodeType:
        """Create unsaved NodeType from data."""
        fields = data.get("fields", {})
        return NodeType(
            name=fields["name"],
            category=fields["category"],
            description=fields.get("description", ""),
            is_active=fields.get("is_active", True),
        )
    
    def create_record(self, data: Dict[str, Any]) -> NodeType:
        """Create and save new NodeType."""
        instance = self.deserialize_record(data)
        instance.save()
        logger.debug(f"Created NodeType: {instance.name}")
        return instance
    
    def update_record(self, existing: NodeType, data: Dict[str, Any]) -> NodeType:
        """Update existing NodeType."""
        fields = data.get("fields", {})
        
        existing.category = fields.get("category", existing.category)
        existing.description = fields.get("description", existing.description)
        existing.is_active = fields.get("is_active", existing.is_active)
        existing.save()
        
        logger.debug(f"Updated NodeType: {existing.name}")
        return existing


@ImporterRegistry.register
class GpuNodeInstanceImporter(BaseImporter):
    """Importer for GpuNodeInstance model.
    
    Uses associated_resource_address as natural key.
    Requires NodeType to be imported first.
    """
    
    model_name = "gpu_node_instances"
    dependencies = ["node_types"]
    
    def get_existing(self, natural_key) -> Optional[GpuNodeInstance]:
        """Find existing GpuNodeInstance by resource address."""
        if natural_key is None:
            return None
        
        address = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
        
        try:
            return GpuNodeInstance.objects.get_by_natural_key(address)
        except GpuNodeInstance.DoesNotExist:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> GpuNodeInstance:
        """Create unsaved GpuNodeInstance from data."""
        fields = data.get("fields", {})
        
        # Resolve node_type foreign key
        node_type_key = fields.get("node_type")
        node_type = resolve_foreign_key(NodeType, node_type_key, "node_type")
        
        if not node_type:
            raise ValueError(f"NodeType not found: {node_type_key}")
        
        return GpuNodeInstance(
            node_type=node_type,
            is_rentable=fields.get("is_rentable", False),
            status=fields.get("status", GpuNodeInstance.StatusChoices.AVAILABLE),
            associated_resource_address=fields["associated_resource_address"],
        )
    
    def create_record(self, data: Dict[str, Any]) -> GpuNodeInstance:
        """Create and save new GpuNodeInstance."""
        instance = self.deserialize_record(data)
        instance.save()
        logger.debug(f"Created GpuNodeInstance: {instance.associated_resource_address}")
        return instance
    
    def update_record(self, existing: GpuNodeInstance, data: Dict[str, Any]) -> GpuNodeInstance:
        """Update existing GpuNodeInstance."""
        fields = data.get("fields", {})
        
        # Update node_type if provided
        node_type_key = fields.get("node_type")
        if node_type_key:
            node_type = resolve_foreign_key(NodeType, node_type_key, "node_type")
            if node_type:
                existing.node_type = node_type
        
        existing.is_rentable = fields.get("is_rentable", existing.is_rentable)
        existing.status = fields.get("status", existing.status)
        existing.save()
        
        logger.debug(f"Updated GpuNodeInstance: {existing.associated_resource_address}")
        return existing


@ImporterRegistry.register
class CpuNodeInstanceImporter(BaseImporter):
    """Importer for CpuNodeInstance model.
    
    Uses associated_resource_address as natural key.
    Requires NodeType to be imported first.
    """
    
    model_name = "cpu_node_instances"
    dependencies = ["node_types"]
    
    def get_existing(self, natural_key) -> Optional[CpuNodeInstance]:
        """Find existing CpuNodeInstance by resource address."""
        if natural_key is None:
            return None
        
        address = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
        
        try:
            return CpuNodeInstance.objects.get_by_natural_key(address)
        except CpuNodeInstance.DoesNotExist:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> CpuNodeInstance:
        """Create unsaved CpuNodeInstance from data."""
        fields = data.get("fields", {})
        
        # Resolve node_type foreign key
        node_type_key = fields.get("node_type")
        node_type = resolve_foreign_key(NodeType, node_type_key, "node_type")
        
        if not node_type:
            raise ValueError(f"NodeType not found: {node_type_key}")
        
        return CpuNodeInstance(
            node_type=node_type,
            is_rentable=fields.get("is_rentable", False),
            status=fields.get("status", CpuNodeInstance.StatusChoices.AVAILABLE),
            associated_resource_address=fields["associated_resource_address"],
        )
    
    def create_record(self, data: Dict[str, Any]) -> CpuNodeInstance:
        """Create and save new CpuNodeInstance."""
        instance = self.deserialize_record(data)
        instance.save()
        logger.debug(f"Created CpuNodeInstance: {instance.associated_resource_address}")
        return instance
    
    def update_record(self, existing: CpuNodeInstance, data: Dict[str, Any]) -> CpuNodeInstance:
        """Update existing CpuNodeInstance."""
        fields = data.get("fields", {})
        
        # Update node_type if provided
        node_type_key = fields.get("node_type")
        if node_type_key:
            node_type = resolve_foreign_key(NodeType, node_type_key, "node_type")
            if node_type:
                existing.node_type = node_type
        
        existing.is_rentable = fields.get("is_rentable", existing.is_rentable)
        existing.status = fields.get("status", existing.status)
        existing.save()
        
        logger.debug(f"Updated CpuNodeInstance: {existing.associated_resource_address}")
        return existing

# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Importers for ColdFront resource models.

Models imported:
    - ResourceType: Resource type definitions
    - Resource: Resource definitions
    - ResourceAttributeType: Attribute type definitions
    - ResourceAttribute: Resource attributes
"""

from typing import Any, Dict, Optional

from ...base import BaseImporter
from ...registry import CoreImporterRegistry


@CoreImporterRegistry.register
class ResourceTypeImporter(BaseImporter):
    """Importer for ResourceType model."""
    
    model_name = "resource_types"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by name."""
        try:
            from coldfront.core.resource.models import ResourceType
            name = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
            return ResourceType.objects.get(name=name)
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create ResourceType instance."""
        try:
            from coldfront.core.resource.models import ResourceType
            fields = data.get("fields", {})
            return ResourceType(
                name=fields.get("name"),
                description=fields.get("description", ""),
            )
        except ImportError:
            return None
    
    def create_or_update(
        self, 
        data: Dict[str, Any], 
        existing: Optional[Any] = None,
        mode: str = "create-or-update",
    ) -> Optional[Any]:
        """Create or update resource type."""
        if existing:
            if mode == "create-only":
                return None
            fields = data.get("fields", {})
            existing.description = fields.get("description", existing.description)
            existing.save()
            return existing
        else:
            if mode == "update-only":
                return None
            instance = self.deserialize_record(data)
            if instance:
                instance.save()
            return instance


@CoreImporterRegistry.register
class ResourceImporter(BaseImporter):
    """Importer for Resource model."""
    
    model_name = "resources"
    dependencies = ["resource_types", "groups", "users"]
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by name."""
        try:
            from coldfront.core.resource.models import Resource
            name = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
            return Resource.objects.get(name=name)
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create Resource instance."""
        try:
            from coldfront.core.resource.models import Resource, ResourceType
            
            fields = data.get("fields", {})
            
            resource_type = None
            if fields.get("resource_type"):
                try:
                    resource_type = ResourceType.objects.get(
                        name=fields["resource_type"]
                    )
                except ResourceType.DoesNotExist:
                    pass
            
            return Resource(
                name=fields.get("name"),
                description=fields.get("description", ""),
                resource_type=resource_type,
                is_available=fields.get("is_available", True),
                is_public=fields.get("is_public", True),
                is_allocatable=fields.get("is_allocatable", True),
                requires_payment=fields.get("requires_payment", False),
            )
        except ImportError:
            return None
    
    def create_or_update(
        self, 
        data: Dict[str, Any], 
        existing: Optional[Any] = None,
        mode: str = "create-or-update",
    ) -> Optional[Any]:
        """Create or update resource."""
        try:
            from django.contrib.auth.models import User, Group
            
            fields = data.get("fields", {})
            
            if existing:
                if mode == "create-only":
                    return None
                
                existing.description = fields.get("description", existing.description)
                existing.is_available = fields.get("is_available", existing.is_available)
                existing.is_public = fields.get("is_public", existing.is_public)
                existing.is_allocatable = fields.get("is_allocatable", existing.is_allocatable)
                existing.save()
                
                resource = existing
            else:
                if mode == "update-only":
                    return None
                resource = self.deserialize_record(data)
                if resource:
                    resource.save()
            
            # Set allowed groups and users
            if resource:
                allowed_groups = fields.get("allowed_groups", [])
                groups = Group.objects.filter(name__in=allowed_groups)
                resource.allowed_groups.set(groups)
                
                allowed_users = fields.get("allowed_users", [])
                users = User.objects.filter(username__in=allowed_users)
                resource.allowed_users.set(users)
            
            return resource
        except ImportError:
            return None


@CoreImporterRegistry.register
class ResourceAttributeTypeImporter(BaseImporter):
    """Importer for ResourceAttributeType model."""
    
    model_name = "resource_attribute_types"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by name."""
        try:
            from coldfront.core.resource.models import ResourceAttributeType
            name = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
            return ResourceAttributeType.objects.get(name=name)
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create ResourceAttributeType instance."""
        try:
            from coldfront.core.resource.models import ResourceAttributeType
            fields = data.get("fields", {})
            return ResourceAttributeType(
                name=fields.get("name"),
            )
        except ImportError:
            return None
    
    def create_or_update(
        self, 
        data: Dict[str, Any], 
        existing: Optional[Any] = None,
        mode: str = "create-or-update",
    ) -> Optional[Any]:
        """Create or update (usually exists from fixtures)."""
        if existing:
            return existing
        if mode == "update-only":
            return None
        instance = self.deserialize_record(data)
        if instance:
            instance.save()
        return instance


@CoreImporterRegistry.register
class ResourceAttributeImporter(BaseImporter):
    """Importer for ResourceAttribute model."""
    
    model_name = "resource_attributes"
    dependencies = ["resources", "resource_attribute_types"]
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by resource and attribute type."""
        try:
            from coldfront.core.resource.models import (
                Resource, ResourceAttribute, ResourceAttributeType
            )
            
            resource_name, attr_type_name = natural_key
            resource = Resource.objects.get(name=resource_name)
            attr_type = ResourceAttributeType.objects.get(name=attr_type_name)
            
            return ResourceAttribute.objects.get(
                resource=resource,
                resource_attribute_type=attr_type,
            )
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create ResourceAttribute instance."""
        try:
            from coldfront.core.resource.models import (
                Resource, ResourceAttribute, ResourceAttributeType
            )
            
            fields = data.get("fields", {})
            
            resource = Resource.objects.get(name=fields["resource_name"])
            attr_type = ResourceAttributeType.objects.get(
                name=fields["attribute_type"]
            )
            
            return ResourceAttribute(
                resource=resource,
                resource_attribute_type=attr_type,
                value=fields.get("value", ""),
            )
        except Exception:
            return None
    
    def create_or_update(
        self, 
        data: Dict[str, Any], 
        existing: Optional[Any] = None,
        mode: str = "create-or-update",
    ) -> Optional[Any]:
        """Create or update resource attribute."""
        fields = data.get("fields", {})
        
        if existing:
            if mode == "create-only":
                return None
            existing.value = fields.get("value", existing.value)
            existing.save()
            return existing
        else:
            if mode == "update-only":
                return None
            instance = self.deserialize_record(data)
            if instance:
                instance.save()
            return instance

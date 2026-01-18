# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Importers for ColdFront allocation models.

Models imported:
    - AllocationStatusChoice: Allocation status options
    - Allocation: Resource allocations
    - AllocationAttributeType: Allocation attribute types
    - AllocationAttribute: Allocation attributes
    - AllocationUserStatusChoice: Allocation user status options
    - AllocationUser: Allocation user memberships
"""

from typing import Any, Dict, Optional

from ...base import BaseImporter
from ...registry import CoreImporterRegistry
from ...utils import deserialize_date


@CoreImporterRegistry.register
class AllocationStatusImporter(BaseImporter):
    """Importer for AllocationStatusChoice model."""
    
    model_name = "allocation_statuses"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by name."""
        try:
            from coldfront.core.allocation.models import AllocationStatusChoice
            name = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
            return AllocationStatusChoice.objects.get(name=name)
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create AllocationStatusChoice instance."""
        try:
            from coldfront.core.allocation.models import AllocationStatusChoice
            fields = data.get("fields", {})
            return AllocationStatusChoice(name=fields.get("name"))
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
class AllocationImporter(BaseImporter):
    """Importer for Allocation model.
    
    Note: Allocations use PKs as natural keys since they don't have
    unique identifying fields. This means imported allocations will
    have new PKs.
    """
    
    model_name = "allocations"
    dependencies = ["projects", "resources", "allocation_statuses"]
    
    # Map old PKs to new PKs for foreign key resolution
    pk_mapping: Dict[int, int] = {}
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by PK (may not exist in new database)."""
        try:
            from coldfront.core.allocation.models import Allocation
            pk = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
            return Allocation.objects.get(pk=pk)
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create Allocation instance."""
        try:
            from coldfront.core.allocation.models import (
                Allocation, AllocationStatusChoice
            )
            from coldfront.core.project.models import Project
            from coldfront.core.resource.models import Resource
            
            fields = data.get("fields", {})
            
            project = Project.objects.get(title=fields["project_title"])
            
            status = None
            if fields.get("status"):
                try:
                    status = AllocationStatusChoice.objects.get(
                        name=fields["status"]
                    )
                except AllocationStatusChoice.DoesNotExist:
                    pass
            
            allocation = Allocation(
                project=project,
                status=status,
                quantity=fields.get("quantity", 1),
                start_date=deserialize_date(fields.get("start_date")),
                end_date=deserialize_date(fields.get("end_date")),
                justification=fields.get("justification", ""),
                description=fields.get("description", ""),
                is_locked=fields.get("is_locked", False),
                is_changeable=fields.get("is_changeable", True),
            )
            
            # Store original PK for later reference
            allocation._original_pk = fields.get("pk")
            
            return allocation
        except Exception:
            return None
    
    def create_or_update(
        self, 
        data: Dict[str, Any], 
        existing: Optional[Any] = None,
        mode: str = "create-or-update",
    ) -> Optional[Any]:
        """Create or update allocation."""
        try:
            from coldfront.core.resource.models import Resource
            
            fields = data.get("fields", {})
            original_pk = fields.get("pk")
            
            if existing:
                if mode == "create-only":
                    return None
                
                # Update existing allocation
                existing.quantity = fields.get("quantity", existing.quantity)
                existing.start_date = deserialize_date(
                    fields.get("start_date")
                ) or existing.start_date
                existing.end_date = deserialize_date(
                    fields.get("end_date")
                ) or existing.end_date
                existing.description = fields.get("description", existing.description)
                existing.save()
                
                allocation = existing
            else:
                if mode == "update-only":
                    return None
                allocation = self.deserialize_record(data)
                if allocation:
                    allocation.save()
            
            if allocation:
                # Set resources
                resource_names = fields.get("resources", [])
                resources = Resource.objects.filter(name__in=resource_names)
                allocation.resources.set(resources)
                
                # Store PK mapping for dependent models
                if original_pk:
                    AllocationImporter.pk_mapping[original_pk] = allocation.pk
            
            return allocation
        except Exception:
            return None


@CoreImporterRegistry.register
class AllocationAttributeTypeImporter(BaseImporter):
    """Importer for AllocationAttributeType model."""
    
    model_name = "allocation_attribute_types"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by name."""
        try:
            from coldfront.core.allocation.models import AllocationAttributeType
            name = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
            return AllocationAttributeType.objects.get(name=name)
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create AllocationAttributeType instance."""
        try:
            from coldfront.core.allocation.models import AllocationAttributeType
            fields = data.get("fields", {})
            return AllocationAttributeType(name=fields.get("name"))
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
class AllocationAttributeImporter(BaseImporter):
    """Importer for AllocationAttribute model."""
    
    model_name = "allocation_attributes"
    dependencies = ["allocations", "allocation_attribute_types"]
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by allocation and attribute type."""
        try:
            from coldfront.core.allocation.models import (
                Allocation, AllocationAttribute, AllocationAttributeType
            )
            
            allocation_pk, attr_type_name = natural_key
            
            # Try to resolve PK from mapping
            new_pk = AllocationImporter.pk_mapping.get(allocation_pk, allocation_pk)
            allocation = Allocation.objects.get(pk=new_pk)
            attr_type = AllocationAttributeType.objects.get(name=attr_type_name)
            
            return AllocationAttribute.objects.get(
                allocation=allocation,
                allocation_attribute_type=attr_type,
            )
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create AllocationAttribute instance."""
        try:
            from coldfront.core.allocation.models import (
                Allocation, AllocationAttribute, AllocationAttributeType
            )
            
            fields = data.get("fields", {})
            
            allocation_pk = fields["allocation_pk"]
            new_pk = AllocationImporter.pk_mapping.get(allocation_pk, allocation_pk)
            
            allocation = Allocation.objects.get(pk=new_pk)
            attr_type = AllocationAttributeType.objects.get(
                name=fields["attribute_type"]
            )
            
            return AllocationAttribute(
                allocation=allocation,
                allocation_attribute_type=attr_type,
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
        """Create or update allocation attribute."""
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


@CoreImporterRegistry.register
class AllocationUserStatusImporter(BaseImporter):
    """Importer for AllocationUserStatusChoice model."""
    
    model_name = "allocation_user_statuses"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by name."""
        try:
            from coldfront.core.allocation.models import AllocationUserStatusChoice
            name = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
            return AllocationUserStatusChoice.objects.get(name=name)
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create AllocationUserStatusChoice instance."""
        try:
            from coldfront.core.allocation.models import AllocationUserStatusChoice
            fields = data.get("fields", {})
            return AllocationUserStatusChoice(name=fields.get("name"))
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
class AllocationUserImporter(BaseImporter):
    """Importer for AllocationUser model."""
    
    model_name = "allocation_users"
    dependencies = ["allocations", "users", "allocation_user_statuses"]
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by allocation and user."""
        try:
            from coldfront.core.allocation.models import Allocation, AllocationUser
            from django.contrib.auth.models import User
            
            allocation_pk, username = natural_key
            
            new_pk = AllocationImporter.pk_mapping.get(allocation_pk, allocation_pk)
            allocation = Allocation.objects.get(pk=new_pk)
            user = User.objects.get(username=username)
            
            return AllocationUser.objects.get(allocation=allocation, user=user)
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create AllocationUser instance."""
        try:
            from coldfront.core.allocation.models import (
                Allocation, AllocationUser, AllocationUserStatusChoice
            )
            from django.contrib.auth.models import User
            
            fields = data.get("fields", {})
            
            allocation_pk = fields["allocation_pk"]
            new_pk = AllocationImporter.pk_mapping.get(allocation_pk, allocation_pk)
            
            allocation = Allocation.objects.get(pk=new_pk)
            user = User.objects.get(username=fields["username"])
            
            status = None
            if fields.get("status"):
                try:
                    status = AllocationUserStatusChoice.objects.get(
                        name=fields["status"]
                    )
                except AllocationUserStatusChoice.DoesNotExist:
                    pass
            
            return AllocationUser(
                allocation=allocation,
                user=user,
                status=status,
            )
        except Exception:
            return None
    
    def create_or_update(
        self, 
        data: Dict[str, Any], 
        existing: Optional[Any] = None,
        mode: str = "create-or-update",
    ) -> Optional[Any]:
        """Create or update allocation user."""
        try:
            from coldfront.core.allocation.models import AllocationUserStatusChoice
            
            fields = data.get("fields", {})
            
            if existing:
                if mode == "create-only":
                    return None
                
                if fields.get("status"):
                    try:
                        existing.status = AllocationUserStatusChoice.objects.get(
                            name=fields["status"]
                        )
                    except AllocationUserStatusChoice.DoesNotExist:
                        pass
                
                existing.save()
                return existing
            else:
                if mode == "update-only":
                    return None
                instance = self.deserialize_record(data)
                if instance:
                    instance.save()
                return instance
        except Exception:
            return None

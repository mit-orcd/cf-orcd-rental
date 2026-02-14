# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Importers for Django auth models.

Models imported:
    - User: Django user accounts (passwords will need to be reset)
    - Group: Permission groups
    - Permission: Custom permissions
    - UserGroups: User-to-group memberships
"""

from typing import Any, Dict, List, Optional

from ...base import BaseImporter, ImportResult
from ...registry import CoreImporterRegistry
from ...utils import deserialize_datetime


@CoreImporterRegistry.register
class UserImporter(BaseImporter):
    """Importer for Django User model.
    
    Note: Passwords are not imported. Users will need to reset passwords
    after import or use SSO authentication.
    """
    
    model_name = "users"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up user by username."""
        from django.contrib.auth.models import User
        try:
            username = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
            return User.objects.get(username=username)
        except User.DoesNotExist:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create User instance from serialized data.
        
        Note: Password is set unusable since we don't export password hashes.
        """
        from django.contrib.auth.models import User
        
        fields = data.get("fields", {})
        user = User(
            username=fields.get("username"),
            email=fields.get("email", ""),
            first_name=fields.get("first_name", ""),
            last_name=fields.get("last_name", ""),
            is_active=fields.get("is_active", True),
            is_staff=fields.get("is_staff", False),
            is_superuser=fields.get("is_superuser", False),
        )
        # Restore date_joined if present in export data
        date_joined = deserialize_datetime(fields.get("date_joined"))
        if date_joined is not None:
            user.date_joined = date_joined
        user.set_unusable_password()
        return user
    
    def _restore_account_timestamp(self, user, fields: Dict[str, Any]):
        """Restore last_modified into UserAccountTimestamp if present."""
        last_modified = deserialize_datetime(fields.get("last_modified"))
        if last_modified is not None:
            try:
                from coldfront_orcd_direct_charge.models import UserAccountTimestamp
                from django.contrib.auth.models import User as _User
                UserAccountTimestamp.objects.update_or_create(
                    user=user,
                    defaults={"last_modified": last_modified},
                )
            except Exception:
                pass  # table may not exist yet during early import
    
    def create_or_update(
        self, 
        data: Dict[str, Any], 
        existing: Optional[Any] = None,
        mode: str = "create-or-update",
    ) -> Optional[Any]:
        """Create or update user."""
        from django.contrib.auth.models import User
        
        fields = data.get("fields", {})
        
        if existing:
            if mode == "create-only":
                return None
            # Update existing user
            existing.email = fields.get("email", existing.email)
            existing.first_name = fields.get("first_name", existing.first_name)
            existing.last_name = fields.get("last_name", existing.last_name)
            existing.is_active = fields.get("is_active", existing.is_active)
            existing.is_staff = fields.get("is_staff", existing.is_staff)
            existing.is_superuser = fields.get("is_superuser", existing.is_superuser)
            # Restore date_joined if present
            date_joined = deserialize_datetime(fields.get("date_joined"))
            if date_joined is not None:
                existing.date_joined = date_joined
            existing.save()
            self._restore_account_timestamp(existing, fields)
            return existing
        else:
            if mode == "update-only":
                return None
            user = self.deserialize_record(data)
            user.save()
            # Use queryset update to set date_joined without triggering
            # the post_save signal (which would overwrite last_modified)
            date_joined = deserialize_datetime(fields.get("date_joined"))
            if date_joined is not None:
                User.objects.filter(pk=user.pk).update(date_joined=date_joined)
                user.refresh_from_db()
            self._restore_account_timestamp(user, fields)
            return user
    
    def create_record(self, data: Dict[str, Any]) -> Any:
        """Create new record."""
        return self.create_or_update(data, existing=None, mode="create-only")
    
    def update_record(self, existing: Any, data: Dict[str, Any]) -> Any:
        """Update existing record."""
        return self.create_or_update(data, existing=existing, mode="update-only")


@CoreImporterRegistry.register
class GroupImporter(BaseImporter):
    """Importer for Django Group model."""
    
    model_name = "groups"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up group by name."""
        from django.contrib.auth.models import Group
        try:
            name = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
            return Group.objects.get(name=name)
        except Group.DoesNotExist:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create Group instance from serialized data."""
        from django.contrib.auth.models import Group
        
        fields = data.get("fields", {})
        return Group(name=fields.get("name"))
    
    def create_or_update(
        self, 
        data: Dict[str, Any], 
        existing: Optional[Any] = None,
        mode: str = "create-or-update",
    ) -> Optional[Any]:
        """Create or update group."""
        from django.contrib.auth.models import Group, Permission
        from django.contrib.contenttypes.models import ContentType
        
        fields = data.get("fields", {})
        
        if existing:
            if mode == "create-only":
                return None
            group = existing
        else:
            if mode == "update-only":
                return None
            group = Group(name=fields.get("name"))
            group.save()
        
        # Set permissions
        permission_codenames = fields.get("permission_codenames", [])
        if permission_codenames:
            permissions = []
            for codename_full in permission_codenames:
                parts = codename_full.split(".")
                if len(parts) == 2:
                    app_label, codename = parts
                    try:
                        content_type = ContentType.objects.get(app_label=app_label)
                        perm = Permission.objects.get(
                            codename=codename,
                            content_type=content_type,
                        )
                        permissions.append(perm)
                    except (ContentType.DoesNotExist, Permission.DoesNotExist):
                        pass
            
            group.permissions.set(permissions)
        
        return group
    
    def create_record(self, data: Dict[str, Any]) -> Any:
        """Create new record."""
        return self.create_or_update(data, existing=None, mode="create-only")
    
    def update_record(self, existing: Any, data: Dict[str, Any]) -> Any:
        """Update existing record."""
        return self.create_or_update(data, existing=existing, mode="update-only")


@CoreImporterRegistry.register
class PermissionImporter(BaseImporter):
    """Importer for custom permissions.
    
    Note: Standard Django/ColdFront permissions are typically created by
    migrations. This importer handles any custom permissions.
    """
    
    model_name = "permissions"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up permission by codename and content type."""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        
        try:
            if len(natural_key) >= 3:
                codename, app_label, model = natural_key[:3]
                content_type = ContentType.objects.get(
                    app_label=app_label,
                    model=model,
                )
                return Permission.objects.get(
                    codename=codename,
                    content_type=content_type,
                )
        except (Permission.DoesNotExist, ContentType.DoesNotExist):
            return None
        return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create Permission instance (usually already exists from migrations)."""
        return None  # Permissions are typically created by migrations
    
    def create_or_update(
        self, 
        data: Dict[str, Any], 
        existing: Optional[Any] = None,
        mode: str = "create-or-update",
    ) -> Optional[Any]:
        """Permissions are usually created by migrations, so skip creation."""
        return existing  # Don't create/update permissions
    
    def create_record(self, data: Dict[str, Any]) -> Any:
        """Create new record."""
        return self.create_or_update(data, existing=None, mode="create-only")
    
    def update_record(self, existing: Any, data: Dict[str, Any]) -> Any:
        """Update existing record."""
        return self.create_or_update(data, existing=existing, mode="update-only")


@CoreImporterRegistry.register
class UserGroupMembershipImporter(BaseImporter):
    """Importer for User-Group memberships."""
    
    model_name = "user_group_memberships"
    dependencies = ["users", "groups"]
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up user by username."""
        from django.contrib.auth.models import User
        try:
            username = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
            return User.objects.get(username=username)
        except User.DoesNotExist:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Return group names list."""
        fields = data.get("fields", {})
        return fields.get("groups", [])
    
    def create_or_update(
        self, 
        data: Dict[str, Any], 
        existing: Optional[Any] = None,
        mode: str = "create-or-update",
    ) -> Optional[Any]:
        """Set user's group memberships."""
        from django.contrib.auth.models import Group
        
        if not existing:
            return None
        
        fields = data.get("fields", {})
        group_names = fields.get("groups", [])
        
        groups = Group.objects.filter(name__in=group_names)
        existing.groups.set(groups)
        
        return existing
    
    def create_record(self, data: Dict[str, Any]) -> Any:
        """Create new record."""
        return self.create_or_update(data, existing=None, mode="create-only")
    
    def update_record(self, existing: Any, data: Dict[str, Any]) -> Any:
        """Update existing record."""
        return self.create_or_update(data, existing=existing, mode="update-only")


@CoreImporterRegistry.register
class UserPermissionImporter(BaseImporter):
    """Importer for direct user permissions."""
    
    model_name = "user_permissions"
    dependencies = ["users", "permissions"]
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up user by username."""
        from django.contrib.auth.models import User
        try:
            username = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
            return User.objects.get(username=username)
        except User.DoesNotExist:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Return permissions list."""
        fields = data.get("fields", {})
        return fields.get("permissions", [])
    
    def create_or_update(
        self, 
        data: Dict[str, Any], 
        existing: Optional[Any] = None,
        mode: str = "create-or-update",
    ) -> Optional[Any]:
        """Set user's direct permissions."""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        
        if not existing:
            return None
        
        fields = data.get("fields", {})
        permission_names = fields.get("permissions", [])
        
        permissions = []
        for perm_name in permission_names:
            parts = perm_name.split(".")
            if len(parts) == 2:
                app_label, codename = parts
                try:
                    content_type = ContentType.objects.get(app_label=app_label)
                    perm = Permission.objects.get(
                        codename=codename,
                        content_type=content_type,
                    )
                    permissions.append(perm)
                except (ContentType.DoesNotExist, Permission.DoesNotExist):
                    pass
        
        existing.user_permissions.set(permissions)
        
        return existing
    
    def create_record(self, data: Dict[str, Any]) -> Any:
        """Create new record."""
        return self.create_or_update(data, existing=None, mode="create-only")
    
    def update_record(self, existing: Any, data: Dict[str, Any]) -> Any:
        """Update existing record."""
        return self.create_or_update(data, existing=existing, mode="update-only")

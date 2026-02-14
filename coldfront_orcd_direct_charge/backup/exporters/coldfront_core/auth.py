# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Exporters for Django auth models.

Models exported:
    - User: Django user accounts (excludes password hashes)
    - Group: Permission groups
    - Permission: Custom permissions
    - UserGroups: User-to-group memberships
"""

from typing import Any, Dict

from ...base import BaseExporter
from ...registry import CoreExporterRegistry
from ...utils import serialize_datetime


@CoreExporterRegistry.register
class UserExporter(BaseExporter):
    """Exporter for Django User model.
    
    Exports user account information but excludes password hashes
    for security. Passwords will need to be reset on import.
    """
    
    model_name = "users"
    dependencies = []
    
    def get_queryset(self):
        """Return all users ordered by username."""
        from django.contrib.auth.models import User
        return (
            User.objects
            .prefetch_related("groups")
            .select_related("account_timestamp")
            .order_by("username")
        )
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize User to dict.
        
        Note: Password is intentionally excluded for security.
        """
        # Fetch last_modified from UserAccountTimestamp (if available)
        account_ts = getattr(instance, "account_timestamp", None)
        last_modified = (
            serialize_datetime(account_ts.last_modified)
            if account_ts is not None
            else None
        )

        return {
            "natural_key": (instance.username,),
            "fields": {
                "username": instance.username,
                "email": instance.email,
                "first_name": instance.first_name,
                "last_name": instance.last_name,
                "is_active": instance.is_active,
                "is_staff": instance.is_staff,
                "is_superuser": instance.is_superuser,
                "date_joined": serialize_datetime(instance.date_joined),
                "last_login": serialize_datetime(instance.last_login),
                "last_modified": last_modified,
                # Groups are exported separately, but include names for reference
                "group_names": [g.name for g in instance.groups.all()],
            }
        }


@CoreExporterRegistry.register
class GroupExporter(BaseExporter):
    """Exporter for Django Group model."""
    
    model_name = "groups"
    dependencies = []
    
    def get_queryset(self):
        """Return all groups ordered by name."""
        from django.contrib.auth.models import Group
        return Group.objects.prefetch_related("permissions").order_by("name")
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize Group to dict."""
        return {
            "natural_key": (instance.name,),
            "fields": {
                "name": instance.name,
                "permission_codenames": [
                    f"{p.content_type.app_label}.{p.codename}"
                    for p in instance.permissions.all()
                ],
            }
        }


@CoreExporterRegistry.register
class PermissionExporter(BaseExporter):
    """Exporter for custom permissions.
    
    Only exports permissions for our apps, not Django built-in ones.
    """
    
    model_name = "permissions"
    dependencies = []
    
    def get_queryset(self):
        """Return custom permissions for relevant apps."""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        
        # Get permissions for our apps
        our_apps = [
            "coldfront_orcd_direct_charge",
            "project",
            "resource",
            "allocation",
        ]
        
        content_types = ContentType.objects.filter(app_label__in=our_apps)
        return Permission.objects.filter(
            content_type__in=content_types
        ).select_related("content_type").order_by("codename")
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize Permission to dict."""
        return {
            "natural_key": (
                instance.codename,
                instance.content_type.app_label,
                instance.content_type.model,
            ),
            "fields": {
                "codename": instance.codename,
                "name": instance.name,
                "content_type_app": instance.content_type.app_label,
                "content_type_model": instance.content_type.model,
            }
        }


@CoreExporterRegistry.register
class UserGroupMembershipExporter(BaseExporter):
    """Exporter for User-Group memberships (M2M relationship)."""
    
    model_name = "user_group_memberships"
    dependencies = ["users", "groups"]
    
    def get_queryset(self):
        """Return all user-group relationships."""
        from django.contrib.auth.models import User
        # Get users with groups
        return User.objects.filter(groups__isnull=False).prefetch_related(
            "groups"
        ).distinct().order_by("username")
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize user's group memberships."""
        return {
            "natural_key": (instance.username,),
            "fields": {
                "username": instance.username,
                "groups": [g.name for g in instance.groups.all()],
            }
        }


@CoreExporterRegistry.register
class UserPermissionExporter(BaseExporter):
    """Exporter for direct user permissions (not via groups)."""
    
    model_name = "user_permissions"
    dependencies = ["users", "permissions"]
    
    def get_queryset(self):
        """Return users with direct permissions."""
        from django.contrib.auth.models import User
        return User.objects.filter(
            user_permissions__isnull=False
        ).prefetch_related(
            "user_permissions__content_type"
        ).distinct().order_by("username")
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize user's direct permissions."""
        return {
            "natural_key": (instance.username,),
            "fields": {
                "username": instance.username,
                "permissions": [
                    f"{p.content_type.app_label}.{p.codename}"
                    for p in instance.user_permissions.all()
                ],
            }
        }

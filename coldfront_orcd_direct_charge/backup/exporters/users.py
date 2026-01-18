# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Exporters for user-related models.

Models exported:
    - UserMaintenanceStatus: User account maintenance status
    - ProjectMemberRole: User roles within projects
"""

from typing import Any, Dict

from ..base import BaseExporter
from ..registry import ExporterRegistry
from ..utils import serialize_datetime
from ...models import UserMaintenanceStatus, ProjectMemberRole


@ExporterRegistry.register
class UserMaintenanceStatusExporter(BaseExporter):
    """Exporter for UserMaintenanceStatus model.
    
    Maintenance status is linked to users by username.
    """
    
    model_name = "user_maintenance_statuses"
    dependencies = []
    
    def get_queryset(self):
        """Return all maintenance statuses with related user."""
        return UserMaintenanceStatus.objects.select_related(
            "user",
            "billing_project",
        ).order_by("user__username")
    
    def serialize_record(self, instance: UserMaintenanceStatus) -> Dict[str, Any]:
        """Serialize UserMaintenanceStatus to dict.
        
        Uses username as natural key.
        """
        return {
            "natural_key": (instance.user.username,),
            "fields": {
                "username": instance.user.username,
                "status": instance.status,
                "billing_project_title": (
                    instance.billing_project.title 
                    if instance.billing_project else None
                ),
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }


@ExporterRegistry.register
class ProjectMemberRoleExporter(BaseExporter):
    """Exporter for ProjectMemberRole model.
    
    Member roles link users to projects with specific roles.
    """
    
    model_name = "project_member_roles"
    dependencies = []
    
    def get_queryset(self):
        """Return all member roles with related user and project."""
        return ProjectMemberRole.objects.select_related(
            "user",
            "project",
        ).order_by("project__title", "user__username", "role")
    
    def serialize_record(self, instance: ProjectMemberRole) -> Dict[str, Any]:
        """Serialize ProjectMemberRole to dict.
        
        Uses project_title + username + role as composite natural key.
        """
        return {
            "natural_key": (
                instance.project.title,
                instance.user.username,
                instance.role,
            ),
            "fields": {
                "project_title": instance.project.title,
                "username": instance.user.username,
                "role": instance.role,
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }

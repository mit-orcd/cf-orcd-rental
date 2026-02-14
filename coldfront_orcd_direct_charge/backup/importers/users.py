# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Importers for user-related models.

Models imported:
    - UserMaintenanceStatus: User account maintenance status
    - ProjectMemberRole: User roles within projects
"""

from typing import Any, Dict, Optional
import logging

from django.contrib.auth.models import User

from ..base import BaseImporter
from ..registry import ImporterRegistry
from ..utils import deserialize_datetime
from ...models import UserMaintenanceStatus, ProjectMemberRole

logger = logging.getLogger(__name__)


def get_project_by_title(title: str):
    """Get ColdFront project by title."""
    if not title:
        return None
    try:
        from coldfront.core.project.models import Project
        return Project.objects.get(title=title)
    except Exception:
        return None


def get_user_by_username(username: str) -> Optional[User]:
    """Get user by username."""
    if not username:
        return None
    try:
        return User.objects.get(username=username)
    except User.DoesNotExist:
        return None


@ImporterRegistry.register
class UserMaintenanceStatusImporter(BaseImporter):
    """Importer for UserMaintenanceStatus model.
    
    Uses username as natural key. Only imports for existing users.
    """
    
    model_name = "user_maintenance_statuses"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[UserMaintenanceStatus]:
        """Find existing UserMaintenanceStatus by username."""
        if not natural_key:
            return None
        
        username = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
        user = get_user_by_username(username)
        
        if not user:
            return None
        
        try:
            return UserMaintenanceStatus.objects.get(user=user)
        except UserMaintenanceStatus.DoesNotExist:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> UserMaintenanceStatus:
        """Create unsaved UserMaintenanceStatus from data."""
        fields = data.get("fields", {})
        
        user = get_user_by_username(fields.get("username"))
        if not user:
            raise ValueError(f"User not found: {fields.get('username')}")
        
        billing_project = get_project_by_title(fields.get("billing_project_title"))
        
        return UserMaintenanceStatus(
            user=user,
            status=fields.get("status", UserMaintenanceStatus.StatusChoices.INACTIVE),
            billing_project=billing_project,
        )
    
    @staticmethod
    def _restore_timestamps(instance: UserMaintenanceStatus, fields: Dict[str, Any]):
        """Restore created/modified timestamps using queryset.update().
        
        TimeStampedModel uses auto_now_add and auto_now which prevent
        normal field assignment.  queryset.update() bypasses this.
        """
        update_fields = {}
        created_dt = deserialize_datetime(fields.get("created"))
        if created_dt is not None:
            update_fields["created"] = created_dt
        modified_dt = deserialize_datetime(fields.get("modified"))
        if modified_dt is not None:
            update_fields["modified"] = modified_dt
        if update_fields:
            UserMaintenanceStatus.objects.filter(pk=instance.pk).update(**update_fields)

    def create_record(self, data: Dict[str, Any]) -> UserMaintenanceStatus:
        """Create and save new UserMaintenanceStatus."""
        instance = self.deserialize_record(data)
        instance.save()
        self._restore_timestamps(instance, data.get("fields", {}))
        logger.debug(f"Created UserMaintenanceStatus for: {instance.user.username}")
        return instance
    
    def update_record(
        self, existing: UserMaintenanceStatus, data: Dict[str, Any]
    ) -> UserMaintenanceStatus:
        """Update existing UserMaintenanceStatus."""
        fields = data.get("fields", {})
        
        existing.status = fields.get("status", existing.status)
        
        billing_project = get_project_by_title(fields.get("billing_project_title"))
        if billing_project:
            existing.billing_project = billing_project
        elif fields.get("billing_project_title") is None:
            existing.billing_project = None
        
        existing.save()
        self._restore_timestamps(existing, fields)
        logger.debug(f"Updated UserMaintenanceStatus for: {existing.user.username}")
        return existing


@ImporterRegistry.register
class ProjectMemberRoleImporter(BaseImporter):
    """Importer for ProjectMemberRole model.
    
    Uses project_title + username + role as composite natural key.
    """
    
    model_name = "project_member_roles"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[ProjectMemberRole]:
        """Find existing ProjectMemberRole by composite key."""
        if not natural_key or len(natural_key) < 3:
            return None
        
        project_title, username, role = natural_key
        
        project = get_project_by_title(project_title)
        user = get_user_by_username(username)
        
        if not project or not user:
            return None
        
        try:
            return ProjectMemberRole.objects.get(
                project=project,
                user=user,
                role=role,
            )
        except ProjectMemberRole.DoesNotExist:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> ProjectMemberRole:
        """Create unsaved ProjectMemberRole from data."""
        fields = data.get("fields", {})
        
        project = get_project_by_title(fields.get("project_title"))
        if not project:
            raise ValueError(f"Project not found: {fields.get('project_title')}")
        
        user = get_user_by_username(fields.get("username"))
        if not user:
            raise ValueError(f"User not found: {fields.get('username')}")
        
        return ProjectMemberRole(
            project=project,
            user=user,
            role=fields.get("role"),
        )
    
    @staticmethod
    def _restore_timestamps(instance: ProjectMemberRole, fields: Dict[str, Any]):
        """Restore created/modified timestamps using queryset.update().
        
        TimeStampedModel uses auto_now_add and auto_now which prevent
        normal field assignment.  queryset.update() bypasses this.
        """
        update_fields = {}
        created_dt = deserialize_datetime(fields.get("created"))
        if created_dt is not None:
            update_fields["created"] = created_dt
        modified_dt = deserialize_datetime(fields.get("modified"))
        if modified_dt is not None:
            update_fields["modified"] = modified_dt
        if update_fields:
            ProjectMemberRole.objects.filter(pk=instance.pk).update(**update_fields)

    def create_record(self, data: Dict[str, Any]) -> ProjectMemberRole:
        """Create and save new ProjectMemberRole."""
        instance = self.deserialize_record(data)
        instance.save()
        self._restore_timestamps(instance, data.get("fields", {}))
        logger.debug(
            f"Created ProjectMemberRole: {instance.user.username} "
            f"as {instance.role} in {instance.project.title}"
        )
        return instance
    
    def update_record(
        self, existing: ProjectMemberRole, data: Dict[str, Any]
    ) -> ProjectMemberRole:
        """Update existing ProjectMemberRole.
        
        Note: Role changes are not supported since role is part of the key.
        Timestamps are still restored from export data if present.
        """
        self._restore_timestamps(existing, data.get("fields", {}))
        logger.debug(f"ProjectMemberRole unchanged: {existing}")
        return existing

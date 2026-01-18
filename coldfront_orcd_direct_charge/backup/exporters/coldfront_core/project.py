# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Exporters for ColdFront project models.

Models exported:
    - FieldOfScience: Field of science reference data
    - Project: Projects
    - ProjectUser: Project memberships
    - ProjectReview: Project review history
"""

from typing import Any, Dict

from ...base import BaseExporter
from ...registry import CoreExporterRegistry
from ...utils import serialize_datetime, serialize_date


@CoreExporterRegistry.register
class FieldOfScienceExporter(BaseExporter):
    """Exporter for FieldOfScience model."""
    
    model_name = "field_of_science"
    dependencies = []
    
    def get_queryset(self):
        """Return all fields of science."""
        try:
            from coldfront.core.field_of_science.models import FieldOfScience
            return FieldOfScience.objects.all().order_by("description")
        except ImportError:
            # Return empty if model doesn't exist
            from django.db.models import QuerySet
            return QuerySet().none()
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize FieldOfScience to dict."""
        return {
            "natural_key": (instance.description,),
            "fields": {
                "description": instance.description,
                "is_selectable": getattr(instance, "is_selectable", True),
            }
        }


@CoreExporterRegistry.register
class ProjectExporter(BaseExporter):
    """Exporter for ColdFront Project model."""
    
    model_name = "projects"
    dependencies = ["users", "field_of_science"]
    
    def get_queryset(self):
        """Return all projects with related data."""
        try:
            from coldfront.core.project.models import Project
            return Project.objects.select_related(
                "pi",
                "field_of_science",
                "status",
            ).order_by("title")
        except ImportError:
            from django.db.models import QuerySet
            return QuerySet().none()
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize Project to dict."""
        return {
            "natural_key": (instance.title,),
            "fields": {
                "title": instance.title,
                "description": instance.description,
                "pi_username": instance.pi.username if instance.pi else None,
                "field_of_science": (
                    instance.field_of_science.description 
                    if instance.field_of_science else None
                ),
                "status": instance.status.name if instance.status else None,
                "force_review": getattr(instance, "force_review", False),
                "requires_review": getattr(instance, "requires_review", True),
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }


@CoreExporterRegistry.register
class ProjectStatusExporter(BaseExporter):
    """Exporter for ProjectStatusChoice model."""
    
    model_name = "project_statuses"
    dependencies = []
    
    def get_queryset(self):
        """Return all project statuses."""
        try:
            from coldfront.core.project.models import ProjectStatusChoice
            return ProjectStatusChoice.objects.all().order_by("name")
        except ImportError:
            from django.db.models import QuerySet
            return QuerySet().none()
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize ProjectStatusChoice to dict."""
        return {
            "natural_key": (instance.name,),
            "fields": {
                "name": instance.name,
            }
        }


@CoreExporterRegistry.register
class ProjectUserExporter(BaseExporter):
    """Exporter for ProjectUser model (project memberships)."""
    
    model_name = "project_users"
    dependencies = ["projects", "users"]
    
    def get_queryset(self):
        """Return all project-user relationships."""
        try:
            from coldfront.core.project.models import ProjectUser
            return ProjectUser.objects.select_related(
                "project",
                "user",
                "role",
                "status",
            ).order_by("project__title", "user__username")
        except ImportError:
            from django.db.models import QuerySet
            return QuerySet().none()
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize ProjectUser to dict."""
        return {
            "natural_key": (instance.project.title, instance.user.username),
            "fields": {
                "project_title": instance.project.title,
                "username": instance.user.username,
                "role": instance.role.name if instance.role else None,
                "status": instance.status.name if instance.status else None,
                "enable_notifications": getattr(
                    instance, "enable_notifications", True
                ),
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }


@CoreExporterRegistry.register
class ProjectUserRoleExporter(BaseExporter):
    """Exporter for ProjectUserRoleChoice model."""
    
    model_name = "project_user_roles"
    dependencies = []
    
    def get_queryset(self):
        """Return all project user roles."""
        try:
            from coldfront.core.project.models import ProjectUserRoleChoice
            return ProjectUserRoleChoice.objects.all().order_by("name")
        except ImportError:
            from django.db.models import QuerySet
            return QuerySet().none()
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize ProjectUserRoleChoice to dict."""
        return {
            "natural_key": (instance.name,),
            "fields": {
                "name": instance.name,
            }
        }


@CoreExporterRegistry.register
class ProjectUserStatusExporter(BaseExporter):
    """Exporter for ProjectUserStatusChoice model."""
    
    model_name = "project_user_statuses"
    dependencies = []
    
    def get_queryset(self):
        """Return all project user statuses."""
        try:
            from coldfront.core.project.models import ProjectUserStatusChoice
            return ProjectUserStatusChoice.objects.all().order_by("name")
        except ImportError:
            from django.db.models import QuerySet
            return QuerySet().none()
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize ProjectUserStatusChoice to dict."""
        return {
            "natural_key": (instance.name,),
            "fields": {
                "name": instance.name,
            }
        }


@CoreExporterRegistry.register
class ProjectReviewExporter(BaseExporter):
    """Exporter for ProjectReview model."""
    
    model_name = "project_reviews"
    dependencies = ["projects"]
    
    def get_queryset(self):
        """Return all project reviews."""
        try:
            from coldfront.core.project.models import ProjectReview
            return ProjectReview.objects.select_related(
                "project",
                "status",
            ).order_by("project__title", "-created")
        except ImportError:
            from django.db.models import QuerySet
            return QuerySet().none()
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize ProjectReview to dict."""
        return {
            "natural_key": (instance.project.title, str(instance.created)),
            "fields": {
                "project_title": instance.project.title,
                "status": instance.status.name if instance.status else None,
                "reason_for_not_updating_project": getattr(
                    instance, "reason_for_not_updating_project", ""
                ),
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }

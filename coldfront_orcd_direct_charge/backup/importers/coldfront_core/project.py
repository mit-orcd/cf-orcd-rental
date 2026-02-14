# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Importers for ColdFront project models.

Models imported:
    - FieldOfScience: Field of science reference data
    - ProjectStatusChoice: Project status options
    - Project: Projects
    - ProjectUserRoleChoice: Project user role options
    - ProjectUserStatusChoice: Project user status options
    - ProjectUser: Project memberships
    - ProjectReview: Project review history
"""

from typing import Any, Dict, Optional

from ...base import BaseImporter
from ...registry import CoreImporterRegistry
from ...utils import deserialize_datetime


@CoreImporterRegistry.register
class FieldOfScienceImporter(BaseImporter):
    """Importer for FieldOfScience model."""
    
    model_name = "field_of_science"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by description."""
        try:
            from coldfront.core.field_of_science.models import FieldOfScience
            description = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
            return FieldOfScience.objects.get(description=description)
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create FieldOfScience instance."""
        try:
            from coldfront.core.field_of_science.models import FieldOfScience
            fields = data.get("fields", {})
            return FieldOfScience(
                description=fields.get("description"),
                is_selectable=fields.get("is_selectable", True),
            )
        except ImportError:
            return None
    
    def create_or_update(
        self, 
        data: Dict[str, Any], 
        existing: Optional[Any] = None,
        mode: str = "create-or-update",
    ) -> Optional[Any]:
        """Create or update field of science."""
        if existing:
            if mode == "create-only":
                return None
            fields = data.get("fields", {})
            existing.is_selectable = fields.get("is_selectable", existing.is_selectable)
            existing.save()
            return existing
        else:
            if mode == "update-only":
                return None
            instance = self.deserialize_record(data)
            if instance:
                instance.save()
            return instance
    
    def create_record(self, data: Dict[str, Any]) -> Any:
        """Create new record."""
        return self.create_or_update(data, existing=None, mode="create-only")
    
    def update_record(self, existing: Any, data: Dict[str, Any]) -> Any:
        """Update existing record."""
        return self.create_or_update(data, existing=existing, mode="update-only")


@CoreImporterRegistry.register
class ProjectStatusImporter(BaseImporter):
    """Importer for ProjectStatusChoice model."""
    
    model_name = "project_statuses"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by name."""
        try:
            from coldfront.core.project.models import ProjectStatusChoice
            name = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
            return ProjectStatusChoice.objects.get(name=name)
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create ProjectStatusChoice instance."""
        try:
            from coldfront.core.project.models import ProjectStatusChoice
            fields = data.get("fields", {})
            return ProjectStatusChoice(name=fields.get("name"))
        except ImportError:
            return None
    
    def create_or_update(
        self, 
        data: Dict[str, Any], 
        existing: Optional[Any] = None,
        mode: str = "create-or-update",
    ) -> Optional[Any]:
        """Create or update status (usually exists from fixtures)."""
        if existing:
            return existing  # Don't modify existing statuses
        if mode == "update-only":
            return None
        instance = self.deserialize_record(data)
        if instance:
            instance.save()
        return instance
    
    def create_record(self, data: Dict[str, Any]) -> Any:
        """Create new record."""
        return self.create_or_update(data, existing=None, mode="create-only")
    
    def update_record(self, existing: Any, data: Dict[str, Any]) -> Any:
        """Update existing record."""
        return self.create_or_update(data, existing=existing, mode="update-only")


@CoreImporterRegistry.register
class ProjectImporter(BaseImporter):
    """Importer for ColdFront Project model."""
    
    model_name = "projects"
    dependencies = ["users", "field_of_science", "project_statuses"]
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by title."""
        try:
            from coldfront.core.project.models import Project
            title = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
            return Project.objects.get(title=title)
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create Project instance."""
        try:
            from coldfront.core.project.models import Project, ProjectStatusChoice
            from coldfront.core.field_of_science.models import FieldOfScience
            from django.contrib.auth.models import User
            
            fields = data.get("fields", {})
            
            # Resolve foreign keys
            pi = None
            if fields.get("pi_username"):
                try:
                    pi = User.objects.get(username=fields["pi_username"])
                except User.DoesNotExist:
                    pass
            
            fos = None
            if fields.get("field_of_science"):
                try:
                    fos = FieldOfScience.objects.get(
                        description=fields["field_of_science"]
                    )
                except FieldOfScience.DoesNotExist:
                    pass
            
            status = None
            if fields.get("status"):
                try:
                    status = ProjectStatusChoice.objects.get(name=fields["status"])
                except ProjectStatusChoice.DoesNotExist:
                    pass
            
            return Project(
                title=fields.get("title"),
                description=fields.get("description", ""),
                pi=pi,
                field_of_science=fos,
                status=status,
            )
        except ImportError:
            return None
    
    @staticmethod
    def _restore_timestamps(project, fields: Dict[str, Any]):
        """Restore created/modified timestamps using queryset.update().
        
        TimeStampedModel uses auto_now_add and auto_now which prevent
        normal field assignment.  queryset.update() bypasses this.
        """
        from coldfront.core.project.models import Project

        update_fields = {}
        created_dt = deserialize_datetime(fields.get("created"))
        if created_dt is not None:
            update_fields["created"] = created_dt
        modified_dt = deserialize_datetime(fields.get("modified"))
        if modified_dt is not None:
            update_fields["modified"] = modified_dt
        if update_fields:
            Project.objects.filter(pk=project.pk).update(**update_fields)
    
    def create_or_update(
        self, 
        data: Dict[str, Any], 
        existing: Optional[Any] = None,
        mode: str = "create-or-update",
    ) -> Optional[Any]:
        """Create or update project."""
        try:
            from coldfront.core.project.models import ProjectStatusChoice
            from coldfront.core.field_of_science.models import FieldOfScience
            from django.contrib.auth.models import User
            
            fields = data.get("fields", {})
            
            if existing:
                if mode == "create-only":
                    return None
                
                # Update existing project
                existing.description = fields.get("description", existing.description)
                
                if fields.get("pi_username"):
                    try:
                        existing.pi = User.objects.get(username=fields["pi_username"])
                    except User.DoesNotExist:
                        pass
                
                if fields.get("status"):
                    try:
                        existing.status = ProjectStatusChoice.objects.get(
                            name=fields["status"]
                        )
                    except ProjectStatusChoice.DoesNotExist:
                        pass
                
                existing.save()
                self._restore_timestamps(existing, fields)
                return existing
            else:
                if mode == "update-only":
                    return None
                instance = self.deserialize_record(data)
                if instance:
                    instance.save()
                    self._restore_timestamps(instance, fields)
                return instance
        except ImportError:
            return None
    
    def create_record(self, data: Dict[str, Any]) -> Any:
        """Create new record."""
        return self.create_or_update(data, existing=None, mode="create-only")
    
    def update_record(self, existing: Any, data: Dict[str, Any]) -> Any:
        """Update existing record."""
        return self.create_or_update(data, existing=existing, mode="update-only")


@CoreImporterRegistry.register
class ProjectUserRoleImporter(BaseImporter):
    """Importer for ProjectUserRoleChoice model."""
    
    model_name = "project_user_roles"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by name."""
        try:
            from coldfront.core.project.models import ProjectUserRoleChoice
            name = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
            return ProjectUserRoleChoice.objects.get(name=name)
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create ProjectUserRoleChoice instance."""
        try:
            from coldfront.core.project.models import ProjectUserRoleChoice
            fields = data.get("fields", {})
            return ProjectUserRoleChoice(name=fields.get("name"))
        except ImportError:
            return None
    
    def create_or_update(
        self, 
        data: Dict[str, Any], 
        existing: Optional[Any] = None,
        mode: str = "create-or-update",
    ) -> Optional[Any]:
        """Create or update role (usually exists from fixtures)."""
        if existing:
            return existing
        if mode == "update-only":
            return None
        instance = self.deserialize_record(data)
        if instance:
            instance.save()
        return instance
    
    def create_record(self, data: Dict[str, Any]) -> Any:
        """Create new record."""
        return self.create_or_update(data, existing=None, mode="create-only")
    
    def update_record(self, existing: Any, data: Dict[str, Any]) -> Any:
        """Update existing record."""
        return self.create_or_update(data, existing=existing, mode="update-only")


@CoreImporterRegistry.register
class ProjectUserStatusImporter(BaseImporter):
    """Importer for ProjectUserStatusChoice model."""
    
    model_name = "project_user_statuses"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by name."""
        try:
            from coldfront.core.project.models import ProjectUserStatusChoice
            name = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
            return ProjectUserStatusChoice.objects.get(name=name)
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create ProjectUserStatusChoice instance."""
        try:
            from coldfront.core.project.models import ProjectUserStatusChoice
            fields = data.get("fields", {})
            return ProjectUserStatusChoice(name=fields.get("name"))
        except ImportError:
            return None
    
    def create_or_update(
        self, 
        data: Dict[str, Any], 
        existing: Optional[Any] = None,
        mode: str = "create-or-update",
    ) -> Optional[Any]:
        """Create or update status (usually exists from fixtures)."""
        if existing:
            return existing
        if mode == "update-only":
            return None
        instance = self.deserialize_record(data)
        if instance:
            instance.save()
        return instance
    
    def create_record(self, data: Dict[str, Any]) -> Any:
        """Create new record."""
        return self.create_or_update(data, existing=None, mode="create-only")
    
    def update_record(self, existing: Any, data: Dict[str, Any]) -> Any:
        """Update existing record."""
        return self.create_or_update(data, existing=existing, mode="update-only")


@CoreImporterRegistry.register
class ProjectUserImporter(BaseImporter):
    """Importer for ProjectUser model (project memberships)."""
    
    model_name = "project_users"
    dependencies = ["projects", "users", "project_user_roles", "project_user_statuses"]
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by project and user."""
        try:
            from coldfront.core.project.models import Project, ProjectUser
            from django.contrib.auth.models import User
            
            project_title, username = natural_key
            project = Project.objects.get(title=project_title)
            user = User.objects.get(username=username)
            return ProjectUser.objects.get(project=project, user=user)
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create ProjectUser instance."""
        try:
            from coldfront.core.project.models import (
                Project, ProjectUser, 
                ProjectUserRoleChoice, ProjectUserStatusChoice
            )
            from django.contrib.auth.models import User
            
            fields = data.get("fields", {})
            
            project = Project.objects.get(title=fields["project_title"])
            user = User.objects.get(username=fields["username"])
            
            role = None
            if fields.get("role"):
                try:
                    role = ProjectUserRoleChoice.objects.get(name=fields["role"])
                except ProjectUserRoleChoice.DoesNotExist:
                    pass
            
            status = None
            if fields.get("status"):
                try:
                    status = ProjectUserStatusChoice.objects.get(name=fields["status"])
                except ProjectUserStatusChoice.DoesNotExist:
                    pass
            
            return ProjectUser(
                project=project,
                user=user,
                role=role,
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
        """Create or update project user."""
        try:
            from coldfront.core.project.models import (
                ProjectUserRoleChoice, ProjectUserStatusChoice
            )
            
            fields = data.get("fields", {})
            
            if existing:
                if mode == "create-only":
                    return None
                
                if fields.get("role"):
                    try:
                        existing.role = ProjectUserRoleChoice.objects.get(
                            name=fields["role"]
                        )
                    except ProjectUserRoleChoice.DoesNotExist:
                        pass
                
                if fields.get("status"):
                    try:
                        existing.status = ProjectUserStatusChoice.objects.get(
                            name=fields["status"]
                        )
                    except ProjectUserStatusChoice.DoesNotExist:
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
    
    def create_record(self, data: Dict[str, Any]) -> Any:
        """Create new record."""
        return self.create_or_update(data, existing=None, mode="create-only")
    
    def update_record(self, existing: Any, data: Dict[str, Any]) -> Any:
        """Update existing record."""
        return self.create_or_update(data, existing=existing, mode="update-only")


@CoreImporterRegistry.register
class ProjectReviewImporter(BaseImporter):
    """Importer for ProjectReview model."""
    
    model_name = "project_reviews"
    dependencies = ["projects"]
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by project and created timestamp."""
        try:
            from coldfront.core.project.models import Project, ProjectReview
            
            project_title, created_str = natural_key
            project = Project.objects.get(title=project_title)
            # Reviews are typically identified by project + creation time
            return ProjectReview.objects.filter(
                project=project
            ).order_by("-created").first()
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create ProjectReview instance."""
        try:
            from coldfront.core.project.models import (
                Project, ProjectReview, ProjectReviewStatusChoice
            )
            
            fields = data.get("fields", {})
            
            project = Project.objects.get(title=fields["project_title"])
            
            status = None
            if fields.get("status"):
                try:
                    status = ProjectReviewStatusChoice.objects.get(
                        name=fields["status"]
                    )
                except Exception:
                    pass
            
            return ProjectReview(
                project=project,
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
        """Create or update project review."""
        if existing:
            return existing  # Don't modify existing reviews
        
        if mode == "update-only":
            return None
        
        instance = self.deserialize_record(data)
        if instance:
            instance.save()
        return instance
    
    def create_record(self, data: Dict[str, Any]) -> Any:
        """Create new record."""
        return self.create_or_update(data, existing=None, mode="create-only")
    
    def update_record(self, existing: Any, data: Dict[str, Any]) -> Any:
        """Update existing record."""
        return self.create_or_update(data, existing=existing, mode="update-only")

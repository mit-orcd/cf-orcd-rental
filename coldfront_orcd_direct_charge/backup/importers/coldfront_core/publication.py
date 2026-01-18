# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Importers for ColdFront publication and grant models.

Models imported:
    - PublicationSource: Publication sources
    - Publication: Research publications
    - GrantFundingAgency: Grant funding agencies
    - GrantStatusChoice: Grant status options
    - Grant: Research grants
"""

from typing import Any, Dict, Optional

from ...base import BaseImporter
from ...registry import CoreImporterRegistry
from ...utils import deserialize_date, deserialize_decimal


@CoreImporterRegistry.register
class PublicationSourceImporter(BaseImporter):
    """Importer for PublicationSource model."""
    
    model_name = "publication_sources"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by name."""
        try:
            from coldfront.core.publication.models import PublicationSource
            name = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
            return PublicationSource.objects.get(name=name)
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create PublicationSource instance."""
        try:
            from coldfront.core.publication.models import PublicationSource
            fields = data.get("fields", {})
            return PublicationSource(
                name=fields.get("name"),
                url=fields.get("url", ""),
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
            if mode == "create-only":
                return None
            fields = data.get("fields", {})
            existing.url = fields.get("url", existing.url)
            existing.save()
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
class PublicationImporter(BaseImporter):
    """Importer for Publication model."""
    
    model_name = "publications"
    dependencies = ["projects", "publication_sources"]
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by unique_id."""
        try:
            from coldfront.core.publication.models import Publication
            unique_id = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
            return Publication.objects.get(unique_id=unique_id)
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create Publication instance."""
        try:
            from coldfront.core.publication.models import Publication, PublicationSource
            from coldfront.core.project.models import Project
            
            fields = data.get("fields", {})
            
            project = Project.objects.get(title=fields["project_title"])
            
            source = None
            if fields.get("source"):
                try:
                    source = PublicationSource.objects.get(name=fields["source"])
                except PublicationSource.DoesNotExist:
                    pass
            
            return Publication(
                project=project,
                title=fields.get("title", ""),
                author=fields.get("author", ""),
                year=fields.get("year"),
                journal=fields.get("journal", ""),
                source=source,
                unique_id=fields.get("unique_id"),
            )
        except Exception:
            return None
    
    def create_or_update(
        self, 
        data: Dict[str, Any], 
        existing: Optional[Any] = None,
        mode: str = "create-or-update",
    ) -> Optional[Any]:
        """Create or update publication."""
        fields = data.get("fields", {})
        
        if existing:
            if mode == "create-only":
                return None
            
            existing.title = fields.get("title", existing.title)
            existing.author = fields.get("author", existing.author)
            existing.year = fields.get("year", existing.year)
            existing.journal = fields.get("journal", existing.journal)
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
class GrantFundingAgencyImporter(BaseImporter):
    """Importer for GrantFundingAgency model."""
    
    model_name = "grant_funding_agencies"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by name."""
        try:
            from coldfront.core.grant.models import GrantFundingAgency
            name = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
            return GrantFundingAgency.objects.get(name=name)
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create GrantFundingAgency instance."""
        try:
            from coldfront.core.grant.models import GrantFundingAgency
            fields = data.get("fields", {})
            return GrantFundingAgency(name=fields.get("name"))
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
    
    def create_record(self, data: Dict[str, Any]) -> Any:
        """Create new record."""
        return self.create_or_update(data, existing=None, mode="create-only")
    
    def update_record(self, existing: Any, data: Dict[str, Any]) -> Any:
        """Update existing record."""
        return self.create_or_update(data, existing=existing, mode="update-only")


@CoreImporterRegistry.register
class GrantStatusImporter(BaseImporter):
    """Importer for GrantStatusChoice model."""
    
    model_name = "grant_statuses"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by name."""
        try:
            from coldfront.core.grant.models import GrantStatusChoice
            name = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
            return GrantStatusChoice.objects.get(name=name)
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create GrantStatusChoice instance."""
        try:
            from coldfront.core.grant.models import GrantStatusChoice
            fields = data.get("fields", {})
            return GrantStatusChoice(name=fields.get("name"))
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
    
    def create_record(self, data: Dict[str, Any]) -> Any:
        """Create new record."""
        return self.create_or_update(data, existing=None, mode="create-only")
    
    def update_record(self, existing: Any, data: Dict[str, Any]) -> Any:
        """Update existing record."""
        return self.create_or_update(data, existing=existing, mode="update-only")


@CoreImporterRegistry.register
class GrantImporter(BaseImporter):
    """Importer for Grant model."""
    
    model_name = "grants"
    dependencies = ["projects", "grant_funding_agencies", "grant_statuses"]
    
    def get_existing(self, natural_key) -> Optional[Any]:
        """Look up by title and project."""
        try:
            from coldfront.core.grant.models import Grant
            from coldfront.core.project.models import Project
            
            title, project_title = natural_key
            project = Project.objects.get(title=project_title)
            return Grant.objects.get(title=title, project=project)
        except Exception:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> Any:
        """Create Grant instance."""
        try:
            from coldfront.core.grant.models import (
                Grant, GrantFundingAgency, GrantStatusChoice
            )
            from coldfront.core.project.models import Project
            from decimal import Decimal
            
            fields = data.get("fields", {})
            
            project = Project.objects.get(title=fields["project_title"])
            
            funding_agency = None
            if fields.get("funding_agency"):
                try:
                    funding_agency = GrantFundingAgency.objects.get(
                        name=fields["funding_agency"]
                    )
                except GrantFundingAgency.DoesNotExist:
                    pass
            
            status = None
            if fields.get("status"):
                try:
                    status = GrantStatusChoice.objects.get(name=fields["status"])
                except GrantStatusChoice.DoesNotExist:
                    pass
            
            return Grant(
                project=project,
                title=fields.get("title", ""),
                grant_number=fields.get("grant_number", ""),
                funding_agency=funding_agency,
                grant_pi_full_name=fields.get("grant_pi_full_name", ""),
                role=fields.get("role", ""),
                status=status,
                total_amount_awarded=deserialize_decimal(
                    fields.get("total_amount_awarded")
                ) or Decimal("0"),
                direct_funding=deserialize_decimal(
                    fields.get("direct_funding")
                ) or Decimal("0"),
                start_date=deserialize_date(fields.get("start_date")),
                end_date=deserialize_date(fields.get("end_date")),
                percent_credit=deserialize_decimal(
                    fields.get("percent_credit")
                ) or Decimal("100"),
            )
        except Exception:
            return None
    
    def create_or_update(
        self, 
        data: Dict[str, Any], 
        existing: Optional[Any] = None,
        mode: str = "create-or-update",
    ) -> Optional[Any]:
        """Create or update grant."""
        fields = data.get("fields", {})
        
        if existing:
            if mode == "create-only":
                return None
            
            existing.grant_number = fields.get("grant_number", existing.grant_number)
            existing.grant_pi_full_name = fields.get(
                "grant_pi_full_name", existing.grant_pi_full_name
            )
            existing.role = fields.get("role", existing.role)
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

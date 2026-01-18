# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Exporters for ColdFront publication and grant models.

Models exported:
    - Publication: Research publications
    - Grant: Research grants
"""

from typing import Any, Dict

from ...base import BaseExporter
from ...registry import CoreExporterRegistry
from ...utils import serialize_datetime, serialize_date


@CoreExporterRegistry.register
class PublicationSourceExporter(BaseExporter):
    """Exporter for PublicationSource model."""
    
    model_name = "publication_sources"
    dependencies = []
    
    def get_queryset(self):
        """Return all publication sources."""
        try:
            from coldfront.core.publication.models import PublicationSource
            return PublicationSource.objects.all().order_by("name")
        except ImportError:
            from django.db.models import QuerySet
            return QuerySet().none()
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize PublicationSource to dict."""
        return {
            "natural_key": (instance.name,),
            "fields": {
                "name": instance.name,
                "url": getattr(instance, "url", ""),
            }
        }


@CoreExporterRegistry.register
class PublicationExporter(BaseExporter):
    """Exporter for Publication model."""
    
    model_name = "publications"
    dependencies = ["projects", "publication_sources"]
    
    def get_queryset(self):
        """Return all publications."""
        try:
            from coldfront.core.publication.models import Publication
            return Publication.objects.select_related(
                "project",
                "source",
                "status",
            ).order_by("project__title", "title")
        except ImportError:
            from django.db.models import QuerySet
            return QuerySet().none()
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize Publication to dict."""
        unique_id = getattr(instance, "unique_id", None) or str(instance.pk)
        return {
            "natural_key": (unique_id,),
            "fields": {
                "unique_id": unique_id,
                "project_title": instance.project.title,
                "title": instance.title,
                "author": getattr(instance, "author", ""),
                "year": getattr(instance, "year", None),
                "journal": getattr(instance, "journal", ""),
                "source": instance.source.name if instance.source else None,
                "status": instance.status.name if instance.status else None,
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }


@CoreExporterRegistry.register
class GrantFundingAgencyExporter(BaseExporter):
    """Exporter for GrantFundingAgency model."""
    
    model_name = "grant_funding_agencies"
    dependencies = []
    
    def get_queryset(self):
        """Return all grant funding agencies."""
        try:
            from coldfront.core.grant.models import GrantFundingAgency
            return GrantFundingAgency.objects.all().order_by("name")
        except ImportError:
            from django.db.models import QuerySet
            return QuerySet().none()
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize GrantFundingAgency to dict."""
        return {
            "natural_key": (instance.name,),
            "fields": {
                "name": instance.name,
            }
        }


@CoreExporterRegistry.register
class GrantStatusExporter(BaseExporter):
    """Exporter for GrantStatusChoice model."""
    
    model_name = "grant_statuses"
    dependencies = []
    
    def get_queryset(self):
        """Return all grant statuses."""
        try:
            from coldfront.core.grant.models import GrantStatusChoice
            return GrantStatusChoice.objects.all().order_by("name")
        except ImportError:
            from django.db.models import QuerySet
            return QuerySet().none()
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize GrantStatusChoice to dict."""
        return {
            "natural_key": (instance.name,),
            "fields": {
                "name": instance.name,
            }
        }


@CoreExporterRegistry.register
class GrantExporter(BaseExporter):
    """Exporter for Grant model."""
    
    model_name = "grants"
    dependencies = ["projects", "grant_funding_agencies", "grant_statuses"]
    
    def get_queryset(self):
        """Return all grants."""
        try:
            from coldfront.core.grant.models import Grant
            return Grant.objects.select_related(
                "project",
                "funding_agency",
                "status",
            ).order_by("project__title", "title")
        except ImportError:
            from django.db.models import QuerySet
            return QuerySet().none()
    
    def serialize_record(self, instance) -> Dict[str, Any]:
        """Serialize Grant to dict."""
        return {
            "natural_key": (instance.title, instance.project.title),
            "fields": {
                "title": instance.title,
                "project_title": instance.project.title,
                "grant_number": getattr(instance, "grant_number", ""),
                "funding_agency": (
                    instance.funding_agency.name 
                    if instance.funding_agency else None
                ),
                "grant_pi_full_name": getattr(instance, "grant_pi_full_name", ""),
                "role": getattr(instance, "role", ""),
                "status": instance.status.name if instance.status else None,
                "total_amount_awarded": str(
                    getattr(instance, "total_amount_awarded", 0)
                ),
                "direct_funding": str(
                    getattr(instance, "direct_funding", 0)
                ),
                "start_date": serialize_date(
                    getattr(instance, "start_date", None)
                ),
                "end_date": serialize_date(
                    getattr(instance, "end_date", None)
                ),
                "percent_credit": str(
                    getattr(instance, "percent_credit", 100)
                ),
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }

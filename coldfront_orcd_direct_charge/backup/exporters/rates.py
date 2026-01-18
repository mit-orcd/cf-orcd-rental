# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Exporters for rate management models.

Models exported:
    - RentalSKU: Rentable items/services
    - RentalRate: Historical rates for SKUs
"""

from typing import Any, Dict

from ..base import BaseExporter
from ..registry import ExporterRegistry
from ..utils import serialize_datetime, serialize_date, serialize_decimal
from ...models import RentalSKU, RentalRate


@ExporterRegistry.register
class RentalSKUExporter(BaseExporter):
    """Exporter for RentalSKU model.
    
    SKUs define billable items with their types and billing units.
    """
    
    model_name = "rental_skus"
    dependencies = []
    
    def get_queryset(self):
        """Return all SKUs ordered by type and name."""
        return RentalSKU.objects.all().order_by("sku_type", "name")
    
    def serialize_record(self, instance: RentalSKU) -> Dict[str, Any]:
        """Serialize RentalSKU to dict.
        
        Uses sku_code as natural key since it's unique.
        """
        return {
            "natural_key": (instance.sku_code,),
            "fields": {
                "sku_code": instance.sku_code,
                "name": instance.name,
                "description": instance.description,
                "sku_type": instance.sku_type,
                "billing_unit": instance.billing_unit,
                "is_active": instance.is_active,
                "linked_model": instance.linked_model,
                "is_public": instance.is_public,
                "metadata": instance.metadata,
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }


@ExporterRegistry.register
class RentalRateExporter(BaseExporter):
    """Exporter for RentalRate model.
    
    Rates track historical pricing for SKUs.
    """
    
    model_name = "rental_rates"
    dependencies = ["rental_skus"]
    
    def get_queryset(self):
        """Return all rates with related SKU."""
        return RentalRate.objects.select_related(
            "sku",
            "set_by",
        ).order_by("sku__sku_code", "-effective_date")
    
    def serialize_record(self, instance: RentalRate) -> Dict[str, Any]:
        """Serialize RentalRate to dict.
        
        Uses sku_code + effective_date as natural key.
        """
        return {
            "natural_key": (instance.sku.sku_code, str(instance.effective_date)),
            "fields": {
                "sku_code": instance.sku.sku_code,
                "rate": serialize_decimal(instance.rate),
                "effective_date": serialize_date(instance.effective_date),
                "set_by_username": (
                    instance.set_by.username 
                    if instance.set_by else None
                ),
                "notes": instance.notes,
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }

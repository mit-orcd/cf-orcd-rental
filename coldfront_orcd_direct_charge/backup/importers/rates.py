# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Importers for rate management models.

Models imported:
    - RentalSKU: Rentable items/services
    - RentalRate: Historical rates for SKUs
"""

from decimal import Decimal
from typing import Any, Dict, Optional
import logging

from django.contrib.auth.models import User

from ..base import BaseImporter
from ..registry import ImporterRegistry
from ..utils import deserialize_date, deserialize_decimal
from ...models import RentalSKU, RentalRate

logger = logging.getLogger(__name__)


def get_user_by_username(username: str) -> Optional[User]:
    """Get user by username."""
    if not username:
        return None
    try:
        return User.objects.get(username=username)
    except User.DoesNotExist:
        return None


@ImporterRegistry.register
class RentalSKUImporter(BaseImporter):
    """Importer for RentalSKU model.
    
    Uses sku_code as natural key.
    """
    
    model_name = "rental_skus"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[RentalSKU]:
        """Find existing RentalSKU by sku_code."""
        if not natural_key:
            return None
        
        sku_code = natural_key[0] if isinstance(natural_key, (list, tuple)) else natural_key
        
        try:
            return RentalSKU.objects.get(sku_code=sku_code)
        except RentalSKU.DoesNotExist:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> RentalSKU:
        """Create unsaved RentalSKU from data."""
        fields = data.get("fields", {})
        
        return RentalSKU(
            sku_code=fields.get("sku_code"),
            name=fields.get("name", ""),
            description=fields.get("description", ""),
            sku_type=fields.get("sku_type"),
            billing_unit=fields.get("billing_unit"),
            is_active=fields.get("is_active", True),
            linked_model=fields.get("linked_model", ""),
            is_public=fields.get("is_public", True),
            metadata=fields.get("metadata", {}),
        )
    
    def create_record(self, data: Dict[str, Any]) -> RentalSKU:
        """Create and save new RentalSKU."""
        instance = self.deserialize_record(data)
        instance.save()
        logger.debug(f"Created RentalSKU: {instance.sku_code}")
        return instance
    
    def update_record(
        self, existing: RentalSKU, data: Dict[str, Any]
    ) -> RentalSKU:
        """Update existing RentalSKU."""
        fields = data.get("fields", {})
        
        existing.name = fields.get("name", existing.name)
        existing.description = fields.get("description", existing.description)
        existing.sku_type = fields.get("sku_type", existing.sku_type)
        existing.billing_unit = fields.get("billing_unit", existing.billing_unit)
        existing.is_active = fields.get("is_active", existing.is_active)
        existing.linked_model = fields.get("linked_model", existing.linked_model)
        existing.is_public = fields.get("is_public", existing.is_public)
        existing.metadata = fields.get("metadata", existing.metadata)
        
        existing.save()
        logger.debug(f"Updated RentalSKU: {existing.sku_code}")
        return existing


@ImporterRegistry.register
class RentalRateImporter(BaseImporter):
    """Importer for RentalRate model.
    
    Uses sku_code + effective_date as natural key.
    """
    
    model_name = "rental_rates"
    dependencies = ["rental_skus"]
    
    def get_existing(self, natural_key) -> Optional[RentalRate]:
        """Find existing RentalRate by sku_code + effective_date."""
        if not natural_key or len(natural_key) < 2:
            return None
        
        sku_code, effective_date_str = natural_key
        
        try:
            sku = RentalSKU.objects.get(sku_code=sku_code)
        except RentalSKU.DoesNotExist:
            return None
        
        effective_date = deserialize_date(effective_date_str)
        if not effective_date:
            return None
        
        try:
            return RentalRate.objects.get(sku=sku, effective_date=effective_date)
        except RentalRate.DoesNotExist:
            return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> RentalRate:
        """Create unsaved RentalRate from data."""
        fields = data.get("fields", {})
        
        sku_code = fields.get("sku_code")
        try:
            sku = RentalSKU.objects.get(sku_code=sku_code)
        except RentalSKU.DoesNotExist:
            raise ValueError(f"RentalSKU not found: {sku_code}")
        
        rate = deserialize_decimal(fields.get("rate"))
        if rate is None:
            rate = Decimal("0")
        
        set_by = get_user_by_username(fields.get("set_by_username"))
        
        return RentalRate(
            sku=sku,
            rate=rate,
            effective_date=deserialize_date(fields.get("effective_date")),
            set_by=set_by,
            notes=fields.get("notes", ""),
        )
    
    def create_record(self, data: Dict[str, Any]) -> RentalRate:
        """Create and save new RentalRate."""
        instance = self.deserialize_record(data)
        instance.save()
        logger.debug(
            f"Created RentalRate: {instance.sku.sku_code} @ {instance.effective_date}"
        )
        return instance
    
    def update_record(
        self, existing: RentalRate, data: Dict[str, Any]
    ) -> RentalRate:
        """Update existing RentalRate.
        
        Note: Rates are generally immutable, but we can update notes.
        """
        fields = data.get("fields", {})
        
        existing.notes = fields.get("notes", existing.notes)
        existing.save()
        
        logger.debug(
            f"Updated RentalRate: {existing.sku.sku_code} @ {existing.effective_date}"
        )
        return existing

# Current Rates Views

This document describes the public-facing rates views. These views are accessible to all logged-in users (no special permission required).

---

## CurrentRatesView

**URL**: `/nodes/rates/current/`  
**Name**: `coldfront_orcd_direct_charge:current-rates`  
**Template**: `coldfront_orcd_direct_charge/current_rates.html`  
**Module**: `views/rates.py`

Public-facing page showing current pricing for all visible SKUs.

**Context Variables**:
- `node_skus` - Public node SKUs with current rates
- `maintenance_skus` - Public maintenance fee SKUs
- `qos_skus` - Public QoS SKUs
- `filter_options` - Dynamic filter options from metadata

**UI Features**:
- Card-based layout grouped by category
- Dynamic filtering by metadata attributes (GPU type, memory, etc.)
- Upcoming rate change badges
- "Rates" link in navbar for all logged-in users

---

## SKUPublicDetailView

**URL**: `/nodes/rates/current/<pk>/`  
**Name**: `coldfront_orcd_direct_charge:sku-public-detail`  
**Template**: `coldfront_orcd_direct_charge/sku_public_detail.html`  
**Module**: `views/rates.py`

Public detail page for a specific SKU showing current rate and metadata.

**Context Variables**:
- `sku` - The RentalSKU object
- `current_rate` - Current effective rate
- `upcoming_rate` - Next scheduled rate change (if any)

---

[← Back to Views and URL Routing](README.md)

# Rate Management Views

This document describes views for rate managers. These views require `can_manage_rates` permission.

> **Note**: See [RATE_MANAGER.md](../RATE_MANAGER.md) for comprehensive documentation on the Rate Manager feature.

---

## RateManagementView

**URL**: `/nodes/rates/`  
**Name**: `coldfront_orcd_direct_charge:rate-management`  
**Template**: `coldfront_orcd_direct_charge/rate_management.html`  
**Module**: `views/rates.py`

Dashboard showing all SKUs grouped by type (NODE, MAINTENANCE, QOS).

**Context Variables**:
- `node_skus` - SKUs for node rentals (H200x8, L40Sx4, etc.)
- `maintenance_skus` - SKUs for maintenance fees (Basic, Advanced)
- `qos_skus` - Custom QoS configuration SKUs

---

## SKURateDetailView

**URL**: `/nodes/rates/sku/<pk>/`  
**Name**: `coldfront_orcd_direct_charge:sku-rate-detail`  
**Template**: `coldfront_orcd_direct_charge/sku_rate_detail.html`  
**Module**: `views/rates.py`

Shows complete rate history for a specific SKU.

**Context Variables**:
- `sku` - The RentalSKU object
- `rates` - All rates for this SKU, ordered by effective_date descending
- `current_rate` - Current effective rate (if any)

---

## AddRateView

**URL**: `/nodes/rates/sku/<pk>/add/`  
**Name**: `coldfront_orcd_direct_charge:add-rate`  
**Template**: `coldfront_orcd_direct_charge/add_rate_form.html`  
**Module**: `views/rates.py`

Form to add a new rate for an existing SKU.

**Form Fields**:
- `rate` - Decimal rate value
- `effective_date` - When the rate takes effect

---

## CreateSKUView

**URL**: `/nodes/rates/sku/create/`  
**Name**: `coldfront_orcd_direct_charge:create-sku`  
**Template**: `coldfront_orcd_direct_charge/create_sku_form.html`  
**Module**: `views/rates.py`

Form to create a new custom QoS SKU.

**Form Fields**:
- `sku_code` - Unique identifier (e.g., "QOS_PREMIUM")
- `name` - Display name
- `description` - Optional description
- `billing_unit` - HOURLY or MONTHLY

---

## ToggleSKUVisibilityView

**URL**: `/nodes/rates/sku/<pk>/visibility/`  
**Name**: `coldfront_orcd_direct_charge:toggle-sku-visibility`  
**Module**: `views/rates.py`

AJAX endpoint to toggle SKU visibility on Current Rates page. Requires `can_manage_rates` permission.

**Response** (JSON):
```json
{
    "success": true,
    "is_public": true
}
```

---

[← Back to Views and URL Routing](README.md)

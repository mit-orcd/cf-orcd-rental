# Rate Manager Feature

This document describes the Rate Manager feature of the ORCD Direct Charge plugin, including technical implementation details, user features, and design rationale.

**Source Files:**
- Models: [`coldfront_orcd_direct_charge/models.py`](../coldfront_orcd_direct_charge/models.py)
- Views: [`coldfront_orcd_direct_charge/views.py`](../coldfront_orcd_direct_charge/views.py)
- Forms: [`coldfront_orcd_direct_charge/forms.py`](../coldfront_orcd_direct_charge/forms.py)
- URLs: [`coldfront_orcd_direct_charge/urls.py`](../coldfront_orcd_direct_charge/urls.py)
- Templates: [`templates/coldfront_orcd_direct_charge/`](../coldfront_orcd_direct_charge/templates/coldfront_orcd_direct_charge/)

---

## Table of Contents

- [Feature Overview](#feature-overview)
- [Data Models](#data-models)
  - [RentalSKU](#rentalsku)
  - [RentalRate](#rentalrate)
- [Current Rates Page](#current-rates-page)
- [SKU Types](#sku-types)
- [Rate History and Effective Dates](#rate-history-and-effective-dates)
- [Permission System](#permission-system)
- [Activity Logging](#activity-logging)
- [UI Components](#ui-components)
- [URL Reference](#url-reference)
- [Management Commands](#management-commands)
- [Integration with Invoice System](#integration-with-invoice-system)
- [Design Decisions](#design-decisions)

---

## Feature Overview

The Rate Manager feature allows designated Rate Managers to maintain charging rates for all rentable items in the system. This includes:

- **Node Rentals** - Hourly rates for GPU and CPU node reservations
- **Account Maintenance Fees** - Monthly subscription fees for user accounts
- **Rentable QoS** - Custom Quality of Service packages with monthly billing

### Key Capabilities

1. **Rate History** - All rate changes are preserved with effective dates, enabling accurate historical billing
2. **Future Rate Scheduling** - Rates can be set with future effective dates to schedule changes
3. **Audit Trail** - All rate changes are logged to the ActivityLog for compliance
4. **Custom SKUs** - Rate Managers can create new SKUs for custom QoS configurations

### Business Context

The Rate Manager role is separate from other administrative roles:
- **Rental Managers** handle reservation approvals
- **Billing Managers** handle cost allocation approvals and invoice preparation
- **Rate Managers** set and maintain the rates used for billing calculations

This separation of duties ensures proper controls over pricing decisions.

---

## Data Models

### Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        RentalSKU                                 │
├─────────────────────────────────────────────────────────────────┤
│ id           │ PK                                                │
│ sku_code     │ Unique identifier (e.g., "NODE_H200x8")           │
│ name         │ Display name (e.g., "H200x8 Node")                │
│ description  │ Optional description                              │
│ sku_type     │ Choice: NODE, MAINTENANCE, QOS                    │
│ billing_unit │ Choice: HOURLY, MONTHLY                           │
│ is_active    │ Boolean                                           │
│ is_public    │ Boolean (visible on Current Rates page)           │
│ linked_model │ Optional: "NodeType:H200x8" for auto-linking      │
│ metadata     │ JSONField (flexible attributes for filtering)     │
│ created      │ Timestamp                                         │
│ modified     │ Timestamp                                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ 1:N
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       RentalRate                                 │
├─────────────────────────────────────────────────────────────────┤
│ id            │ PK                                               │
│ sku           │ FK → RentalSKU                                   │
│ rate          │ Decimal (per billing unit)                       │
│ effective_date│ Date when rate becomes active                    │
│ set_by        │ FK → User (Rate Manager who set it)              │
│ notes         │ Optional notes about rate change                 │
│ created       │ Timestamp                                        │
└─────────────────────────────────────────────────────────────────┘
```

### RentalSKU

A Stock Keeping Unit (SKU) represents a billable item that can be rented or subscribed to.

**Table:** `coldfront_orcd_direct_charge_rentalsku`

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `sku_code` | CharField(50) | Unique identifier (e.g., "NODE_H200x8") |
| `name` | CharField(100) | Display name |
| `description` | TextField | Optional description |
| `sku_type` | CharField(20) | NODE, MAINTENANCE, or QOS |
| `billing_unit` | CharField(20) | HOURLY or MONTHLY |
| `is_active` | BooleanField | Whether SKU is currently available |
| `is_public` | BooleanField | Whether visible on Current Rates page |
| `linked_model` | CharField(100) | Optional link to source model |
| `metadata` | JSONField | Flexible attributes for filtering |
| `created` | DateTimeField | Auto-set on creation |
| `modified` | DateTimeField | Auto-updated on save |

**Methods:**

```python
# Get rate effective on a specific date
rate = sku.get_rate_for_date(target_date)

# Get current effective rate
current = sku.current_rate
```

**Permissions:**

```python
class Meta:
    permissions = [
        ("can_manage_rates", "Can manage rental rates"),
    ]
```

### RentalRate

A rate entry for a SKU with an effective date. Multiple rates can exist per SKU, with only the most recent (by effective_date) being "current".

**Table:** `coldfront_orcd_direct_charge_rentalrate`

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `sku` | ForeignKey(RentalSKU) | Parent SKU |
| `rate` | DecimalField(12,6) | Rate per billing unit (up to 6 decimal places) |
| `effective_date` | DateField | When rate becomes active |
| `set_by` | ForeignKey(User) | Who set this rate |
| `notes` | TextField | Optional notes |
| `created` | DateTimeField | Auto-set on creation |
| `modified` | DateTimeField | Auto-updated on save |

**Constraints:**

```python
class Meta:
    unique_together = ["sku", "effective_date"]  # One rate per date per SKU
    ordering = ["-effective_date"]  # Newest first
```

---

## Current Rates Page

The Current Rates page is a **public-facing page** visible to all logged-in users, displaying the current pricing for all available SKUs.

### Purpose

- Allow users to view current rental rates before making reservations
- Show upcoming rate changes with effective dates
- Provide transparency in pricing across all rentable items

### Features

1. **Card-based Layout** - SKUs displayed as attractive cards grouped by category
2. **Dynamic Filtering** - Filter by category and metadata attributes (GPU type, memory, etc.)
3. **Upcoming Rate Alerts** - Visual badges showing scheduled rate changes
4. **SKU Details** - Link to detailed view with full metadata and description

### Visibility Control

Rate Managers can control which SKUs appear on the Current Rates page using the `is_public` field:

- **is_public = True** (default): SKU visible on Current Rates page
- **is_public = False**: SKU hidden from Current Rates page

This allows Rate Managers to:
- Keep placeholder SKUs private until rates are finalized
- Hide deprecated SKUs without deleting them
- Stage new offerings before public release

### Toggle Visibility

From the Rate Management dashboard, Rate Managers can toggle visibility using the "Public" switch column. Changes are applied immediately via AJAX.

### Metadata for Filtering

The `metadata` JSONField allows flexible attributes that power the filter dropdowns:

```json
{
  "gpu_type": "NVIDIA H200",
  "gpu_count": 8,
  "gpu_memory_gb": 80,
  "system_memory_gb": 1500,
  "category": "GPU"
}
```

Common metadata keys:
- `gpu_type` - GPU model name
- `gpu_count` - Number of GPUs
- `gpu_memory_gb` - GPU memory in GB
- `cpu_cores` - Number of CPU cores
- `system_memory_gb` - System RAM in GB
- `local_storage_tb` - Local NVMe storage in TB
- `features` - List of special features (e.g., ["NVLink", "InfiniBand"])

### URL Structure

| URL | View | Access | Description |
|-----|------|--------|-------------|
| `/nodes/rates/current/` | `CurrentRatesView` | All logged-in users | Main rates page |
| `/nodes/rates/current/<pk>/` | `SKUPublicDetailView` | All logged-in users | SKU detail page |
| `/nodes/rates/sku/<pk>/visibility/` | `ToggleSKUVisibilityView` | Rate Managers | Toggle is_public |

### Navigation

A "Rates" link appears in the main navbar for all logged-in users, providing quick access to the Current Rates page.

---

## SKU Types

| Type | Billing Unit | Examples | Created By |
|------|--------------|----------|------------|
| `NODE` | Hourly | H200x8, L40Sx4, CPU_384G | Migration (from NodeType) |
| `MAINTENANCE` | Monthly | Basic Account Maintenance Fee | Migration |
| `QOS` | Monthly | Custom tiers | Rate Manager (UI) |

### Initial SKUs Created by Migration

The migration `0022_rentalsku_rentalrate` creates initial SKUs:

**Node SKUs (9 total):**
- NODE_H200x8, NODE_H200x4, NODE_H200x2, NODE_H200x1
- NODE_L40Sx4, NODE_L40Sx2, NODE_L40Sx1
- NODE_CPU_384G, NODE_CPU_1500G

**Maintenance SKUs (2 total):**
- MAINT_STANDARD
- MAINT_ADVANCED

All initial SKUs receive a placeholder rate of $0.01 effective on the migration date.

---

## Rate History and Effective Dates

### How It Works

1. Each SKU can have multiple rates with different effective dates
2. When looking up a rate, the system finds the most recent rate where `effective_date <= target_date`
3. Rates are **immutable** - once created, they cannot be modified or deleted
4. To change a rate, add a new rate with a new effective date

### Example Timeline

```
Date        Rate     Notes
2024-01-01  $10.00   Initial rate
2024-06-01  $12.00   Mid-year increase
2025-01-01  $15.00   Annual update (scheduled)
```

On May 15, 2024: `get_rate_for_date(date(2024, 5, 15))` returns $10.00
On July 1, 2024: `get_rate_for_date(date(2024, 7, 1))` returns $12.00

### Rate Lookup for Invoicing

```python
def calculate_reservation_cost(reservation):
    """Calculate cost using rate effective on reservation start date."""
    sku = RentalSKU.objects.get(
        sku_type="NODE",
        linked_model=f"NodeType:{reservation.node_instance.node_type.name}"
    )
    rate = sku.get_rate_for_date(reservation.start_date)
    if rate:
        return reservation.billable_hours * rate.rate
    return Decimal("0.00")
```

---

## Permission System

### The `can_manage_rates` Permission

Defined on the `RentalSKU` model, this permission grants access to:
- View all SKUs and rate history
- Add new rates to existing SKUs
- Create new custom SKUs (QoS type)

### Rate Manager Group

The `setup_rate_manager` management command creates and manages the Rate Manager group:

```bash
# Create the group with permission
python manage.py setup_rate_manager --create-group

# Add a user to the group
python manage.py setup_rate_manager --add-user USERNAME

# Remove a user from the group
python manage.py setup_rate_manager --remove-user USERNAME

# List all Rate Managers
python manage.py setup_rate_manager --list
```

### What Rate Managers Cannot Do

- Delete existing rates (preserves audit trail)
- Delete SKUs (can only deactivate)
- Create NODE-type SKUs (auto-created from NodeType)
- Modify existing rate values (add new rate instead)

---

## Activity Logging

All rate changes are logged to the ActivityLog with category `RATE`.

### New ActionCategory

```python
class ActionCategory(models.TextChoices):
    # ... existing categories ...
    RATE = "rate", "Rate Management"
```

### Logged Actions

| Action | Trigger | Description |
|--------|---------|-------------|
| `rate.created` | New rate added | Rate for SKU: $X/unit effective DATE |
| `rate.updated` | Rate modified (rare) | Rate updated for SKU |
| `sku.created` | New SKU created | SKU 'NAME' (CODE) created |

### Log Data Structure

```python
log_activity(
    action="rate.created",
    category=ActivityLog.ActionCategory.RATE,
    description="Rate for H200x8 Node: $15.00/Per Hour effective 2024-01-01",
    user=request.user,
    target=rate_instance,
    extra_data={
        "sku_code": "NODE_H200x8",
        "sku_name": "H200x8 Node",
        "rate": "15.00",
        "effective_date": "2024-01-01",
        "billing_unit": "HOURLY",
    },
)
```

---

## UI Components

### Rate Management Dashboard

**URL:** `/nodes/rates/`  
**Template:** `rate_management.html`

Displays all SKUs grouped by type (Node, Maintenance, QoS) with:
- Current rate and effective date
- Quick links to add rate or view history
- "Add Custom QoS" button for creating new SKUs

```
┌─────────────────────────────────────────────────────────────────┐
│  Rate Management                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─ Node Rentals (Hourly) ─────────────────────────────────────┐ │
│  │ SKU          │ Current Rate │ Effective │ Actions           │ │
│  │ NODE_H200x8  │ $15.00/hr    │ Jan 1     │ [Add] [History]   │ │
│  │ NODE_L40Sx4  │ $8.00/hr     │ Jan 1     │ [Add] [History]   │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─ Maintenance Fees (Monthly) ────────────────────────────────┐ │
│  │ SKU          │ Current Rate │ Effective │ Actions           │ │
│  │ MAINT_STANDARD │ $50.00/mo  │ Jan 1     │ [Add] [History]   │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─ Rentable QoS (Monthly) ────────────────────────────────────┐ │
│  │ [+ Add Custom QoS]                                           │ │
│  │ (No QoS SKUs configured)                                     │ │
│  └──────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### SKU Rate Detail View

**URL:** `/nodes/rates/sku/<pk>/`  
**Template:** `sku_rate_detail.html`

Shows:
- SKU details (code, name, type, billing unit, status)
- Current effective rate
- Complete rate history with who set each rate and when

### Add Rate Form

**URL:** `/nodes/rates/sku/<pk>/add/`  
**Template:** `add_rate_form.html`

Form fields:
- Rate (decimal with up to 6 decimal places, required)
- Effective Date (date picker, required)
- Notes (textarea, optional)

Validation:
- Only one rate per effective date
- Rate must be non-negative
- Up to 6 decimal places supported for precision pricing

### Create SKU Form

**URL:** `/nodes/rates/sku/create/`  
**Template:** `create_sku_form.html`

Form fields:
- SKU Code (auto-uppercased, alphanumeric + underscores)
- Display Name
- Description (optional)
- SKU Type (QoS or Maintenance)
- Initial Rate

Note: NODE-type SKUs cannot be created manually - they are auto-generated from NodeType records.

---

## URL Reference

### Rate Manager URLs (Requires `can_manage_rates` permission)

| URL | View | Description |
|-----|------|-------------|
| `/nodes/rates/` | `RateManagementView` | Rate dashboard |
| `/nodes/rates/sku/<pk>/` | `SKURateDetailView` | SKU detail with history |
| `/nodes/rates/sku/<pk>/add/` | `AddRateView` | Add new rate form |
| `/nodes/rates/sku/<pk>/visibility/` | `ToggleSKUVisibilityView` | Toggle public visibility (AJAX) |
| `/nodes/rates/sku/create/` | `CreateSKUView` | Create custom SKU |

### Public URLs (All logged-in users)

| URL | View | Description |
|-----|------|-------------|
| `/nodes/rates/current/` | `CurrentRatesView` | Public current rates page |
| `/nodes/rates/current/<pk>/` | `SKUPublicDetailView` | Public SKU detail page |

---

## Management Commands

### setup_rate_manager

Location: `management/commands/setup_rate_manager.py`

```bash
# Show help
python manage.py setup_rate_manager --help

# Create the Rate Manager group with can_manage_rates permission
python manage.py setup_rate_manager --create-group

# Add user to Rate Manager group
python manage.py setup_rate_manager --add-user jdoe

# Remove user from Rate Manager group
python manage.py setup_rate_manager --remove-user jdoe

# List all Rate Managers
python manage.py setup_rate_manager --list
```

---

## Integration with Invoice System

### Rate Lookup During Invoice Preparation

The invoice system uses `RentalSKU.get_rate_for_date()` to determine the correct rate for each billable item:

```python
# For node reservations
def get_reservation_rate(reservation):
    node_type = reservation.node_instance.node_type.name
    sku = RentalSKU.objects.get(linked_model=f"NodeType:{node_type}")
    return sku.get_rate_for_date(reservation.start_date)

# For maintenance fees
def get_maintenance_rate(status_type, billing_month):
    sku_code = f"MAINT_{status_type.upper()}"
    sku = RentalSKU.objects.get(sku_code=sku_code)
    # Use first day of billing month
    return sku.get_rate_for_date(date(billing_month.year, billing_month.month, 1))
```

### Future Rates

Rates with future effective dates are stored but not used until their effective date arrives. This allows:
- Scheduling rate increases in advance
- Announcing changes before they take effect
- Auditing planned changes

---

## Design Decisions

### Why Immutable Rates?

**Decision:** Rates cannot be modified or deleted once created.

**Rationale:**
1. **Audit Compliance** - Complete history of all pricing decisions
2. **Billing Accuracy** - Historical invoices always use the rate that was in effect
3. **Dispute Resolution** - Easy to verify what rate was applied and when
4. **Simplicity** - No need for complex versioning or soft deletes

### Why Separate Rate Manager Role?

**Decision:** Rate management is a distinct permission from Rental Manager and Billing Manager.

**Rationale:**
1. **Separation of Duties** - Pricing decisions separate from operational approvals
2. **Flexibility** - Organizations can assign roles based on their structure
3. **Accountability** - Clear audit trail of who can change prices

### Why linked_model Field?

**Decision:** NODE SKUs have a `linked_model` field like "NodeType:H200x8".

**Rationale:**
1. **Auto-creation** - Migration creates SKUs from existing NodeTypes
2. **Lookup Efficiency** - Fast rate lookup by node type name
3. **Loose Coupling** - SKUs can exist independently of NodeType records
4. **Extensibility** - Pattern can be used for other linked models

### Why Placeholder $0.01 Initial Rates?

**Decision:** Initial SKUs have $0.01 rates instead of $0.00 or no rate.

**Rationale:**
1. **Visibility** - All SKUs appear in the UI with a current rate
2. **Testing** - Non-zero allows verification of billing calculations
3. **Reminder** - Obviously placeholder value prompts Rate Manager to set real rates
4. **Safety** - Prevents accidental $0.00 billing if real rates aren't set

---

## Files Reference

| File | Purpose |
|------|---------|
| `models.py` | RentalSKU (with is_public, metadata), RentalRate models |
| `signals.py` | log_rate_change signal handler |
| `views/rates.py` | Rate management and public rates views |
| `urls.py` | Rate management and public rates URL patterns |
| `forms.py` | RateForm, SKUForm |
| `admin.py` | RentalSKUAdmin (with metadata and visibility), RentalRateAdmin |
| `templates/common/authorized_navbar.html` | "Rates" nav link (all users), "Manage Rates" (Rate Managers) |
| `templates/.../rate_management.html` | Rate dashboard with visibility toggles |
| `templates/.../sku_rate_detail.html` | SKU detail view (Rate Manager) |
| `templates/.../add_rate_form.html` | Add rate form |
| `templates/.../create_sku_form.html` | Create SKU form |
| `templates/.../current_rates.html` | Public current rates page with filtering |
| `templates/.../sku_public_detail.html` | Public SKU detail page |
| `management/commands/setup_rate_manager.py` | Management command |
| `migrations/0022_rentalsku_rentalrate.py` | Models + initial data |
| `migrations/0024_rentalsku_metadata_visibility.py` | is_public, metadata fields |


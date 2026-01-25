# Invoice Views

This document describes views for invoice management. These views require `can_manage_billing` permission.

---

## InvoicePreparationView

**URL**: `/nodes/billing/invoice/`  
**Name**: `coldfront_orcd_direct_charge:invoice-preparation`  
**Template**: `coldfront_orcd_direct_charge/invoice_preparation.html`

Month selector showing all months with reservations.

**Context Variables**:
- `invoice_months` - List of dicts with year, month, month_name, status, override_count

---

## InvoiceDetailView

**URL**: `/nodes/billing/invoice/<year>/<month>/`  
**Name**: `coldfront_orcd_direct_charge:invoice-detail`  
**Template**: `coldfront_orcd_direct_charge/invoice_detail.html`

Detailed invoice report for a specific month.

**Query Parameters**:
- `owner` - Filter by project owner username
- `title` - Filter by project title (contains)

**Context Variables**:
- `year`, `month`, `month_name` - Period info
- `invoice_period` - InvoicePeriod instance
- `projects` - List of project data with reservations and cost breakdowns
- `total_reservations`, `excluded_count` - Counts
- `owners` - Distinct owner usernames for filter dropdown
- `owner_filter`, `title_filter` - Current filter values

**POST Actions**:
- `action=finalize`: Set status to FINALIZED, log activity
- `action=unfinalize`: Reopen for editing, log activity

**Helper Methods**:
- `_calculate_hours_for_month(reservation, year, month)` - Hours calculation
- `_calculate_cost_breakdown(reservation, year, month, hours)` - Cost object split
- `_get_hours_for_day(reservation, target_date, year, month)` - Daily hours

---

## InvoiceEditView

**URL**: `/nodes/billing/invoice/<year>/<month>/edit/`  
**Name**: `coldfront_orcd_direct_charge:invoice-edit`  
**Template**: `coldfront_orcd_direct_charge/invoice_edit.html`

Add/modify invoice line overrides.

**Query Parameters**:
- `reservation` - Reservation ID to edit

**POST Data**:
- `reservation_id` - Target reservation
- `override_type` - HOURS, COST_SPLIT, or EXCLUDE
- `notes` - Required explanation
- `override_hours` - For HOURS type
- `cost_object_*` - For COST_SPLIT type

---

## InvoiceExportView

**URL**: `/nodes/billing/invoice/<year>/<month>/export/`  
**Name**: `coldfront_orcd_direct_charge:invoice-export`

Export invoice data as JSON file.

**Response**: JSON file download with full invoice data including overrides and audit metadata.

---

## InvoiceDeleteOverrideView

**URL**: `/nodes/billing/invoice/<year>/<month>/override/<override_id>/delete/`  
**Name**: `coldfront_orcd_direct_charge:invoice-delete-override`

Delete an invoice line override.

---

[← Back to Views and URL Routing](README.md)

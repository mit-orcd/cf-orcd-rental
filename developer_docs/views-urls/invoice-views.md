# Invoice Views

This document describes views for invoice management. These views require `can_manage_billing` permission.

---

## InvoicePreparationView

**URL**: `/nodes/billing/invoice/`  
**Name**: `coldfront_orcd_direct_charge:invoice-preparation`  
**Template**: `coldfront_orcd_direct_charge/invoice_preparation.html`

Month selector showing all months with billable activity (approved reservations, active AMF entries, or active QoS subscriptions).

**Context Variables**:
- `invoice_months` - List of dicts with year, month, month_name, status, override_count

---

## InvoiceDetailView

**URL**: `/nodes/billing/invoice/<year>/<month>/`  
**Name**: `coldfront_orcd_direct_charge:invoice-detail`  
**Template**: `coldfront_orcd_direct_charge/invoice_detail.html`

Detailed invoice report for a specific month. Includes reservations, account maintenance fees (AMF), and QoS subscriptions.

AMF and QoS billing data is built using the shared helpers in
`utils/invoice_builders.py` -- the same functions used by the REST API
(`InvoiceReportView`). This ensures the web portal and API produce
identical billing data.

**Query Parameters**:
- `owner` - Filter by project owner username
- `title` - Filter by project title (contains)

**Context Variables**:
- `year`, `month`, `month_name` - Period info
- `invoice_period` - InvoicePeriod instance
- `projects` - List of project data, each containing:
  - `lines` - Reservation line items with hours, cost breakdowns, maintenance deductions, overrides
  - `amf_entries` - Account Maintenance Fee entries with SKU, rate, fraction, cost breakdown
  - `qos_entries` - QoS subscription entries with SKU, rate, fraction, cost breakdown
  - `total_hours`, `cost_totals` - Aggregated reservation data
- `total_reservations`, `excluded_count` - Reservation counts
- `total_amf_entries`, `total_qos_entries` - AMF/QoS counts
- `owners` - Distinct owner usernames for filter dropdown
- `owner_filter`, `title_filter` - Current filter values

**POST Actions**:
- `action=finalize`: Set status to FINALIZED, log activity
- `action=unfinalize`: Reopen for editing, log activity

**Helper Methods** (reservation-specific, on the view class):
- `_calculate_hours_for_month(reservation, year, month)` - Hours calculation
- `_calculate_cost_breakdown(reservation, year, month, hours)` - Cost object split
- `_get_hours_for_day(reservation, target_date, year, month)` - Daily hours

**Shared Builders** (in `utils/invoice_builders.py`, used by both API and portal):
- `build_amf_lines(year, month)` - AMF billing line items
- `build_qos_lines(year, month)` - QoS billing line items
- `build_reservation_lines(year, month, invoice_period)` - Reservation billing line items
- `build_combined_response(...)` - Project-grouped JSON response

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

**Response**: JSON file download with full invoice data including reservations, AMF entries, QoS entries, overrides, and audit metadata. The export format matches the REST API response structure.

---

## InvoiceDeleteOverrideView

**URL**: `/nodes/billing/invoice/<year>/<month>/override/<override_id>/delete/`  
**Name**: `coldfront_orcd_direct_charge:invoice-delete-override`

Delete an invoice line override.

---

[← Back to Views and URL Routing](README.md)

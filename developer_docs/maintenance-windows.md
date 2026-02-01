# Maintenance Windows

This document describes the Maintenance Window feature for the ORCD Direct Charge plugin.

## Overview

Maintenance windows allow rental managers to define scheduled maintenance periods during which node rentals are not billed. This ensures researchers are not charged for time when nodes are unavailable due to planned maintenance.

**Key Concepts:**
- Rentals can extend through maintenance windows without interruption
- Billable hours are automatically reduced to exclude any overlap with maintenance periods
- The adjustment appears on invoices showing maintenance deductions
- All nodes are affected by maintenance windows (system-wide)

---

## Model Schema

**Table:** `coldfront_orcd_direct_charge_maintenancewindow`

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `title` | CharField(200) | Short title describing the maintenance |
| `description` | TextField | Optional detailed description |
| `start_datetime` | DateTimeField | When the maintenance period begins |
| `end_datetime` | DateTimeField | When the maintenance period ends |
| `created_by` | ForeignKey(User) | Rental manager who created this window (nullable) |
| `created` | DateTimeField | Auto-set on creation |
| `modified` | DateTimeField | Auto-updated on save |

**Computed Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `duration_hours` | float | Duration of the maintenance window in hours |
| `is_upcoming` | bool | True if the window hasn't started yet |
| `is_in_progress` | bool | True if the window is currently active |
| `is_completed` | bool | True if the window has ended |

**Model Validation:**
- `end_datetime` must be after `start_datetime`

**Ordering:** By `start_datetime` descending (most recent first)

---

## Billing Calculation Algorithm

When calculating billable hours for a reservation, the system automatically deducts maintenance window overlap:

### Algorithm

```
For each day of the reservation in the billing month:
    1. Calculate the day boundaries (00:00 to 00:00 next day)
    2. Clip to reservation boundaries (may start/end mid-day)
    3. Calculate raw hours for the effective period
    4. Find all maintenance windows that overlap with this period
    5. For each overlapping window:
        - Calculate overlap_start = max(window.start, effective_start)
        - Calculate overlap_end = min(window.end, effective_end)
        - Add overlap duration to maintenance_hours
    6. Return max(0, raw_hours - maintenance_hours)
```

### Key Implementation Details

- The `_get_maintenance_hours_for_period()` helper calculates total maintenance overlap for any time period
- `_get_hours_for_day()` subtracts maintenance hours from daily billable hours
- Invoice line items include a `maintenance_deduction` field showing hours deducted
- Deductions are calculated at the daily level to ensure accuracy across month boundaries

---

## Invoicing Examples

### Example 1: Rental Fully Within Maintenance Window

```
Rental: Feb 15 4PM - Feb 16 9AM (17 hours)
Maintenance Window: Feb 15 12AM - Feb 17 12AM (48 hours)

Calculation:
  - Raw hours: 17
  - Overlap: Feb 15 4PM - Feb 16 9AM = 17 hours (fully contained)
  - Deduction: 17 hours

Result: 0 billable hours
```

### Example 2: Rental Partially Overlapping

```
Rental: Feb 14 4PM - Feb 16 9AM (41 hours)
Maintenance Window: Feb 15 8AM - Feb 15 8PM (12 hours)

Calculation:
  - Raw hours: 41
  - Overlap: Feb 15 8AM - Feb 15 8PM = 12 hours
  - Deduction: 12 hours

Result: 29 billable hours
```

### Example 3: Multiple Maintenance Windows

```
Rental: Feb 14 4PM - Feb 20 9AM (137 hours)
Maintenance Windows:
  - Feb 15 8AM - Feb 15 8PM (12 hours)
  - Feb 18 12AM - Feb 19 12AM (24 hours)

Calculation:
  - Raw hours: 137
  - Overlap window 1: 12 hours
  - Overlap window 2: 24 hours
  - Total deduction: 36 hours

Result: 101 billable hours
```

### Example 4: No Overlap

```
Rental: Feb 10 4PM - Feb 12 9AM (41 hours)
Maintenance Window: Feb 15 8AM - Feb 15 8PM (12 hours)

Calculation:
  - Raw hours: 41
  - Overlap: 0 hours (no overlap)
  - Deduction: 0 hours

Result: 41 billable hours (unchanged)
```

---

## Web UI

### Access

Rental managers access the feature via **Admin Functions > Maintenance Windows** in the navigation bar.

### List View

The list view (`/nodes/maintenance-windows/`) displays all maintenance windows with:

| Column | Description |
|--------|-------------|
| Title | Maintenance window title |
| Start | Start date and time |
| End | End date and time |
| Duration | Duration in hours |
| Status | Badge showing Upcoming/In Progress/Completed |
| Actions | Edit/Delete buttons (for future windows) or "Locked" indicator |

### Status Badges

| Badge | Color | Meaning |
|-------|-------|---------|
| Upcoming | Green | Window hasn't started yet |
| In Progress | Yellow/Warning | Window is currently active |
| Completed | Gray | Window has ended |

### Create/Edit Form

The form includes fields for:
- **Title** (required) - Short descriptive title
- **Start Date/Time** (required) - When maintenance begins
- **End Date/Time** (required) - When maintenance ends
- **Description** (optional) - Detailed description

### Edit/Delete Restrictions

**Important:** Only **future** maintenance windows can be edited or deleted via the web UI.

- Past and in-progress windows are locked to preserve billing accuracy
- Attempting to access edit/delete URLs for locked windows redirects with an error message
- Django admin allows modifications for administrative corrections if needed

### Help System

A "Help" button in the list view opens a modal with in-page documentation explaining:
- Feature purpose and behavior
- Billing impact with examples
- When to use maintenance windows
- Important notes about restrictions

---

## REST API

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/nodes/api/maintenance-windows/` | List all maintenance windows |
| POST | `/nodes/api/maintenance-windows/` | Create a new maintenance window |
| GET | `/nodes/api/maintenance-windows/{id}/` | Get maintenance window detail |
| PUT | `/nodes/api/maintenance-windows/{id}/` | Update a maintenance window |
| PATCH | `/nodes/api/maintenance-windows/{id}/` | Partially update a maintenance window |
| DELETE | `/nodes/api/maintenance-windows/{id}/` | Delete a maintenance window |

### Authentication

Requires token authentication with `can_manage_rentals` permission.

```bash
curl -H "Authorization: Token YOUR_TOKEN" \
     "http://localhost:8000/nodes/api/maintenance-windows/"
```

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status: `upcoming`, `in_progress`, or `completed` |

**Example:**
```bash
# Get only upcoming maintenance windows
curl -H "Authorization: Token YOUR_TOKEN" \
     "http://localhost:8000/nodes/api/maintenance-windows/?status=upcoming"
```

### Response Format

```json
{
    "id": 1,
    "title": "Scheduled Maintenance",
    "description": "Monthly system updates and security patches",
    "start_datetime": "2026-02-15T00:00:00Z",
    "end_datetime": "2026-02-16T12:00:00Z",
    "duration_hours": 36.0,
    "is_upcoming": true,
    "is_in_progress": false,
    "is_completed": false,
    "created_by_username": "rental_manager",
    "created": "2026-01-30T10:00:00Z",
    "modified": "2026-01-30T10:00:00Z"
}
```

### Create Request

```bash
curl -X POST \
     -H "Authorization: Token YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
         "title": "Emergency Maintenance",
         "description": "Critical security patch",
         "start_datetime": "2026-02-20T00:00:00Z",
         "end_datetime": "2026-02-20T06:00:00Z"
     }' \
     "http://localhost:8000/nodes/api/maintenance-windows/"
```

---

## Management Commands

### create_maintenance_window

Create a new maintenance window from the command line.

**Usage:**
```bash
coldfront create_maintenance_window \
    --start "2026-02-15 00:00" \
    --end "2026-02-16 12:00" \
    --title "Scheduled maintenance"

# With description
coldfront create_maintenance_window \
    --start "2026-02-15 00:00" \
    --end "2026-02-16 12:00" \
    --title "Emergency fix" \
    --description "Applying critical security patches"

# Preview without creating (dry run)
coldfront create_maintenance_window \
    --start "2026-02-15 00:00" \
    --end "2026-02-16 12:00" \
    --title "Scheduled maintenance" \
    --dry-run
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `--start` | Yes | Start datetime in "YYYY-MM-DD HH:MM" format |
| `--end` | Yes | End datetime in "YYYY-MM-DD HH:MM" format |
| `--title` | Yes | Title for the maintenance window |
| `--description` | No | Optional description |
| `--dry-run` | No | Show what would be created without making changes |

### list_maintenance_windows

List all maintenance windows with optional filtering.

**Usage:**
```bash
# List all windows
coldfront list_maintenance_windows

# List only upcoming windows
coldfront list_maintenance_windows --upcoming

# Filter by status
coldfront list_maintenance_windows --status upcoming
coldfront list_maintenance_windows --status in_progress
coldfront list_maintenance_windows --status completed
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `--upcoming` | Show only future windows |
| `--status` | Filter by status: `upcoming`, `in_progress`, or `completed` |

**Output Format:**
```
#1: Scheduled Maintenance | 2026-02-15 00:00:00 - 2026-02-16 12:00:00 | 36.0h | UPCOMING
#2: Emergency Fix | 2026-01-20 08:00:00 - 2026-01-20 14:00:00 | 6.0h | COMPLETED
```

### delete_maintenance_window

Delete a maintenance window by ID.

**Usage:**
```bash
# Delete with confirmation prompt
coldfront delete_maintenance_window 1

# Delete without confirmation
coldfront delete_maintenance_window 1 --force
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `window_id` | Yes | ID of the maintenance window to delete |
| `--force` | No | Skip confirmation prompt |

---

## Activity Logging

All maintenance window actions are logged to the activity log with category `maintenance`.

| Action | Description | Extra Data |
|--------|-------------|------------|
| `maintenance_window.created` | Window created | window_id, start_datetime, end_datetime, duration_hours |
| `maintenance_window.updated` | Window modified | window_id, start_datetime, end_datetime, duration_hours |
| `maintenance_window.deleted` | Window deleted | window_id, window_title, start_datetime, end_datetime, duration_hours |

**Example Activity Log Entry:**
```json
{
    "action": "maintenance_window.created",
    "category": "maintenance",
    "description": "Created maintenance window: Scheduled Maintenance",
    "extra_data": {
        "window_id": 1,
        "start_datetime": "2026-02-15T00:00:00Z",
        "end_datetime": "2026-02-16T12:00:00Z",
        "duration_hours": 36.0
    }
}
```

---

## Export/Import

Maintenance windows are included in the portal data export/import system.

### Export

Maintenance windows are exported to `maintenance_windows.json` with:
- Natural key: `(title, start_datetime)` tuple
- All fields including `created_by_username`

### Import

Import resolves:
- Existing windows by natural key (title + start_datetime)
- `created_by` user by username lookup

---

## Django Admin

Maintenance windows are registered in Django admin at `/admin/coldfront_orcd_direct_charge/maintenancewindow/`.

### List Display

| Column | Description |
|--------|-------------|
| Title | Maintenance window title |
| Start DateTime | When maintenance begins |
| End DateTime | When maintenance ends |
| Duration | Duration in hours |
| Status | Upcoming/In Progress/Completed |
| Created By | User who created the window |
| Created | Creation timestamp |

### Filters

- Start DateTime
- Created Date

### Search Fields

- Title
- Description

---

## Related Documentation

- [Data Models Reference](data-models.md) - MaintenanceWindow model details
- [API Reference](api-reference.md) - REST API endpoints
- [Activity Logging](signals.md) - Activity log integration
- [Export/Import](backup_restore.md) - Backup system integration

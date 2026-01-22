# REST API Reference

This document describes all REST API endpoints provided by the ORCD Direct Charge plugin.

**Sources**:
- [`coldfront_orcd_direct_charge/api/views.py`](../coldfront_orcd_direct_charge/api/views.py)
- [`coldfront_orcd_direct_charge/api/serializers.py`](../coldfront_orcd_direct_charge/api/serializers.py)
- [`coldfront_orcd_direct_charge/api/urls.py`](../coldfront_orcd_direct_charge/api/urls.py)

---

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [API Endpoints](#api-endpoints)
  - [Reservations API](#reservations-api)
  - [User Search API](#user-search-api)
  - [Invoice API](#invoice-api)
  - [Activity Log API](#activity-log-api)
- [Serializers](#serializers)
- [Permissions](#permissions)
- [CLI Tools](#cli-tools)

---

## Overview

The plugin provides a REST API built with [Django REST Framework](https://www.django-rest-framework.org/) (DRF). The API is mounted at `/nodes/api/`.

| Endpoint | Method | Description | Permission |
|----------|--------|-------------|------------|
| `/nodes/api/rentals/` | GET | List all reservations | `can_manage_rentals` |
| `/nodes/api/rentals/<pk>/` | GET | Single reservation detail | `can_manage_rentals` |
| `/nodes/api/user-search/` | GET | Search users for autocomplete | Authenticated |
| `/nodes/api/invoice/` | GET | List months with reservations | `can_manage_billing` |
| `/nodes/api/invoice/<year>/<month>/` | GET | Full invoice report | `can_manage_billing` |
| `/nodes/api/activity-log/` | GET | Query activity logs | Billing/Rental Manager |

---

## Authentication

### Token Authentication

The API uses DRF's TokenAuthentication. Each user can have an API token.

**Generate Token**:
```bash
export PLUGIN_API=True
uv run coldfront drf_create_token <username>
```

**View Token on Profile**:
The API token is displayed on the user profile page at `/user/user-profile/` with copy-to-clipboard functionality.

**Using the Token**:
```bash
curl -H "Authorization: Token YOUR_TOKEN_HERE" \
     http://localhost:8000/nodes/api/rentals/
```

**Regenerate Token**:
Tokens can be regenerated from the user profile page.

### Enabling the API

The API requires `PLUGIN_API=True` in the environment or settings:

```bash
export PLUGIN_API=True
```

Or in `local_settings.py`:
```python
PLUGIN_API = True
```

---

## API Endpoints

### Reservations API

#### List Reservations

```
GET /nodes/api/rentals/
```

Returns all reservations with optional filtering.

**Permission**: `can_manage_rentals`

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status (PENDING, APPROVED, DECLINED, CANCELLED) |
| `node` | string | Filter by node address (exact match) |
| `node_type` | string | Filter by node type name (exact match) |
| `project` | string | Filter by project title (case-insensitive contains) |
| `requesting_user` | string | Filter by username (exact match) |
| `start_date_after` | date | Start date >= this value |
| `start_date_before` | date | Start date <= this value |

**Example Request**:
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
     "http://localhost:8000/nodes/api/rentals/?status=APPROVED&node_type=H200x8"
```

**Example Response**:
```json
[
    {
        "id": 6,
        "node": "node2433",
        "node_type": "H200x8",
        "project_id": 1,
        "project_title": "Angular momentum in QGP holography",
        "requesting_user": "cgray",
        "start_date": "2025-12-30",
        "start_datetime": "2025-12-30T16:00:00",
        "end_datetime": "2026-01-03T09:00:00",
        "num_blocks": 8,
        "billable_hours": 89,
        "status": "APPROVED",
        "manager_notes": "",
        "rental_notes": "Benchmark testing",
        "rental_metadata_entries": [
            {
                "id": 1,
                "content": "Approved for credit",
                "created": "2025-12-19T16:44:27.824686",
                "modified": "2025-12-19T16:44:27.824686"
            }
        ],
        "created": "2025-12-19T16:32:39.260668",
        "modified": "2025-12-19T16:33:06.467894"
    }
]
```

#### Get Single Reservation

```
GET /nodes/api/rentals/<pk>/
```

Returns details for a single reservation.

**Permission**: `can_manage_rentals`

---

### User Search API

```
GET /nodes/api/user-search/
```

Search for users by username, name, or email. Used for autocomplete in the Add Member form.

**Permission**: Authenticated

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | string | Search query (minimum 2 characters) |
| `project_id` | integer | Optional - exclude owner and existing members |

**Example Request**:
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
     "http://localhost:8000/nodes/api/user-search/?q=john&project_id=5"
```

**Example Response**:
```json
[
    {
        "username": "johndoe",
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "display": "johndoe - John Doe"
    }
]
```

**Notes**:
- Returns maximum 10 results
- Searches across: username, first_name, last_name, email
- Filters to active users only
- If `project_id` provided, excludes project owner and existing members

---

### Invoice API

#### List Invoice Periods

```
GET /nodes/api/invoice/
```

Returns all months that have confirmed reservations, with invoice status.

**Permission**: `can_manage_billing`

**Example Response**:
```json
[
    {
        "year": 2025,
        "month": 12,
        "month_name": "December",
        "status": "Draft",
        "is_finalized": false,
        "override_count": 2
    },
    {
        "year": 2025,
        "month": 11,
        "month_name": "November",
        "status": "Finalized",
        "is_finalized": true,
        "override_count": 0
    }
]
```

**Response Fields**:
- `year`, `month` - Period identifiers
- `month_name` - Human-readable month name
- `status` - "Draft", "Finalized", or "Not Started"
- `is_finalized` - Boolean
- `override_count` - Number of line overrides

---

#### Get Invoice Report

```
GET /nodes/api/invoice/<year>/<month>/
```

Returns the full invoice report for a specific month.

**Permission**: `can_manage_billing`

**Example Request**:
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
     "http://localhost:8000/nodes/api/invoice/2025/12/"
```

**Example Response**:
```json
{
    "metadata": {
        "year": 2025,
        "month": 12,
        "month_name": "December",
        "generated_at": "2025-12-26T14:30:00.000000Z",
        "generated_by": "admin",
        "invoice_status": "Draft",
        "total_reservations": 5,
        "excluded_count": 1
    },
    "projects": [
        {
            "project_id": 1,
            "project_title": "Research Project Alpha",
            "project_owner": "jsmith",
            "total_hours": 156.5,
            "cost_totals": {
                "CO-123": 78.25,
                "CO-456": 78.25
            },
            "reservations": [
                {
                    "reservation_id": 6,
                    "node": "node2433",
                    "start_date": "2025-12-15",
                    "start_datetime": "2025-12-15T16:00:00",
                    "end_date": "2025-12-18",
                    "end_datetime": "2025-12-18T09:00:00",
                    "billable_hours": 65,
                    "hours_in_month": 65,
                    "excluded": false,
                    "cost_breakdown": [
                        {"cost_object": "CO-123", "hours": 32.5},
                        {"cost_object": "CO-456", "hours": 32.5}
                    ]
                }
            ]
        }
    ]
}
```

**Response Structure**:
- `metadata` - Report metadata and summary
- `projects[]` - Array of project data
  - `project_id`, `project_title`, `project_owner` - Project info
  - `total_hours` - Sum of all non-excluded hours
  - `cost_totals` - Hours by cost object
  - `reservations[]` - Individual reservation details

**Reservation Override Fields** (if override exists):
```json
{
    "override": {
        "type": "Hours Override",
        "notes": "Adjusted for maintenance window",
        "created_by": "billing_manager",
        "created_at": "2025-12-20T10:00:00",
        "original_value": {"hours": 89},
        "override_value": {"hours": 65}
    }
}
```

---

### Activity Log API

```
GET /nodes/api/activity-log/
```

Query the activity log for audit trail entries.

**Permission**: Billing Manager, Rental Manager, or Superuser

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `category` | string | Filter by action category |
| `user` | string | Filter by username (exact match) |
| `action` | string | Filter by action (contains) |
| `date_from` | date | Start date (YYYY-MM-DD) |
| `date_to` | date | End date (YYYY-MM-DD) |
| `limit` | integer | Max results (default 100, max 1000) |

**Example Request**:
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
     "http://localhost:8000/nodes/api/activity-log/?category=reservation&limit=50"
```

**Example Response**:
```json
[
    {
        "timestamp": "2025-12-25T15:30:00.000000Z",
        "user": "rental_manager",
        "action": "reservation.approved",
        "category": "reservation",
        "description": "Reservation #6 confirmed by rental_manager",
        "target_type": "Reservation",
        "target_id": 6,
        "target_repr": "node2433 - 2025-12-30 (Confirmed)",
        "ip_address": "192.168.1.100",
        "extra_data": {
            "project_id": 1,
            "project_title": "Research Project Alpha",
            "node": "node2433"
        }
    }
]
```

**Action Categories**:
- `auth` - Authentication events
- `reservation` - Reservation CRUD
- `project` - Project changes
- `member` - Member management
- `cost_allocation` - Cost allocation changes
- `billing` - Billing actions
- `invoice` - Invoice operations
- `maintenance` - Maintenance status changes
- `api` - API access logs
- `view` - Page views

---

## Serializers

### ReservationSerializer

**Source**: [`api/serializers.py`](../coldfront_orcd_direct_charge/api/serializers.py)

```python
class ReservationSerializer(serializers.ModelSerializer):
    node = serializers.CharField(source="node_instance.associated_resource_address")
    node_type = serializers.CharField(source="node_instance.node_type.name")
    project_id = serializers.IntegerField(source="project.id")
    project_title = serializers.SlugRelatedField(slug_field="title", source="project")
    requesting_user = serializers.SlugRelatedField(slug_field="username")
    start_datetime = serializers.DateTimeField(read_only=True)
    end_datetime = serializers.DateTimeField(read_only=True)
    billable_hours = serializers.IntegerField(read_only=True)
    rental_metadata_entries = ReservationMetadataEntrySerializer(
        source="metadata_entries", many=True
    )
    
    class Meta:
        model = Reservation
        fields = (
            "id", "node", "node_type", "project_id", "project_title",
            "requesting_user", "start_date", "start_datetime", "end_datetime",
            "num_blocks", "billable_hours", "status", "manager_notes",
            "rental_notes", "rental_metadata_entries", "created", "modified",
        )
```

### ReservationMetadataEntrySerializer

```python
class ReservationMetadataEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = ReservationMetadataEntry
        fields = ("id", "content", "created", "modified")
```

---

## Permissions

### Custom Permission Classes

**Source**: [`api/views.py`](../coldfront_orcd_direct_charge/api/views.py)

```python
class HasManageRentalsPermission(permissions.BasePermission):
    """Permission check for can_manage_rentals."""
    
    def has_permission(self, request, view):
        return request.user.has_perm("coldfront_orcd_direct_charge.can_manage_rentals")


class HasManageBillingPermission(permissions.BasePermission):
    """Permission check for can_manage_billing."""
    
    def has_permission(self, request, view):
        return request.user.has_perm("coldfront_orcd_direct_charge.can_manage_billing")


class HasActivityLogPermission(permissions.BasePermission):
    """Permission check for viewing activity logs."""
    
    def has_permission(self, request, view):
        return can_view_activity_log(request.user)
```

### Permission Matrix

| Endpoint | Required Permission |
|----------|---------------------|
| `/api/rentals/` | `can_manage_rentals` |
| `/nodes/api/user-search/` | Authenticated |
| `/api/invoice/` | `can_manage_billing` |
| `/api/invoice/<year>/<month>/` | `can_manage_billing` |
| `/api/activity-log/` | `can_manage_billing` OR `can_manage_rentals` OR Superuser |

---

## CLI Tools

The plugin includes command-line tools for API access.

### rentals.py

**Location**: [`helper_programs/orcd_dc_cli/rentals.py`](../helper_programs/orcd_dc_cli/rentals.py)

Query reservations from the command line.

**Environment Variables**:
```bash
export COLDFRONT_API_TOKEN="your_token_here"
export COLDFRONT_BASE_URL="http://localhost:8000"  # Optional, defaults to localhost
```

**Usage**:
```bash
cd helper_programs/orcd_dc_cli

# List all rentals
python rentals.py

# Filter by status
python rentals.py --status PENDING
python rentals.py --status APPROVED

# Filter by node
python rentals.py --node node2433

# Filter by node type
python rentals.py --node-type H200x8

# Filter by project
python rentals.py --project "Research Project"

# Filter by date range
python rentals.py --start-after 2025-12-01 --start-before 2025-12-31

# Output formats
python rentals.py --format json    # JSON (default)
python rentals.py --format table   # ASCII table
python rentals.py --format csv     # CSV format
```

---

## Filter Implementation

### ReservationFilter

```python
class ReservationFilter(filters.FilterSet):
    status = filters.ChoiceFilter(choices=Reservation.StatusChoices.choices)
    node = filters.CharFilter(field_name="node_instance__associated_resource_address")
    node_type = filters.CharFilter(field_name="node_instance__node_type__name")
    project = filters.CharFilter(field_name="project__title", lookup_expr="icontains")
    requesting_user = filters.CharFilter(field_name="requesting_user__username")
    start_date = filters.DateFromToRangeFilter()

    class Meta:
        model = Reservation
        fields = ["status", "node", "node_type", "project", "requesting_user", "start_date"]
```

**Filter Usage**:
- `?status=APPROVED` - Exact status match
- `?node=node2433` - Exact node address match
- `?project=research` - Case-insensitive contains
- `?start_date_after=2025-12-01&start_date_before=2025-12-31` - Date range

---

## Error Responses

### Authentication Errors

**401 Unauthorized**:
```json
{
    "detail": "Authentication credentials were not provided."
}
```

**401 Invalid Token**:
```json
{
    "detail": "Invalid token."
}
```

### Permission Errors

**403 Forbidden**:
```json
{
    "detail": "You do not have permission to perform this action."
}
```

### Validation Errors

**400 Bad Request** (Invoice API):
```json
{
    "error": "Month must be between 1 and 12"
}
```

---

## Activity Logging

All API access is logged to the ActivityLog with category `api`:

| Action | Description |
|--------|-------------|
| `api.invoice_list` | Invoice list retrieved |
| `api.invoice_report` | Specific month invoice retrieved |
| `api.activity_log` | Activity log queried |

Reservation list queries are not logged individually (would create too much noise).

---

## Related Documentation

- [Data Models](data-models.md) - Model definitions
- [Views & URLs](views-urls.md) - Web interface views
- [Django REST Framework](https://www.django-rest-framework.org/) - Framework documentation
- [django-filter](https://django-filter.readthedocs.io/) - Filter documentation



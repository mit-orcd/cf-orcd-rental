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
  - [Cost Allocations API](#cost-allocations-api)
  - [Maintenance Windows API](#maintenance-windows-api)
  - [User Search API](#user-search-api)
  - [Invoice API](#invoice-api)
  - [Activity Log API](#activity-log-api)
  - [Subscription APIs](#subscription-apis)
  - [SKU API](#sku-api)
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
| `/nodes/api/cost-allocations/` | GET | List all cost allocations | `can_manage_billing` |
| `/nodes/api/cost-allocations/<pk>/` | GET | Single cost allocation detail | `can_manage_billing` |
| `/nodes/api/maintenance-windows/` | GET, POST | List/create maintenance windows | `can_manage_rentals` |
| `/nodes/api/maintenance-windows/<pk>/` | GET, PUT, PATCH, DELETE | Maintenance window detail/update/delete | `can_manage_rentals` |
| `/nodes/api/user-search/` | GET | Search users for autocomplete | Authenticated |
| `/nodes/api/invoice/` | GET | List months with reservations | `can_manage_billing` |
| `/nodes/api/invoice/<year>/<month>/` | GET | Full invoice report | `can_manage_billing` |
| `/nodes/api/activity-log/` | GET | Query activity logs | Billing/Rental Manager |
| `/nodes/api/maintenance-subscriptions/` | GET | List maintenance subscriptions | Manager: all, User: own |
| `/nodes/api/qos-subscriptions/` | GET | List QoS subscriptions | Manager: all, User: own |
| `/nodes/api/skus/` | GET | List available SKUs with rates | Authenticated |

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

### Cost Allocations API

#### List Cost Allocations

```
GET /nodes/api/cost-allocations/
```

Returns all project cost allocations with optional filtering.

**Permission**: `can_manage_billing`

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status (PENDING, APPROVED, REJECTED) |
| `project` | string | Filter by project title (case-insensitive contains) |
| `project_pi` | string | Filter by project PI username (exact match) |
| `created_after` | datetime | Created date >= this value |
| `created_before` | datetime | Created date <= this value |
| `modified_after` | datetime | Modified date >= this value |
| `modified_before` | datetime | Modified date <= this value |
| `reviewed_by` | string | Filter by reviewer username (exact match) |

**Example Request**:
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
     "http://localhost:8000/nodes/api/cost-allocations/?status=PENDING"
```

**Example Response**:
```json
[
    {
        "id": 1,
        "project_id": 5,
        "project_title": "Research Project Alpha",
        "notes": "Main research allocation",
        "status": "APPROVED",
        "reviewed_by": "billing_manager",
        "reviewed_at": "2025-12-20T10:00:00",
        "review_notes": "Verified cost objects",
        "cost_objects": [
            {
                "id": 1,
                "cost_object": "CO-12345",
                "percentage": "60.00"
            },
            {
                "id": 2,
                "cost_object": "CO-67890",
                "percentage": "40.00"
            }
        ],
        "total_percentage": "100.00",
        "created": "2025-12-15T14:30:00",
        "modified": "2025-12-20T10:00:00"
    }
]
```

**Response Fields**:
- `id` - Cost allocation ID
- `project_id` - Associated project ID
- `project_title` - Project title
- `notes` - Notes about the allocation
- `status` - Approval status (PENDING, APPROVED, REJECTED)
- `reviewed_by` - Username of reviewer (nullable)
- `reviewed_at` - Review timestamp (nullable)
- `review_notes` - Notes from the reviewer
- `cost_objects[]` - Array of cost objects with percentages
- `total_percentage` - Sum of all cost object percentages
- `created`, `modified` - Timestamps

#### Get Single Cost Allocation

```
GET /nodes/api/cost-allocations/<pk>/
```

Returns details for a single cost allocation.

**Permission**: `can_manage_billing`

---

### Maintenance Windows API

Full CRUD API for managing maintenance windows. Maintenance windows define scheduled maintenance periods during which node rentals are not billed.

#### List Maintenance Windows

```
GET /nodes/api/maintenance-windows/
```

Returns all maintenance windows with optional filtering.

**Permission**: `can_manage_rentals`

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status: `upcoming`, `in_progress`, or `completed` |

**Example Request**:
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
     "http://localhost:8000/nodes/api/maintenance-windows/?status=upcoming"
```

**Example Response**:
```json
[
    {
        "id": 1,
        "title": "Scheduled Maintenance",
        "description": "Monthly system updates",
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
]
```

#### Create Maintenance Window

```
POST /nodes/api/maintenance-windows/
```

Create a new maintenance window.

**Permission**: `can_manage_rentals`

**Request Body**:
```json
{
    "title": "Emergency Maintenance",
    "description": "Critical security patch",
    "start_datetime": "2026-02-20T00:00:00Z",
    "end_datetime": "2026-02-20T06:00:00Z"
}
```

**Example Request**:
```bash
curl -X POST \
     -H "Authorization: Token YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"title": "Emergency Maintenance", "start_datetime": "2026-02-20T00:00:00Z", "end_datetime": "2026-02-20T06:00:00Z"}' \
     "http://localhost:8000/nodes/api/maintenance-windows/"
```

#### Get Single Maintenance Window

```
GET /nodes/api/maintenance-windows/<pk>/
```

Returns details for a single maintenance window.

**Permission**: `can_manage_rentals`

#### Update Maintenance Window

```
PUT /nodes/api/maintenance-windows/<pk>/
```

Update all fields of a maintenance window.

**Permission**: `can_manage_rentals`

```
PATCH /nodes/api/maintenance-windows/<pk>/
```

Partially update a maintenance window.

**Permission**: `can_manage_rentals`

#### Delete Maintenance Window

```
DELETE /nodes/api/maintenance-windows/<pk>/
```

Delete a maintenance window.

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

### Subscription APIs

#### List Maintenance Subscriptions

```
GET /nodes/api/maintenance-subscriptions/
```

Returns maintenance fee subscriptions. Managers see all subscriptions; regular users see only their own.

**Permission**: Authenticated (scoped by role)

**Example Request**:
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
     "http://localhost:8000/nodes/api/maintenance-subscriptions/"
```

**Example Response**:
```json
[
    {
        "id": 1,
        "subscription_type": "maintenance",
        "user_id": 5,
        "username": "orcd_u1",
        "user_email": "orcd_u1@example.com",
        "status": "basic",
        "is_active": true,
        "sku_code": "MAINT_STANDARD",
        "sku_name": "Standard Account Maintenance Fee",
        "start_date": "2026-01-25",
        "end_date": null,
        "billing_project_id": 6,
        "billing_project_title": "orcd_u1_group",
        "current_rate": "50.00",
        "created": "2026-01-25T19:15:00-05:00",
        "modified": "2026-01-25T19:15:00-05:00"
    }
]
```

**Response Fields**:
- `id` - Subscription ID
- `subscription_type` - Type identifier ("maintenance")
- `user_id` - User's ID
- `username` - User's username
- `user_email` - User's email address
- `status` - Maintenance status level (inactive, basic, advanced)
- `is_active` - Whether subscription is active (derived from status != "inactive")
- `sku_code` - SKU code for the maintenance tier (MAINT_STANDARD or MAINT_ADVANCED, nullable if inactive)
- `sku_name` - Human-readable SKU name (nullable if inactive)
- `start_date` - Subscription start date (derived from created timestamp)
- `end_date` - Subscription end date (always null for maintenance subscriptions)
- `billing_project_id` - Associated billing project ID (nullable)
- `billing_project_title` - Associated billing project title (nullable)
- `current_rate` - Current rate for this SKU (nullable if inactive or no rate set)
- `created`, `modified` - Timestamps

---

#### List QoS Subscriptions

```
GET /nodes/api/qos-subscriptions/
```

Returns QoS (Quality of Service) tier subscriptions. Managers see all subscriptions; regular users see only their own.

**Permission**: Authenticated (scoped by role)

**Example Request**:
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
     "http://localhost:8000/nodes/api/qos-subscriptions/"
```

**Example Response**:
```json
[
    {
        "id": 1,
        "subscription_type": "qos",
        "user_id": 2,
        "username": "cnh",
        "user_email": "cnh@example.com",
        "sku_code": "QOS_PREMIUM",
        "sku_name": "Premium QoS Tier",
        "is_active": true,
        "start_date": "2026-01-01",
        "end_date": null,
        "billing_project_id": 2,
        "billing_project_title": "cnh_group",
        "current_rate": "150.00",
        "created": "2026-01-01T00:00:00-05:00",
        "modified": "2026-01-01T00:00:00-05:00"
    }
]
```

**Response Fields**:
- `id` - Subscription ID
- `subscription_type` - Type identifier ("qos")
- `user_id` - User's ID
- `username` - User's username
- `user_email` - User's email address
- `sku_code` - SKU code for the QoS tier
- `sku_name` - Human-readable SKU name
- `is_active` - Whether subscription is currently active
- `start_date` - Subscription start date
- `end_date` - Subscription end date (nullable for ongoing subscriptions)
- `billing_project_id` - Associated billing project ID (nullable)
- `billing_project_title` - Associated billing project title (nullable)
- `current_rate` - Current rate for this SKU
- `created`, `modified` - Timestamps

---

### SKU API

#### List SKUs

```
GET /nodes/api/skus/
```

Returns available SKUs with their current rates. Can be filtered by SKU type.

**Permission**: Authenticated

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `type` | string | Filter by SKU type (NODE, MAINTENANCE, QOS) |

**Example Request**:
```bash
# List all active SKUs
curl -H "Authorization: Token YOUR_TOKEN" \
     "http://localhost:8000/nodes/api/skus/"

# List only maintenance SKUs
curl -H "Authorization: Token YOUR_TOKEN" \
     "http://localhost:8000/nodes/api/skus/?type=MAINTENANCE"

# List only QoS SKUs
curl -H "Authorization: Token YOUR_TOKEN" \
     "http://localhost:8000/nodes/api/skus/?type=QOS"
```

**Example Response**:
```json
[
    {
        "id": 1,
        "sku_code": "MAINT_BASIC",
        "name": "Basic Account Maintenance Fee",
        "description": "Basic maintenance subscription",
        "sku_type": "MAINTENANCE",
        "billing_unit": "MONTHLY",
        "is_active": true,
        "current_rate": "50.00",
        "metadata": {}
    },
    {
        "id": 2,
        "sku_code": "QOS_PREMIUM",
        "name": "Premium QoS Tier",
        "description": "Premium quality of service tier",
        "sku_type": "QOS",
        "billing_unit": "MONTHLY",
        "is_active": true,
        "current_rate": "150.00",
        "metadata": {}
    }
]
```

**Response Fields**:
- `id` - SKU ID
- `sku_code` - Unique SKU identifier code
- `name` - Human-readable SKU name
- `description` - SKU description
- `sku_type` - Type of SKU (NODE, MAINTENANCE, QOS)
- `billing_unit` - Billing unit (e.g., MONTHLY, HOURLY)
- `is_active` - Whether SKU is currently available
- `current_rate` - Current rate for this SKU (nullable if no rate set)
- `metadata` - Additional metadata as JSON object

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

### ProjectCostAllocationSerializer

```python
class ProjectCostAllocationSerializer(serializers.ModelSerializer):
    project_id = serializers.IntegerField(source="project.id")
    project_title = serializers.CharField(source="project.title")
    reviewed_by = serializers.SlugRelatedField(slug_field="username")
    cost_objects = ProjectCostObjectSerializer(many=True)
    total_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    
    class Meta:
        model = ProjectCostAllocation
        fields = (
            "id", "project_id", "project_title", "notes", "status",
            "reviewed_by", "reviewed_at", "review_notes",
            "cost_objects", "total_percentage", "created", "modified",
        )
```

### ProjectCostObjectSerializer

```python
class ProjectCostObjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectCostObject
        fields = ("id", "cost_object", "percentage")
```

### MaintenanceWindowSerializer

```python
class MaintenanceWindowSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(
        source="created_by.username",
        read_only=True,
        allow_null=True,
    )
    duration_hours = serializers.FloatField(read_only=True)
    is_upcoming = serializers.BooleanField(read_only=True)
    is_in_progress = serializers.BooleanField(read_only=True)
    is_completed = serializers.BooleanField(read_only=True)

    class Meta:
        model = MaintenanceWindow
        fields = (
            "id", "title", "description", "start_datetime", "end_datetime",
            "duration_hours", "is_upcoming", "is_in_progress", "is_completed",
            "created_by_username", "created", "modified",
        )
        read_only_fields = ("created", "modified")
```

### MaintenanceSubscriptionSerializer

Provides a schema compatible with QoSSubscriptionSerializer by deriving SKU-related fields from the maintenance status.

```python
class MaintenanceSubscriptionSerializer(serializers.ModelSerializer):
    subscription_type = serializers.SerializerMethodField()  # Always "maintenance"
    user_id = serializers.IntegerField(source="user.id")
    username = serializers.CharField(source="user.username")
    user_email = serializers.EmailField(source="user.email")
    is_active = serializers.SerializerMethodField()  # status != "inactive"
    sku_code = serializers.SerializerMethodField()   # MAINT_STANDARD or MAINT_ADVANCED
    sku_name = serializers.SerializerMethodField()   # From looked-up SKU
    start_date = serializers.SerializerMethodField() # From created timestamp
    end_date = serializers.SerializerMethodField()   # Always null
    billing_project_id = serializers.IntegerField(source="billing_project.id", allow_null=True)
    billing_project_title = serializers.CharField(source="billing_project.title", allow_null=True)
    current_rate = serializers.SerializerMethodField()  # From looked-up SKU
    
    # Status to SKU mapping: basic -> MAINT_STANDARD, advanced -> MAINT_ADVANCED
    
    class Meta:
        model = UserMaintenanceStatus
        fields = ("id", "subscription_type", "user_id", "username", "user_email",
                  "status", "is_active", "sku_code", "sku_name", "start_date", 
                  "end_date", "billing_project_id", "billing_project_title", 
                  "current_rate", "created", "modified")
```

### QoSSubscriptionSerializer

```python
class QoSSubscriptionSerializer(serializers.ModelSerializer):
    subscription_type = serializers.SerializerMethodField()  # Always "qos"
    user_id = serializers.IntegerField(source="user.id")
    username = serializers.CharField(source="user.username")
    user_email = serializers.EmailField(source="user.email")
    sku_code = serializers.CharField(source="sku.sku_code")
    sku_name = serializers.CharField(source="sku.name")
    billing_project_id = serializers.IntegerField(source="billing_project.id", allow_null=True)
    billing_project_title = serializers.CharField(source="billing_project.title", allow_null=True)
    current_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = UserQoSSubscription
        fields = ("id", "subscription_type", "user_id", "username", "user_email",
                  "sku_code", "sku_name", "is_active", "start_date", "end_date", 
                  "billing_project_id", "billing_project_title", "current_rate", 
                  "created", "modified")
```

### SKUSerializer

```python
class SKUSerializer(serializers.ModelSerializer):
    current_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = RentalSKU
        fields = ("id", "sku_code", "name", "description", "sku_type",
                  "billing_unit", "is_active", "current_rate", "metadata")
    
    def get_current_rate(self, obj):
        rate = obj.current_rate
        return str(rate.rate) if rate else None
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
| `/api/cost-allocations/` | `can_manage_billing` |
| `/nodes/api/user-search/` | Authenticated |
| `/api/invoice/` | `can_manage_billing` |
| `/api/invoice/<year>/<month>/` | `can_manage_billing` |
| `/api/activity-log/` | `can_manage_billing` OR `can_manage_rentals` OR Superuser |
| `/api/maintenance-subscriptions/` | Authenticated (Manager: all, User: own) |
| `/api/qos-subscriptions/` | Authenticated (Manager: all, User: own) |
| `/api/skus/` | Authenticated |

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

### CostAllocationFilter

```python
class CostAllocationFilter(filters.FilterSet):
    status = filters.ChoiceFilter(choices=ProjectCostAllocation.StatusChoices.choices)
    project = filters.CharFilter(field_name="project__title", lookup_expr="icontains")
    project_pi = filters.CharFilter(field_name="project__pi__username")
    created = filters.DateTimeFromToRangeFilter()
    modified = filters.DateTimeFromToRangeFilter()
    reviewed_by = filters.CharFilter(field_name="reviewed_by__username")

    class Meta:
        model = ProjectCostAllocation
        fields = ["status", "project", "project_pi", "created", "modified", "reviewed_by"]
```

**Filter Usage**:
- `?status=PENDING` - Exact status match (PENDING, APPROVED, REJECTED)
- `?project=research` - Case-insensitive contains on project title
- `?project_pi=jsmith` - Exact match on project PI username
- `?created_after=2025-01-01&created_before=2025-12-31` - Created date range
- `?modified_after=2025-06-01` - Modified after date
- `?reviewed_by=billing_admin` - Exact match on reviewer username

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
- [Views & URLs](views-urls/) - Web interface views
- [Django REST Framework](https://www.django-rest-framework.org/) - Framework documentation
- [django-filter](https://django-filter.readthedocs.io/) - Filter documentation



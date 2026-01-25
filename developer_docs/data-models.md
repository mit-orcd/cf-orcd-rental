# Data Models Reference

This document describes all Django models defined in the ORCD Direct Charge plugin.

**Source**: [`coldfront_orcd_direct_charge/models.py`](../coldfront_orcd_direct_charge/models.py)

---

## Table of Contents

- [Model Overview](#model-overview)
- [Node Models](#node-models)
  - [NodeType](#nodetype)
  - [GpuNodeInstance](#gpunodeinstance)
  - [CpuNodeInstance](#cpunodeinstance)
- [Reservation Models](#reservation-models)
  - [Reservation](#reservation)
  - [ReservationMetadataEntry](#reservationmetadataentry)
- [User & Maintenance Models](#user--maintenance-models)
  - [UserMaintenanceStatus](#usermaintenancestatus)
- [Project Role Models](#project-role-models)
  - [ProjectMemberRole](#projectmemberrole)
- [Cost Allocation Models](#cost-allocation-models)
  - [ProjectCostAllocation](#projectcostallocation)
  - [ProjectCostObject](#projectcostobject)
- [Invoice Models](#invoice-models)
  - [CostAllocationSnapshot](#costallocationsnapshot)
  - [CostObjectSnapshot](#costobjectsnapshot)
  - [InvoicePeriod](#invoiceperiod)
  - [InvoiceLineOverride](#invoicelineoverride)
- [Activity Logging](#activity-logging)
  - [ActivityLog](#activitylog)
- [Helper Functions](#helper-functions)

---

## Model Overview

```
┌──────────────────┐     ┌───────────────────┐     ┌─────────────────────┐
│    NodeType      │────▶│  GpuNodeInstance  │────▶│    Reservation      │
│                  │     └───────────────────┘     │                     │
│                  │     ┌───────────────────┐     │  ┌───────────────┐  │
│                  │────▶│  CpuNodeInstance  │     │  │MetadataEntry  │  │
└──────────────────┘     └───────────────────┘     └──┴───────────────┴──┘
                                                            │
                                                            ▼
┌──────────────────┐     ┌───────────────────┐     ┌─────────────────────┐
│   User (Django)  │────▶│UserMaintenance    │     │  Project (CF Core)  │
│                  │     │Status             │     │                     │
└──────────────────┘     └───────────────────┘     └─────────────────────┘
         │                                                  │
         │                                                  ▼
         │               ┌───────────────────┐     ┌─────────────────────┐
         └──────────────▶│ ProjectMemberRole │────▶│ProjectCostAllocation│
                         └───────────────────┘     │  ┌───────────────┐  │
                                                   │  │ProjectCostObj │  │
                                                   └──┴───────────────┴──┘
                                                            │
                                                            ▼
                                                   ┌─────────────────────┐
                                                   │CostAllocationSnap   │
                                                   │  ┌───────────────┐  │
                                                   │  │CostObjSnapshot│  │
                                                   └──┴───────────────┴──┘

┌──────────────────┐     ┌───────────────────┐
│  InvoicePeriod   │────▶│InvoiceLineOverride│
└──────────────────┘     └───────────────────┘

┌──────────────────┐
│   ActivityLog    │  (Audit trail for all actions)
└──────────────────┘
```

---

## Node Models

### NodeType

Defines the available categories of GPU and CPU nodes.

**Table**: `coldfront_orcd_direct_charge_nodetype`

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `name` | CharField(64) | Unique name (e.g., "H200x8", "CPU_384G") |
| `category` | CharField(16) | "GPU" or "CPU" |
| `description` | TextField | Optional description |
| `is_active` | BooleanField | Whether type is currently available |
| `created` | DateTimeField | Auto-set on creation |
| `modified` | DateTimeField | Auto-updated on save |

**Choices**:
- `CategoryChoices.GPU` = "GPU"
- `CategoryChoices.CPU` = "CPU"

**Natural Key**: `name`

**Usage**:
```python
# Get a node type
node_type = NodeType.objects.get(name="H200x8")

# Natural key lookup (for fixtures)
node_type = NodeType.objects.get_by_natural_key("H200x8")
```

---

### GpuNodeInstance

Represents an individual GPU node that can be rented.

**Table**: `coldfront_orcd_direct_charge_gpunodeinstance`

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `node_type` | ForeignKey(NodeType) | Type of GPU node |
| `is_rentable` | BooleanField | Whether node can be reserved |
| `status` | CharField(32) | "AVAILABLE" or "PLACEHOLDER" |
| `associated_resource_address` | CharField(128) | Unique node identifier (e.g., "node2433") |
| `created` | DateTimeField | Auto-set on creation |
| `modified` | DateTimeField | Auto-updated on save |

**Choices**:
- `StatusChoices.AVAILABLE` = "AVAILABLE"
- `StatusChoices.PLACEHOLDER` = "PLACEHOLDER"

**Natural Key**: `associated_resource_address`

**Related Names**:
- `node_type.gpu_instances` - All GPU instances of a node type
- `reservations` - All reservations for this node

**Constraints**:
- `node_type` limited to `category="GPU"` via `limit_choices_to`

---

### CpuNodeInstance

Represents an individual CPU node.

**Table**: `coldfront_orcd_direct_charge_cpunodeinstance`

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `node_type` | ForeignKey(NodeType) | Type of CPU node |
| `is_rentable` | BooleanField | Whether node can be reserved |
| `status` | CharField(32) | "AVAILABLE" or "PLACEHOLDER" |
| `associated_resource_address` | CharField(128) | Unique node identifier |
| `created` | DateTimeField | Auto-set on creation |
| `modified` | DateTimeField | Auto-updated on save |

**Natural Key**: `associated_resource_address`

**Related Names**:
- `node_type.cpu_instances` - All CPU instances of a node type

---

## Reservation Models

### Reservation

A booking request for a GPU node instance.

**Table**: `coldfront_orcd_direct_charge_reservation`

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `node_instance` | ForeignKey(GpuNodeInstance) | The GPU node being reserved |
| `project` | ForeignKey(Project) | ColdFront project |
| `requesting_user` | ForeignKey(User) | User who submitted request |
| `processed_by` | ForeignKey(User) | Manager who confirmed/declined (nullable) |
| `start_date` | DateField | Reservation starts at 4 PM on this date |
| `num_blocks` | PositiveIntegerField | Number of 12-hour blocks (1-14) |
| `status` | CharField(16) | Approval status |
| `manager_notes` | TextField | Notes from manager (visible to user) |
| `rental_notes` | TextField | Notes from requester |
| `rental_management_metadata` | TextField | Internal metadata (deprecated) |
| `created` | DateTimeField | Auto-set on creation |
| `modified` | DateTimeField | Auto-updated on save |

**Status Choices**:
- `PENDING` - Awaiting approval
- `APPROVED` - Confirmed (displayed as "Confirmed" in UI)
- `DECLINED` - Declined by manager
- `CANCELLED` - Cancelled by user

**Computed Properties**:

```python
reservation.start_datetime  # datetime at 4:00 PM on start_date
reservation.end_datetime    # Calculated end, capped at 9:00 AM
reservation.billable_hours  # Total hours (after truncation)
reservation.end_date        # Calendar date when reservation ends
```

**Time Constants**:
- `START_HOUR = 16` (4:00 PM)
- `MAX_END_HOUR = 9` (9:00 AM cap)

**Permissions**:
- `can_manage_rentals` - Ability to approve/decline reservations

**Related Names**:
- `node_instance.reservations`
- `project.node_reservations`
- `requesting_user.node_reservation_requests`
- `metadata_entries` - ReservationMetadataEntry records

**Static Methods**:
```python
# Calculate end datetime with 9 AM cap
end = Reservation.calculate_end_datetime(start_dt, num_blocks)
```

---

### ReservationMetadataEntry

Timestamped notes attached to a reservation by managers.

**Table**: `coldfront_orcd_direct_charge_reservationmetadataentry`

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `reservation` | ForeignKey(Reservation) | Parent reservation |
| `content` | TextField | Note content |
| `created` | DateTimeField | When note was added |
| `modified` | DateTimeField | Auto-updated on save |

**Related Names**:
- `reservation.metadata_entries`

---

## User & Maintenance Models

### UserMaintenanceStatus

Tracks the account maintenance fee status for each user. The account maintenance fee is a 
recurring monthly charge. Researchers participating in a paid maintenance fee tier (Basic 
or Advanced) are able to use rental services. Base ORCD services are available to all 
researchers, even those not paying an account maintenance fee.

**Table**: `coldfront_orcd_direct_charge_usermaintenancestatus`

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `user` | OneToOneField(User) | The Django user |
| `status` | CharField(16) | Maintenance level |
| `billing_project` | ForeignKey(Project) | Project for fee billing (nullable) |
| `created` | DateTimeField | Auto-set on creation |
| `modified` | DateTimeField | Auto-updated on save |

**Status Choices**:
- `inactive` - Not subscribed (default) - can use base ORCD services
- `basic` - Basic tier - enables rental services
- `advanced` - Advanced tier - enables rental services

**Related Names**:
- `user.maintenance_status`
- `billing_project.maintenance_fee_users`

**Business Rules**:
- `inactive` status requires no billing project
- `basic`/`advanced` require a billing project
- User must have eligible role in billing project (owner, technical_admin, member - NOT financial_admin)

---

## Project Role Models

### ProjectMemberRole

ORCD-specific role assignments for project members.

**Table**: `coldfront_orcd_direct_charge_projectmemberrole`

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `project` | ForeignKey(Project) | ColdFront project |
| `user` | ForeignKey(User) | User with this role |
| `role` | CharField(32) | Role identifier |
| `created` | DateTimeField | When role was assigned |
| `modified` | DateTimeField | Auto-updated on save |

**Role Choices**:
- `financial_admin` - Can edit cost allocations, manage roles, NOT in reservations
- `technical_admin` - Can manage members, in reservations and billing
- `member` - Basic role, in reservations and billing

**Note**: Owner role is implicit via `project.pi` and NOT stored in this table.

**Constraints**:
- `unique_together = ("project", "user", "role")` - Users can have multiple roles

**Related Names**:
- `project.member_roles`
- `user.project_member_roles`

**Role Hierarchy**:
```
Owner (implicit)
    └── Financial Admin
    └── Technical Admin
            └── Member
```

---

## Cost Allocation Models

### ProjectCostAllocation

Overall cost allocation settings for a project.

**Table**: `coldfront_orcd_direct_charge_projectcostallocation`

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `project` | OneToOneField(Project) | Parent project |
| `notes` | TextField | Allocation notes |
| `status` | CharField(16) | Approval status |
| `reviewed_by` | ForeignKey(User) | Billing Manager who reviewed |
| `reviewed_at` | DateTimeField | When reviewed |
| `review_notes` | TextField | Reviewer's notes |
| `created` | DateTimeField | Auto-set on creation |
| `modified` | DateTimeField | Auto-updated on save |

**Status Choices**:
- `PENDING` - Awaiting approval
- `APPROVED` - Approved for use
- `REJECTED` - Rejected, needs revision

**Permissions**:
- `can_manage_billing` - Ability to approve/reject allocations

**Related Names**:
- `project.cost_allocation`
- `reviewed_by.reviewed_cost_allocations`
- `cost_objects` - ProjectCostObject records
- `snapshots` - CostAllocationSnapshot records

**Methods**:
```python
allocation.total_percentage()  # Sum of all cost object percentages
allocation.is_approved()       # Boolean check for APPROVED status
```

---

### ProjectCostObject

Individual cost object with percentage allocation.

**Table**: `coldfront_orcd_direct_charge_projectcostobject`

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `allocation` | ForeignKey(ProjectCostAllocation) | Parent allocation |
| `cost_object` | CharField(64) | Cost object identifier |
| `percentage` | DecimalField(5,2) | Percentage (0.00-100.00) |
| `created` | DateTimeField | Auto-set on creation |
| `modified` | DateTimeField | Auto-updated on save |

**Validation**:
- `cost_object` pattern: `^[A-Za-z0-9-]+$` (alphanumeric + hyphens)
- All percentages in an allocation must sum to 100%

**Related Names**:
- `allocation.cost_objects`

---

## Invoice Models

### CostAllocationSnapshot

Historical snapshot of cost allocation at approval time.

**Table**: `coldfront_orcd_direct_charge_costallocationsnapshot`

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `allocation` | ForeignKey(ProjectCostAllocation) | Parent allocation |
| `approved_at` | DateTimeField | When this split was approved |
| `approved_by` | ForeignKey(User) | Approving Billing Manager |
| `superseded_at` | DateTimeField | When replaced (null if current) |
| `created` | DateTimeField | Auto-set on creation |
| `modified` | DateTimeField | Auto-updated on save |

**Related Names**:
- `allocation.snapshots`
- `approved_by.approved_cost_snapshots`
- `cost_objects` - CostObjectSnapshot records

**Class Methods**:
```python
# Get active snapshot for a specific date
snapshot = CostAllocationSnapshot.get_active_snapshot_for_date(project, target_date)
```

---

### CostObjectSnapshot

Cost object values at snapshot time.

**Table**: `coldfront_orcd_direct_charge_costobjectsnapshot`

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `snapshot` | ForeignKey(CostAllocationSnapshot) | Parent snapshot |
| `cost_object` | CharField(64) | Cost object identifier |
| `percentage` | DecimalField(5,2) | Percentage at snapshot time |
| `created` | DateTimeField | Auto-set on creation |
| `modified` | DateTimeField | Auto-updated on save |

**Related Names**:
- `snapshot.cost_objects`

---

### InvoicePeriod

Status tracking for a billing month.

**Table**: `coldfront_orcd_direct_charge_invoiceperiod`

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `year` | IntegerField | Year (e.g., 2025) |
| `month` | IntegerField | Month (1-12) |
| `status` | CharField(16) | Draft or Finalized |
| `finalized_by` | ForeignKey(User) | Who finalized |
| `finalized_at` | DateTimeField | When finalized |
| `notes` | TextField | Optional notes |
| `created` | DateTimeField | Auto-set on creation |
| `modified` | DateTimeField | Auto-updated on save |

**Status Choices**:
- `DRAFT` - Editable
- `FINALIZED` - Locked for billing

**Constraints**:
- `unique_together = ("year", "month")`

**Permissions**:
- `can_manage_invoices` - Manage invoice preparation

**Properties**:
```python
invoice_period.is_finalized  # Boolean check
```

**Related Names**:
- `finalized_by.finalized_invoices`
- `overrides` - InvoiceLineOverride records

---

### InvoiceLineOverride

Manual adjustment to an invoice line item.

**Table**: `coldfront_orcd_direct_charge_invoicelineoverride`

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `invoice_period` | ForeignKey(InvoicePeriod) | Parent period |
| `reservation` | ForeignKey(Reservation) | Reservation being adjusted |
| `override_type` | CharField(16) | Type of override |
| `original_value` | JSONField | Original calculated values |
| `override_value` | JSONField | New override values |
| `notes` | TextField | Required explanation |
| `created_by` | ForeignKey(User) | Who created override |
| `created` | DateTimeField | Auto-set on creation |
| `modified` | DateTimeField | Auto-updated on save |

**Override Types**:
- `HOURS` - Override billable hours
- `COST_SPLIT` - Override cost object split
- `EXCLUDE` - Exclude from invoice

**Constraints**:
- `unique_together = ("invoice_period", "reservation")` - One override per reservation per period

**Related Names**:
- `invoice_period.overrides`
- `reservation.invoice_overrides`
- `created_by.invoice_overrides_created`

---

## Rate Management Models

### RentalSKU

Represents a rentable item with a unique SKU code. Used for tracking rates and billing.

**Table**: `coldfront_orcd_direct_charge_rentalsku`

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `sku_code` | CharField(50) | Unique identifier (e.g., "H200x8", "MAINTENANCE_BASIC") |
| `name` | CharField(100) | Display name |
| `description` | TextField | Optional description |
| `sku_type` | CharField(20) | Type: NODE, MAINTENANCE, or QOS |
| `billing_unit` | CharField(20) | HOURLY or MONTHLY |
| `is_active` | BooleanField | Whether SKU is currently available |
| `is_public` | BooleanField | Whether visible on Current Rates page |
| `metadata` | JSONField | Dynamic attributes (e.g., GPU type, memory) |
| `created` | DateTimeField | Auto-set on creation |
| `modified` | DateTimeField | Auto-updated on save |

**SKU Types**:
- `NODE` - Node rentals (H200x8, L40Sx4, CPU_384G, CPU_1500G)
- `MAINTENANCE` - Maintenance fees (Basic, Advanced)
- `QOS` - Custom QoS configurations

**Methods**:
```python
sku.get_rate_at_date(date)  # Returns rate effective on given date
sku.current_rate            # Property: current effective rate
```

**Permissions**:
- `can_manage_rates` - Required to manage SKUs and rates

---

### RentalRate

Tracks rate history for SKUs with effective dates.

**Table**: `coldfront_orcd_direct_charge_rentalrate`

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `sku` | ForeignKey(RentalSKU) | The SKU this rate applies to |
| `rate` | DecimalField(10,2) | Rate value |
| `effective_date` | DateField | When this rate takes effect |
| `set_by` | ForeignKey(User) | Rate Manager who set this rate |
| `notes` | TextField | Optional notes about rate change |
| `created` | DateTimeField | Auto-set on creation |

**Related Names**:
- `sku.rates`
- `set_by.rental_rates_set`

**Ordering**: By `effective_date` descending (most recent first)

---

## Activity Logging

### ActivityLog

Audit trail for all significant user actions.

**Table**: `coldfront_orcd_direct_charge_activitylog`

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `timestamp` | DateTimeField | When action occurred (indexed) |
| `user` | ForeignKey(User) | User who performed action |
| `action` | CharField(100) | Machine-readable action ID (indexed) |
| `category` | CharField(30) | Action category (indexed) |
| `description` | TextField | Human-readable description |
| `target_type` | CharField(100) | Target model class name |
| `target_id` | PositiveIntegerField | Target object PK |
| `target_repr` | CharField(255) | String representation of target |
| `ip_address` | GenericIPAddressField | Request IP |
| `user_agent` | TextField | Browser/client info |
| `extra_data` | JSONField | Additional structured data |

**Action Categories**:
- `auth` - Authentication (login, logout, failed login)
- `reservation` - Reservation CRUD
- `project` - Project changes
- `member` - Member management
- `cost_allocation` - Cost allocation changes
- `billing` - Billing actions
- `invoice` - Invoice operations
- `maintenance` - Maintenance status changes
- `api` - API access
- `view` - Page views (optional)

**Database Indexes**:
- `(user, -timestamp)`
- `(category, -timestamp)`
- `(action, -timestamp)`

**Related Names**:
- `user.activity_logs`

---

## Helper Functions

These functions are defined in `models.py` for role and permission checking:

### Role Functions

```python
def get_user_project_roles(user, project) -> list:
    """Return all roles for user in project (e.g., ["owner", "financial_admin"])"""

def get_user_project_role(user, project) -> str | None:
    """DEPRECATED: Returns highest-priority single role"""

def can_edit_cost_allocation(user, project) -> bool:
    """True if user is owner, financial_admin, or superuser"""

def can_manage_members(user, project) -> bool:
    """True if user is owner, financial_admin, technical_admin, or superuser"""

def can_manage_financial_admins(user, project) -> bool:
    """True if user is owner, financial_admin, or superuser"""

def is_included_in_reservations(user, project) -> bool:
    """True if user should appear in reservations (NOT financial_admin alone)"""

def can_use_for_maintenance_fee(user, project) -> bool:
    """True if user can bill maintenance fees to this project"""

def get_project_members_for_reservation(project) -> list:
    """Get all users to include in reservations for a project"""

def has_approved_cost_allocation(project) -> bool:
    """True if project has an APPROVED cost allocation"""
```

### Activity Logging Functions

```python
def get_client_ip(request) -> str:
    """Extract client IP from request, handling X-Forwarded-For"""

def log_activity(
    action: str,
    category: str,
    description: str,
    user: User = None,
    request: HttpRequest = None,
    target: Model = None,
    extra_data: dict = None,
) -> ActivityLog | None:
    """Create an ActivityLog entry"""

def can_view_activity_log(user) -> bool:
    """True if user can view activity logs (Billing/Rental Manager or superuser)"""
```

---

## Migration History

| Migration | Description |
|-----------|-------------|
| `0001_initial` | NodeType, GpuNodeInstance, CpuNodeInstance |
| `0002_rename_cpu_node_labels` | Field renaming |
| `0003_reservation` | Reservation model |
| `0004_reservation_rental_notes` | Add rental_notes, rental_management_metadata |
| `0005_reservationmetadataentry` | ReservationMetadataEntry model |
| `0006_migrate_metadata_to_entries` | Data migration for metadata |
| `0007_rename_default_projects` | USERNAME_default_project → USERNAME_personal |
| `0008_delete_old_default_projects` | Clean up old project names |
| `0009_create_group_projects` | Create USERNAME_group projects |
| `0010_usermaintenancestatus` | UserMaintenanceStatus model |
| `0011_create_maintenance_status_for_users` | Initialize status for existing users |
| `0012_usermaintenancestatus_billing_project` | Add billing_project field |
| `0013_project_cost_allocation` | ProjectCostAllocation, ProjectCostObject |
| `0014_projectmemberrole` | ProjectMemberRole model |
| `0015_initialize_member_roles` | Initialize roles for existing members |
| `0016_change_projectmemberrole_unique_constraint` | Allow multiple roles per user |
| `0017_add_cost_allocation_approval` | Add approval workflow fields |
| `0018_costallocationsnapshot_invoiceperiod...` | Invoice preparation models |
| `0019_backfill_cost_allocation_snapshots` | Historical snapshot backfill |
| `0020_activitylog` | ActivityLog model |
| `0021_reservation_processed_by` | Add processed_by field to Reservation |
| `0022_rentalsku_rentalrate` | RentalSKU, RentalRate models + initial SKU data |
| `0023_alter_rentalrate_rate` | Adjust rate field precision |
| `0024_rentalsku_metadata_visibility` | Add is_public, metadata to RentalSKU |

---

## Related Documentation

- [Views & URLs](views-urls/) - How models are used in views
- [API Reference](api-reference.md) - Model serialization for API
- [Signals](signals.md) - Signal handlers for model changes



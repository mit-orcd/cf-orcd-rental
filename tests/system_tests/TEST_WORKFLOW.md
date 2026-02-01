# System Test Workflow Plan

This document defines a comprehensive system test suite for the ORCD Rental Portal. Tests are modular, YAML-driven, and designed for CI/CD integration.

## Table of Contents

1. [Overview](#overview)
2. [Test Architecture](#test-architecture)
3. [Test Users and Roles](#test-users-and-roles)
4. [Test Phases and Dependencies](#test-phases-and-dependencies)
5. [YAML Configuration Schema](#yaml-configuration-schema)
6. [Test Module Specifications](#test-module-specifications)
7. [CI/CD Integration](#cicd-integration)
8. [Implementation Guide](#implementation-guide)

---

## Overview

### Purpose

The system test suite validates end-to-end functionality of the ORCD Rental Portal, covering:

- User authentication and authorization
- Project management and member roles
- Cost allocation workflows
- Reservation lifecycle (request, approval, billing)
- Invoice generation and finalization
- Maintenance window management
- Rate management
- API endpoints

### Design Principles

1. **YAML-Driven**: All test data and configurations defined in human-editable YAML files
2. **Modular**: Tests organized into independent modules with explicit dependencies
3. **Parameterized**: Common values defined once and referenced throughout (DRY principle)
4. **Idempotent**: Tests can be re-run without side effects (cleanup included)
5. **CI/CD Ready**: Designed for GitHub Actions, Buildkite, or Woodpecker CI

---

## Test Architecture

### Directory Structure

```
tests/system_tests/
├── TEST_WORKFLOW.md              # This document
├── TEST_SUITE_MAINTENANCE.md     # Maintenance prompts and review guides
├── config/
│   ├── test_config.yaml          # Main configuration file
│   ├── users.yaml                # User definitions
│   ├── projects.yaml             # Project and cost allocation definitions
│   ├── reservations.yaml         # Reservation test cases
│   ├── invoices.yaml             # Invoice test scenarios
│   └── maintenance_windows.yaml  # Maintenance window definitions
├── fixtures/
│   ├── base_data.json            # Django fixtures for initial state
│   └── node_types.json           # Node type fixtures
├── modules/
│   ├── __init__.py
│   ├── base.py                   # Base test class with utilities
│   ├── test_01_users.py          # User creation and authentication
│   ├── test_02_projects.py       # Project creation and setup
│   ├── test_03_members.py        # Member management
│   ├── test_04_cost_allocation.py # Cost allocation workflow
│   ├── test_05_rates.py          # Rate management
│   ├── test_06_reservations.py   # Reservation workflow
│   ├── test_07_maintenance.py    # Maintenance window management
│   ├── test_08_invoices.py       # Invoice workflow
│   ├── test_09_api.py            # API endpoint tests
│   └── test_10_activity_log.py   # Activity log verification
├── utils/
│   ├── __init__.py
│   ├── yaml_loader.py            # YAML configuration loader
│   ├── api_client.py             # REST API client wrapper
│   ├── browser_client.py         # Web UI test client (optional)
│   └── assertions.py             # Custom test assertions
├── run_tests.py                  # Test runner script
├── run_tests.sh                  # Shell wrapper for CI
└── requirements.txt              # Test dependencies
```

### Test Execution Order

Tests are numbered to enforce execution order due to dependencies:

```
01_users       → Creates test users with roles
02_projects    → Creates test projects (requires users)
03_members     → Adds members to projects (requires projects + users)
04_cost_allocation → Creates and approves allocations (requires projects)
05_rates       → Tests rate management (requires rate manager)
06_reservations → Tests reservation workflow (requires approved allocations + rates)
07_maintenance  → Tests maintenance windows (requires rental manager)
08_invoices    → Tests invoice workflow (requires reservations)
09_api         → Tests API endpoints (requires all data)
10_activity_log → Verifies activity logging (runs last)
```

---

## Test Users and Roles

### Required Test Users

The test suite requires users with specific roles and permissions. These are defined in `config/users.yaml`.

| User ID | Username | Role(s) | Permissions | Purpose |
|---------|----------|---------|-------------|---------|
| `user_pi` | `test_pi` | Project Owner (PI) | Project ownership | Create projects, full project access |
| `user_financial` | `test_financial_admin` | Financial Admin | Project financial access | Cost allocation, member management |
| `user_technical` | `test_tech_admin` | Technical Admin | Project technical access | Member management, reservations |
| `user_member` | `test_member` | Member | Basic project access | Reservations only |
| `user_rental_mgr` | `test_rental_manager` | Rental Manager | `can_manage_rentals` | Approve reservations, maintenance windows |
| `user_billing_mgr` | `test_billing_manager` | Billing Manager | `can_manage_billing` | Approve allocations, manage invoices |
| `user_rate_mgr` | `test_rate_manager` | Rate Manager | `can_manage_rates` | Manage SKUs and rates |
| `user_multi_role` | `test_multi_role` | Financial + Technical Admin | Combined roles | Test multi-role scenarios |

### Permission Matrix

```yaml
permissions:
  can_manage_rentals:
    - Approve/decline reservations
    - Add reservation metadata
    - Create/edit/delete maintenance windows
    - View activity logs
    
  can_manage_billing:
    - Approve/reject cost allocations
    - View/edit/finalize invoices
    - Create invoice overrides
    - View activity logs
    
  can_manage_rates:
    - Create/edit SKUs
    - Add/modify rates
    - Toggle SKU visibility
```

---

## Test Phases and Dependencies

### Phase 1: Foundation (No Dependencies)

#### Module 01: User Management

**Dependencies**: None

**Tests**:
1. Create superuser for test administration
2. Create each test user with appropriate permissions
3. Verify user login via password authentication
4. Verify permission assignments
5. Test user search API endpoint

**Artifacts Created**:
- Test user accounts
- Permission assignments

---

### Phase 2: Project Setup (Requires Phase 1)

#### Module 02: Project Creation

**Dependencies**: Module 01 (users exist)

**Tests**:
1. Create test projects with `test_pi` as PI
2. Verify project appears in user's project list
3. Test project detail view access
4. Verify initial state (no cost allocation, no members beyond PI)

**Artifacts Created**:
- Test projects

#### Module 03: Member Management

**Dependencies**: Module 02 (projects exist)

**Tests**:
1. PI adds Financial Admin to project
2. PI adds Technical Admin to project
3. Technical Admin adds Member to project
4. Verify role-based access restrictions
5. Test multi-role assignment
6. Test member removal
7. Verify Financial Admin cannot be added by Technical Admin

**Artifacts Created**:
- Project member role assignments

---

### Phase 3: Cost Allocation (Requires Phase 2)

#### Module 04: Cost Allocation Workflow

**Dependencies**: Module 03 (members assigned)

**Tests**:
1. **Create Allocation**:
   - Financial Admin creates cost allocation with cost objects
   - Verify percentages must sum to 100%
   - Verify allocation status is PENDING

2. **Approval Workflow**:
   - Billing Manager views pending allocations
   - Billing Manager approves allocation
   - Verify snapshot is created
   - Verify project is now usable for reservations

3. **Rejection Workflow**:
   - Create second project with allocation
   - Billing Manager rejects allocation with notes
   - Verify project cannot be used for reservations
   - Financial Admin modifies and resubmits
   - Billing Manager approves on resubmission

4. **Modification After Approval**:
   - Financial Admin modifies approved allocation
   - Verify new PENDING status
   - Billing Manager approves modification
   - Verify new snapshot is created, old preserved

**Artifacts Created**:
- Approved cost allocations
- Cost allocation snapshots

---

### Phase 4: Rate Management (Requires Phase 1)

#### Module 05: Rate Management

**Dependencies**: Module 01 (rate manager user exists)

**Tests**:
1. **View Current Rates**:
   - Any authenticated user views current rates page
   - Verify visible SKUs are displayed
   - Verify rates show correct values

2. **Rate History**:
   - Rate Manager views SKU detail
   - Verify rate history is displayed

3. **Add New Rate**:
   - Rate Manager adds future rate to SKU
   - Verify rate appears in history
   - Verify rate is not yet effective

4. **Create Custom SKU**:
   - Rate Manager creates new QoS SKU
   - Add initial rate to new SKU
   - Verify SKU appears in rate management

5. **Toggle Visibility**:
   - Rate Manager toggles SKU visibility
   - Verify SKU hidden from public rates page
   - Toggle back and verify visible

**Artifacts Created**:
- Rate history entries
- Custom SKUs (optional)

---

### Phase 5: Reservations (Requires Phases 3, 4)

#### Module 06: Reservation Workflow

**Dependencies**: Module 04 (approved allocations), Module 05 (rates configured)

**Tests**:
1. **Prerequisite Checks**:
   - Verify user cannot reserve without maintenance subscription
   - Set up maintenance subscription for test user
   - Verify user cannot reserve with unapproved allocation

2. **Reservation Request**:
   - Member creates reservation request
   - Verify 7-day advance requirement
   - Verify date range restrictions (max 3 months)
   - Verify reservation appears as PENDING

3. **Approval Workflow**:
   - Rental Manager views pending reservations
   - Rental Manager approves reservation
   - Verify status changes to APPROVED
   - Verify reservation appears on calendar

4. **Decline Workflow**:
   - Create second reservation request
   - Rental Manager declines with notes
   - Verify status is DECLINED
   - Verify requester can see decline reason

5. **Conflict Detection**:
   - Attempt to create overlapping reservation
   - Verify conflict error on approval attempt

6. **Cancellation**:
   - Create and approve reservation
   - User cancels reservation
   - Verify status is CANCELLED

7. **Metadata Management**:
   - Rental Manager adds metadata entry to reservation
   - Verify metadata is visible to managers only

**Artifacts Created**:
- Reservations in various states (APPROVED, DECLINED, CANCELLED)
- Reservation metadata entries

---

### Phase 6: Maintenance Windows (Requires Phase 1)

#### Module 07: Maintenance Window Management

**Dependencies**: Module 01 (rental manager user exists)

**Tests**:
1. **Create Maintenance Window**:
   - Rental Manager creates future maintenance window
   - Verify window appears in list
   - Verify window is editable (future)

2. **Edit Maintenance Window**:
   - Rental Manager edits future window
   - Verify changes are saved

3. **Delete Maintenance Window**:
   - Rental Manager deletes future window
   - Verify window is removed

4. **Past Window Restrictions**:
   - Create window that starts immediately (simulated)
   - Verify past/in-progress windows cannot be edited
   - Verify past/in-progress windows cannot be deleted

5. **Billing Impact Verification**:
   - Create reservation spanning a maintenance window
   - Verify billable hours are reduced by maintenance overlap

**Artifacts Created**:
- Maintenance windows for billing tests

---

### Phase 7: Invoicing (Requires Phases 5, 6)

#### Module 08: Invoice Workflow

**Dependencies**: Module 06 (reservations), Module 07 (maintenance windows)

**Tests**:
1. **Invoice Generation**:
   - Billing Manager accesses invoice list
   - Verify months with reservations are listed
   - View invoice for month with reservations

2. **Invoice Calculations**:
   - Verify correct hours calculated for reservations
   - Verify maintenance window deductions applied
   - Verify cost allocation splits match active snapshot

3. **Invoice Overrides**:
   - Create HOURS override (adjust billable hours)
   - Verify override is reflected in invoice
   - Create COST_SPLIT override (change allocation)
   - Create EXCLUDE override (exclude reservation)
   - Verify all overrides require notes

4. **Delete Override**:
   - Delete an override
   - Verify invoice reverts to calculated values

5. **Finalization**:
   - Billing Manager finalizes invoice
   - Verify invoice status is FINALIZED
   - Verify finalized invoice cannot be edited
   - Export invoice as JSON

6. **Reopen Invoice**:
   - Billing Manager reopens finalized invoice
   - Verify invoice can be edited again

**Artifacts Created**:
- Invoice periods with various states
- Invoice overrides

---

### Phase 8: API Testing (Requires All Previous Phases)

#### Module 09: API Endpoints

**Dependencies**: All previous modules (full data set)

**Tests**:
1. **Authentication**:
   - Verify unauthenticated requests are rejected
   - Verify authenticated requests succeed

2. **Reservations API** (`/api/rentals/`):
   - List reservations with various filters
   - Verify correct results returned
   - Verify permission requirements

3. **Cost Allocations API** (`/api/cost-allocations/`):
   - List allocations with filters
   - Verify correct results returned

4. **Maintenance Windows API** (`/api/maintenance-windows/`):
   - CRUD operations via API
   - Verify permission requirements

5. **Invoice API** (`/api/invoice/`):
   - List invoice months
   - Get invoice detail for specific month
   - Verify JSON export format

6. **Activity Log API** (`/api/activity-log/`):
   - Query logs with filters
   - Verify correct entries returned

7. **User Search API** (`/api/user-search/`):
   - Search for users
   - Verify autocomplete functionality

8. **Subscriptions APIs**:
   - List maintenance subscriptions
   - List QoS subscriptions
   - Verify user-specific vs manager views

**Artifacts Created**:
- None (read-only tests)

---

### Phase 9: Activity Log Verification (Runs Last)

#### Module 10: Activity Log

**Dependencies**: All previous modules (actions logged)

**Tests**:
1. **Log Entry Verification**:
   - Query activity log for each action type
   - Verify entries exist for:
     - User authentication
     - Reservation created/approved/declined
     - Cost allocation submitted/approved/rejected
     - Maintenance window created/edited/deleted
     - Invoice finalized
     - Rate changes

2. **Log Detail Verification**:
   - Verify log entries contain:
     - Correct user
     - Correct action type
     - Correct target object
     - IP address (when applicable)
     - Timestamp

3. **Category Filtering**:
   - Test filtering by each category
   - Verify correct entries returned

**Artifacts Created**:
- None (verification only)

---

## YAML Configuration Schema

### Main Configuration (`config/test_config.yaml`)

```yaml
# Test Suite Configuration
# This file defines global settings and references to other config files

version: "1.0"

# Environment settings
environment:
  base_url: "${TEST_BASE_URL:-http://localhost:8000}"
  admin_user: "${TEST_ADMIN_USER:-admin}"
  admin_password: "${TEST_ADMIN_PASSWORD:-adminpass}"
  
# Database settings (for direct DB access if needed)
database:
  use_fixtures: true
  cleanup_after_tests: "${TEST_CLEANUP:-true}"

# Timeouts (seconds)
timeouts:
  page_load: 30
  api_request: 10
  reservation_advance_days: 7

# Date settings (parameterized for test consistency)
dates:
  # Use relative dates for reproducibility
  reservation_start: "+8d"      # 8 days from now
  reservation_end: "+9d"        # 9 days from now
  maintenance_start: "+10d"     # 10 days from now
  maintenance_end: "+10d 12h"   # 10 days + 12 hours from now
  invoice_month: "current-1"    # Previous month

# References to other config files
includes:
  users: "users.yaml"
  projects: "projects.yaml"
  reservations: "reservations.yaml"
  invoices: "invoices.yaml"
  maintenance_windows: "maintenance_windows.yaml"

# Test module settings
modules:
  enabled:
    - test_01_users
    - test_02_projects
    - test_03_members
    - test_04_cost_allocation
    - test_05_rates
    - test_06_reservations
    - test_07_maintenance
    - test_08_invoices
    - test_09_api
    - test_10_activity_log
  
  # Skip specific tests (useful for debugging)
  skip: []
```

### Users Configuration (`config/users.yaml`)

```yaml
# Test User Definitions
# These users are created during test setup

# Reusable password for all test users
defaults:
  password: &default_password "TestPass123!"
  email_domain: &email_domain "@test.example.com"

users:
  # Project Owner / PI
  - id: user_pi
    username: test_pi
    email: "test_pi${email_domain}"
    password: *default_password
    first_name: "Test"
    last_name: "PI"
    is_staff: false
    is_superuser: false
    permissions: []
    
  # Financial Admin
  - id: user_financial
    username: test_financial_admin
    email: "test_financial${email_domain}"
    password: *default_password
    first_name: "Test"
    last_name: "FinancialAdmin"
    is_staff: false
    is_superuser: false
    permissions: []
    
  # Technical Admin
  - id: user_technical
    username: test_tech_admin
    email: "test_technical${email_domain}"
    password: *default_password
    first_name: "Test"
    last_name: "TechAdmin"
    is_staff: false
    is_superuser: false
    permissions: []
    
  # Regular Member
  - id: user_member
    username: test_member
    email: "test_member${email_domain}"
    password: *default_password
    first_name: "Test"
    last_name: "Member"
    is_staff: false
    is_superuser: false
    permissions: []
    maintenance_status: basic  # Required for reservations
    
  # Rental Manager (system permission)
  - id: user_rental_mgr
    username: test_rental_manager
    email: "test_rental_mgr${email_domain}"
    password: *default_password
    first_name: "Test"
    last_name: "RentalManager"
    is_staff: true
    is_superuser: false
    permissions:
      - "coldfront_orcd_direct_charge.can_manage_rentals"
      
  # Billing Manager (system permission)
  - id: user_billing_mgr
    username: test_billing_manager
    email: "test_billing_mgr${email_domain}"
    password: *default_password
    first_name: "Test"
    last_name: "BillingManager"
    is_staff: true
    is_superuser: false
    permissions:
      - "coldfront_orcd_direct_charge.can_manage_billing"
      
  # Rate Manager (system permission)
  - id: user_rate_mgr
    username: test_rate_manager
    email: "test_rate_mgr${email_domain}"
    password: *default_password
    first_name: "Test"
    last_name: "RateManager"
    is_staff: true
    is_superuser: false
    permissions:
      - "coldfront_orcd_direct_charge.can_manage_rates"
      
  # Multi-role user (for testing role combinations)
  - id: user_multi_role
    username: test_multi_role
    email: "test_multi_role${email_domain}"
    password: *default_password
    first_name: "Test"
    last_name: "MultiRole"
    is_staff: false
    is_superuser: false
    permissions: []
```

### Projects Configuration (`config/projects.yaml`)

```yaml
# Test Project Definitions

defaults:
  status: &default_status "Active"

# Reusable cost objects
cost_objects:
  primary: &cost_obj_primary "TEST-001-ABC"
  secondary: &cost_obj_secondary "TEST-002-XYZ"
  tertiary: &cost_obj_tertiary "TEST-003-DEF"

projects:
  # Primary test project (approved allocation)
  - id: project_primary
    title: "Test Project Primary"
    description: "Primary test project for system tests"
    pi: user_pi                    # Reference to user id
    status: *default_status
    field_of_science: "Computer Science"
    cost_allocation:
      status: approved
      notes: "Test allocation for primary project"
      cost_objects:
        - object: *cost_obj_primary
          percentage: 100.0
    members:
      - user: user_financial
        roles: [financial_admin]
      - user: user_technical
        roles: [technical_admin]
      - user: user_member
        roles: [member]
        
  # Secondary project (for rejection testing)
  - id: project_secondary
    title: "Test Project Secondary"
    description: "Secondary test project for rejection workflow"
    pi: user_pi
    status: *default_status
    field_of_science: "Physics"
    cost_allocation:
      status: pending
      notes: "Test allocation pending approval"
      cost_objects:
        - object: *cost_obj_secondary
          percentage: 60.0
        - object: *cost_obj_tertiary
          percentage: 40.0
    members:
      - user: user_financial
        roles: [financial_admin]
        
  # Multi-role test project
  - id: project_multi_role
    title: "Test Project Multi-Role"
    description: "Project for testing multi-role scenarios"
    pi: user_pi
    status: *default_status
    field_of_science: "Engineering"
    cost_allocation:
      status: approved
      notes: "Allocation for multi-role testing"
      cost_objects:
        - object: *cost_obj_primary
          percentage: 50.0
        - object: *cost_obj_secondary
          percentage: 50.0
    members:
      - user: user_multi_role
        roles: [financial_admin, technical_admin]
```

### Reservations Configuration (`config/reservations.yaml`)

```yaml
# Test Reservation Definitions

defaults:
  node_type: &default_node_type "H200x8"
  start_hour: &start_hour 16  # 4 PM

reservations:
  # Standard approval test
  - id: reservation_approve
    description: "Reservation to be approved"
    project: project_primary
    user: user_member
    node_type: *default_node_type
    node_index: 0                  # First available node
    start_date: "+8d"              # 8 days from now
    num_blocks: 2                  # 17 hours
    rental_notes: "Test reservation for approval workflow"
    expected_status: approved
    
  # Decline test
  - id: reservation_decline
    description: "Reservation to be declined"
    project: project_primary
    user: user_member
    node_type: *default_node_type
    node_index: 1
    start_date: "+9d"
    num_blocks: 1
    rental_notes: "Test reservation for decline workflow"
    expected_status: declined
    decline_reason: "Test decline reason"
    
  # Conflict test (overlaps with reservation_approve)
  - id: reservation_conflict
    description: "Reservation that conflicts with approved reservation"
    project: project_primary
    user: user_technical
    node_type: *default_node_type
    node_index: 0                  # Same node as reservation_approve
    start_date: "+8d"              # Same date
    num_blocks: 1
    rental_notes: "This should fail due to conflict"
    expect_conflict: true
    
  # Cancellation test
  - id: reservation_cancel
    description: "Reservation to be cancelled"
    project: project_primary
    user: user_member
    node_type: *default_node_type
    node_index: 2
    start_date: "+10d"
    num_blocks: 3
    rental_notes: "Test reservation for cancellation"
    expected_status: cancelled
    
  # Reservation spanning maintenance window
  - id: reservation_maintenance_overlap
    description: "Reservation that overlaps with maintenance window"
    project: project_primary
    user: user_member
    node_type: *default_node_type
    node_index: 3
    start_date: "+14d"
    num_blocks: 4
    rental_notes: "Test reservation for maintenance deduction"
    expected_status: approved
    maintenance_overlap_hours: 8  # Expected deduction

validation_tests:
  # Tests that should fail validation
  - id: validation_no_allocation
    description: "Reservation with unapproved allocation should fail"
    project: project_secondary      # Has pending allocation
    user: user_member
    expected_error: "approved cost allocation"
    
  - id: validation_advance_notice
    description: "Reservation without 7-day notice should fail"
    project: project_primary
    user: user_member
    start_date: "+3d"               # Only 3 days ahead
    expected_error: "7-day lead time"
    
  - id: validation_max_date
    description: "Reservation too far in future should fail"
    project: project_primary
    user: user_member
    start_date: "+120d"             # 4 months ahead
    expected_error: "3 months in advance"
```

### Maintenance Windows Configuration (`config/maintenance_windows.yaml`)

```yaml
# Test Maintenance Window Definitions

maintenance_windows:
  # Standard maintenance window
  - id: maint_standard
    title: "Scheduled System Maintenance"
    description: "Regular monthly maintenance"
    start_datetime: "+14d 08:00"    # 14 days from now at 8 AM
    end_datetime: "+14d 20:00"      # Same day at 8 PM
    created_by: user_rental_mgr
    expected_duration_hours: 12
    
  # Window for edit testing
  - id: maint_editable
    title: "Editable Maintenance Window"
    description: "Window to test edit functionality"
    start_datetime: "+20d 00:00"
    end_datetime: "+20d 12:00"
    created_by: user_rental_mgr
    expected_duration_hours: 12
    
  # Window for delete testing
  - id: maint_deletable
    title: "Deletable Maintenance Window"
    description: "Window to test delete functionality"
    start_datetime: "+25d 00:00"
    end_datetime: "+25d 06:00"
    created_by: user_rental_mgr
    expected_duration_hours: 6

edit_tests:
  - window: maint_editable
    new_title: "Updated Maintenance Window"
    new_end_datetime: "+20d 18:00"
    expected_new_duration: 18

delete_tests:
  - window: maint_deletable
    verify_removed: true
```

### Invoices Configuration (`config/invoices.yaml`)

```yaml
# Test Invoice Definitions

# Invoice periods to test
invoice_periods:
  - id: invoice_current
    year: "${CURRENT_YEAR}"
    month: "${CURRENT_MONTH}"
    description: "Current month invoice"
    expected_status: draft
    
  - id: invoice_previous
    year: "${PREVIOUS_YEAR}"
    month: "${PREVIOUS_MONTH}"
    description: "Previous month invoice for finalization testing"
    expected_status: finalized

# Override tests
override_tests:
  - id: override_hours
    invoice: invoice_current
    reservation: reservation_approve
    override_type: hours
    original_hours: 17
    override_hours: 12
    notes: "Test hours override - system maintenance"
    
  - id: override_cost_split
    invoice: invoice_current
    reservation: reservation_approve
    override_type: cost_split
    new_split:
      - cost_object: "TEST-001-ABC"
        percentage: 70.0
      - cost_object: "TEST-002-XYZ"
        percentage: 30.0
    notes: "Test cost split override - reallocation"
    
  - id: override_exclude
    invoice: invoice_current
    reservation: reservation_cancel
    override_type: exclude
    notes: "Test exclude override - cancelled reservation"

finalization_tests:
  - invoice: invoice_previous
    finalize: true
    export_json: true
    reopen: true
    verify_editable_after_reopen: true
```

---

## Test Module Specifications

### Module 01: User Management (`test_01_users.py`)

**Purpose**: Create and verify test users with appropriate roles and permissions.

**Setup**:
- Load users from `config/users.yaml`
- Create Django User objects
- Assign permissions

**Tests**:

```python
class TestUserManagement:
    def test_create_users(self):
        """Create all test users defined in YAML config."""
        
    def test_user_login(self):
        """Verify each user can log in via password authentication."""
        
    def test_permission_assignment(self):
        """Verify users have correct permissions."""
        
    def test_rental_manager_permissions(self):
        """Verify rental manager can access rental management views."""
        
    def test_billing_manager_permissions(self):
        """Verify billing manager can access billing views."""
        
    def test_rate_manager_permissions(self):
        """Verify rate manager can access rate management views."""
        
    def test_user_search_api(self):
        """Test user search API endpoint."""
```

**Cleanup**: None (users persist for subsequent tests)

---

### Module 02: Project Creation (`test_02_projects.py`)

**Purpose**: Create test projects with PIs.

**Dependencies**: Module 01

**Setup**:
- Load projects from `config/projects.yaml`
- Use PI users created in Module 01

**Tests**:

```python
class TestProjectCreation:
    def test_create_projects(self):
        """Create all test projects defined in YAML config."""
        
    def test_project_visible_to_pi(self):
        """Verify project appears in PI's project list."""
        
    def test_project_detail_access(self):
        """Verify PI can access project detail view."""
        
    def test_initial_state(self):
        """Verify project has no cost allocation or members initially."""
```

---

### Module 03: Member Management (`test_03_members.py`)

**Purpose**: Test adding and managing project members with various roles.

**Dependencies**: Modules 01, 02

**Tests**:

```python
class TestMemberManagement:
    def test_pi_adds_financial_admin(self):
        """PI can add Financial Admin to project."""
        
    def test_pi_adds_technical_admin(self):
        """PI can add Technical Admin to project."""
        
    def test_technical_admin_adds_member(self):
        """Technical Admin can add Member to project."""
        
    def test_technical_admin_cannot_add_financial_admin(self):
        """Technical Admin cannot add Financial Admin role."""
        
    def test_multi_role_assignment(self):
        """User can have multiple roles in a project."""
        
    def test_update_member_roles(self):
        """Existing member roles can be updated."""
        
    def test_remove_member(self):
        """Member can be removed from project."""
        
    def test_financial_admin_excluded_from_billing(self):
        """Financial Admin (without other roles) excluded from billing."""
```

---

### Module 04: Cost Allocation (`test_04_cost_allocation.py`)

**Purpose**: Test cost allocation creation and approval workflow.

**Dependencies**: Modules 01, 02, 03

**Tests**:

```python
class TestCostAllocationWorkflow:
    def test_create_allocation(self):
        """Financial Admin creates cost allocation."""
        
    def test_percentage_validation(self):
        """Cost object percentages must sum to 100%."""
        
    def test_allocation_pending_status(self):
        """New allocation has PENDING status."""
        
    def test_billing_manager_sees_pending(self):
        """Billing Manager sees pending allocations in review list."""
        
    def test_approve_allocation(self):
        """Billing Manager approves allocation."""
        
    def test_snapshot_created_on_approval(self):
        """Snapshot is created when allocation is approved."""
        
    def test_reject_allocation(self):
        """Billing Manager rejects allocation with notes."""
        
    def test_resubmit_rejected_allocation(self):
        """Financial Admin can modify and resubmit rejected allocation."""
        
    def test_modify_approved_allocation(self):
        """Modifying approved allocation creates new PENDING state."""
        
    def test_snapshot_preserved_on_modification(self):
        """Previous snapshot preserved when new one created."""
```

---

### Module 05: Rate Management (`test_05_rates.py`)

**Purpose**: Test rate and SKU management.

**Dependencies**: Module 01 (rate manager)

**Tests**:

```python
class TestRateManagement:
    def test_view_current_rates(self):
        """Authenticated user can view current rates."""
        
    def test_visible_skus_displayed(self):
        """Only visible SKUs shown on public page."""
        
    def test_rate_manager_sku_detail(self):
        """Rate Manager can view SKU detail with history."""
        
    def test_add_rate(self):
        """Rate Manager adds new rate to SKU."""
        
    def test_rate_effective_date(self):
        """Rate becomes effective on specified date."""
        
    def test_create_sku(self):
        """Rate Manager creates new SKU."""
        
    def test_toggle_visibility(self):
        """Rate Manager toggles SKU visibility."""
```

---

### Module 06: Reservations (`test_06_reservations.py`)

**Purpose**: Test reservation creation, approval, and lifecycle.

**Dependencies**: Modules 01-05

**Tests**:

```python
class TestReservationWorkflow:
    def test_maintenance_subscription_required(self):
        """User cannot reserve without maintenance subscription."""
        
    def test_set_maintenance_subscription(self):
        """Set up maintenance subscription for test user."""
        
    def test_approved_allocation_required(self):
        """User cannot reserve with unapproved allocation."""
        
    def test_create_reservation_request(self):
        """Member creates reservation request."""
        
    def test_advance_notice_required(self):
        """Reservation requires 7-day advance notice."""
        
    def test_max_date_restriction(self):
        """Reservation cannot exceed 3 months in future."""
        
    def test_reservation_pending_status(self):
        """New reservation has PENDING status."""
        
    def test_rental_manager_sees_pending(self):
        """Rental Manager sees pending reservations."""
        
    def test_approve_reservation(self):
        """Rental Manager approves reservation."""
        
    def test_reservation_on_calendar(self):
        """Approved reservation appears on calendar."""
        
    def test_decline_reservation(self):
        """Rental Manager declines reservation with notes."""
        
    def test_conflict_detection(self):
        """Overlapping reservation detected on approval."""
        
    def test_cancel_reservation(self):
        """User can cancel their reservation."""
        
    def test_add_metadata(self):
        """Rental Manager adds metadata to reservation."""
        
    def test_metadata_manager_only(self):
        """Metadata visible to managers only."""
```

---

### Module 07: Maintenance Windows (`test_07_maintenance.py`)

**Purpose**: Test maintenance window CRUD operations.

**Dependencies**: Module 01 (rental manager)

**Tests**:

```python
class TestMaintenanceWindows:
    def test_create_maintenance_window(self):
        """Rental Manager creates maintenance window."""
        
    def test_window_in_list(self):
        """Window appears in maintenance windows list."""
        
    def test_edit_future_window(self):
        """Rental Manager can edit future window."""
        
    def test_delete_future_window(self):
        """Rental Manager can delete future window."""
        
    def test_cannot_edit_past_window(self):
        """Past or in-progress window cannot be edited."""
        
    def test_cannot_delete_past_window(self):
        """Past or in-progress window cannot be deleted."""
        
    def test_billing_deduction(self):
        """Maintenance window reduces billable hours."""
```

---

### Module 08: Invoices (`test_08_invoices.py`)

**Purpose**: Test invoice generation, editing, and finalization.

**Dependencies**: Modules 06, 07

**Tests**:

```python
class TestInvoiceWorkflow:
    def test_invoice_list_access(self):
        """Billing Manager can access invoice list."""
        
    def test_months_with_reservations(self):
        """Months with reservations appear in list."""
        
    def test_view_invoice(self):
        """Billing Manager can view invoice detail."""
        
    def test_hours_calculation(self):
        """Invoice calculates correct hours per reservation."""
        
    def test_maintenance_deduction(self):
        """Maintenance window deduction applied correctly."""
        
    def test_cost_allocation_split(self):
        """Cost allocated according to active snapshot."""
        
    def test_create_hours_override(self):
        """Create override to adjust hours."""
        
    def test_create_cost_split_override(self):
        """Create override to change cost split."""
        
    def test_create_exclude_override(self):
        """Create override to exclude reservation."""
        
    def test_override_requires_notes(self):
        """Override must include notes."""
        
    def test_delete_override(self):
        """Delete override reverts to calculated values."""
        
    def test_finalize_invoice(self):
        """Billing Manager finalizes invoice."""
        
    def test_finalized_not_editable(self):
        """Finalized invoice cannot be edited."""
        
    def test_export_invoice_json(self):
        """Export invoice as JSON."""
        
    def test_reopen_invoice(self):
        """Billing Manager can reopen finalized invoice."""
```

---

### Module 09: API Testing (`test_09_api.py`)

**Purpose**: Test REST API endpoints.

**Dependencies**: All previous modules

**Tests**:

```python
class TestAPIEndpoints:
    def test_unauthenticated_rejected(self):
        """Unauthenticated requests are rejected."""
        
    def test_reservations_api_list(self):
        """GET /api/rentals/ returns reservations."""
        
    def test_reservations_api_filters(self):
        """Reservation API supports filtering."""
        
    def test_cost_allocations_api(self):
        """GET /api/cost-allocations/ returns allocations."""
        
    def test_maintenance_windows_api_crud(self):
        """Maintenance windows API supports CRUD."""
        
    def test_invoice_api_list(self):
        """GET /api/invoice/ returns invoice months."""
        
    def test_invoice_api_detail(self):
        """GET /api/invoice/<year>/<month>/ returns detail."""
        
    def test_activity_log_api(self):
        """GET /api/activity-log/ returns logs."""
        
    def test_user_search_api(self):
        """GET /api/user-search/ returns users."""
        
    def test_subscriptions_api(self):
        """Subscription APIs return correct data."""
        
    def test_skus_api(self):
        """GET /api/skus/ returns SKUs with rates."""
```

---

### Module 10: Activity Log (`test_10_activity_log.py`)

**Purpose**: Verify all actions are logged correctly.

**Dependencies**: All previous modules

**Tests**:

```python
class TestActivityLog:
    def test_authentication_logged(self):
        """User login is logged."""
        
    def test_reservation_actions_logged(self):
        """Reservation create/approve/decline logged."""
        
    def test_cost_allocation_actions_logged(self):
        """Cost allocation submit/approve/reject logged."""
        
    def test_maintenance_window_actions_logged(self):
        """Maintenance window CRUD logged."""
        
    def test_invoice_actions_logged(self):
        """Invoice finalization logged."""
        
    def test_rate_actions_logged(self):
        """Rate changes logged."""
        
    def test_log_entry_details(self):
        """Log entries contain required details."""
        
    def test_category_filtering(self):
        """Activity log can be filtered by category."""
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/system-tests.yml
name: System Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM UTC

jobs:
  system-tests:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: coldfront_test
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
          
      redis:
        image: redis:7
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r tests/system_tests/requirements.txt
          
      - name: Set up test database
        run: |
          python manage.py migrate
          python manage.py loaddata tests/system_tests/fixtures/base_data.json
          
      - name: Run system tests
        env:
          TEST_BASE_URL: http://localhost:8000
          TEST_ADMIN_USER: admin
          TEST_ADMIN_PASSWORD: ${{ secrets.TEST_ADMIN_PASSWORD }}
          DATABASE_URL: postgres://postgres:postgres@localhost:5432/coldfront_test
        run: |
          python manage.py runserver &
          sleep 5
          python tests/system_tests/run_tests.py --config tests/system_tests/config/test_config.yaml
          
      - name: Upload test results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: test-results
          path: tests/system_tests/results/
```

### Buildkite Example

```yaml
# .buildkite/pipeline.yml
steps:
  - label: ":python: System Tests"
    commands:
      - pip install -r requirements.txt
      - pip install -r tests/system_tests/requirements.txt
      - ./tests/system_tests/run_tests.sh
    plugins:
      - docker-compose#v4.14.0:
          config: tests/system_tests/docker-compose.yml
          run: tests
    artifact_paths:
      - "tests/system_tests/results/**/*"
```

### Woodpecker CI Example

```yaml
# .woodpecker.yml
pipeline:
  system-tests:
    image: python:3.11
    commands:
      - pip install -r requirements.txt
      - pip install -r tests/system_tests/requirements.txt
      - ./tests/system_tests/run_tests.sh
    environment:
      - TEST_BASE_URL=http://app:8000
    when:
      event: [push, pull_request]
      
services:
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=coldfront_test
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      
  app:
    image: coldfront:test
    commands:
      - python manage.py runserver 0.0.0.0:8000
```

---

## Implementation Guide

### Step-by-Step Implementation Order

1. **Create Directory Structure**
   - Create all directories as specified in architecture
   - Add `__init__.py` files to Python packages

2. **Implement Utilities**
   - `yaml_loader.py`: YAML parsing with variable substitution
   - `api_client.py`: REST API client with authentication
   - `assertions.py`: Custom test assertions
   - `base.py`: Base test class with common setup/teardown

3. **Create YAML Configuration Files**
   - Start with `test_config.yaml` and `users.yaml`
   - Add other config files as needed

4. **Implement Test Modules (in order)**
   - Module 01: Users
   - Module 02: Projects
   - Module 03: Members
   - Continue in numbered order

5. **Create Test Runner**
   - `run_tests.py`: Main test runner script
   - `run_tests.sh`: Shell wrapper for CI

6. **CI/CD Integration**
   - Create workflow files for target CI system
   - Test locally first with Docker

### Implementation Notes for Agents

When implementing each module:

1. **Read the YAML config first** to understand test data
2. **Follow the dependency chain** - don't implement module N before modules 1 to N-1 are working
3. **Use the base test class** for common functionality
4. **Log all actions** for debugging
5. **Clean up conditionally** based on config setting
6. **Return clear error messages** on failure
7. **Use parameterization** for similar tests with different data

### Testing the Test Suite

Before running the full suite:

1. Test YAML loading in isolation
2. Test individual modules with `--module` flag
3. Run with `--dry-run` to validate config
4. Check database state after each module

---

## Appendix: Quick Reference

### YAML Variable Substitution

```yaml
# Environment variables
base_url: "${TEST_BASE_URL:-http://localhost:8000}"

# Relative dates
start_date: "+7d"      # 7 days from now
start_date: "-1d"      # Yesterday
start_date: "current"  # Today

# References
user: user_pi          # References users.yaml id
project: project_primary  # References projects.yaml id
```

### Test Status Codes

| Code | Meaning |
|------|---------|
| 0 | All tests passed |
| 1 | Test failures |
| 2 | Configuration error |
| 3 | Dependency error |
| 4 | Environment error |

### Common Assertions

```python
# User permissions
assert_user_has_permission(user, "can_manage_rentals")

# Object state
assert_status_equals(reservation, "APPROVED")

# API response
assert_api_response_ok(response)
assert_api_returns_count(response, 5)

# Access control
assert_access_denied(response)
assert_redirect_to_login(response)
```

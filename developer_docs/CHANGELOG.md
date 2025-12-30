# Changelog

All notable changes to the ORCD Direct Charge plugin are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### December 29, 2025

#### Added - Home2 Dashboard & UX Improvements

##### Home2 Dashboard Page (`b6c29ee`, `8ed6a25`, `e159e3f`)
- New dashboard page at `/nodes/home2/` for previewing redesigned home experience
- Four summary cards with icons and action buttons:
  - **My Rentals**: upcoming/pending/past counts, next 3 reservations
  - **My Projects**: owned/member counts, recent projects list, create button
  - **My Account**: status badge, billing project display
  - **My Billing**: approval status counts, projects needing attention
- Bootstrap 4 responsive card layout (2x2 grid on desktop, single column on mobile)
- Home2 tab added to navbar with dashboard icon
- Help icon (?) on each card header with Bootstrap popover
- Help text includes descriptions and clickable mailto link for orcd-help@mit.edu
- Dismissible close button (×) on popover headers
- Fixed mobile scroll-to-top issue by using button elements instead of anchors

##### Member Removal with Notes (`2961194`)
- Replaced basic JavaScript `confirm()` with Bootstrap modal for member removal
- Modal includes member name, optional notes textarea for removal reason
- Removal notes stored in ActivityLog `extra_data` for audit trail
- Owner protection: cannot remove project owner (enforced in view)

##### Maintenance Fee Cost Allocation Validation (`2aa1cdb`)
- Enhanced validation for account maintenance fee billing project selection
- Backend: Added `has_approved_cost_allocation()` check in `update_maintenance_status` view
- Frontend: New `get_projects_for_maintenance_fee` template tag filters dropdown options
- Only projects with approved cost allocations appear in billing project dropdown
- Warning message displays when no eligible projects exist

##### Navigation & Menu Updates (`8e2625f`, `e2106bd`)
- Activity Log added to Admin Functions menu
- Simplified Project dropdown menu for cleaner navigation

##### Account Maintenance Column (`60cb48e`)
- Added Account Maintenance column to Project Members page
- Shows each member's maintenance fee status badge

##### Autocomplete Add Users (`6fa24c3`)
- Replaced legacy add-users search with autocomplete interface
- Uses Select2 dropdown with API search

---

### December 27, 2025

#### Added - My Reservations Page
- New user-centric page at `/nodes/my/reservations/`
- Shows reservations from all projects where user has a role
- Categorized tabs: Upcoming, Pending, Past, Declined/Cancelled
- Summary cards showing counts per category
- Displays user's roles for each reservation's project

---

### December 26, 2025

#### Added - Activity Logging
- `ActivityLog` model for comprehensive audit trail
- Signal handlers for authentication events (login, logout, failed login)
- Signal handlers for model changes (reservations, members, cost allocations, maintenance)
- Activity logging in all key view POST methods
- Web interface at `/nodes/activity-log/` with filters and pagination
- API endpoint at `/nodes/api/activity-log/` for programmatic access
- Admin interface for superusers (read-only)
- Access restricted to Billing/Rental Managers and superusers

**Commit**: `041a669`

---

### December 22-23, 2025

#### Added - Invoice Reporting & API

##### Invoice Preparation Feature (`ade0c26`)
- Monthly invoice reports with cost object breakdowns
- `InvoicePeriod` model for tracking invoice status (Draft/Finalized)
- `InvoiceLineOverride` model for manual adjustments
- `CostAllocationSnapshot` and `CostObjectSnapshot` for historical billing accuracy
- Month selector view at `/nodes/billing/invoice/`
- Invoice detail view with per-project and per-reservation breakdowns

##### Invoice API Endpoints (`5b7215a`)
- `GET /nodes/api/invoice/` - List months with reservations
- `GET /nodes/api/invoice/YYYY/MM/` - Full invoice report JSON
- Programmatic access for CLI tools and integrations

##### Invoice UI Improvements (`2068f9c`, `29778f5`)
- Renamed "Invoice Preparation" tab to "Invoice Reporting"
- Added filter options by project owner and title
- JSON export functionality

##### API Token Display (`b35b53d`)
- API token shown on user profile page
- Copy-to-clipboard functionality
- Token regeneration capability

##### Pre-login Page (`c02d5e3`)
- ORCD-branded pre-login page with rental portal information

---

### December 20, 2025

#### Added - Cost Allocation & Member Roles

##### Cost Allocation Approval Workflow (`d0ef33a`)
- `ProjectCostAllocation` approval states (pending, approved, rejected)
- Billing Manager role with `can_manage_billing` permission
- `setup_billing_manager` management command
- Review interface at `/nodes/billing/allocation/<pk>/review/`
- Pending allocations list at `/nodes/billing/pending/`

##### Project Member Roles (`b47eeb9`, `dda4c52`, `6c41012`)
- `ProjectMemberRole` model with four-tier hierarchy:
  - Owner (implicit via project.pi)
  - Financial Admin
  - Technical Admin
  - Member
- Multi-role support (users can have multiple roles)
- Role-based permissions for reservations and maintenance fee billing
- Member management views at `/nodes/project/<pk>/members/`

##### Cost Object Allocation (`6832493`)
- `ProjectCostAllocation` model for project billing settings
- `ProjectCostObject` model for cost object percentage splits
- Cost allocation editor at `/nodes/project/<pk>/cost-allocation/`
- Percentage validation (must sum to 100%)

##### Member Management UI
- Add member with role selection (`04957cc`)
- Username autocomplete via API (`/nodes/api/users/search/`)
- Override ColdFront's add-users flow (`63bd122`)
- Fix duplicate field display (`8840d5c`)
- Logging for member operations (`33cfd3e`)

#### Changed
- Left-shift rental calendar to start from today's date (`f64b1d3`)
- Remove Field of Science from project update form (`9a2f2fe`)

#### Fixed
- Billing project requirement for maintenance fees (`46735df`)
- Auto-reset maintenance when user loses project eligibility

---

### December 19, 2025

#### Added - Maintenance Status & Branding

##### Account Maintenance Fee Status (`4a2d4d2`)
- `UserMaintenanceStatus` model (inactive, basic, advanced)
- Displayed on User Profile page with edit modal
- Billing project selection for non-inactive statuses
- Signal handlers to reset status when project access changes

##### Auto-Configuration Features (`fc1e0b1`)
- `AUTO_PI_ENABLE` setting - automatically set all users as PIs
- `AUTO_DEFAULT_PROJECT_ENABLE` - create personal and group projects
- Environment variable and `local_settings.py` configuration
- Startup application to existing users
- Signal handlers for new users

##### Branding Customizations
- ORCD favicon and "ORCD Rental Portal" title (`940e4df`)
- ORCD logo in navbar (`5bd95a1`)
- "Project Owner" terminology (`b9a462a`)
- Simplified project detail page (`ca652c7`)
- Hide PI Status when AUTO_PI_ENABLE is True (`64c9d3e`)

##### Group Projects (`b9a462a`)
- Renamed default projects to `USERNAME_personal`
- Added `USERNAME_group` projects for team collaboration
- Migrations to rename existing projects

#### Changed
- Rename 'Rental Managers' group to 'Rental Manager' (`588c1ad`)
- Change 'University Role(s)' to 'Role(s)' on user profile (`4935601`)

#### Fixed
- Fix user_profile template settings_value load (`424defe`)

---

### December 18-19, 2025

#### Added - Rental Calendar & Reservations

##### Rental Calendar (`e979478`)
- Calendar view showing H200x8 node availability by month
- Color-coded availability (available, rented, partial)
- Navigation between months
- 3-month forward visibility limit (`65cdca7`)

##### Reservation System
- `Reservation` model with status workflow
- `ReservationMetadataEntry` model for manager notes
- Reservation request form linked to ColdFront projects
- 7-day advance booking requirement (`317233c`, `224ef37`)
- 9 AM end time cap for reservations (`ddae369`)

##### Rental Manager Features
- Rental manager dashboard at `/nodes/renting/manage/`
- Approve/decline reservation workflow
- `setup_rental_manager` management command (`8ad3d0f`)
- Booking management metadata entries (`63c73f2`)

##### Calendar Visualization
- Partial rental visualization with diagonal split (`a3fee47`)
- Person icon for user's project bookings (`cde59e9`)
- Pending reservation indicator ("P") (`bd80f9c`)
- Simplified legend (`651d340`)

##### REST API (`6ac82b8`)
- `GET /nodes/api/rentals/` endpoint
- Filtering by status, node, project, user, date
- Token authentication
- CLI tool in `helper_programs/orcd_dc_cli/`

#### Changed
- Update 7-day validation error message (`8351030`)
- Rename 'Reservation Rules' to 'Reservation Configuration' (`985d1f0`)

---

### December 18, 2025

#### Added - Node Instance Management

##### Initial Release (`8b834e2` and earlier)
- `NodeType` model for GPU/CPU node type definitions
- `GpuNodeInstance` model for GPU nodes
- `CpuNodeInstance` model for CPU nodes
- Natural key support for fixture updates
- Django admin interface
- Node instance list view at `/nodes/`
- Node detail views at `/nodes/gpu/<pk>/` and `/nodes/cpu/<pk>/`

##### Fixtures
- `node_types.json` - H200x8, L40Sx4, CPU_384G, CPU_1500G
- `gpu_node_instances.json` - 62 GPU nodes (12 H200x8, 50 L40Sx4)
- `cpu_node_instances.json` - 50 CPU nodes
- `node_resource_types.json` - ColdFront ResourceType entries

##### Helper Programs
- CSV to Django fixture converter
- Slurm scontrol to CSV converter

##### Template Overrides
- Override ColdFront navbar with plugin links
- Hide Center Summary (configurable)
- Hide Allocations section (configurable)

---

## Migration History

| Version | Migration | Description |
|---------|-----------|-------------|
| 0001 | `0001_initial` | NodeType, GpuNodeInstance, CpuNodeInstance |
| 0002 | `0002_rename_cpu_node_labels` | Field renaming |
| 0003 | `0003_reservation` | Reservation model |
| 0004 | `0004_reservation_rental_notes` | rental_notes, rental_management_metadata |
| 0005 | `0005_reservationmetadataentry` | ReservationMetadataEntry model |
| 0006 | `0006_migrate_metadata_to_entries` | Data migration for metadata |
| 0007 | `0007_rename_default_projects` | USERNAME_default_project → USERNAME_personal |
| 0008 | `0008_delete_old_default_projects` | Clean up old project names |
| 0009 | `0009_create_group_projects` | Create USERNAME_group projects |
| 0010 | `0010_usermaintenancestatus` | UserMaintenanceStatus model |
| 0011 | `0011_create_maintenance_status_for_users` | Initialize status for existing users |
| 0012 | `0012_usermaintenancestatus_billing_project` | Add billing_project field |
| 0013 | `0013_project_cost_allocation` | ProjectCostAllocation, ProjectCostObject |
| 0014 | `0014_projectmemberrole` | ProjectMemberRole model |
| 0015 | `0015_initialize_member_roles` | Initialize roles for existing members |
| 0016 | `0016_change_projectmemberrole_unique_constraint` | Allow multiple roles per user |
| 0017 | `0017_add_cost_allocation_approval` | Approval workflow fields |
| 0018 | `0018_costallocationsnapshot_invoiceperiod...` | Invoice preparation models |
| 0019 | `0019_backfill_cost_allocation_snapshots` | Historical snapshot backfill |
| 0020 | `0020_activitylog` | ActivityLog model |

---

## Commit Reference

Recent commits in reverse chronological order:

| Commit | Date | Description |
|--------|------|-------------|
| `e159e3f` | 2025-12-29 | Enhance Home2 dashboard cards with help popovers |
| `2aa1cdb` | 2025-12-29 | Require approved cost allocation for maintenance fee billing |
| `2961194` | 2025-12-29 | Add confirmation modal with notes for member removal |
| `8ed6a25` | 2025-12-29 | Reorder Home2 dashboard cards for better UX |
| `b6c29ee` | 2025-12-28 | Add Home2 dashboard page with summary cards |
| `8e2625f` | 2025-12-28 | Add Activity Log to Admin Functions menu |
| `e2106bd` | 2025-12-28 | Simplify Project dropdown menu for cleaner navigation |
| `60cb48e` | 2025-12-27 | Add Account Maintenance column to Project Members page |
| `6fa24c3` | 2025-12-27 | Replace legacy add-users search with autocomplete interface |
| `041a669` | 2025-12-26 | Add comprehensive activity logging feature |
| `29778f5` | 2025-12-23 | Add filter options to invoice detail page |
| `b35b53d` | 2025-12-23 | Add API token display to user profile page |
| `5b7215a` | 2025-12-23 | Add Invoice API endpoints for CLI/programmatic access |
| `2068f9c` | 2025-12-22 | Rename Invoice Preparation tab to Invoice Reporting |
| `ade0c26` | 2025-12-22 | Add Invoice Preparation feature for billing management |
| `c02d5e3` | 2025-12-22 | Add ORCD-branded pre-login page with rental portal information |
| `d0ef33a` | 2025-12-20 | Add Cost Allocation approval workflow with Billing Manager role |
| `04957cc` | 2025-12-20 | Add username autocomplete to Add Member form |
| `6c41012` | 2025-12-20 | Fix ProjectMembersView to group roles by user |
| `dda4c52` | 2025-12-20 | Add multi-role support for project members |
| `8840d5c` | 2025-12-20 | Fix duplicate field display in add-users search results |
| `63bd122` | 2025-12-20 | Override add-users page to use ORCD roles and remove allocations |
| `33cfd3e` | 2025-12-20 | Add logging for member role management operations |
| `b47eeb9` | 2025-12-20 | Add project member roles feature with four-tier hierarchy |
| `6832493` | 2025-12-20 | Add project cost object allocation feature |
| `f64b1d3` | 2025-12-20 | Left-shift rental calendar to start from today's date |
| `9a2f2fe` | 2025-12-20 | Remove Field of Science from project update form |
| `46735df` | 2025-12-20 | Add billing project requirement and auto-reset for maintenance fees |
| `4a2d4d2` | 2025-12-19 | Add Account Maintenance Fee Status feature |
| `ca652c7` | 2025-12-19 | Simplify project detail page for rental portal |
| `940e4df` | 2025-12-19 | Customize branding: favicon, title, and terminology |
| `b9a462a` | 2025-12-19 | Add USERNAME_group project and rename terminology |
| `5bd95a1` | 2025-12-19 | Change site logo to ORCD logo |
| `fc1e0b1` | 2025-12-19 | Add auto-PI and auto-default-project features |
| `e979478` | 2025-12-18 | Add H200x8 GPU node rental calendar and reservation system |
| `6ac82b8` | 2025-12-19 | Add Rentals REST API endpoint and CLI tool |
| `8ad3d0f` | 2025-12-19 | Add Rental Manager role with management command and navbar link |

---

## Breaking Changes

### December 2025

1. **Reservation Requires Approved Cost Allocation**
   - Projects must have an approved cost allocation before reservations can be made
   - Migration: Submit cost allocation, wait for Billing Manager approval

2. **ProjectMemberRole Multi-Role Support** (`0016`)
   - Changed unique constraint to allow multiple roles per user
   - No action required - backward compatible

3. **USERNAME_personal and USERNAME_group Projects** (`0007-0009`)
   - Renamed `USERNAME_default_project` to `USERNAME_personal`
   - Added `USERNAME_group` projects
   - Automatic migration for existing projects

---

## Related Documentation

- [README](README.md) - Architecture overview
- [Data Models](data-models.md) - Complete model reference
- [Views & URLs](views-urls.md) - View and URL documentation
- [API Reference](api-reference.md) - REST API documentation
- [Signals](signals.md) - Signal handlers and auto-configuration



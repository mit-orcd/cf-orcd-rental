# Views and URL Routing

This document describes all view classes and URL patterns in the ORCD Direct Charge plugin.

**Sources**:
- [`coldfront_orcd_direct_charge/views/`](../coldfront_orcd_direct_charge/views/) - View package (refactored Jan 2026)
- [`coldfront_orcd_direct_charge/urls.py`](../coldfront_orcd_direct_charge/urls.py)

> **Note**: Views were refactored from a monolithic `views.py` to a `views/` package in Jan 2026.
> See [CODE_ORGANIZATION.md](CODE_ORGANIZATION.md) for details on the module structure.

---

## Table of Contents

- [URL Overview](#url-overview)
- [URL Configuration](#url-configuration)
- [Dashboard Views](#dashboard-views)
- [Node Instance Views](#node-instance-views)
- [Rental Calendar Views](#rental-calendar-views)
- [Rental Manager Views](#rental-manager-views)
- [User Views](#user-views)
- [Project Cost Allocation Views](#project-cost-allocation-views)
- [Billing Manager Views](#billing-manager-views)
- [Invoice Views](#invoice-views)
- [Member Management Views](#member-management-views)
- [Rate Management Views](#rate-management-views)
- [Activity Log Views](#activity-log-views)
- [Template Override Views](#template-override-views)

---

## URL Overview

All plugin URLs are prefixed with `/nodes/` (configured in ColdFront's `urls.py`).

| Category | URL Pattern | Description |
|----------|-------------|-------------|
| **Dashboard** | `/` | Dashboard home page (template override) |
| **Node Instances** | `/nodes/` | List all nodes |
| | `/nodes/gpu/<pk>/` | GPU node detail |
| | `/nodes/cpu/<pk>/` | CPU node detail |
| **Rental Calendar** | `/nodes/renting/` | Availability calendar |
| | `/nodes/renting/request/` | Submit reservation |
| **Reservation** | `/nodes/reservation/<pk>/` | Reservation detail page |
| **Rental Management** | `/nodes/renting/manage/` | Manager dashboard |
| | `/nodes/renting/manage/<pk>/approve/` | Approve reservation |
| | `/nodes/renting/manage/<pk>/decline/` | Decline reservation |
| | `/nodes/renting/manage/<pk>/metadata/` | Add metadata |
| **User** | `/nodes/user/update-maintenance-status/` | AJAX maintenance update |
| | `/nodes/my/reservations/` | User's reservations |
| **Project** | `/nodes/project/<pk>/reservations/` | Project reservations |
| | `/nodes/project/<pk>/cost-allocation/` | Edit cost allocation |
| **Billing** | `/nodes/billing/pending/` | Pending allocations |
| | `/nodes/billing/allocation/<pk>/review/` | Review allocation |
| **Invoice** | `/nodes/billing/invoice/` | Month selector |
| | `/nodes/billing/invoice/<year>/<month>/` | Invoice detail |
| | `/nodes/billing/invoice/<year>/<month>/edit/` | Edit overrides |
| | `/nodes/billing/invoice/<year>/<month>/export/` | Export JSON |
| **Members** | `/nodes/project/<pk>/members/` | List members |
| | `/nodes/project/<pk>/members/add/` | Add member |
| | `/nodes/project/<pk>/members/<user_pk>/update/` | Update roles |
| | `/nodes/project/<pk>/members/<user_pk>/remove/` | Remove member |
| **Project Add Users** | `/nodes/project/<pk>/add-users/` | Autocomplete add users |
| | `/nodes/project/<pk>/add-users-search-results/` | Search results |
| **Rate Management** | `/nodes/rates/` | Rate management dashboard |
| | `/nodes/rates/sku/<pk>/` | SKU rate detail and history |
| | `/nodes/rates/sku/<pk>/add-rate/` | Add new rate for SKU |
| | `/nodes/rates/sku/create/` | Create new SKU |
| **Activity Log** | `/nodes/activity-log/` | View activity log |
| **API** | `/nodes/api/...` | REST API endpoints |

---

## URL Configuration

### Main URL Configuration

**File**: [`urls.py`](../coldfront_orcd_direct_charge/urls.py)

```python
app_name = "coldfront_orcd_direct_charge"

urlpatterns = [
    # Node instance views
    path("", views.NodeInstanceListView.as_view(), name="node-instance-list"),
    path("gpu/<int:pk>/", views.GpuNodeInstanceDetailView.as_view(), name="gpu-node-detail"),
    path("cpu/<int:pk>/", views.CpuNodeInstanceDetailView.as_view(), name="cpu-node-detail"),
    
    # Renting views
    path("renting/", views.RentingCalendarView.as_view(), name="renting-calendar"),
    path("renting/request/", views.ReservationRequestView.as_view(), name="reservation-request"),
    path("renting/manage/", views.RentalManagerView.as_view(), name="rental-manager"),
    # ... more patterns
    
    # API (included from api/urls.py)
    path("api/", include("coldfront_orcd_direct_charge.api.urls")),
]
```

### Integration with ColdFront

In `coldfront/coldfront/config/urls.py`:

```python
if "coldfront_orcd_direct_charge" in settings.INSTALLED_APPS:
    urlpatterns.append(path("nodes/", include("coldfront_orcd_direct_charge.urls")))
```

---

## Dashboard Home Page

The dashboard is now the **default home page** for authenticated users. It replaces ColdFront's original home via template override.

> **Note**: The original `Home2View` class and `/nodes/home2/` URL were removed in commit `ac437c1`. The dashboard functionality was merged into `portal/authorized_home.html` using a template tag for context.

### Implementation

**Template**: `portal/authorized_home.html` (overrides ColdFront core)  
**Context Provider**: `get_dashboard_data` template tag

The dashboard context is now provided by a template tag instead of a view class:

```python
# templatetags/project_roles.py

@register.simple_tag(takes_context=True)
def get_dashboard_data(context):
    """Get all dashboard data for the current user.
    
    Returns a dict with all context needed for dashboard cards:
    - Projects (owned, member, counts)
    - Cost allocation status
    - Maintenance status
    - Reservations summary
    """
```

**Usage in Template**:
```django
{% load project_roles %}
{% get_dashboard_data as dashboard %}

{{ dashboard.owned_count }}
{{ dashboard.upcoming_count }}
```

**Context Variables** (returned in `dashboard` dict):

| Variable | Type | Description |
|----------|------|-------------|
| `owned_projects` | QuerySet | Projects where user is owner |
| `member_projects` | QuerySet | Projects where user has a role (not owner) |
| `owned_count` | int | Count of owned projects |
| `member_count` | int | Count of member projects |
| `total_projects` | int | Total project count |
| `recent_projects` | list | Top 5 projects for quick list |
| `is_pi` | bool | Whether user has PI status |
| `cost_approved_count` | int | Projects with approved cost allocation |
| `cost_pending_count` | int | Projects with pending cost allocation |
| `cost_rejected_count` | int | Projects with rejected cost allocation |
| `cost_not_configured_count` | int | Projects without cost allocation |
| `projects_needing_attention` | list | Up to 5 projects needing attention |
| `maintenance_status` | str | User's maintenance status display |
| `maintenance_status_raw` | str | Raw status value |
| `maintenance_billing_project` | Project | Billing project for maintenance |
| `upcoming_reservations` | list | Next 3 upcoming reservations |
| `upcoming_count` | int | Total upcoming reservation count |
| `pending_reservation_count` | int | Pending reservation count |
| `past_count` | int | Past reservation count |
| `total_reservations` | int | Total reservation count |

**UI Features**:
- Four summary cards: My Rentals, My Projects, My Account, My Billing
- Help icon (?) on each card with Bootstrap popover for guidance
- Clickable mailto link for orcd-help@mit.edu in help text
- Responsive layout (2x2 grid on desktop, single column on mobile)
- Home nav item links to this dashboard (default `/` route)

---

### MyReservationsView

**URL**: `/nodes/my/reservations/`  
**Name**: `coldfront_orcd_direct_charge:my-reservations`  
**Template**: `coldfront_orcd_direct_charge/my_reservations.html`

User-centric reservation page showing all reservations from projects where the user has any role.

```python
class MyReservationsView(LoginRequiredMixin, TemplateView):
    """Display reservations for projects where the user has a role.

    Shows all reservations from projects where the logged-in user is:
    - Owner (project.pi)
    - Financial Admin
    - Technical Admin
    - Member
    """
    template_name = "coldfront_orcd_direct_charge/my_reservations.html"
```

**Context Variables**:

| Variable | Type | Description |
|----------|------|-------------|
| `upcoming` | list | Confirmed reservations with end_date >= today |
| `pending` | list | Reservations awaiting approval |
| `past` | list | Confirmed reservations already completed |
| `declined_cancelled` | list | Rejected or cancelled reservations |
| `upcoming_count` | int | Count of upcoming reservations |
| `pending_count` | int | Count of pending reservations |
| `past_count` | int | Count of past reservations |
| `declined_cancelled_count` | int | Count of declined/cancelled |
| `user_roles` | dict | User's roles per project: `{project_pk: [roles]}` |

**UI Features**:
- Tabbed interface for each category (Upcoming, Pending, Past, Declined/Cancelled)
- Summary cards showing counts per category
- Displays user's roles for each reservation's project
- Sorted by start_date descending
- ID column links to reservation detail page

---

### ReservationDetailView

**URL**: `/nodes/reservation/<pk>/`  
**Name**: `coldfront_orcd_direct_charge:reservation-detail`  
**Template**: `coldfront_orcd_direct_charge/reservation_detail.html`

Displays comprehensive information about a single reservation.

```python
class ReservationDetailView(LoginRequiredMixin, DetailView):
    """Display detailed information about a reservation."""
    model = Reservation
    template_name = "coldfront_orcd_direct_charge/reservation_detail.html"
    context_object_name = "reservation"
```

**Permission Check**:
- User must be the requesting user, a project member, or a rental manager/superuser

**Context Variables**:

| Variable | Type | Description |
|----------|------|-------------|
| `reservation` | Reservation | The reservation object |
| `is_manager` | bool | Whether user can manage rentals |
| `metadata_entries` | QuerySet | Manager notes (visible to managers only) |
| `billable_hours` | int | Calculated billable hours |

**Displayed Information**:
- Reservation ID and status badge
- Node name and project
- Start/end dates with duration in blocks
- Billable hours calculation
- Requesting user
- Rental notes (from requester)
- Manager notes (from rental manager, visible to managers only)
- Metadata entries (visible to managers only)

---

### ProjectReservationsView

**URL**: `/nodes/project/<pk>/reservations/`  
**Name**: `coldfront_orcd_direct_charge:project-reservations`  
**Template**: `coldfront_orcd_direct_charge/project_reservations.html`

Lists all reservations for a specific project, accessible from project detail page.

```python
class ProjectReservationsView(LoginRequiredMixin, TemplateView):
    """Display all reservations for a project."""
    template_name = "coldfront_orcd_direct_charge/project_reservations.html"
```

**Permission Check**:
- User must be project owner, have an ORCD role in the project, or be a superuser

**Context Variables**:

| Variable | Type | Description |
|----------|------|-------------|
| `project` | Project | The project object |
| `future_reservations` | list | Reservations with end_date >= today, sorted ascending |
| `past_reservations` | list | Reservations with end_date < today, sorted descending |

**UI Features**:
- Two-section layout: Future (next first) and Past (most recent first)
- Displays node, start/end dates, duration, status, requester
- ID column links to reservation detail page

---

## Node Instance Views

### NodeInstanceListView

**URL**: `/nodes/`  
**Name**: `coldfront_orcd_direct_charge:node-instance-list`  
**Template**: `coldfront_orcd_direct_charge/node_instance_list.html`

Lists all GPU and CPU node instances with counts.

```python
class NodeInstanceListView(LoginRequiredMixin, TemplateView):
    template_name = "coldfront_orcd_direct_charge/node_instance_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["gpu_nodes"] = GpuNodeInstance.objects.all()
        context["cpu_nodes"] = CpuNodeInstance.objects.all()
        context["gpu_count"] = GpuNodeInstance.objects.count()
        context["cpu_count"] = CpuNodeInstance.objects.count()
        return context
```

**Context Variables**:
- `gpu_nodes` - QuerySet of all GPU nodes
- `cpu_nodes` - QuerySet of all CPU nodes
- `gpu_count` - Total GPU node count
- `cpu_count` - Total CPU node count

---

### GpuNodeInstanceDetailView

**URL**: `/nodes/gpu/<pk>/`  
**Name**: `coldfront_orcd_direct_charge:gpu-node-detail`  
**Template**: `coldfront_orcd_direct_charge/gpu_node_detail.html`

```python
class GpuNodeInstanceDetailView(LoginRequiredMixin, DetailView):
    model = GpuNodeInstance
    template_name = "coldfront_orcd_direct_charge/gpu_node_detail.html"
    context_object_name = "node"
```

---

### CpuNodeInstanceDetailView

**URL**: `/nodes/cpu/<pk>/`  
**Name**: `coldfront_orcd_direct_charge:cpu-node-detail`  
**Template**: `coldfront_orcd_direct_charge/cpu_node_detail.html`

```python
class CpuNodeInstanceDetailView(LoginRequiredMixin, DetailView):
    model = CpuNodeInstance
    template_name = "coldfront_orcd_direct_charge/cpu_node_detail.html"
    context_object_name = "node"
```

---

## Rental Calendar Views

### RentingCalendarView

**URL**: `/nodes/renting/`  
**Name**: `coldfront_orcd_direct_charge:renting-calendar`  
**Template**: `coldfront_orcd_direct_charge/renting_calendar.html`

Displays H200x8 node availability calendar with AM/PM period visualization.

**Query Parameters**:
- `year` - Calendar year (defaults to earliest bookable month)
- `month` - Calendar month (1-12)

**Context Variables**:
- `nodes` - QuerySet of rentable H200x8 nodes
- `days` - List of day numbers to display
- `availability` - Dict: `{node_id: {day: {rental_type, am_is_mine, pm_is_mine, is_bookable, has_pending}}}`
- `year`, `month`, `month_name` - Current calendar position
- `prev_year`, `prev_month`, `next_year`, `next_month` - Navigation values
- `show_prev`, `show_next` - Whether navigation buttons are enabled
- `earliest_bookable` - Date 7 days from today
- `max_month_name`, `max_year` - Maximum visible month (3 months ahead)

**Availability Matrix Values**:
- `rental_type`: "available", "am_only", "pm_only", "full"
- `am_is_mine`, `pm_is_mine`: Boolean for user's project reservations
- `is_bookable`: Boolean (false for dates < 7 days ahead)
- `has_pending`: Boolean indicating pending reservations

---

### ReservationRequestView

**URL**: `/nodes/renting/request/`  
**Name**: `coldfront_orcd_direct_charge:reservation-request`  
**Template**: `coldfront_orcd_direct_charge/reservation_request.html`

Form for submitting new reservation requests.

```python
class ReservationRequestView(LoginRequiredMixin, CreateView):
    model = Reservation
    form_class = ReservationRequestForm
    success_url = reverse_lazy("coldfront_orcd_direct_charge:renting-calendar")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs
```

**Form**: [`ReservationRequestForm`](../coldfront_orcd_direct_charge/forms.py)

**Validation**:
- User must have active maintenance subscription (not inactive)
- Node must be rentable H200x8
- Project must have approved cost allocation
- Start date must be 7+ days in future
- Start date must be within 3 months (max date validation)
- No overlapping confirmed reservations

**UI Features**:
- Flatpickr date picker with minDate (7 days) and maxDate (3 months) constraints
- Users with inactive maintenance subscription see error message and cannot submit
- No overlapping confirmed reservations

---

## Rental Manager Views

These views require `can_manage_rentals` permission.

### RentalManagerView

**URL**: `/nodes/renting/manage/`  
**Name**: `coldfront_orcd_direct_charge:rental-manager`  
**Template**: `coldfront_orcd_direct_charge/rental_manager.html`

Dashboard for reviewing and processing reservation requests.

**Context Variables**:
- `pending_reservations` - QuerySet of PENDING reservations
- `recent_reservations` - Recently processed (last 30 days)
- `decline_form` - ReservationDeclineForm instance

**UI Features**:
- DataTables enabled for sorting and filtering on both tables
- Columns include: ID, Request Date, Node, Project, Requester, Dates, Duration, Status
- Recently Processed table shows 'Processed By' column with manager who confirmed/declined
- 'Confirm Rental' button (renamed from 'Approve')

---

### ReservationApproveView

**URL**: `/nodes/renting/manage/<pk>/approve/`  
**Name**: `coldfront_orcd_direct_charge:reservation-approve`

POST-only view to confirm a reservation (button label: "Confirm Rental").

**Behavior**:
1. Validates reservation is PENDING
2. Checks for conflicts with existing confirmed reservations
3. Sets status to APPROVED
4. Logs activity to ActivityLog
5. Displays success message

---

### ReservationDeclineView

**URL**: `/nodes/renting/manage/<pk>/decline/`  
**Name**: `coldfront_orcd_direct_charge:reservation-decline`

POST-only view to decline a reservation with optional notes.

---

### ReservationMetadataView

**URL**: `/nodes/renting/manage/<pk>/metadata/`  
**Name**: `coldfront_orcd_direct_charge:reservation-metadata`

POST-only view to add metadata entries to a reservation.

**POST Data**:
- `new_entry_0`, `new_entry_1`, etc. - Content for new entries

---

## User Views

### update_maintenance_status

**URL**: `/nodes/user/update-maintenance-status/`  
**Name**: `coldfront_orcd_direct_charge:update-maintenance-status`

AJAX function view for updating user's maintenance status.

```python
@login_required
@require_POST
def update_maintenance_status(request):
    """Update the current user's account maintenance status via AJAX."""
```

**POST Data**:
- `status` - New status value (inactive, basic, advanced)
- `project_id` - Billing project ID (required for basic/advanced)

**Response** (JSON):
```json
{
    "success": true,
    "status": "basic",
    "display": "Basic (charged to: project_name)",
    "project_id": 123,
    "project_title": "project_name"
}
```

**Validation**:
- Status must be valid choice
- For basic/advanced, billing project required
- User must have eligible role in billing project (not financial_admin alone)
- **New (Dec 2025)**: Billing project must have an approved cost allocation

**Related Template Tag**:
- `get_projects_for_maintenance_fee(user)` - Returns only projects with approved cost allocations that the user can use for maintenance billing

---

## Project Cost Allocation Views

### ProjectCostAllocationView

**URL**: `/nodes/project/<pk>/cost-allocation/`  
**Name**: `coldfront_orcd_direct_charge:project-cost-allocation`  
**Template**: `coldfront_orcd_direct_charge/project_cost_allocation.html`

Edit cost allocation settings for a project.

**Permission Check**:
```python
if not can_edit_cost_allocation(request.user, self.project):
    messages.error(request, "...")
    return redirect("project-detail", pk=self.project.pk)
```

**Forms**:
- `ProjectCostAllocationForm` - Notes field
- `ProjectCostObjectFormSet` - Inline formset for cost objects

**POST Behavior**:
1. Validate forms
2. Reset status to PENDING
3. Clear review fields
4. Save allocation and cost objects
5. Redirect to project detail

---

## Billing Manager Views

These views require `can_manage_billing` permission.

### PendingCostAllocationsView

**URL**: `/nodes/billing/pending/`  
**Name**: `coldfront_orcd_direct_charge:pending-cost-allocations`  
**Template**: `coldfront_orcd_direct_charge/pending_cost_allocations.html`

Lists all cost allocations awaiting approval.

**Context Variables**:
- `pending_allocations` - QuerySet of PENDING allocations with related data
- `pending_count` - Count of pending allocations

---

### CostAllocationApprovalView

**URL**: `/nodes/billing/allocation/<pk>/review/`  
**Name**: `coldfront_orcd_direct_charge:cost-allocation-review`  
**Template**: `coldfront_orcd_direct_charge/cost_allocation_review.html`

Review and approve/reject a cost allocation.

**Context Variables**:
- `allocation` - ProjectCostAllocation instance
- `project` - Related Project
- `cost_objects` - QuerySet of cost objects
- `total_percentage` - Sum of percentages

**POST Actions**:
- `action=approve`: 
  - Create CostAllocationSnapshot
  - Copy cost objects to CostObjectSnapshot
  - Set status to APPROVED
  - Log activity
- `action=reject`:
  - Require review_notes
  - Set status to REJECTED
  - Log activity

---

## Invoice Views

These views require `can_manage_billing` permission.

### InvoicePreparationView

**URL**: `/nodes/billing/invoice/`  
**Name**: `coldfront_orcd_direct_charge:invoice-preparation`  
**Template**: `coldfront_orcd_direct_charge/invoice_preparation.html`

Month selector showing all months with reservations.

**Context Variables**:
- `invoice_months` - List of dicts with year, month, month_name, status, override_count

---

### InvoiceDetailView

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

### InvoiceEditView

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

### InvoiceExportView

**URL**: `/nodes/billing/invoice/<year>/<month>/export/`  
**Name**: `coldfront_orcd_direct_charge:invoice-export`

Export invoice data as JSON file.

**Response**: JSON file download with full invoice data including overrides and audit metadata.

---

### InvoiceDeleteOverrideView

**URL**: `/nodes/billing/invoice/<year>/<month>/override/<override_id>/delete/`  
**Name**: `coldfront_orcd_direct_charge:invoice-delete-override`

Delete an invoice line override.

---

## Member Management Views

### ProjectMembersView

**URL**: `/nodes/project/<pk>/members/`  
**Name**: `coldfront_orcd_direct_charge:project-members`  
**Template**: `coldfront_orcd_direct_charge/project_members.html`

List project members with their ORCD roles.

**Context Variables**:
- `project` - Project instance
- `members` - List of member dicts with user, roles, roles_display, is_owner
- `can_manage_members` - Boolean permission check
- `can_manage_financial_admins` - Boolean permission check
- `current_user_role` - Current user's highest role

**UI Features**:
- **Account Maintenance column** (added Dec 2025): Shows each member's maintenance fee status badge
- **Removal modal**: Bootstrap modal with optional notes textarea for audit trail (replaces basic `confirm()`)
- Owner row is protected - no remove button displayed

---

### AddMemberView

**URL**: `/nodes/project/<pk>/members/add/`  
**Name**: `coldfront_orcd_direct_charge:add-member`  
**Template**: `coldfront_orcd_direct_charge/add_member.html`

Add a new member with role selection.

**Form**: `AddMemberForm`
- `username` - Username to add (with autocomplete)
- `roles` - Multiple choice checkboxes

---

### UpdateMemberRoleView

**URL**: `/nodes/project/<pk>/members/<user_pk>/update/`  
**Name**: `coldfront_orcd_direct_charge:update-member-role`  
**Template**: `coldfront_orcd_direct_charge/update_member_role.html`

Modify a member's roles.

**Form**: `UpdateMemberRoleForm` (alias: `ManageMemberRolesForm`)

---

### RemoveMemberView

**URL**: `/nodes/project/<pk>/members/<user_pk>/remove/`  
**Name**: `coldfront_orcd_direct_charge:remove-member`

POST-only view to remove a member and all their roles.

```python
class RemoveMemberView(LoginRequiredMixin, View):
    """View for removing a member (and all their roles) from a project."""

    def post(self, request, pk, user_pk):
        # Get optional removal notes from form
        removal_notes = request.POST.get("notes", "").strip()
        # ... validation and removal logic
```

**POST Data**:
- `notes` (optional) - Removal reason for audit trail

**Behavior**:
1. Validates user is not the project owner (owners cannot be removed)
2. Checks permission via `can_manage_members()`
3. Technical admins cannot remove financial admins
4. Removes all `ProjectMemberRole` entries for the user
5. Removes `ProjectUser` entry from ColdFront core
6. Logs activity with optional removal notes in `extra_data`

**UI Integration**:
- Frontend uses Bootstrap modal with notes textarea instead of basic `confirm()`
- Modal displays member name for confirmation
- Notes are optional but stored in ActivityLog for audit

---

### ProjectAddUsersSearchResultsView

**URL**: `/nodes/project/<pk>/add-users-search-results/`  
**Name**: `coldfront_orcd_direct_charge:project-add-users-search-results`  
**Template**: `project/add_user_search_results.html`

Override of ColdFront's add-users search to use ORCD roles.

---

### ProjectAddUsersView

**URL**: `/nodes/project/<pk>/add-users/`  
**Name**: `coldfront_orcd_direct_charge:project-add-users`

Handle form submission to add users from search results.

---

## Rate Management Views

These views require `can_manage_rates` permission.

> **Note**: See [RATE_MANAGER.md](RATE_MANAGER.md) for comprehensive documentation on the Rate Manager feature.

### RateManagementView

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

### SKURateDetailView

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

### AddRateView

**URL**: `/nodes/rates/sku/<pk>/add-rate/`  
**Name**: `coldfront_orcd_direct_charge:add-rate`  
**Template**: `coldfront_orcd_direct_charge/add_rate_form.html`  
**Module**: `views/rates.py`

Form to add a new rate for an existing SKU.

**Form Fields**:
- `rate` - Decimal rate value
- `effective_date` - When the rate takes effect

---

### CreateSKUView

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

## Activity Log Views

### ActivityLogView

**URL**: `/nodes/activity-log/`  
**Name**: `coldfront_orcd_direct_charge:activity-log`  
**Template**: `coldfront_orcd_direct_charge/activity_log.html`

View and filter activity logs.

**Permission Check**:
```python
if not can_view_activity_log(request.user):
    raise PermissionDenied("...")
```

**Query Parameters**:
- `category` - Filter by action category
- `user` - Filter by username (contains)
- `action` - Filter by action (contains)
- `date_from`, `date_to` - Date range filters
- `page` - Pagination

**Context Variables**:
- `logs` - Paginated QuerySet (50 per page)
- `categories` - List of ActionCategory choices
- `filters` - Current filter values

---

## Template Override Views

The plugin overrides several ColdFront templates via template directory injection in `apps.py`.

### Template Directory Structure

```
templates/
├── coldfront_orcd_direct_charge/   # Plugin-specific templates
│   ├── activity_log.html
│   ├── add_member.html
│   ├── cost_allocation_review.html
│   ├── cpu_node_detail.html
│   ├── gpu_node_detail.html
│   ├── invoice_detail.html
│   ├── invoice_edit.html
│   ├── invoice_preparation.html
│   ├── my_reservations.html         # User's reservations page
│   ├── node_instance_list.html
│   ├── pending_cost_allocations.html
│   ├── project_cost_allocation.html
│   ├── project_members.html         # Updated: removal modal with notes
│   ├── rental_manager.html
│   ├── renting_calendar.html
│   ├── reservation_request.html
│   └── update_member_role.html
├── common/                          # Override core ColdFront
│   ├── authorized_navbar.html       # Navigation links
│   ├── base.html                    # Favicon, title
│   ├── navbar_brand.html            # ORCD logo
│   └── nonauthorized_navbar.html
├── portal/
│   ├── authorized_home.html         # Dashboard home page (NEW: replaces ColdFront home)
│   └── nonauthorized_home.html      # Pre-login page
├── project/
│   ├── add_user_search_results.html # ORCD role selection
│   ├── project_add_users.html       # Updated: autocomplete interface
│   ├── project_detail.html          # Simplified layout
│   ├── project_list.html            # "Project Owner" column
│   └── project_update_form.html
└── user/
    ├── user_profile.html            # Maintenance status, API token
    └── user_projects_managers.html  # "Project Owner" terminology
```

### Template Injection Mechanism

In `apps.py`:

```python
def ready(self):
    plugin_templates_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "templates"
    )
    
    for template_setting in settings.TEMPLATES:
        if plugin_templates_dir not in template_setting["DIRS"]:
            template_setting["DIRS"] = [plugin_templates_dir] + list(
                template_setting["DIRS"]
            )
```

This prepends the plugin's templates directory, allowing templates with matching paths to override ColdFront core templates.

---

## Permission Summary

| Permission | Required For |
|------------|--------------|
| `can_manage_rentals` | Rental manager dashboard, approve/decline, metadata, activity log |
| `can_manage_billing` | Cost allocation approval, invoice management, activity log |
| Superuser | All features, admin access |

**Role-based Permissions** (project level):
- Owner/Financial Admin: Cost allocation editing
- Owner/Financial/Technical Admin: Member management
- Any role: View members list

---

## Related Documentation

- [Data Models](data-models.md) - Model definitions
- [API Reference](api-reference.md) - REST API endpoints
- [Signals](signals.md) - Background processing



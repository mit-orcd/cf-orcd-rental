# Dashboard Views

This document describes the dashboard and reservation-related views.

---

## Dashboard Home Page

The dashboard is now the **default home page** for authenticated users. It replaces ColdFront's original home via template override.

> **Note**: The `/nodes/home2/` URL route was removed in commit `ac437c1`. The `Home2View` class still exists in `views/dashboard.py` but is no longer routed. Dashboard functionality was merged into `portal/authorized_home.html` using a template tag for context.

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

## MyReservationsView

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

## ReservationDetailView

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

## ProjectReservationsView

**URL**: `/nodes/orcd-project/<pk>/reservations/`  
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

[← Back to Views and URL Routing](README.md)

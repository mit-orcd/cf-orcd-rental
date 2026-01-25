# User Views

This document describes user-related views.

---

## update_maintenance_status

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

[← Back to Views and URL Routing](README.md)

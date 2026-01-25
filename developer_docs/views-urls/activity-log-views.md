# Activity Log Views

This document describes views for the activity log.

---

## ActivityLogView

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

[← Back to Views and URL Routing](README.md)

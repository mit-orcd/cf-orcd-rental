# Code Organization

This document describes the organization patterns used in the `coldfront_orcd_direct_charge` plugin to maintain code clarity and developer productivity.

## Views Package Structure

The views are organized as a Python package (`views/`) rather than a single `views.py` file. This improves:

- **Discoverability**: Developers can quickly find relevant code by domain
- **Maintainability**: Smaller files are easier to review and modify
- **Collaboration**: Reduces merge conflicts when multiple developers work on different domains

### Directory Structure

```
coldfront_orcd_direct_charge/
├── views/
│   ├── __init__.py      # Re-exports all views for backward compatibility
│   ├── nodes.py         # Node instance views (GPU/CPU inventory)
│   ├── rentals.py       # Reservation and rental management
│   ├── billing.py       # Cost allocation and invoice management
│   ├── members.py       # Project member management
│   ├── rates.py         # Rate/SKU management
│   └── dashboard.py     # Home page and activity log
├── models.py
├── forms.py
├── urls.py
└── ...
```

### Module Responsibilities

| Module | Description | Views |
|--------|-------------|-------|
| `nodes.py` | Node instance inventory display | `NodeInstanceListView`, `GpuNodeInstanceDetailView`, `CpuNodeInstanceDetailView` |
| `rentals.py` | Reservation workflow and calendar | `RentingCalendarView`, `ReservationRequestView`, `RentalManagerView`, `ReservationApproveView`, `ReservationDeclineView`, `ReservationMetadataView`, `ReservationDetailView`, `MyReservationsView`, `update_maintenance_status` |
| `billing.py` | Cost allocation and invoicing | `ProjectCostAllocationView`, `PendingCostAllocationsView`, `CostAllocationApprovalView`, `InvoicePreparationView`, `InvoiceDetailView`, `InvoiceEditView`, `InvoiceExportView`, `InvoiceDeleteOverrideView` |
| `members.py` | Project member management | `ProjectMembersView`, `AddMemberView`, `UpdateMemberRoleView`, `RemoveMemberView`, `ProjectAddUsersSearchResultsView`, `ProjectAddUsersView`, `ProjectReservationsView` |
| `rates.py` | Rate management for Rate Managers | `RateManagementView`, `SKURateDetailView`, `AddRateView`, `CreateSKUView` |
| `dashboard.py` | User dashboard and activity log | `Home2View`, `ActivityLogView` |

### How It Works

The `views/__init__.py` file re-exports all views, maintaining backward compatibility:

```python
# This still works (used by urls.py):
from coldfront_orcd_direct_charge import views
views.NodeInstanceListView.as_view()

# Direct imports also work:
from coldfront_orcd_direct_charge.views import NodeInstanceListView
from coldfront_orcd_direct_charge.views.nodes import NodeInstanceListView
```

## Adding New Views

When adding a new view:

1. **Identify the domain**: Determine which module the view belongs to
2. **Add to the appropriate module**: Add the view class/function to the domain module
3. **Update `__init__.py`**: Add the import and include in `__all__`
4. **Add URL pattern**: Update `urls.py` as usual

### Example: Adding a new rental-related view

```python
# 1. Add to views/rentals.py
class MyNewRentalView(LoginRequiredMixin, TemplateView):
    template_name = "coldfront_orcd_direct_charge/my_new_rental.html"
    # ...

# 2. Update views/__init__.py
from coldfront_orcd_direct_charge.views.rentals import (
    # ... existing imports ...
    MyNewRentalView,
)

__all__ = [
    # ... existing exports ...
    "MyNewRentalView",
]

# 3. Add to urls.py
path("renting/my-new/", views.MyNewRentalView.as_view(), name="my-new-rental"),
```

## When to Create a New Module

Create a new module when:

- A new domain area is introduced (e.g., a new feature set)
- An existing module exceeds ~500-600 lines
- Views share common imports and patterns distinct from other modules

Keep related views together even if a module grows larger than average—cohesion is more important than strict line limits.

## Best Practices

1. **Keep imports organized**: Group Django imports, then third-party, then local
2. **Use descriptive docstrings**: Each view class should have a docstring explaining its purpose and access requirements
3. **Log significant actions**: Use the `log_activity()` helper for auditable operations
4. **Follow permission patterns**: Use `PermissionRequiredMixin` or manual checks consistently

## Related Patterns

The codebase follows similar organizational patterns in:

- **Models**: Single `models.py` with helper functions; consider splitting if it grows
- **Forms**: Single `forms.py` organized by related view domain
- **Templates**: Organized by feature area under `templates/coldfront_orcd_direct_charge/`
- **API**: Separate `api/` package with its own views and serializers


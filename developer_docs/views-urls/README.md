# Views and URL Routing

This directory contains documentation for all view classes and URL patterns in the ORCD Direct Charge plugin.

**Sources**:
- [`coldfront_orcd_direct_charge/views/`](../../coldfront_orcd_direct_charge/views/) - View package (refactored Jan 2026)
- [`coldfront_orcd_direct_charge/urls.py`](../../coldfront_orcd_direct_charge/urls.py)

> **Note**: Views were refactored from a monolithic `views.py` to a `views/` package in Jan 2026.
> See [CODE_ORGANIZATION.md](../CODE_ORGANIZATION.md) for details on the module structure.

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [URL Configuration](url-configuration.md) | Main URL configuration and ColdFront integration |
| [Dashboard Views](dashboard-views.md) | Dashboard home page, MyReservations, ReservationDetail, ProjectReservations |
| [Node Instance Views](node-instance-views.md) | GPU and CPU node listing and detail views |
| [Rental Calendar Views](rental-calendar-views.md) | Availability calendar and reservation request |
| [Rental Manager Views](rental-manager-views.md) | Manager dashboard, approve/decline, metadata |
| [User Views](user-views.md) | User maintenance status updates |
| [Project Cost Allocation Views](project-cost-allocation-views.md) | Cost allocation editing |
| [Billing Manager Views](billing-manager-views.md) | Cost allocation approval/rejection |
| [Invoice Views](invoice-views.md) | Invoice preparation, detail, editing, export |
| [Member Management Views](member-management-views.md) | Project member listing, add/update/remove |
| [Rate Management Views](rate-management-views.md) | SKU rate management (managers only) |
| [Current Rates Views](current-rates-views.md) | Public-facing rates pages |
| [Activity Log Views](activity-log-views.md) | Activity log viewing and filtering |
| [Authentication Views](authentication-views.md) | Password login (when enabled) |
| [Template Override Views](template-override-views.md) | Template directory structure and injection |
| [Permissions](permissions.md) | Permission summary table |

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
| **Project** | `/nodes/orcd-project/<pk>/reservations/` | Project reservations |
| | `/nodes/orcd-project/<pk>/cost-allocation/` | Edit cost allocation |
| **Billing** | `/nodes/billing/pending/` | Pending allocations |
| | `/nodes/billing/allocation/<pk>/review/` | Review allocation |
| **Invoice** | `/nodes/billing/invoice/` | Month selector |
| | `/nodes/billing/invoice/<year>/<month>/` | Invoice detail |
| | `/nodes/billing/invoice/<year>/<month>/edit/` | Edit overrides |
| | `/nodes/billing/invoice/<year>/<month>/export/` | Export JSON |
| **Members** | `/nodes/orcd-project/<pk>/members/` | List members |
| | `/nodes/orcd-project/<pk>/add-users-search/` | Add members (autocomplete) |
| | `/nodes/orcd-project/<pk>/members/<user_pk>/update/` | Update roles |
| | `/nodes/orcd-project/<pk>/members/<user_pk>/remove/` | Remove member |
| **Project Add Users** | `/nodes/orcd-project/<pk>/add-users-search/` | Autocomplete search interface |
| | `/nodes/orcd-project/<pk>/add-users-search-results/` | Search results |
| | `/nodes/orcd-project/<pk>/add-users/` | Add selected users |
| **Rate Management** | `/nodes/rates/` | Rate management dashboard |
| | `/nodes/rates/sku/<pk>/` | SKU rate detail and history |
| | `/nodes/rates/sku/<pk>/add/` | Add new rate for SKU |
| | `/nodes/rates/sku/create/` | Create new SKU |
| | `/nodes/rates/sku/<pk>/visibility/` | Toggle SKU public visibility (AJAX) |
| **Current Rates** | `/nodes/rates/current/` | Public rates page (all users) |
| | `/nodes/rates/current/<pk>/` | Public SKU detail |
| **Activity Log** | `/nodes/activity-log/` | View activity log |
| **Authentication** | `/nodes/user/login?opt=password` | Password login (when enabled) |
| **API** | `/nodes/api/...` | REST API endpoints |

---

## Related Documentation

- [Data Models](../data-models.md) - Model definitions
- [API Reference](../api-reference.md) - REST API endpoints
- [Signals](../signals.md) - Background processing

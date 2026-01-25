# URL Configuration

This document describes the URL configuration for the ORCD Direct Charge plugin.

---

## Main URL Configuration

**File**: [`urls.py`](../../coldfront_orcd_direct_charge/urls.py)

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

---

## Integration with ColdFront

In `coldfront/coldfront/config/urls.py`:

```python
if "coldfront_orcd_direct_charge" in settings.INSTALLED_APPS:
    urlpatterns.append(path("nodes/", include("coldfront_orcd_direct_charge.urls")))
```

---

[← Back to Views and URL Routing](README.md)

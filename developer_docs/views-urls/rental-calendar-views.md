# Rental Calendar Views

This document describes views for the rental calendar and reservation requests.

---

## RentingCalendarView

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

## ReservationRequestView

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

**Form**: [`ReservationRequestForm`](../../coldfront_orcd_direct_charge/forms.py)

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

[← Back to Views and URL Routing](README.md)

# Rental Manager Views

This document describes views for rental managers. These views require `can_manage_rentals` permission.

---

## RentalManagerView

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

## ReservationApproveView

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

## ReservationDeclineView

**URL**: `/nodes/renting/manage/<pk>/decline/`  
**Name**: `coldfront_orcd_direct_charge:reservation-decline`

POST-only view to decline a reservation with optional notes.

---

## ReservationMetadataView

**URL**: `/nodes/renting/manage/<pk>/metadata/`  
**Name**: `coldfront_orcd_direct_charge:reservation-metadata`

POST-only view to add metadata entries to a reservation.

**POST Data**:
- `new_entry_0`, `new_entry_1`, etc. - Content for new entries

---

[← Back to Views and URL Routing](README.md)

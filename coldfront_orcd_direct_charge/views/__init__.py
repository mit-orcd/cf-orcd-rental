# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Views package for coldfront_orcd_direct_charge plugin.

This package organizes views by domain:
- nodes: Node instance views (GPU/CPU inventory)
- rentals: Reservation and rental management
- billing: Cost allocation and invoice management
- members: Project member management
- rates: Rate/SKU management
- dashboard: Home page and activity log

All views are re-exported here for backward compatibility with:
    from coldfront_orcd_direct_charge import views
    views.SomeView
"""

# Node views
from coldfront_orcd_direct_charge.views.nodes import (
    NodeInstanceListView,
    GpuNodeInstanceDetailView,
    CpuNodeInstanceDetailView,
)

# Rental/reservation views
from coldfront_orcd_direct_charge.views.rentals import (
    RentingCalendarView,
    ReservationRequestView,
    RentalManagerView,
    ReservationApproveView,
    ReservationDeclineView,
    ReservationMetadataView,
    ReservationDetailView,
    MyReservationsView,
    update_maintenance_status,
)

# Billing/cost allocation views
from coldfront_orcd_direct_charge.views.billing import (
    ProjectCostAllocationView,
    PendingCostAllocationsView,
    CostAllocationApprovalView,
    InvoicePreparationView,
    InvoiceDetailView,
    InvoiceEditView,
    InvoiceExportView,
    InvoiceDeleteOverrideView,
)

# Member management views
from coldfront_orcd_direct_charge.views.members import (
    ProjectMembersView,
    AddMemberView,
    UpdateMemberRoleView,
    RemoveMemberView,
    ProjectAddUsersSearchView,
    ProjectAddUsersSearchResultsView,
    ProjectAddUsersView,
    ProjectReservationsView,
)

# Rate management views
from coldfront_orcd_direct_charge.views.rates import (
    RateManagementView,
    SKURateDetailView,
    AddRateView,
    CreateSKUView,
    CurrentRatesView,
    SKUPublicDetailView,
    ToggleSKUVisibilityView,
)

# Dashboard views
from coldfront_orcd_direct_charge.views.dashboard import (
    Home2View,
    ActivityLogView,
)

# Export all views for `from coldfront_orcd_direct_charge.views import *`
__all__ = [
    # Nodes
    "NodeInstanceListView",
    "GpuNodeInstanceDetailView",
    "CpuNodeInstanceDetailView",
    # Rentals
    "RentingCalendarView",
    "ReservationRequestView",
    "RentalManagerView",
    "ReservationApproveView",
    "ReservationDeclineView",
    "ReservationMetadataView",
    "ReservationDetailView",
    "MyReservationsView",
    "update_maintenance_status",
    # Billing
    "ProjectCostAllocationView",
    "PendingCostAllocationsView",
    "CostAllocationApprovalView",
    "InvoicePreparationView",
    "InvoiceDetailView",
    "InvoiceEditView",
    "InvoiceExportView",
    "InvoiceDeleteOverrideView",
    # Members
    "ProjectMembersView",
    "AddMemberView",
    "UpdateMemberRoleView",
    "RemoveMemberView",
    "ProjectAddUsersSearchView",
    "ProjectAddUsersSearchResultsView",
    "ProjectAddUsersView",
    "ProjectReservationsView",
    # Rates
    "RateManagementView",
    "SKURateDetailView",
    "AddRateView",
    "CreateSKUView",
    "CurrentRatesView",
    "SKUPublicDetailView",
    "ToggleSKUVisibilityView",
    # Dashboard
    "Home2View",
    "ActivityLogView",
]


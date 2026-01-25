# Billing Manager Views

This document describes views for billing managers. These views require `can_manage_billing` permission.

---

## PendingCostAllocationsView

**URL**: `/nodes/billing/pending/`  
**Name**: `coldfront_orcd_direct_charge:pending-cost-allocations`  
**Template**: `coldfront_orcd_direct_charge/pending_cost_allocations.html`

Lists all cost allocations awaiting approval.

**Context Variables**:
- `pending_allocations` - QuerySet of PENDING allocations with related data
- `pending_count` - Count of pending allocations

---

## CostAllocationApprovalView

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

[← Back to Views and URL Routing](README.md)

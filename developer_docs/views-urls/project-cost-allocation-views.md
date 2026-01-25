# Project Cost Allocation Views

This document describes views for managing project cost allocations.

---

## ProjectCostAllocationView

**URL**: `/nodes/orcd-project/<pk>/cost-allocation/`  
**Name**: `coldfront_orcd_direct_charge:project-cost-allocation`  
**Template**: `coldfront_orcd_direct_charge/project_cost_allocation.html`

Edit cost allocation settings for a project.

**Permission Check**:
```python
if not can_edit_cost_allocation(request.user, self.project):
    messages.error(request, "...")
    return redirect("project-detail", pk=self.project.pk)
```

**Forms**:
- `ProjectCostAllocationForm` - Notes field
- `ProjectCostObjectFormSet` - Inline formset for cost objects

**POST Behavior**:
1. Validate forms
2. Reset status to PENDING
3. Clear review fields
4. Save allocation and cost objects
5. Redirect to project detail

---

[← Back to Views and URL Routing](README.md)

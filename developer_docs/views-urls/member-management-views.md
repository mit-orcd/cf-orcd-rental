# Member Management Views

This document describes views for managing project members.

---

## ProjectMembersView

**URL**: `/nodes/orcd-project/<pk>/members/`  
**Name**: `coldfront_orcd_direct_charge:project-members`  
**Template**: `coldfront_orcd_direct_charge/project_members.html`

List project members with their ORCD roles.

**Context Variables**:
- `project` - Project instance
- `members` - List of member dicts with user, roles, roles_display, is_owner
- `can_manage_members` - Boolean permission check
- `can_manage_financial_admins` - Boolean permission check
- `current_user_role` - Current user's highest role

**UI Features**:
- **Account Maintenance column** (added Dec 2025): Shows each member's maintenance fee status badge
- **Removal modal**: Bootstrap modal with optional notes textarea for audit trail (replaces basic `confirm()`)
- Owner row is protected - no remove button displayed

---

## AddMemberView (legacy redirect)

**URL**: `/nodes/orcd-project/<pk>/members/add/`  
**Name**: `coldfront_orcd_direct_charge:add-member`  
**Behavior**: Redirects to `project-add-users-search` after permission check.  
**Template**: (legacy) `coldfront_orcd_direct_charge/add_member.html` (no longer rendered)

Legacy entry point retained for bookmarks; all adds now go through the autocomplete UI.

---

## UpdateMemberRoleView

**URL**: `/nodes/orcd-project/<pk>/members/<user_pk>/update/`  
**Name**: `coldfront_orcd_direct_charge:update-member-role`  
**Template**: `coldfront_orcd_direct_charge/update_member_role.html`

Modify a member's roles.

**Form**: `UpdateMemberRoleForm` (alias: `ManageMemberRolesForm`)

---

## RemoveMemberView

**URL**: `/nodes/orcd-project/<pk>/members/<user_pk>/remove/`  
**Name**: `coldfront_orcd_direct_charge:remove-member`

POST-only view to remove a member and all their roles.

```python
class RemoveMemberView(LoginRequiredMixin, View):
    """View for removing a member (and all their roles) from a project."""

    def post(self, request, pk, user_pk):
        # Get optional removal notes from form
        removal_notes = request.POST.get("notes", "").strip()
        # ... validation and removal logic
```

**POST Data**:
- `notes` (optional) - Removal reason for audit trail

**Behavior**:
1. Validates user is not the project owner (owners cannot be removed)
2. Checks permission via `can_manage_members()`
3. Technical admins cannot remove financial admins
4. Removes all `ProjectMemberRole` entries for the user
5. Removes `ProjectUser` entry from ColdFront core
6. Logs activity with optional removal notes in `extra_data`

**UI Integration**:
- Frontend uses Bootstrap modal with notes textarea instead of basic `confirm()`
- Modal displays member name for confirmation
- Notes are optional but stored in ActivityLog for audit

---

## ProjectAddUsersSearchView

**URL**: `/nodes/orcd-project/<pk>/add-users-search/`  
**Name**: `coldfront_orcd_direct_charge:project-add-users-search`  
**Template**: `project/project_add_users.html`

Autocomplete interface for searching and adding users to a project. This view replaces ColdFront's legacy text-based search with a modern autocomplete interface.

**Permission Check**:
- User must be able to manage members (owner, financial admin, or technical admin)
- Project must be Active or New status

**UI Features**:
- Real-time autocomplete search as user types
- Role selection checkboxes (Financial Admin, Technical Admin, Member)
- Multiple users can be selected before submitting
- Form validation ensures at least one role per user

---

## ProjectAddUsersSearchResultsView

**URL**: `/nodes/orcd-project/<pk>/add-users-search-results/`  
**Name**: `coldfront_orcd_direct_charge:project-add-users-search-results`  
**Template**: `project/add_user_search_results.html`

Legacy search results view for backwards compatibility. Override of ColdFront's add-users search to use ORCD roles.

---

## ProjectAddUsersView

**URL**: `/nodes/orcd-project/<pk>/add-users/`  
**Name**: `coldfront_orcd_direct_charge:project-add-users`

Handle form submission to add users from search results.

---

[← Back to Views and URL Routing](README.md)

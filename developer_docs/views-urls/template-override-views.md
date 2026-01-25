# Template Override Views

This document describes the template override mechanism and directory structure.

The plugin overrides several ColdFront templates via template directory injection in `apps.py`.

---

## Template Directory Structure

```
templates/
├── coldfront_orcd_direct_charge/   # Plugin-specific templates
│   ├── activity_log.html           # Activity log viewer
│   ├── add_member.html             # Legacy add member (redirects)
│   ├── add_rate_form.html          # Add rate to SKU form
│   ├── cost_allocation_review.html # Billing manager approval page
│   ├── cpu_node_detail.html        # CPU node detail view
│   ├── create_sku_form.html        # Create new SKU form
│   ├── current_rates.html          # Public current rates page
│   ├── gpu_node_detail.html        # GPU node detail view
│   ├── invoice_detail.html         # Invoice detail/finalize page
│   ├── invoice_edit.html           # Invoice override editing
│   ├── invoice_preparation.html    # Month selector for invoices
│   ├── my_reservations.html        # User's reservations page
│   ├── node_instance_list.html     # GPU/CPU node inventory
│   ├── pending_cost_allocations.html  # Pending approvals list
│   ├── project_cost_allocation.html   # Cost allocation form
│   ├── project_members.html        # Member list with removal modal
│   ├── project_reservations.html   # Project-specific reservations
│   ├── rate_management.html        # Rate manager dashboard
│   ├── rental_manager.html         # Rental manager dashboard
│   ├── renting_calendar.html       # Node availability calendar
│   ├── reservation_detail.html     # Single reservation detail
│   ├── reservation_request.html    # Submit reservation form
│   ├── sku_public_detail.html      # Public SKU detail page
│   ├── sku_rate_detail.html        # SKU rate history (managers)
│   └── update_member_role.html     # Update member roles form
├── common/                          # Override core ColdFront
│   ├── authorized_navbar.html       # Navigation links
│   ├── base.html                    # Favicon, title
│   ├── footer.html                  # Version footer
│   ├── navbar_brand.html            # ORCD logo
│   ├── navbar_login.html            # Login dropdown
│   └── nonauthorized_navbar.html    # Pre-login navbar
├── portal/
│   ├── authorized_home.html         # Dashboard home page
│   └── nonauthorized_home.html      # Pre-login page
├── project/
│   ├── add_user_search_results.html # ORCD role selection
│   ├── project_add_users.html       # Autocomplete add users interface
│   ├── project_archive.html         # Project archive page
│   ├── project_create_form.html     # Create project form
│   ├── project_detail.html          # Simplified layout
│   ├── project_list.html            # "Project Owner" column
│   └── project_update_form.html     # Edit project form
└── user/
    ├── login_password.html          # Password login form (when enabled)
    ├── user_profile.html            # Maintenance status, API token
    └── user_projects_managers.html  # "Project Owner" terminology
```

---

## Template Injection Mechanism

In `apps.py`:

```python
def ready(self):
    plugin_templates_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "templates"
    )
    
    for template_setting in settings.TEMPLATES:
        if plugin_templates_dir not in template_setting["DIRS"]:
            template_setting["DIRS"] = [plugin_templates_dir] + list(
                template_setting["DIRS"]
            )
```

This prepends the plugin's templates directory, allowing templates with matching paths to override ColdFront core templates.

---

[← Back to Views and URL Routing](README.md)

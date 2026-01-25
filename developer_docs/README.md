# ORCD Direct Charge Plugin - Developer Documentation

**Version**: 0.1.0  
**License**: AGPL-3.0-or-later  
**Last Updated**: December 29, 2025

This documentation is intended for maintainers and developers working on the `coldfront-orcd-direct-charge` plugin. It covers architecture, code organization, APIs, and change history.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Directory Structure](#directory-structure)
3. [Key Concepts](#key-concepts)
4. [Documentation Index](#documentation-index)
5. [Getting Started for Developers](#getting-started-for-developers)
6. [External Resources](#external-resources)

---

## Architecture Overview

The ORCD Direct Charge plugin extends [ColdFront](https://github.com/ubccr/coldfront) (an open-source HPC resource allocation management system) with functionality for:

1. **Node Instance Tracking**: GPU and CPU node inventory management
2. **Rental Reservation System**: Calendar-based booking for H200x8 GPU nodes
3. **ORCD-Specific Project Roles**: Four-tier role hierarchy (Owner, Financial Admin, Technical Admin, Member)
4. **Cost Allocation & Billing**: Project cost object management with approval workflows
5. **Invoice Reporting**: Monthly billing reports with cost object breakdowns
6. **Activity Logging**: Comprehensive audit trail for all site activity
7. **User Auto-Configuration**: Automatic PI status and default project creation
8. **Dashboard Home Page**: User-centric dashboard as the default home page
9. **My Reservations**: Cross-project reservation view for users

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           ColdFront Core                            │
│  (User Management, Projects, Allocations, Resources)                │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ Extends via Django App
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  coldfront_orcd_direct_charge                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │   Models    │  │    Views    │  │     API     │  │  Signals   │ │
│  │  - NodeType │  │  - Calendar │  │  - Rentals  │  │  - AutoPI  │ │
│  │  - Nodes    │  │  - Manager  │  │  - Invoice  │  │  - Logging │ │
│  │  - Reserve  │  │  - Billing  │  │  - Activity │  │  - Maint.  │ │
│  │  - Roles    │  │  - Members  │  │  - Users    │  │            │ │
│  │  - Billing  │  │  - Activity │  │             │  │            │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### Integration Points with ColdFront

| ColdFront Component | Integration |
|---------------------|-------------|
| `User` (Django auth) | Extended with `UserMaintenanceStatus`, auto-PI via signals |
| `Project` | Extended with `ProjectCostAllocation`, `ProjectMemberRole`, reservations |
| `ProjectUser` | Signals monitor for maintenance status reset |
| Templates | Overridden for custom branding, navigation, and terminology |
| Settings | Plugin adds custom settings (`AUTO_PI_ENABLE`, etc.) |

---

## Directory Structure

```
coldfront-orcd-direct-charge/
├── pyproject.toml                  # Package configuration
├── README.md                       # User-facing documentation
├── developer_docs/                 # This directory - developer documentation
│   ├── README.md                   # This file
│   ├── data-models.md              # Model documentation
│   ├── views-urls/                 # Views and URL routing (split into subdirectory)
│   ├── api-reference.md            # REST API documentation
│   ├── signals.md                  # Signals and auto-configuration
│   └── CHANGELOG.md                # Change log
├── helper_programs/                # Utility tools
│   ├── csv_to_fixtures/            # CSV to Django fixture converter
│   ├── mk_gpucpunode_csv/          # Slurm to CSV converter
│   └── orcd_dc_cli/                # CLI tools for API access
└── coldfront_orcd_direct_charge/   # Main plugin package
    ├── __init__.py
    ├── apps.py                     # Django AppConfig, settings, template injection
    ├── models.py                   # All data models (incl. RentalSKU, RentalRate)
    ├── views/                      # View classes (refactored into package)
    │   ├── __init__.py             # Re-exports all views for backward compatibility
    │   ├── nodes.py                # Node instance views
    │   ├── rentals.py              # Reservation and rental management
    │   ├── billing.py              # Cost allocation and invoice management
    │   ├── members.py              # Project member management
    │   ├── rates.py                # Rate/SKU management
    │   └── dashboard.py            # Home page and activity log
    ├── urls.py                     # URL routing
    ├── forms.py                    # Form classes
    ├── admin.py                    # Django admin configuration
    ├── signals.py                  # Signal handlers
    ├── api/                        # REST API (Django REST Framework)
    │   ├── __init__.py
    │   ├── serializers.py          # DRF serializers
    │   ├── views.py                # API viewsets
    │   └── urls.py                 # API routing
    ├── management/commands/        # Django management commands
    │   ├── setup_rental_manager.py
    │   └── setup_billing_manager.py
    ├── templatetags/               # Custom template tags/filters
    │   ├── calendar_filters.py
    │   └── project_roles.py
    ├── migrations/                 # Database migrations (20 total)
    ├── fixtures/                   # Seed data
    │   ├── node_types.json
    │   ├── gpu_node_instances.json
    │   ├── cpu_node_instances.json
    │   └── node_resource_types.json
    └── templates/                  # Template overrides
        ├── coldfront_orcd_direct_charge/  # Plugin-specific templates
        ├── common/                 # Override core navbar, base
        ├── portal/                 # Override home pages
        ├── project/                # Override project templates
        └── user/                   # Override user profile
```

---

## Key Concepts

### 1. Node Types and Instances

- **NodeType**: Defines categories of nodes (e.g., "H200x8", "CPU_384G")
- **GpuNodeInstance / CpuNodeInstance**: Individual physical nodes with rental status
- Loaded via fixtures, use natural keys for updates

### 2. Reservation System

- Reservations book GPU nodes in 12-hour blocks
- Start time: Always 4:00 PM on start date
- End time capped at 9:00 AM (no reservations extend past this)
- Requires 7-day advance booking, 3-month visibility window

### 3. ORCD Role Hierarchy

| Role | Permissions |
|------|-------------|
| Owner | All (implicit via `project.pi`) |
| Financial Admin | Cost allocation, role management, NOT in reservations/billing |
| Technical Admin | Member management, reservations, maintenance billing |
| Member | Reservations only, maintenance billing |

### 4. Cost Allocation Workflow

1. Project owner/financial admin submits cost objects
2. Allocation goes to PENDING status
3. Billing Manager reviews and approves/rejects
4. On approval, a snapshot is created for billing accuracy
5. Reservations require approved cost allocation

### 5. Activity Logging

- All significant actions are logged to `ActivityLog`
- Categories: auth, reservation, project, member, cost_allocation, billing, invoice, maintenance, api, view
- Accessible to Billing/Rental Managers via web UI and API

### 6. Dashboard Home Page (Dec 2025)

- Dashboard is now the **default home page** for authenticated users
- Implemented via template override of `portal/authorized_home.html`
- Context provided by `get_dashboard_data` template tag (not a view class)
- Four summary cards: My Rentals, My Projects, My Account, My Billing
- Help popovers on each card with guidance and support contact
- Responsive layout (2x2 grid on desktop, single column on mobile)

### 7. My Reservations Page (New - Dec 2025)

- User-centric view at `/nodes/my/reservations/`
- Shows all reservations from projects where user has any role
- Tabbed interface: Upcoming, Pending, Past, Declined/Cancelled
- Displays user's roles per project

### 8. Enhanced Member Management (New - Dec 2025)

- Account Maintenance column in Project Members table
- Confirmation modal with notes for member removal (stored in ActivityLog)
- Autocomplete interface for adding users (replaces legacy search)
- Maintenance fee billing requires approved cost allocation on billing project

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [Data Models](data-models.md) | Complete model reference with fields and relationships |
| [Views & URLs](views-urls/) | View classes, URL patterns, and request flow |
| [API Reference](api-reference.md) | REST API endpoints, authentication, examples |
| [Signals](signals.md) | Signal handlers, auto-configuration, activity logging |
| [Runtime Config](RUNTIME_CONFIG.md) | Runtime configuration with hot-reload via SIGHUP |
| [Rate Manager](RATE_MANAGER.md) | Rate management feature for rental charging rates |
| [Code Organization](CODE_ORGANIZATION.md) | Views package structure and module organization |
| [Changelog](CHANGELOG.md) | Version history and changes |

---

## Getting Started for Developers

### Prerequisites

- Python 3.9+
- ColdFront 1.1.0+
- Django 4.2+
- Django REST Framework (for API functionality)

### Development Setup

```bash
# Clone the repository (assumes ColdFront is already set up)
cd /path/to/your-project
git clone <repo-url> coldfront-orcd-direct-charge

# Install in development mode
cd coldfront
uv pip install -e ../coldfront-orcd-direct-charge

# Apply migrations
export PLUGIN_API=True
uv run coldfront migrate

# Load fixtures
uv run coldfront loaddata node_types gpu_node_instances cpu_node_instances

# Run development server
export AUTO_PI_ENABLE=True AUTO_DEFAULT_PROJECT_ENABLE=True
DEBUG=True uv run coldfront runserver
```

### Running with Full Features

```bash
cd /path/to/coldfront
export PLUGIN_API=True
export AUTO_PI_ENABLE=True
export AUTO_DEFAULT_PROJECT_ENABLE=True
DEBUG=True uv run coldfront runserver
```

### Creating Migrations

```bash
cd /path/to/coldfront
export PLUGIN_API=True
uv run coldfront makemigrations coldfront_orcd_direct_charge
```

### Setting Up Manager Roles

```bash
# Rental Manager - can approve/decline reservations
uv run coldfront setup_rental_manager --create-group
uv run coldfront setup_rental_manager --add-user <username>

# Billing Manager - can approve cost allocations, manage invoices
uv run coldfront setup_billing_manager --create-group
uv run coldfront setup_billing_manager --add-user <username>
```

---

## External Resources

### ColdFront Documentation

- [ColdFront GitHub](https://github.com/ubccr/coldfront)
- [ColdFront Documentation](https://coldfront.readthedocs.io/)
- [ColdFront Plugin Development](https://coldfront.readthedocs.io/en/latest/plugin/)

### Django Documentation

- [Django Models](https://docs.djangoproject.com/en/4.2/topics/db/models/)
- [Django Views](https://docs.djangoproject.com/en/4.2/topics/http/views/)
- [Django Signals](https://docs.djangoproject.com/en/4.2/topics/signals/)
- [Django Admin](https://docs.djangoproject.com/en/4.2/ref/contrib/admin/)

### Django REST Framework

- [DRF Quickstart](https://www.django-rest-framework.org/tutorial/quickstart/)
- [DRF Authentication](https://www.django-rest-framework.org/api-guide/authentication/)
- [DRF Filtering](https://django-filter.readthedocs.io/)

---

## Code Style and Conventions

- **License Headers**: All source files include SPDX license headers
- **Docstrings**: All models, views, and functions have docstrings
- **Logging**: Use `logging.getLogger(__name__)` for all logging
- **Type Hints**: Not currently enforced but encouraged for new code
- **Forms**: Use Django forms for all user input validation
- **Templates**: Extend `common/base.html` for consistency



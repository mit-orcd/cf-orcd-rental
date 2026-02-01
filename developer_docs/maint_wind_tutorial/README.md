# Maintenance Window Feature: A Comprehensive Development Tutorial

## Concepts, Design Decisions, and Implementation Details

---

## Tutorial Files

This tutorial directory contains:

| File | Description |
|------|-------------|
| [README.md](README.md) | This document - the main comprehensive tutorial |
| [ORCD_PROJECT_ABSTRACTION.md](ORCD_PROJECT_ABSTRACTION.md) | Deep dive into how the ORCD plugin extends ColdFront's project model |

---

**Document Purpose:** This tutorial provides a complete walkthrough of designing and implementing the maintenance window feature for the ColdFront ORCD Direct Charge plugin. It serves as both a learning resource for developers new to Django and ColdFront, and a reference for understanding plan-driven agentic development workflows.

**Target Audience:** Software developers with programming experience who are new to Django and/or ColdFront. You should be familiar with:
- Programming in at least one language (Python, JavaScript, Java, Ruby, etc.)
- Basic web development concepts (HTTP requests/responses, REST APIs, databases)
- MVC or similar architectural patterns
- Version control with Git

**What You Will Learn:**
- Django's architecture and key patterns (models, views, templates, migrations)
- ColdFront's plugin system and how to extend its functionality
- Full-stack feature implementation from database model to user interface
- How AI agents can execute complex multi-task development work from a structured plan

---

## Table of Contents

### Section 1: Introduction
- [1.1 The Business Need](#11-the-business-need)
- [1.2 Feature Requirements Summary](#12-feature-requirements-summary)
- [1.3 Overview of the Development Session](#13-overview-of-the-development-session)

### Section 2: Foundations for Non-Django Developers
- 2.1 What is Django?
- 2.2 Django Project Structure Explained
- 2.3 What is ColdFront?
- 2.4 Plugin Architecture
- 2.5 ORCD Project Abstraction (see [ORCD_PROJECT_ABSTRACTION.md](ORCD_PROJECT_ABSTRACTION.md))
- 2.6 Terminology Glossary
- 2.7 Key Django Patterns You'll Encounter
- 2.8 The Django Development Workflow
- 2.9 How to Read Django Code

### Section 3: Key Concepts in Depth
- 3.1 Django Concepts (Deep Dive)
- 3.2 ColdFront Concepts (Deep Dive)
- 3.3 Plugin-Specific Patterns (Deep Dive)

### Section 4: TODO Overview and Concept Mapping
- 4.1 Architecture Diagram
- 4.2 Concept-to-TODO Mapping Table
- 4.3 Dependency Graph

### Section 5: Detailed TODO Walkthroughs
- 5.1 TODO 1: Create MaintenanceWindow Model and Migration
- 5.2 TODO 2: Update Billing Calculations
- 5.3 TODO 3: Create Web UI Views and Templates
- 5.4 TODO 4: Add REST API
- 5.5 TODO 5: Create Management Commands
- 5.6 TODO 6: Add Export/Import
- 5.7 TODO 7: Register Django Admin
- 5.8 TODO 8: Add Activity Logging
- 5.9 TODO 9: Update Invoice Templates
- 5.10 TODO 10: Create Help Text System
- 5.11 TODO 11: Implement Edit Restrictions
- 5.12 TODO 12: Create Documentation

### Section 6: Agentic Development Process
- 6.1 The Planning Phase
- 6.2 Plan Structure
- 6.3 Agent Execution Model
- 6.4 Prompt Engineering Patterns
- 6.5 Agent Coordination
- 6.6 Lessons Learned

---

# Section 1: Introduction

This section establishes the context for the maintenance window feature: why it's needed, what it must do, and how the development work was structured into discrete, executable tasks.

## 1.1 The Business Need

### The GPU Node Rental Context

Research computing centers often provide dedicated GPU nodes that research groups can rent on a long-term basis. Unlike traditional HPC job scheduling where users submit jobs to a shared queue, rental arrangements give a research group exclusive access to specific hardware for extended periods—typically months at a time.

This rental model requires a billing system that tracks:
- Which GPU nodes are assigned to which research groups
- The duration of each rental period (reservation)
- How charges should be allocated across the group's funding accounts
- Monthly invoices showing billable hours and associated costs

The ColdFront ORCD Direct Charge plugin implements exactly this system. It manages GPU node inventory, tracks reservations, calculates billable hours, and generates invoices for research groups.

### The Problem: Maintenance Periods and Fair Billing

Computing infrastructure requires periodic maintenance. Hardware needs firmware updates. Software stacks need security patches. Storage systems need expansion or replacement. During these maintenance windows, researchers cannot access their rented nodes—the machines are simply unavailable.

Here's the fairness issue: **researchers should not pay for time when they cannot use the resources they've rented.**

Consider this scenario:
- A research group rents a GPU node for January 2026
- January has 744 hours (31 days × 24 hours)
- The computing center schedules a 48-hour maintenance window from January 15-17
- Fair billing: the group should pay for 696 hours (744 - 48), not the full 744

Without automated maintenance tracking, administrators face unpleasant choices:

1. **Manual invoice adjustments:** An administrator manually calculates the overlap between each maintenance window and each active reservation, then applies credits or adjustments to invoices. This is tedious, error-prone, and doesn't scale.

2. **Ad-hoc record keeping:** Maintenance periods are tracked in spreadsheets, emails, or institutional memory. When billing disputes arise months later, reconstructing what happened becomes archaeology.

3. **Ignore the problem:** Charge researchers for time they couldn't use the system. This damages trust and institutional relationships.

### The Solution: Automated Maintenance Window Tracking

The maintenance window feature solves this by:

1. **Providing a formal data model** for maintenance windows with start times, end times, titles, and descriptions
2. **Automatically calculating overlap** between maintenance periods and active reservations during billing
3. **Transparently displaying deductions** on invoices so researchers see exactly why their charges differ from simple hourly multiplication
4. **Creating an audit trail** of all maintenance windows for compliance and dispute resolution

This transforms maintenance tracking from an operational burden into a first-class feature with proper tooling, visibility, and automation.

### Why Automation Matters

Consider a computing center with:
- 20 GPU nodes available for rental
- 15 active reservations at any given time
- Monthly maintenance windows of varying duration
- Quarterly extended maintenance for major upgrades

Manual calculation requires examining each reservation against each maintenance window for each billing period. With 15 reservations and 4-5 maintenance windows per quarter, that's 60-75 overlap calculations per quarter—just for one billing cycle. Errors compound over time, and reconciliation becomes increasingly difficult.

Automated tracking eliminates this entire class of work. When the system knows about maintenance windows, it calculates the correct deductions every time, for every reservation, without human intervention.

## 1.2 Feature Requirements Summary

The maintenance window feature was designed to meet specific functional and non-functional requirements derived from real operational needs.

### Functional Requirements

**FR-1: Create and Manage Maintenance Windows**

Rental managers must be able to:
- Create new maintenance windows with title, description, start date/time, and end date/time
- View a list of all maintenance windows (past, current, and future)
- Edit upcoming maintenance windows (modify times, update descriptions)
- Delete upcoming maintenance windows that are no longer needed

> **Design Decision:** Only upcoming windows can be edited or deleted through the standard interface. Once a maintenance window is in progress or completed, it becomes part of the historical billing record. Allowing casual modification of past windows would undermine audit integrity. However, administrators with Django admin access can still modify past windows when corrections are genuinely needed.

**FR-2: Automatic Billing Deduction**

The billing system must:
- Automatically detect overlaps between maintenance windows and active reservations
- Calculate the exact hours of overlap for each reservation in each billing period
- Deduct maintenance hours from billable hours before calculating charges
- Display the maintenance deduction on invoices with clear explanations

> **Example Calculation:**
> - Reservation: January 1-31, 2026 (744 total hours)
> - Maintenance Window: January 15, 08:00 to January 17, 08:00 (48 hours)
> - Overlap with reservation: 48 hours
> - Billable hours: 744 - 48 = 696 hours

**FR-3: REST API Access**

External systems and automation tools must be able to:
- Query maintenance windows via authenticated API calls
- Filter windows by date range, status, or other criteria
- Create new maintenance windows programmatically
- Integrate maintenance data into monitoring dashboards or alerting systems

**FR-4: Command-Line Tools**

System administrators must be able to:
- List maintenance windows from the command line
- Create maintenance windows via shell scripts or automation
- Delete maintenance windows when needed
- Perform operations in non-interactive (scripted) or interactive modes

**FR-5: Data Portability**

The maintenance window data must support:
- Export to JSON format for backup or migration
- Import from JSON format for restoration or data transfer between environments
- Conflict resolution when importing windows that may already exist

### Non-Functional Requirements

**NFR-1: Auditability**

Every create, update, and delete operation on maintenance windows must be logged with:
- Who performed the action
- When it occurred
- What changed (before and after values for updates)

This supports compliance requirements and enables investigation of billing discrepancies.

**NFR-2: Ease of Use**

The web interface must:
- Follow existing patterns in the ColdFront interface for consistency
- Provide clear navigation and intuitive workflows
- Display maintenance window status (upcoming, in progress, completed) at a glance
- Include contextual help for users unfamiliar with the feature

**NFR-3: Data Integrity**

The system must:
- Validate that end times are after start times
- Handle timezone-aware date/time values correctly
- Preserve historical maintenance records for billing accuracy
- Support natural keys for fixture-based data loading

**NFR-4: Developer Experience**

The feature must:
- Follow established plugin patterns for maintainability
- Include documentation for API usage and extension
- Integrate with existing backup/restore infrastructure
- Be testable via standard Django testing approaches

## 1.3 Overview of the Development Session

### A Plan-Driven Approach

This feature was implemented through a structured, plan-driven development process. Rather than building the feature incrementally in an exploratory manner, the work began with comprehensive planning that identified all necessary tasks, their dependencies, and their implementation details.

The plan document captured:
- The complete scope of the feature across all layers (model, views, API, CLI, admin)
- Dependencies between tasks (e.g., the model must exist before views can query it)
- Specific files to create or modify for each task
- Patterns to follow from existing code in the plugin

### Twelve Discrete Implementation Tasks

The implementation was broken into 12 self-contained tasks (TODOs), each representing a cohesive unit of work:

| TODO | Title | Purpose |
|------|-------|---------|
| 1 | Model and Migration | Create the `MaintenanceWindow` database model |
| 2 | Billing Calculations | Integrate maintenance deductions into billing |
| 3 | Web UI | Build views and templates for CRUD operations |
| 4 | REST API | Add API endpoints using Django REST Framework |
| 5 | Management Commands | Create CLI tools for administrators |
| 6 | Export/Import | Enable backup and restoration of maintenance data |
| 7 | Django Admin | Register model in Django's admin interface |
| 8 | Activity Logging | Add audit trail for all operations |
| 9 | Invoice Display | Update invoice templates to show deductions |
| 10 | Help Text System | Add contextual help for the feature |
| 11 | Edit Restrictions | Prevent modification of historical windows |
| 12 | Documentation | Create developer and user documentation |

### Task Dependencies

The tasks follow a logical dependency structure:

```
TODO 1 (Model) ← Foundation for everything
    │
    ├── TODO 2 (Billing) ────► TODO 9 (Invoice Display)
    │
    ├── TODO 3 (Web UI) ──┬──► TODO 8 (Activity Logging)
    │                     ├──► TODO 10 (Help Text)
    │                     └──► TODO 11 (Edit Restrictions)
    │
    ├── TODO 4 (REST API)
    │
    ├── TODO 5 (Management Commands)
    │
    ├── TODO 6 (Export/Import)
    │
    └── TODO 7 (Django Admin)
            │
            └──► TODO 12 (Documentation) [depends on all]
```

TODO 1 is the foundation—without the model, nothing else can work. TODOs 2-7 can be implemented in parallel (they all depend only on TODO 1). TODOs 8-11 build on the web UI (TODO 3). TODO 12 comes last because it documents everything that came before.

### Agent-Executed Implementation

Each TODO was executed by an AI coding agent with access to:
- The full plan document describing all tasks
- The specific task to implement
- The project codebase
- Tools for reading, writing, and executing code

The agents worked sequentially, with each agent's output becoming part of the codebase for subsequent agents. This approach offered several benefits:

1. **Focused context:** Each agent only needed to understand its specific task, not the entire feature
2. **Clear boundaries:** Task completion criteria were explicit in the plan
3. **Pattern consistency:** Agents were instructed to follow existing patterns in the codebase
4. **Incremental validation:** Each task could be verified before proceeding to the next

### What This Tutorial Covers

The remaining sections of this tutorial explain:

- **Section 2:** Django and ColdFront fundamentals for developers new to these technologies
- **Section 3:** Deep dives into specific patterns used in the implementation
- **Section 4:** How the abstract concepts map to the concrete implementation tasks
- **Section 5:** Detailed walkthroughs of each TODO with code explanations
- **Section 6:** The agentic development process itself—how prompts were structured, how agents were coordinated, and lessons learned

By the end, you'll understand not just *what* was built, but *why* each design decision was made and *how* the pieces fit together. Whether you're learning Django, extending ColdFront, or exploring agentic development workflows, this tutorial provides a complete case study of a real feature implementation.

---

*Continue to [Section 2: Foundations for Non-Django Developers](#section-2-foundations-for-non-django-developers) to learn about Django's architecture and how ColdFront extends it.*

---

# Section 2: Foundations for Non-Django Developers

This section provides experienced software developers with the Django and ColdFront knowledge needed to understand the maintenance window implementation. If you're coming from Rails, Express, Spring, or other web frameworks, you'll find familiar concepts mapped to Django's terminology and patterns.

## 2.1 What is Django?

### High-Level Overview

Django is a high-level Python web framework that follows the "batteries included" philosophy. Unlike micro-frameworks that provide minimal functionality and expect you to choose your own components, Django ships with:

- An **Object-Relational Mapper (ORM)** for database operations
- A **template engine** for rendering HTML
- A **URL routing system** for mapping URLs to code
- An **authentication system** with users, groups, and permissions
- An **admin interface** that auto-generates CRUD screens from your models
- **Form handling** with validation and CSRF protection
- **Database migration** support for schema evolution
- **Testing tools** integrated into the framework

This comprehensive approach means less time choosing and integrating libraries, and more consistency across Django projects.

### Comparison to Frameworks You Might Know

| If You Know... | Django Is Like... | Key Difference |
|----------------|-------------------|----------------|
| **Ruby on Rails** | Very similar philosophy—convention over configuration, ORM-centric, "batteries included" | Python instead of Ruby; Django's "View" = Rails controller |
| **Express.js** | More opinionated; includes ORM and admin UI out of the box | Express is minimal; Django provides the whole stack |
| **Spring Boot** | Similar in scope and enterprise readiness | Python's simplicity vs Java's verbosity; faster iteration |
| **Flask** | Django is Flask's "full-stack" sibling | Flask is micro-framework; Django includes everything |
| **ASP.NET MVC** | Similar MVC concepts, similar scope | Python ecosystem; Django's admin is unique |
| **Laravel** | Very similar—Eloquent ORM ≈ Django ORM, Blade ≈ Django templates | Django is older with larger ecosystem |

> **Coming from Rails?** You'll feel at home. Django's ORM is like ActiveRecord, migrations work similarly, and the project structure has familiar concepts. The main mental shift: Django calls controllers "views" and calls views "templates."

> **Coming from Express/Node?** Django is much more opinionated. You don't pick a database library—you use the ORM. You don't pick a template engine—you use Django templates. This is either liberating or constraining depending on your perspective.

### The MTV Architecture

Django uses **Model-Template-View (MTV)**, which is a variant of the classic MVC pattern. The naming is historically unfortunate because Django's "View" is actually what most frameworks call a "Controller."

Here's how requests flow through a Django application:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         HTTP Request                                 │
│                    (GET /maintenance-windows/)                       │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     URL Dispatcher (urls.py)                         │
│                                                                       │
│  urlpatterns = [                                                      │
│      path("maintenance-windows/", MaintenanceWindowListView.as_view())│
│  ]                                                                    │
│                                                                       │
│  "Match URL pattern to a View"                                        │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        View (views.py)                               │
│                                                                       │
│  class MaintenanceWindowListView(ListView):                          │
│      model = MaintenanceWindow                                        │
│      template_name = "maintenance_window_list.html"                   │
│                                                                       │
│  "Handle request logic, query the Model, choose the Template"         │
│                                                                       │
│  ⚠️  THIS IS LIKE A CONTROLLER IN OTHER FRAMEWORKS                    │
└─────────────────────────────────────────────────────────────────────┘
                    │                           │
                    ▼                           ▼
┌───────────────────────────────┐ ┌───────────────────────────────────┐
│      Model (models.py)        │ │     Template (*.html files)       │
│                               │ │                                    │
│  class MaintenanceWindow:     │ │  {% for window in object_list %}   │
│      title = CharField(...)   │ │      <tr>{{ window.title }}</tr>   │
│      start_datetime = ...     │ │  {% endfor %}                      │
│                               │ │                                    │
│  "Python class = DB table"    │ │  ⚠️  THIS IS THE "VIEW" IN MVC     │
│  "Instance = DB row"          │ │  "HTML with placeholders"          │
└───────────────────────────────┘ └───────────────────────────────────┘
                    │                           │
                    └─────────────┬─────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        HTTP Response                                 │
│                     (Rendered HTML page)                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Insight: Django's Naming Convention

| Django Term | Traditional MVC Term | What It Does |
|-------------|---------------------|--------------|
| **Model** | Model | Represents data and database operations |
| **Template** | View | Presents data to the user (HTML rendering) |
| **View** | Controller | Handles request logic, orchestrates Model and Template |

This tutorial uses Django's terminology throughout. When you see "View," think "the code that handles the request" (like a controller action).

## 2.2 Django Project Structure Explained

### Annotated Directory Tree

A typical Django project with one application looks like this:

```
my_project/                          # ← Project root directory
│
├── manage.py                        # ← CLI tool for all Django commands
│                                    #   (runserver, migrate, makemigrations, etc.)
│
├── my_project/                      # ← Project configuration package
│   │                                #   (same name as root by convention)
│   │
│   ├── __init__.py                  # ← Makes this a Python package
│   ├── settings.py                  # ← Configuration: database, apps, middleware
│   ├── urls.py                      # ← Root URL routing (includes app URLs)
│   ├── wsgi.py                      # ← Web Server Gateway Interface entry point
│   └── asgi.py                      # ← Async entry point (for WebSockets, etc.)
│
└── my_app/                          # ← A Django "app" (modular component)
    │
    ├── __init__.py                  # ← Makes this a Python package
    ├── apps.py                      # ← App configuration class
    ├── models.py                    # ← Database models (ORM classes)
    ├── views.py                     # ← Request handlers (controllers)
    ├── urls.py                      # ← App-specific URL routing
    ├── admin.py                     # ← Admin interface configuration
    ├── forms.py                     # ← Form classes for data entry
    ├── serializers.py               # ← API serializers (Django REST Framework)
    │
    ├── templates/                   # ← HTML templates
    │   └── my_app/                  # ← Namespaced by app name
    │       ├── base.html
    │       └── item_list.html
    │
    ├── static/                      # ← CSS, JavaScript, images
    │   └── my_app/
    │       └── style.css
    │
    ├── migrations/                  # ← Database schema change files
    │   ├── __init__.py
    │   ├── 0001_initial.py          # ← First migration (create tables)
    │   └── 0002_add_field.py        # ← Subsequent changes
    │
    ├── management/                  # ← Custom CLI commands
    │   └── commands/
    │       ├── __init__.py
    │       └── my_command.py        # ← Invoked: python manage.py my_command
    │
    └── tests/                       # ← Test files
        ├── __init__.py
        └── test_models.py
```

### Key Files Explained

**`manage.py`** — The command-line interface to Django. You'll use it constantly:

```bash
python manage.py runserver          # Start development server
python manage.py migrate            # Apply database migrations
python manage.py makemigrations     # Create new migrations from model changes
python manage.py createsuperuser    # Create admin user
python manage.py shell              # Interactive Python shell with Django loaded
python manage.py test               # Run tests
```

**`settings.py`** — Central configuration. Key settings include:

```python
INSTALLED_APPS = [
    'django.contrib.admin',         # Built-in admin
    'django.contrib.auth',          # Authentication
    'my_app',                        # Your app (must be listed to be recognized)
    'coldfront_orcd_direct_charge',  # Third-party plugin
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mydb',
    }
}
```

**`urls.py`** (project level) — Maps URL patterns to apps or views:

```python
urlpatterns = [
    path('admin/', admin.site.urls),                    # Django admin
    path('nodes/', include('my_app.urls')),             # All /nodes/* URLs
    path('api/', include('my_app.api_urls')),           # API endpoints
]
```

### "App" vs "Project": The Key Distinction

This is one of the most confusing aspects of Django for newcomers. Here's the difference:

| Concept | Definition | Quantity | Example |
|---------|-----------|----------|---------|
| **Project** | The entire web application | One per deployment | "The ColdFront portal" |
| **App** | A modular, reusable component | Many per project | "User management," "GPU rentals," "Maintenance windows" |

**Analogy: Building a Car**

Think of a Django **Project** as the complete car you're building. A Django **App** is like a major component:

```
PROJECT (The Car)
├── APP: Engine           (could be reused in different cars)
├── APP: Transmission     (self-contained component)
├── APP: Braking System   (interacts with other systems via defined interfaces)
├── APP: Entertainment    (optional, pluggable)
└── APP: Navigation       (could be swapped for different implementation)
```

Each app:
- Has its own models, views, templates, and tests
- Can be reused in different projects
- Has defined interfaces for interacting with other apps
- Can be distributed as a package (like `coldfront-orcd-direct-charge`)

> **Coming from Rails?** Django apps are like Rails engines. A Rails engine can have its own models, controllers, views, and routes—just like a Django app.

> **Coming from Java/Spring?** Think of apps as modules in a multi-module Maven project. Each module has its own domain, but they're assembled into a single deployable application.

## 2.3 What is ColdFront?

### High-Level Overview

ColdFront is an open-source **resource allocation management system** designed for High-Performance Computing (HPC) centers. It helps research computing organizations:

- Track who can access which computing resources
- Manage project-based allocations of compute time, storage, and specialized hardware
- Handle approval workflows for resource requests
- Generate reports for funding agencies and compliance

ColdFront is built on Django, which means everything you learned in Section 2.1 applies. ColdFront is essentially a Django project with multiple apps for user management, project management, allocation management, and more.

### Why ColdFront Matters for This Tutorial

The maintenance window feature is implemented as a **plugin for ColdFront**. Specifically, it extends the `coldfront-orcd-direct-charge` plugin, which adds GPU node rental functionality to ColdFront.

Understanding this hierarchy helps you see where our code fits:

```
┌─────────────────────────────────────────────────────────────────────┐
│                           ColdFront Core                             │
│                                                                       │
│  • User authentication and management                                 │
│  • Project creation and membership                                    │
│  • Allocation workflows                                               │
│  • Built-in reporting                                                 │
│                                                                       │
│  (Django project with multiple apps)                                  │
├─────────────────────────────────────────────────────────────────────┤
│                  coldfront-orcd-direct-charge Plugin                 │
│                                                                       │
│  • GPU Node inventory management                                      │
│  • Reservation (rental) tracking                                      │
│  • Billing calculation and invoices                                   │
│  • Cost allocation across funding accounts                            │
│  • ★ Maintenance Windows ★  ← What we're building                     │
│                                                                       │
│  (Django app installed as a package)                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### ColdFront's Core Entities

To understand how our plugin integrates, you need to know ColdFront's main data model:

```
┌─────────────────┐              ┌─────────────────┐
│      User       │◄────────────►│     Project     │
│                 │   member of  │                 │
│  • username     │   (many-to-  │  • title        │
│  • email        │    many)     │  • description  │
│  • first_name   │              │  • pi (User FK) │
└─────────────────┘              └─────────────────┘
                                         │
                                         │ has many
                                         ▼
                                 ┌─────────────────┐
                                 │   Allocation    │
                                 │                 │
                                 │  • project (FK) │
                                 │  • resource(FK) │
                                 │  • status       │
                                 │  • start_date   │
                                 │  • end_date     │
                                 └─────────────────┘
                                         │
                                         │ for a
                                         ▼
                                 ┌─────────────────┐
                                 │    Resource     │
                                 │                 │
                                 │  • name         │
                                 │  • description  │
                                 │  • resource_type│
                                 └─────────────────┘
```

**In plain English:**
- **Users** are researchers who need computing resources
- **Projects** are research groups (usually a PI and their lab members)
- **Allocations** grant a Project access to a specific Resource for a time period
- **Resources** are the computing assets: clusters, storage systems, GPU nodes

The rental plugin adds its own models (`GPUNode`, `Reservation`, `Invoice`) that link to ColdFront's core models.

## 2.4 Plugin Architecture

### What is a Django Plugin?

A Django plugin (often called a "reusable app" or "third-party app") is:

1. **A Python package** installable via pip
2. **A Django app** that gets added to `INSTALLED_APPS`
3. **Self-contained** with its own models, views, templates, and URLs

When you install a plugin, you're essentially adding a pre-built Django app to your project. The plugin can:

- Add new database tables (via its own models)
- Add new URL routes (via its own urls.py)
- Add new views and templates
- Add new admin interfaces
- Add new CLI commands
- Hook into the host application's signals and extension points

### How INSTALLED_APPS Works

Django's `INSTALLED_APPS` setting is a list of strings identifying which apps are active in the project:

```python
# settings.py
INSTALLED_APPS = [
    # Django built-in apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    
    # ColdFront core apps
    'coldfront.core.user',
    'coldfront.core.project',
    'coldfront.core.allocation',
    
    # Third-party plugins
    'coldfront_orcd_direct_charge',    # ← Our plugin
    
    # Other third-party packages
    'rest_framework',
    'django_filters',
]
```

When Django starts, it:
1. Iterates through `INSTALLED_APPS`
2. Loads each app's configuration (`apps.py`)
3. Discovers and registers the app's models
4. Collects the app's static files and templates
5. Loads URL patterns if included in the root `urls.py`

### How This Plugin Integrates with ColdFront

The `coldfront-orcd-direct-charge` plugin integrates with ColdFront at multiple points:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ColdFront Settings                            │
│                                                                       │
│  INSTALLED_APPS = [                                                   │
│      ...                                                              │
│      'coldfront_orcd_direct_charge',  ← Plugin registered            │
│  ]                                                                    │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────────┐
        ▼                           ▼                               ▼
┌───────────────┐        ┌───────────────────┐          ┌───────────────┐
│  URL Mounting │        │   Model Loading   │          │Template Search│
│               │        │                   │          │               │
│ /nodes/*      │        │ GPUNode           │          │ Plugin's      │
│ routes to     │        │ Reservation       │          │ templates/    │
│ plugin views  │        │ MaintenanceWindow │          │ directory is  │
│               │        │ etc.              │          │ searched      │
└───────────────┘        └───────────────────┘          └───────────────┘
```

**URL Integration:** The ColdFront project's `urls.py` includes the plugin's URLs:

```python
urlpatterns = [
    ...
    path('nodes/', include('coldfront_orcd_direct_charge.urls')),
]
```

**Model Integration:** The plugin's models can have ForeignKey relationships to ColdFront models:

```python
# Plugin model linking to ColdFront's User
class Reservation(models.Model):
    created_by = models.ForeignKey(
        'auth.User',  # ColdFront uses Django's User model
        on_delete=models.SET_NULL
    )
```

**Permission Integration:** The plugin defines its own permissions that integrate with ColdFront's permission system:

```python
class Meta:
    permissions = [
        ('can_manage_rentals', 'Can manage GPU rentals'),
        ('can_manage_billing', 'Can manage billing'),
    ]
```

## 2.5 ORCD Project Abstraction

The ORCD plugin extends ColdFront's base project model with domain-specific role management for GPU rental billing. This is a critical architectural concept that underpins how permissions and billing work in the rental portal.

### The Layered Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Django Framework                                │
│  • User model, Group and Permission models, ORM, Admin interface             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ▲
                                      │ extends
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ColdFront Core                                  │
│  • Project model (title, PI, status)                                         │
│  • ProjectUser model (links users to projects with generic roles)            │
│  • Allocation model (grants project access to resources)                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ▲
                                      │ extends
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ORCD Direct Charge Plugin                            │
│  • ProjectMemberRole model (ORCD-specific roles: financial_admin,            │
│    technical_admin, member)                                                  │
│  • Reservation, MaintenanceWindow, ProjectCostAllocation, etc.               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Dual-Record Pattern

A user participating in an ORCD project requires **two** types of records:

1. **ProjectUser** (ColdFront requirement): Links user to project with a generic role ("Manager" or "User")
2. **ProjectMemberRole** (ORCD requirement): Assigns domain-specific permissions

```python
# ORCD roles with distinct permissions
class ProjectMemberRole(models.Model):
    class RoleChoices(models.TextChoices):
        FINANCIAL_ADMIN = "financial_admin"  # Manages billing, NOT billed for AMF
        TECHNICAL_ADMIN = "technical_admin"  # Manages members, IS billed for AMF
        MEMBER = "member"                    # Basic user, IS billed for AMF
    
    project = models.ForeignKey(Project, ...)
    user = models.ForeignKey(User, ...)
    role = models.CharField(choices=RoleChoices.choices, ...)
```

### Key Design Principles

| Principle | Description |
|-----------|-------------|
| **Multiple roles per user** | Users can have multiple ORCD roles in the same project |
| **Additive permissions** | Each role adds capabilities; roles don't conflict |
| **Role-based billing** | Financial admins are excluded from maintenance fee billing |
| **Implicit owner** | The project PI has full permissions without explicit role assignment |

> **For the complete deep dive**, see [ORCD_PROJECT_ABSTRACTION.md](ORCD_PROJECT_ABSTRACTION.md) which covers:
> - Detailed model definitions and relationships
> - Permission checking patterns
> - How maintenance windows integrate with the project billing system
> - Code examples for creating projects programmatically

## 2.6 Terminology Glossary

Quick reference tables for terms used throughout this tutorial.

### Django Terms

| Term | Definition | Analogy for Other Frameworks |
|------|------------|------------------------------|
| **Model** | Python class representing a database table. Each attribute is a column. | Rails ActiveRecord, JPA Entity, SQLAlchemy model |
| **Migration** | Python file describing database schema changes. Applied with `manage.py migrate`. | Rails migration, Flyway script, Alembic revision |
| **View** | Function or class that handles HTTP requests and returns responses. | Rails controller action, Express route handler, Spring @Controller |
| **Template** | HTML file with Django template language for dynamic content. | ERB, Jinja2, Thymeleaf, Blade, JSP |
| **ORM** | Object-Relational Mapping—query databases with Python objects. | Hibernate, ActiveRecord, Sequelize, Entity Framework |
| **QuerySet** | Lazy-evaluated database query. Chainable; executes only when evaluated. | LINQ, Java Streams, Rails scopes |
| **Mixin** | Class providing reusable functionality via multiple inheritance. | Ruby module, Java interface with default methods, Scala trait |
| **Serializer** | Converts model instances to/from JSON (Django REST Framework). | Jackson, Marshmallow, ActiveModel::Serializer |
| **ViewSet** | Class providing CRUD operations for an API resource (DRF). | Rails resource controller, Spring @RestController |
| **Fixture** | JSON/YAML file with initial database data for testing or seeding. | Rails seeds, SQL insert scripts |
| **Management Command** | CLI command invoked via `manage.py`. | Rake task, Artisan command, Spring Boot CLI |
| **App** | Modular component within a Django project. | Rails engine, Spring module |
| **Middleware** | Code that processes requests/responses globally. | Express middleware, Rack middleware, servlet filter |

### ColdFront Terms

| Term | Definition |
|------|------------|
| **Project** | A research group or grant that users belong to. Has a Principal Investigator (PI). |
| **Allocation** | Permission for a project to use a specific computing resource for a time period. |
| **PI** | Principal Investigator—the project owner, typically a faculty member. |
| **Resource** | A computing asset: HPC cluster, storage system, cloud allocation, GPU nodes. |
| **Manager** | User with elevated permissions for certain operations. |

### Plugin-Specific Terms (coldfront-orcd-direct-charge)

| Term | Definition |
|------|------------|
| **GPU Node** | A physical server with GPU hardware available for rental. |
| **Reservation** | A booking of a GPU node for a specific time period by a project. |
| **Rental Manager** | User with permission to approve/decline reservations and manage inventory. |
| **Billing Manager** | User with permission to view/manage invoices and billing data. |
| **Invoice** | Monthly billing record showing charges for a project's reservations. |
| **Cost Allocation** | How charges are split across a project's funding accounts. |
| **Maintenance Window** | A scheduled period when nodes are unavailable and should not be billed. |

## 2.7 Key Django Patterns You'll Encounter

This section introduces the patterns you'll see repeatedly in the maintenance window implementation.

### Pattern 1: Class-Based Views (CBVs)

Django offers two approaches to writing views:

**Function-Based Views (FBVs):** Simple, explicit, more code

```python
def maintenance_window_list(request):
    """List all maintenance windows."""
    if not request.user.is_authenticated:
        return redirect('login')
    if not request.user.has_perm('app.can_manage_rentals'):
        raise PermissionDenied()
    
    windows = MaintenanceWindow.objects.all().order_by('-start_datetime')
    return render(request, 'maintenance_window_list.html', {'windows': windows})
```

**Class-Based Views (CBVs):** Declarative, reusable, less boilerplate

```python
class MaintenanceWindowListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """List all maintenance windows."""
    model = MaintenanceWindow
    template_name = 'maintenance_window_list.html'
    context_object_name = 'windows'
    ordering = ['-start_datetime']
    permission_required = 'app.can_manage_rentals'
```

The CBV version:
- Automatically handles authentication (via `LoginRequiredMixin`)
- Automatically handles permission checks (via `PermissionRequiredMixin`)
- Automatically queries the model and paginates results
- Follows Django conventions without reinventing the wheel

> **Coming from Rails?** CBVs are somewhat like using Rails' scaffolding but with more flexibility. The view classes are similar to inheriting from `ApplicationController` and calling class methods like `before_action`.

### Pattern 2: Mixins for Composition

Python supports multiple inheritance, and Django uses this for composable view behavior:

```python
class MaintenanceWindowUpdateView(
    LoginRequiredMixin,           # 1st: Must be logged in
    PermissionRequiredMixin,      # 2nd: Must have permission
    SuccessMessageMixin,          # 3rd: Show message after success
    UpdateView                    # 4th: Base functionality
):
    model = MaintenanceWindow
    permission_required = 'app.can_manage_rentals'
    success_message = "Maintenance window updated successfully."
```

Mixins are read **left to right** but resolved **right to left** (Method Resolution Order). The last class (`UpdateView`) provides the base implementation; earlier classes can override or extend behavior.

Common Django mixins:
- `LoginRequiredMixin` — Redirect to login if not authenticated
- `PermissionRequiredMixin` — Return 403 if missing permission
- `SuccessMessageMixin` — Flash a message after successful form submission
- `UserPassesTestMixin` — Custom test function for access control

### Pattern 3: QuerySet Chaining

Django QuerySets are lazy—they don't hit the database until evaluated:

```python
# No database query yet
qs = MaintenanceWindow.objects.all()

# Still no query—we're just building the query
qs = qs.filter(start_datetime__gte=now)    # Only future windows
qs = qs.filter(created_by=user)             # Created by specific user
qs = qs.order_by('start_datetime')          # Order by start time

# NOW the query executes (when we iterate or convert to list)
for window in qs:
    print(window.title)
```

This allows you to build queries incrementally and pass QuerySets around without performance concerns.

> **Coming from Rails?** This is exactly like ActiveRecord scopes. `User.where(active: true).order(:name)` doesn't execute until you iterate.

### Pattern 4: Template Inheritance

Django templates support inheritance with `{% extends %}` and `{% block %}`:

**base.html** (parent template):
```html
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}My Site{% endblock %}</title>
</head>
<body>
    <nav>{% include "navbar.html" %}</nav>
    
    <main>
        {% block content %}
        <!-- Child templates fill this in -->
        {% endblock %}
    </main>
    
    <footer>© 2026 Research Computing</footer>
</body>
</html>
```

**maintenance_window_list.html** (child template):
```html
{% extends "base.html" %}

{% block title %}Maintenance Windows{% endblock %}

{% block content %}
<h1>Maintenance Windows</h1>
<table>
    {% for window in object_list %}
    <tr>
        <td>{{ window.title }}</td>
        <td>{{ window.start_datetime|date:"Y-m-d H:i" }}</td>
    </tr>
    {% empty %}
    <tr><td colspan="2">No maintenance windows found.</td></tr>
    {% endfor %}
</table>
{% endblock %}
```

The child template:
- Inherits all HTML from `base.html`
- Overrides specific `{% block %}` sections
- Has access to context variables passed by the view

## 2.8 The Django Development Workflow

When adding a new feature to a Django application, you typically follow this workflow:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Step 1: DEFINE MODELS                                               │
│                                                                       │
│  Edit models.py to define your data structure:                        │
│                                                                       │
│    class MaintenanceWindow(models.Model):                             │
│        title = models.CharField(max_length=200)                       │
│        start_datetime = models.DateTimeField()                        │
│        ...                                                            │
└───────────────────────────────────┬─────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 2: CREATE MIGRATIONS                                           │
│                                                                       │
│  $ python manage.py makemigrations                                    │
│                                                                       │
│  Django inspects model changes and generates migration files.         │
└───────────────────────────────────┬─────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 3: APPLY MIGRATIONS                                            │
│                                                                       │
│  $ python manage.py migrate                                           │
│                                                                       │
│  Django executes migration files to update the database schema.       │
└───────────────────────────────────┬─────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 4: CREATE VIEWS                                                │
│                                                                       │
│  Edit views.py to handle requests:                                    │
│                                                                       │
│    class MaintenanceWindowListView(ListView):                         │
│        model = MaintenanceWindow                                      │
│        template_name = 'maintenance_window_list.html'                 │
└───────────────────────────────────┬─────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 5: DEFINE URLS                                                 │
│                                                                       │
│  Edit urls.py to map URL patterns to views:                           │
│                                                                       │
│    urlpatterns = [                                                    │
│        path('maintenance-windows/',                                   │
│             MaintenanceWindowListView.as_view(),                      │
│             name='maintenance_window_list'),                          │
│    ]                                                                  │
└───────────────────────────────────┬─────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 6: CREATE TEMPLATES                                            │
│                                                                       │
│  Create HTML files in templates/ directory:                           │
│                                                                       │
│    {% extends "base.html" %}                                          │
│    {% block content %}                                                │
│      <h1>Maintenance Windows</h1>                                     │
│      ...                                                              │
│    {% endblock %}                                                     │
└───────────────────────────────────┬─────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 7: TEST                                                        │
│                                                                       │
│  $ python manage.py test                                              │
│                                                                       │
│  Run automated tests to verify the feature works correctly.           │
└─────────────────────────────────────────────────────────────────────┘
```

The maintenance window feature follows this exact workflow, spread across 12 TODOs:
- **TODO 1** handles Steps 1-3 (Model and Migrations)
- **TODO 3** handles Steps 4-6 (Views, URLs, Templates)
- Other TODOs add additional layers (API, CLI, admin, etc.)

## 2.9 How to Read Django Code

This section provides annotated examples to help you read Django code even if you've never seen it before.

### Reading a Model

```python
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from coldfront_orcd_direct_charge.models import TimeStampedModel

User = get_user_model()  # Gets the active User model (allows customization)


class MaintenanceWindow(TimeStampedModel):
    """
    Represents a scheduled maintenance period during which
    GPU nodes are unavailable.
    """
    #
    # ┌─────────────────────────────────────────────────────────────┐
    # │ TimeStampedModel is a base class that automatically adds:   │
    # │   - created_at: DateTimeField (auto-set on creation)        │
    # │   - modified_at: DateTimeField (auto-set on every save)     │
    # └─────────────────────────────────────────────────────────────┘
    
    # CharField = VARCHAR in SQL. max_length is required.
    title = models.CharField(
        max_length=200,
        help_text="Brief name for this maintenance window"
    )
    
    # TextField = TEXT in SQL. No max_length needed.
    description = models.TextField(
        blank=True,     # ← Form validation: field can be empty
        default='',     # ← Database default value
        help_text="Detailed description of the maintenance work"
    )
    
    # DateTimeField = DATETIME/TIMESTAMP in SQL
    start_datetime = models.DateTimeField(
        help_text="When maintenance begins"
    )
    
    end_datetime = models.DateTimeField(
        help_text="When maintenance ends"
    )
    
    # ForeignKey = Foreign key relationship to another table
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,  # ← If user deleted, set this field to NULL
        null=True,                   # ← Database allows NULL values
        blank=True,                  # ← Form allows empty submission
        related_name='created_maintenance_windows'  # ← Reverse accessor name
    )
    #
    # ┌─────────────────────────────────────────────────────────────┐
    # │ on_delete options:                                          │
    # │   CASCADE   - Delete this record when related record deleted│
    # │   SET_NULL  - Set to NULL when related record deleted       │
    # │   PROTECT   - Prevent deletion of related record            │
    # │   SET_DEFAULT - Set to default value                        │
    # └─────────────────────────────────────────────────────────────┘

    class Meta:
        """Model metadata and options."""
        ordering = ['-start_datetime']  # Default sort: newest first
        
        # Custom permissions for this model
        permissions = [
            ('can_manage_maintenance_windows', 'Can manage maintenance windows'),
        ]

    def __str__(self):
        """String representation shown in admin and shell."""
        return f"{self.title} ({self.start_datetime.date()})"
    
    # Property = computed attribute (not stored in database)
    @property
    def is_upcoming(self):
        """Return True if this window hasn't started yet."""
        return timezone.now() < self.start_datetime
    
    @property
    def is_in_progress(self):
        """Return True if maintenance is currently happening."""
        now = timezone.now()
        return self.start_datetime <= now < self.end_datetime
    
    @property
    def duration_hours(self):
        """Return the duration in hours (computed, not stored)."""
        delta = self.end_datetime - self.start_datetime
        return delta.total_seconds() / 3600
```

### Reading a View

```python
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.messages.views import SuccessMessageMixin

from .models import MaintenanceWindow


class MaintenanceWindowListView(
    LoginRequiredMixin,       # ← User must be logged in
    PermissionRequiredMixin,  # ← User must have specific permission
    ListView                  # ← Base class for displaying a list of objects
):
    """
    Display a list of all maintenance windows.
    
    ┌─────────────────────────────────────────────────────────────────┐
    │ What ListView provides automatically:                          │
    │   - Queries MaintenanceWindow.objects.all()                    │
    │   - Passes results as 'object_list' to template                │
    │   - Handles pagination if configured                           │
    │   - Renders the specified template                             │
    └─────────────────────────────────────────────────────────────────┘
    """
    
    # Required attributes
    model = MaintenanceWindow                           # What model to query
    template_name = 'maintenance_window_list.html'      # Which template to render
    permission_required = 'app.can_manage_rentals'      # Required permission
    
    # Optional customization
    context_object_name = 'maintenance_windows'         # Variable name in template
    ordering = ['-start_datetime']                       # Sort order
    paginate_by = 25                                     # Items per page
    
    def get_queryset(self):
        """
        Override to customize the query.
        Called automatically by ListView.
        """
        # Start with default queryset
        qs = super().get_queryset()
        
        # Optional: filter based on query parameters
        status = self.request.GET.get('status')
        if status == 'upcoming':
            qs = qs.filter(start_datetime__gt=timezone.now())
        
        return qs
    
    def get_context_data(self, **kwargs):
        """
        Override to add extra variables to template context.
        """
        context = super().get_context_data(**kwargs)
        
        # Add custom data for the template
        context['total_count'] = MaintenanceWindow.objects.count()
        context['page_title'] = 'Maintenance Windows'
        
        return context
```

### Reading URL Configuration

```python
from django.urls import path
from . import views

# App namespace for URL reversing
app_name = 'orcd_direct_charge'

urlpatterns = [
    #
    # ┌─────────────────────────────────────────────────────────────┐
    # │ path() arguments:                                           │
    # │   1. URL pattern (string)                                   │
    # │   2. View to handle the request                             │
    # │   3. name for reverse lookup (optional but recommended)     │
    # └─────────────────────────────────────────────────────────────┘
    
    # List view: GET /maintenance-windows/
    path(
        'maintenance-windows/',                      # URL pattern
        views.MaintenanceWindowListView.as_view(),  # View class → callable
        name='maintenance_window_list'               # Name for {% url %} tag
    ),
    #
    # ┌─────────────────────────────────────────────────────────────┐
    # │ .as_view() converts a class into a callable function.      │
    # │ Each request creates a new instance of the view class.     │
    # └─────────────────────────────────────────────────────────────┘
    
    # Create view: GET/POST /maintenance-windows/create/
    path(
        'maintenance-windows/create/',
        views.MaintenanceWindowCreateView.as_view(),
        name='maintenance_window_create'
    ),
    
    # Detail/Update view: GET/POST /maintenance-windows/42/edit/
    path(
        'maintenance-windows/<int:pk>/edit/',  # ← pk = primary key (integer)
        views.MaintenanceWindowUpdateView.as_view(),
        name='maintenance_window_update'
    ),
    #
    # ┌─────────────────────────────────────────────────────────────┐
    # │ Path converters:                                            │
    # │   <int:pk>  - Matches integers, passed as pk argument       │
    # │   <str:slug> - Matches any non-empty string                 │
    # │   <uuid:id> - Matches UUID format                           │
    # └─────────────────────────────────────────────────────────────┘
    
    # Delete view: GET/POST /maintenance-windows/42/delete/
    path(
        'maintenance-windows/<int:pk>/delete/',
        views.MaintenanceWindowDeleteView.as_view(),
        name='maintenance_window_delete'
    ),
]
```

**Using Named URLs in Templates:**

```html
<!-- Link to the list view -->
<a href="{% url 'orcd_direct_charge:maintenance_window_list' %}">
    View All Windows
</a>

<!-- Link with an argument (pk=42) -->
<a href="{% url 'orcd_direct_charge:maintenance_window_update' pk=window.pk %}">
    Edit {{ window.title }}
</a>
```

**Using Named URLs in Python:**

```python
from django.urls import reverse

# Generate URL string
url = reverse('orcd_direct_charge:maintenance_window_list')
# Returns: '/nodes/maintenance-windows/'

# With arguments
url = reverse('orcd_direct_charge:maintenance_window_update', kwargs={'pk': 42})
# Returns: '/nodes/maintenance-windows/42/edit/'
```

---

> **Summary:** This section covered the foundational knowledge needed to understand the maintenance window implementation. You learned about Django's MTV architecture, project structure, ColdFront's role, how plugins integrate, and the key patterns used throughout Django applications. In Section 3, we'll dive deeper into specific patterns and techniques used in the actual implementation.

---

*Continue to [Section 3: Key Concepts in Depth](#section-3-key-concepts-in-depth) for detailed coverage of Django ORM, Class-Based Views, Django REST Framework, and plugin-specific patterns.*

---

# Section 3: Key Concepts in Depth

This section builds on the foundations from Section 2, providing detailed explanations and code examples for the specific patterns used in the maintenance window implementation. These concepts will appear repeatedly in the TODO walkthroughs in Section 5.

## 3.1 Django Concepts (Deep Dive)

### Models and Migrations

#### TimeStampedModel: Automatic Timestamp Tracking

Many database tables need `created_at` and `modified_at` timestamps. Rather than adding these fields to every model, Django developers use abstract base classes:

```python
# coldfront_orcd_direct_charge/models.py (base class)

from django.db import models


class TimeStampedModel(models.Model):
    """
    Abstract base class that provides self-updating
    'created_at' and 'modified_at' fields.
    """
    created_at = models.DateTimeField(auto_now_add=True)  # Set once on creation
    modified_at = models.DateTimeField(auto_now=True)     # Updated on every save

    class Meta:
        abstract = True  # ← Django won't create a table for this class
        #
        # ┌─────────────────────────────────────────────────────────────┐
        # │ abstract = True means:                                       │
        # │   - No database table is created for TimeStampedModel       │
        # │   - Child classes inherit the fields                         │
        # │   - Each child gets its own created_at/modified_at columns  │
        # └─────────────────────────────────────────────────────────────┘


# Child class inherits the timestamp fields
class MaintenanceWindow(TimeStampedModel):
    title = models.CharField(max_length=200)
    # ... automatically has created_at and modified_at
```

> **Coming from Rails?** This is similar to a concern or module that adds timestamps, but implemented through inheritance rather than `include`.

#### ForeignKey on_delete Behaviors

When a referenced record is deleted, Django needs to know what to do with records that point to it. The `on_delete` parameter specifies this behavior:

```python
class MaintenanceWindow(TimeStampedModel):
    # If the user who created this window is deleted...
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,  # ...set this field to NULL
        null=True,                   # ...which requires allowing NULL
    )
    
    # Other on_delete options with examples:
    
    # CASCADE: Delete this record when parent is deleted
    # Use for: child records that make no sense without parent
    # allocation = models.ForeignKey(Allocation, on_delete=models.CASCADE)
    
    # PROTECT: Prevent parent deletion if children exist
    # Use for: important references that should never become orphaned
    # project = models.ForeignKey(Project, on_delete=models.PROTECT)
    
    # SET_DEFAULT: Set to a default value
    # Use for: when you have a meaningful default
    # status = models.ForeignKey(Status, on_delete=models.SET_DEFAULT, default=1)
    
    # DO_NOTHING: Take no action (database may raise IntegrityError)
    # Use for: database-level handling with triggers
    # legacy_ref = models.ForeignKey(Legacy, on_delete=models.DO_NOTHING)
```

#### Properties vs Database Fields

Model attributes can be **stored** (database columns) or **computed** (calculated on access):

```python
class MaintenanceWindow(TimeStampedModel):
    # STORED FIELDS: These are database columns
    title = models.CharField(max_length=200)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    
    # COMPUTED PROPERTIES: These are calculated, not stored
    @property
    def duration_hours(self):
        """Duration in hours (computed from start and end)."""
        delta = self.end_datetime - self.start_datetime
        return delta.total_seconds() / 3600
    
    @property
    def is_upcoming(self):
        """True if maintenance hasn't started yet."""
        return timezone.now() < self.start_datetime
    
    @property
    def is_in_progress(self):
        """True if maintenance is currently happening."""
        now = timezone.now()
        return self.start_datetime <= now < self.end_datetime
    
    @property
    def is_completed(self):
        """True if maintenance has ended."""
        return timezone.now() >= self.end_datetime
    
    @property
    def status(self):
        """Return a status string for display."""
        if self.is_upcoming:
            return "Upcoming"
        elif self.is_in_progress:
            return "In Progress"
        else:
            return "Completed"
```

**When to use properties vs fields:**

| Use Property When... | Use Field When... |
|---------------------|-------------------|
| Value can be calculated from other fields | Value is independent data |
| Value changes based on current time | Value is fixed at entry time |
| Storage cost outweighs computation cost | Fast access is critical |
| Value would become stale if stored | Value needs to be queried/filtered |

> **Important:** You cannot use `filter()` on properties! If you need `MaintenanceWindow.objects.filter(is_upcoming=True)`, you must write `MaintenanceWindow.objects.filter(start_datetime__gt=timezone.now())`.

#### The clean() Method for Business Rule Validation

Django's `clean()` method runs during model validation (before save). Use it for business rules that span multiple fields:

```python
from django.core.exceptions import ValidationError


class MaintenanceWindow(TimeStampedModel):
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    
    def clean(self):
        """
        Validate business rules before saving.
        Called by full_clean() and ModelForm validation.
        """
        super().clean()  # Always call parent's clean()
        
        # Rule 1: End must be after start
        if self.start_datetime and self.end_datetime:
            if self.end_datetime <= self.start_datetime:
                raise ValidationError({
                    'end_datetime': 'End date/time must be after start date/time.'
                })
        
        # Rule 2: Window must be at least 1 hour
        if self.start_datetime and self.end_datetime:
            duration = self.end_datetime - self.start_datetime
            if duration.total_seconds() < 3600:
                raise ValidationError(
                    'Maintenance window must be at least 1 hour.'
                )
    
    def save(self, *args, **kwargs):
        """Ensure validation runs on save."""
        self.full_clean()  # Calls clean() and field validation
        super().save(*args, **kwargs)
```

> **Why This Way?** Django separates validation from saving for flexibility. Some operations (bulk updates, migrations) skip validation intentionally. Calling `full_clean()` in `save()` ensures validation always runs.

#### Natural Keys for Data Portability

Natural keys allow fixture loading and data export without relying on auto-generated primary keys:

```python
class MaintenanceWindowManager(models.Manager):
    """Custom manager with natural key support."""
    
    def get_by_natural_key(self, title, start_datetime_str):
        """
        Retrieve a record using its natural key.
        Called during fixture loading.
        """
        start_datetime = datetime.fromisoformat(start_datetime_str)
        return self.get(title=title, start_datetime=start_datetime)


class MaintenanceWindow(TimeStampedModel):
    title = models.CharField(max_length=200)
    start_datetime = models.DateTimeField()
    
    objects = MaintenanceWindowManager()  # Use custom manager
    
    def natural_key(self):
        """
        Return a tuple that uniquely identifies this record.
        Used during serialization (dumpdata, export).
        """
        return (self.title, self.start_datetime.isoformat())
```

**Why natural keys matter:**

```json
// WITHOUT natural keys (fragile - IDs differ between databases)
{"model": "app.maintenancewindow", "pk": 42, "fields": {...}}

// WITH natural keys (portable - works across databases)
{"model": "app.maintenancewindow", "pk": ["January Maintenance", "2026-01-15T08:00:00"], "fields": {...}}
```

### Class-Based Views in Detail

#### The CBV Inheritance Hierarchy

Django's CBV classes form a hierarchy of increasing specialization:

```
View                          ← Base class, handles dispatch
  │
  └── TemplateView            ← Renders a template with context
        │
        ├── ListView          ← Lists multiple objects
        ├── DetailView        ← Shows one object
        │
        └── FormView          ← Handles form display and processing
              │
              ├── CreateView  ← Form for creating new objects
              ├── UpdateView  ← Form for editing existing objects
              └── DeleteView  ← Confirmation for deleting objects
```

Each level adds functionality:

```python
# View: Minimal base - just dispatch HTTP methods
class View:
    def dispatch(self, request, *args, **kwargs):
        handler = getattr(self, request.method.lower(), self.http_method_not_allowed)
        return handler(request, *args, **kwargs)

# TemplateView: Adds template rendering
class TemplateView(View):
    template_name = None
    def get(self, request):
        context = self.get_context_data()
        return render(request, self.template_name, context)

# ListView: Adds queryset handling and pagination
class ListView(TemplateView):
    model = None
    def get_queryset(self):
        return self.model.objects.all()
    def get_context_data(self):
        context = super().get_context_data()
        context['object_list'] = self.get_queryset()
        return context
```

#### How as_view() Works

URL patterns require callables, but classes aren't callable. The `as_view()` class method creates a wrapper function:

```python
# In urls.py
path('windows/', MaintenanceWindowListView.as_view(), name='list')

# What as_view() does (simplified):
@classmethod
def as_view(cls, **initkwargs):
    def view(request, *args, **kwargs):
        # Create a NEW instance for EACH request
        self = cls(**initkwargs)
        self.request = request
        self.args = args
        self.kwargs = kwargs
        return self.dispatch(request, *args, **kwargs)
    return view
```

**Key insight:** A new view instance is created for every request. This means instance attributes are request-specific and don't persist.

#### Method Override Points

Each CBV provides specific methods to override for customization:

```python
class MaintenanceWindowListView(ListView):
    model = MaintenanceWindow
    
    # ┌─────────────────────────────────────────────────────────────┐
    # │ get_queryset(): Control WHAT objects are available         │
    # └─────────────────────────────────────────────────────────────┘
    def get_queryset(self):
        """Return only upcoming windows for non-admins."""
        qs = super().get_queryset()
        if not self.request.user.is_superuser:
            qs = qs.filter(start_datetime__gte=timezone.now())
        return qs
    
    # ┌─────────────────────────────────────────────────────────────┐
    # │ get_context_data(): Add EXTRA variables to template        │
    # └─────────────────────────────────────────────────────────────┘
    def get_context_data(self, **kwargs):
        """Add summary statistics to context."""
        context = super().get_context_data(**kwargs)
        context['upcoming_count'] = self.get_queryset().filter(
            start_datetime__gt=timezone.now()
        ).count()
        return context


class MaintenanceWindowCreateView(CreateView):
    model = MaintenanceWindow
    fields = ['title', 'description', 'start_datetime', 'end_datetime']
    
    # ┌─────────────────────────────────────────────────────────────┐
    # │ form_valid(): Process the form AFTER validation passes     │
    # └─────────────────────────────────────────────────────────────┘
    def form_valid(self, form):
        """Set created_by before saving."""
        form.instance.created_by = self.request.user
        return super().form_valid(form)
    
    # ┌─────────────────────────────────────────────────────────────┐
    # │ get_success_url(): Where to redirect after success         │
    # └─────────────────────────────────────────────────────────────┘
    def get_success_url(self):
        """Redirect to the detail page of the new window."""
        return reverse('maintenance_window_detail', kwargs={'pk': self.object.pk})


class MaintenanceWindowUpdateView(UpdateView):
    model = MaintenanceWindow
    
    # ┌─────────────────────────────────────────────────────────────┐
    # │ get_object(): Retrieve the specific object to update       │
    # └─────────────────────────────────────────────────────────────┘
    def get_object(self, queryset=None):
        """Only allow editing upcoming windows."""
        obj = super().get_object(queryset)
        if not obj.is_upcoming:
            raise Http404("Cannot edit past maintenance windows.")
        return obj
```

### URL Routing

#### path() Syntax and Converters

The `path()` function maps URL patterns to views:

```python
from django.urls import path, include

urlpatterns = [
    # Static path
    path('maintenance-windows/', views.list_view, name='list'),
    
    # Path with integer parameter
    path('maintenance-windows/<int:pk>/', views.detail_view, name='detail'),
    
    # Path with string parameter
    path('maintenance-windows/<str:slug>/', views.by_slug, name='by_slug'),
    
    # Path with UUID parameter
    path('api/windows/<uuid:id>/', views.api_detail, name='api_detail'),
    
    # Multiple parameters
    path('invoices/<int:year>/<int:month>/', views.invoice, name='invoice'),
]
```

**Available path converters:**

| Converter | Matches | Example |
|-----------|---------|---------|
| `str` | Any non-empty string (excluding `/`) | `hello-world` |
| `int` | Zero or positive integers | `42` |
| `slug` | Letters, numbers, hyphens, underscores | `my-page-2026` |
| `uuid` | UUID format | `550e8400-e29b-41d4-a716-446655440000` |
| `path` | Any non-empty string (including `/`) | `foo/bar/baz` |

#### reverse_lazy for Class Attributes

In class definitions, you can't call `reverse()` because URLs aren't loaded yet. Use `reverse_lazy()`:

```python
from django.urls import reverse_lazy

class MaintenanceWindowCreateView(CreateView):
    model = MaintenanceWindow
    # reverse_lazy evaluates when accessed, not when class is defined
    success_url = reverse_lazy('orcd_direct_charge:maintenance_window_list')
    
    # Alternative: compute in method (called after URLs are loaded)
    def get_success_url(self):
        return reverse('orcd_direct_charge:maintenance_window_detail', 
                       kwargs={'pk': self.object.pk})
```

#### Organizing URLs with include()

Large applications split URLs across files:

```python
# project/urls.py (root)
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('nodes/', include('coldfront_orcd_direct_charge.urls')),
    path('api/', include('coldfront_orcd_direct_charge.api_urls')),
]

# coldfront_orcd_direct_charge/urls.py (app)
app_name = 'orcd_direct_charge'  # Namespace for reversing

urlpatterns = [
    path('maintenance-windows/', views.MaintenanceWindowListView.as_view(), 
         name='maintenance_window_list'),
    # ... more URLs
]
```

With namespace: `{% url 'orcd_direct_charge:maintenance_window_list' %}`

### Templates

#### Template Inheritance with extends and block

Create a base template with replaceable sections:

```html
<!-- templates/coldfront_orcd_direct_charge/base.html -->
{% extends "common/base.html" %}

{% block title %}GPU Node Rentals{% endblock %}

{% block content %}
<div class="container">
    {% block page_header %}{% endblock %}
    
    {% block main_content %}
    <!-- Child templates fill this in -->
    {% endblock %}
</div>
{% endblock %}
```

Child templates extend and override blocks:

```html
<!-- templates/coldfront_orcd_direct_charge/maintenance_window_list.html -->
{% extends "coldfront_orcd_direct_charge/base.html" %}

{% block page_header %}
<h1>Maintenance Windows</h1>
{% endblock %}

{% block main_content %}
<table class="table">
    {% for window in object_list %}
    <tr>
        <td>{{ window.title }}</td>
        <td>{{ window.start_datetime }}</td>
    </tr>
    {% empty %}
    <tr><td colspan="2">No maintenance windows scheduled.</td></tr>
    {% endfor %}
</table>
{% endblock %}
```

#### Common Template Tags

```html
<!-- Loops -->
{% for window in windows %}
    <p>{{ forloop.counter }}. {{ window.title }}</p>
{% empty %}
    <p>No windows found.</p>
{% endfor %}

<!-- Conditionals -->
{% if window.is_upcoming %}
    <span class="badge badge-info">Upcoming</span>
{% elif window.is_in_progress %}
    <span class="badge badge-warning">In Progress</span>
{% else %}
    <span class="badge badge-secondary">Completed</span>
{% endif %}

<!-- URL generation -->
<a href="{% url 'orcd_direct_charge:maintenance_window_update' pk=window.pk %}">
    Edit
</a>

<!-- CSRF token (required in forms) -->
<form method="post">
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit">Save</button>
</form>

<!-- Include partial templates -->
{% include "partials/pagination.html" %}
```

#### Template Filters

```html
<!-- Date formatting -->
{{ window.start_datetime|date:"Y-m-d H:i" }}  <!-- 2026-01-15 08:00 -->
{{ window.start_datetime|timesince }}          <!-- 3 days ago -->

<!-- Number formatting -->
{{ hours|floatformat:2 }}                       <!-- 123.46 -->
{{ amount|intcomma }}                           <!-- 1,234,567 -->

<!-- String manipulation -->
{{ title|truncatewords:5 }}                     <!-- First five words... -->
{{ description|linebreaks }}                    <!-- <p> tags for newlines -->
{{ value|default:"N/A" }}                       <!-- Default if empty -->

<!-- Boolean -->
{{ window.is_upcoming|yesno:"Yes,No,Unknown" }}
```

#### Custom Template Tags

Create reusable template functionality:

```python
# templatetags/maintenance_tags.py
from django import template

register = template.Library()


@register.simple_tag
def maintenance_badge(window):
    """Return HTML badge for window status."""
    if window.is_upcoming:
        return '<span class="badge badge-info">Upcoming</span>'
    elif window.is_in_progress:
        return '<span class="badge badge-warning">In Progress</span>'
    return '<span class="badge badge-secondary">Completed</span>'


@register.filter
def duration_display(window):
    """Format window duration for display."""
    hours = window.duration_hours
    if hours < 24:
        return f"{hours:.1f} hours"
    days = hours / 24
    return f"{days:.1f} days"
```

Usage in templates:

```html
{% load maintenance_tags %}

{{ window|duration_display }}
{% maintenance_badge window %}
```

### Django REST Framework

#### ModelSerializer

Automatically map model fields to JSON:

```python
from rest_framework import serializers

class MaintenanceWindowSerializer(serializers.ModelSerializer):
    """Serialize MaintenanceWindow for API responses."""
    
    class Meta:
        model = MaintenanceWindow
        fields = [
            'id', 'title', 'description', 
            'start_datetime', 'end_datetime',
            'created_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at', 'created_by']
```

#### SerializerMethodField for Computed Values

Add computed fields to API responses:

```python
class MaintenanceWindowSerializer(serializers.ModelSerializer):
    # Computed fields (read-only)
    status = serializers.SerializerMethodField()
    duration_hours = serializers.SerializerMethodField()
    created_by_username = serializers.SerializerMethodField()
    
    class Meta:
        model = MaintenanceWindow
        fields = ['id', 'title', 'status', 'duration_hours', 'created_by_username']
    
    def get_status(self, obj):
        """Return status string from model property."""
        return obj.status
    
    def get_duration_hours(self, obj):
        """Return duration with 2 decimal places."""
        return round(obj.duration_hours, 2)
    
    def get_created_by_username(self, obj):
        """Return username or None."""
        return obj.created_by.username if obj.created_by else None
```

#### ModelViewSet and DefaultRouter

Provide full CRUD API with minimal code:

```python
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

class MaintenanceWindowViewSet(viewsets.ModelViewSet):
    """API endpoint for maintenance windows."""
    queryset = MaintenanceWindow.objects.all()
    serializer_class = MaintenanceWindowSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Allow filtering by status."""
        qs = super().get_queryset()
        status = self.request.query_params.get('status')
        if status == 'upcoming':
            qs = qs.filter(start_datetime__gt=timezone.now())
        return qs
    
    def perform_create(self, serializer):
        """Set created_by on creation."""
        serializer.save(created_by=self.request.user)
```

Register with router for automatic URL generation:

```python
# api_urls.py
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register('maintenance-windows', MaintenanceWindowViewSet)

urlpatterns = router.urls
# Creates: GET/POST /maintenance-windows/
#          GET/PUT/PATCH/DELETE /maintenance-windows/{id}/
```

### Management Commands

#### File Location and Structure

Commands must be in a specific location:

```
app_name/
└── management/
    └── commands/
        ├── __init__.py
        └── create_maintenance_window.py  ← Command name = filename
```

Invoke with: `python manage.py create_maintenance_window`

#### BaseCommand Structure

```python
# management/commands/create_maintenance_window.py
from django.core.management.base import BaseCommand
from coldfront_orcd_direct_charge.models import MaintenanceWindow


class Command(BaseCommand):
    help = 'Create a maintenance window from the command line'
    
    def add_arguments(self, parser):
        """Define command-line arguments."""
        # Positional (required) arguments
        parser.add_argument('title', type=str, help='Window title')
        
        # Optional arguments
        parser.add_argument(
            '--start',
            type=str,
            required=True,
            help='Start datetime (ISO format)'
        )
        parser.add_argument(
            '--end',
            type=str,
            required=True,
            help='End datetime (ISO format)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without saving'
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        title = options['title']
        start = datetime.fromisoformat(options['start'])
        end = datetime.fromisoformat(options['end'])
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(f"Would create: {title} ({start} to {end})")
            return
        
        window = MaintenanceWindow.objects.create(
            title=title,
            start_datetime=start,
            end_datetime=end
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'Created maintenance window: {window}')
        )
```

### Django Admin

#### Registration and ModelAdmin

```python
# admin.py
from django.contrib import admin
from .models import MaintenanceWindow


@admin.register(MaintenanceWindow)
class MaintenanceWindowAdmin(admin.ModelAdmin):
    """Admin interface for maintenance windows."""
    
    # List view configuration
    list_display = ['title', 'start_datetime', 'end_datetime', 'status_display', 'duration']
    list_filter = ['start_datetime', 'created_by']
    search_fields = ['title', 'description']
    ordering = ['-start_datetime']
    
    # Form configuration
    fieldsets = [
        (None, {
            'fields': ['title', 'description']
        }),
        ('Schedule', {
            'fields': ['start_datetime', 'end_datetime']
        }),
        ('Metadata', {
            'fields': ['created_by', 'created_at', 'modified_at'],
            'classes': ['collapse']  # Collapsible section
        }),
    ]
    readonly_fields = ['created_at', 'modified_at']
    
    # Computed display methods
    @admin.display(description='Status')
    def status_display(self, obj):
        """Show status with color coding."""
        return obj.status
    
    @admin.display(description='Duration')
    def duration(self, obj):
        """Format duration for display."""
        return f"{obj.duration_hours:.1f} hours"
```

## 3.2 ColdFront Concepts (Deep Dive)

### Plugin Architecture

#### AppConfig and Initialization

Every Django app has an `apps.py` with configuration:

```python
# coldfront_orcd_direct_charge/apps.py
from django.apps import AppConfig


class ColdFrontOrcdDirectChargeConfig(AppConfig):
    name = 'coldfront_orcd_direct_charge'
    verbose_name = 'ORCD Direct Charge'
    
    def ready(self):
        """
        Called when Django starts up.
        Use for signal registration and initialization.
        """
        # Import signals to register handlers
        from . import signals  # noqa
```

#### Signal Handlers

Signals enable loose coupling between components:

```python
# signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import MaintenanceWindow


@receiver(post_save, sender=MaintenanceWindow)
def window_saved(sender, instance, created, **kwargs):
    """React to window creation or update."""
    if created:
        # Log creation
        log_activity(f"Maintenance window created: {instance.title}")


@receiver(post_delete, sender=MaintenanceWindow)
def window_deleted(sender, instance, **kwargs):
    """React to window deletion."""
    log_activity(f"Maintenance window deleted: {instance.title}")
```

### Permission System

#### Defining Custom Permissions

```python
class MaintenanceWindow(TimeStampedModel):
    # ... fields ...
    
    class Meta:
        permissions = [
            ('can_manage_maintenance_windows', 'Can manage maintenance windows'),
            ('can_view_all_maintenance_windows', 'Can view all maintenance windows'),
        ]
```

#### Permission Naming Convention

Full permission name: `app_label.codename`

Example: `coldfront_orcd_direct_charge.can_manage_maintenance_windows`

#### Checking Permissions

```python
# In views
class MaintenanceWindowListView(PermissionRequiredMixin, ListView):
    permission_required = 'coldfront_orcd_direct_charge.can_manage_rentals'

# In code
if user.has_perm('coldfront_orcd_direct_charge.can_manage_rentals'):
    # Allow action

# In templates
{% if perms.coldfront_orcd_direct_charge.can_manage_rentals %}
    <a href="{% url 'create' %}">Create Window</a>
{% endif %}
```

### Template Overrides

Django searches templates in order. Later apps can override earlier ones:

```python
# settings.py
INSTALLED_APPS = [
    'coldfront.core.portal',           # Original templates
    'coldfront_orcd_direct_charge',    # Can override templates
]
```

To override a template, create a file at the same path:

```
coldfront_orcd_direct_charge/
└── templates/
    └── portal/
        └── navbar.html  ← Overrides coldfront.core.portal's navbar.html
```

## 3.3 Plugin-Specific Patterns (Deep Dive)

### Activity Logging

#### Purpose and Implementation

Activity logging provides an audit trail for compliance and debugging:

```python
# utils/activity_logging.py
from .models import ActivityLog


class ActionCategory:
    """Categories for activity log entries."""
    MAINTENANCE = 'maintenance'
    BILLING = 'billing'
    RESERVATION = 'reservation'


def log_activity(
    user,
    action: str,
    category: str = ActionCategory.MAINTENANCE,
    target_object=None,
    extra_data: dict = None
):
    """
    Create an activity log entry.
    
    Args:
        user: The user performing the action
        action: Description of the action (e.g., "Created maintenance window")
        category: Action category for filtering
        target_object: Optional model instance this action relates to
        extra_data: Optional dict of additional context (stored as JSON)
    """
    ActivityLog.objects.create(
        user=user,
        action=action,
        category=category,
        content_type=ContentType.objects.get_for_model(target_object) if target_object else None,
        object_id=target_object.pk if target_object else None,
        extra_data=extra_data or {}
    )
```

Usage in views:

```python
class MaintenanceWindowCreateView(CreateView):
    def form_valid(self, form):
        response = super().form_valid(form)
        log_activity(
            user=self.request.user,
            action=f"Created maintenance window: {self.object.title}",
            category=ActionCategory.MAINTENANCE,
            target_object=self.object,
            extra_data={
                'start': self.object.start_datetime.isoformat(),
                'end': self.object.end_datetime.isoformat()
            }
        )
        return response
```

### Backup/Export System

#### Registry Pattern

The plugin uses a registry to track exportable/importable models:

```python
# backup/registry.py

class BackupRegistry:
    """Central registry for backup exporters and importers."""
    
    _exporters = {}
    _importers = {}
    
    @classmethod
    def register_exporter(cls, exporter_class):
        """Register an exporter class."""
        cls._exporters[exporter_class.model] = exporter_class
    
    @classmethod
    def register_importer(cls, importer_class):
        """Register an importer class."""
        cls._importers[importer_class.model] = importer_class
    
    @classmethod
    def get_all_exporters(cls):
        """Return all registered exporters."""
        return cls._exporters.values()


# Usage: register at module load time
@BackupRegistry.register_exporter
class MaintenanceWindowExporter(BaseExporter):
    model = MaintenanceWindow
    filename = 'maintenance_windows.json'
```

#### BaseExporter Contract

```python
class BaseExporter:
    """Base class for data exporters."""
    model = None      # Required: the model to export
    filename = None   # Required: output filename
    
    def get_queryset(self):
        """Return queryset of objects to export."""
        return self.model.objects.all()
    
    def serialize(self, obj):
        """Convert object to exportable dict."""
        return {
            'natural_key': obj.natural_key(),
            'title': obj.title,
            'description': obj.description,
            'start_datetime': obj.start_datetime.isoformat(),
            'end_datetime': obj.end_datetime.isoformat(),
        }
```

#### BaseImporter with Conflict Resolution

```python
class BaseImporter:
    """Base class for data importers."""
    model = None
    
    def get_existing(self, data):
        """Find existing record matching this data."""
        try:
            return self.model.objects.get_by_natural_key(*data['natural_key'])
        except self.model.DoesNotExist:
            return None
    
    def import_record(self, data, strategy='skip'):
        """
        Import a single record.
        
        Strategies:
            skip: Skip if exists
            update: Update if exists
            error: Raise error if exists
        """
        existing = self.get_existing(data)
        
        if existing:
            if strategy == 'skip':
                return existing, 'skipped'
            elif strategy == 'update':
                return self.update_record(existing, data), 'updated'
            else:
                raise ValueError(f"Record already exists: {data['natural_key']}")
        
        return self.create_record(data), 'created'
```

### Billing Calculation

#### Invoice Period Structure

```python
class InvoicePeriod:
    """Represents a billing period (year/month)."""
    
    def __init__(self, year: int, month: int):
        self.year = year
        self.month = month
    
    @property
    def start_date(self):
        """First day of the billing period."""
        return date(self.year, self.month, 1)
    
    @property
    def end_date(self):
        """Last day of the billing period."""
        _, last_day = calendar.monthrange(self.year, self.month)
        return date(self.year, self.month, last_day)
    
    @property
    def total_hours(self):
        """Total hours in this billing period."""
        days = (self.end_date - self.start_date).days + 1
        return days * 24
```

#### Day-by-Day Calculation

The billing system calculates hours day-by-day to handle partial periods:

```python
def calculate_billable_hours(reservation, period: InvoicePeriod):
    """
    Calculate billable hours for a reservation in a period.
    
    1. Determine which days the reservation is active
    2. For each active day, calculate hours (usually 24, but may be partial)
    3. Subtract maintenance hours from each day
    4. Sum total billable hours
    """
    total_hours = 0
    
    # Iterate through each day in the billing period
    for day in date_range(period.start_date, period.end_date):
        # Check if reservation is active this day
        if not reservation.is_active_on(day):
            continue
        
        # Calculate hours for this day (24, or partial for start/end days)
        day_hours = get_hours_for_day(reservation, day)
        
        # Subtract maintenance hours
        maintenance_hours = get_maintenance_hours_for_day(day)
        
        billable_hours = max(0, day_hours - maintenance_hours)
        total_hours += billable_hours
    
    return total_hours


def get_maintenance_hours_for_day(day: date) -> float:
    """
    Calculate total maintenance hours for a given day.
    
    Multiple maintenance windows may overlap with a single day.
    """
    day_start = datetime.combine(day, time.min)
    day_end = datetime.combine(day, time.max)
    
    total_maintenance = 0
    windows = MaintenanceWindow.objects.filter(
        start_datetime__lt=day_end,
        end_datetime__gt=day_start
    )
    
    for window in windows:
        # Calculate overlap with this specific day
        overlap_start = max(window.start_datetime, day_start)
        overlap_end = min(window.end_datetime, day_end)
        overlap_hours = (overlap_end - overlap_start).total_seconds() / 3600
        total_maintenance += overlap_hours
    
    return total_maintenance
```

#### Cost Allocation Snapshots

For billing accuracy, cost allocations are snapshotted at billing time:

```python
class CostAllocationSnapshot(models.Model):
    """
    Frozen copy of cost allocation at time of invoice generation.
    
    Why snapshots? If a project changes their cost allocation after
    an invoice is generated, the invoice should still reflect the
    allocation that was active during the billing period.
    """
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    account_code = models.CharField(max_length=50)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)
```

---

> **Summary:** This section covered the key patterns you'll encounter in the maintenance window implementation: Django models with validation and natural keys, class-based views with customization points, URL routing, templates with inheritance and custom tags, Django REST Framework for APIs, management commands for CLI tools, and Django admin for administrative interfaces. We also covered ColdFront's plugin architecture, permission system, and plugin-specific patterns for activity logging, backup/export, and billing calculations.

---

*Continue to [Section 4: TODO Overview and Concept Mapping](#section-4-todo-overview-and-concept-mapping) to see how these concepts map to the concrete implementation tasks.*

---

# Section 4: TODO Overview and Concept Mapping

This section provides a bird's-eye view of the implementation work. Before diving into the detailed walkthroughs in Section 5, you'll see how the 12 TODOs are organized architecturally, which concepts from Sections 2-3 apply to each TODO, how tasks depend on each other, and what files are created or modified.

## 4.1 Architecture Diagram

The maintenance window feature spans all layers of the application. Here's how the 12 TODOs map to a layered architecture:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PRESENTATION LAYER                                 │
│                      (How users interact with the feature)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────┐  ┌──────────────────┐  ┌────────────────────────┐ │
│  │      Web UI          │  │    REST API      │  │         CLI            │ │
│  │                      │  │                  │  │                        │ │
│  │  TODO 3:  Views      │  │  TODO 4:         │  │  TODO 5:               │ │
│  │  TODO 10: Help Text  │  │  Serializers     │  │  Management Commands   │ │
│  │  TODO 11: Edit       │  │  ViewSets        │  │  list, create, delete  │ │
│  │           Restrictions│  │  Permissions     │  │                        │ │
│  └──────────────────────┘  └──────────────────┘  └────────────────────────┘ │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                           BUSINESS LOGIC LAYER                               │
│                    (Core functionality and integrations)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────┐  ┌──────────────────┐  ┌────────────────────────┐ │
│  │   Billing Engine     │  │  Activity Log    │  │    Django Admin        │ │
│  │                      │  │                  │  │                        │ │
│  │  TODO 2:             │  │  TODO 8:         │  │  TODO 7:               │ │
│  │  Overlap calculation │  │  Audit trail     │  │  Admin interface       │ │
│  │  Deduction from      │  │  Create/Update/  │  │  List/filter/edit      │ │
│  │  billable hours      │  │  Delete logging  │  │  (including past)      │ │
│  │                      │  │                  │  │                        │ │
│  │  TODO 9:             │  │                  │  │                        │ │
│  │  Invoice display     │  │                  │  │                        │ │
│  └──────────────────────┘  └──────────────────┘  └────────────────────────┘ │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                             DATA LAYER                                       │
│                    (Persistence and data management)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────┐  ┌──────────────────┐  ┌────────────────────────┐ │
│  │   Model & Schema     │  │  Export/Import   │  │    Documentation       │ │
│  │                      │  │                  │  │                        │ │
│  │  TODO 1:             │  │  TODO 6:         │  │  TODO 12:              │ │
│  │  MaintenanceWindow   │  │  Backup system   │  │  Developer docs        │ │
│  │  model definition    │  │  JSON export     │  │  API reference         │ │
│  │  Database migration  │  │  Import with     │  │  Data model docs       │ │
│  │  Validation rules    │  │  conflict        │  │  README updates        │ │
│  │                      │  │  resolution      │  │                        │ │
│  └──────────────────────┘  └──────────────────┘  └────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Layer Responsibilities:**

| Layer | Purpose | TODOs |
|-------|---------|-------|
| **Presentation** | User-facing interfaces (web, API, CLI) | 3, 4, 5, 10, 11 |
| **Business Logic** | Core calculations, integrations, admin | 2, 7, 8, 9 |
| **Data** | Persistence, portability, documentation | 1, 6, 12 |

## 4.2 Concept-to-TODO Mapping Table

This table shows which Django/ColdFront concepts from Sections 2-3 are applied in each TODO. Use this to quickly find which section covers a concept you want to learn more about.

| Concept (Section Reference) | TODOs | Description |
|-----------------------------|-------|-------------|
| **Models & Fields** (2.8, 3.1) | 1 | MaintenanceWindow model with CharField, DateTimeField, ForeignKey |
| **TimeStampedModel** (3.1) | 1 | Automatic created_at/modified_at fields via inheritance |
| **Model Properties** (3.1) | 1 | Computed is_upcoming, is_in_progress, status properties |
| **clean() Validation** (3.1) | 1 | Business rule: end_datetime must be after start_datetime |
| **Migrations** (2.7, 3.1) | 1 | Database schema creation via makemigrations/migrate |
| **Natural Keys** (3.1) | 1, 6 | Portable data serialization for export/import |
| **Class-Based Views** (2.6, 3.1) | 3, 11 | ListView, CreateView, UpdateView, DeleteView |
| **Mixins** (2.6, 3.1) | 3, 11 | LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin |
| **Template Inheritance** (2.6, 3.1) | 3, 9, 10 | {% extends %}, {% block %} pattern |
| **Template Tags** (3.1) | 3, 9, 10 | {% for %}, {% if %}, {% url %}, custom tags |
| **URL Routing** (2.8, 3.1) | 3, 4 | path(), named URLs, namespace prefixes |
| **ModelSerializer** (3.1) | 4 | Automatic model-to-JSON field mapping |
| **SerializerMethodField** (3.1) | 4 | Computed API fields (status, duration_hours) |
| **ModelViewSet** (3.1) | 4 | Full CRUD API with permissions |
| **DefaultRouter** (3.1) | 4 | Automatic URL generation for ViewSets |
| **Management Commands** (3.1) | 5 | CLI tools via BaseCommand |
| **Dry-Run Pattern** (3.1) | 5 | Safe testing with --dry-run flag |
| **Registry Pattern** (3.3) | 6 | Extensible backup system registration |
| **BaseExporter/Importer** (3.3) | 6 | Standardized export/import interfaces |
| **Django Admin** (3.1) | 7 | @admin.register, ModelAdmin, list_display |
| **Activity Logging** (3.3) | 8 | log_activity() for audit trail |
| **Billing Calculation** (3.3) | 2, 9 | Day-by-day hour calculation with maintenance deduction |
| **Permission Checks** (3.2) | 3, 4, 7, 11 | permission_required, has_perm(), template perms |
| **get_queryset() Override** (3.1) | 3, 4, 11 | Filtering objects based on user or status |

## 4.3 Dependency Graph

The TODOs follow a dependency structure that determines their execution order:

```
                              ┌─────────────────────┐
                              │      TODO 1         │
                              │  Model & Migration  │
                              │    (Foundation)     │
                              └─────────┬───────────┘
                                        │
        ┌───────────────┬───────────────┼───────────────┬───────────────┐
        │               │               │               │               │
        ▼               ▼               ▼               ▼               ▼
┌───────────────┐ ┌───────────┐ ┌───────────────┐ ┌───────────┐ ┌───────────┐
│    TODO 2     │ │  TODO 3   │ │    TODO 4     │ │  TODO 5   │ │  TODO 6   │
│   Billing     │ │  Web UI   │ │   REST API    │ │    CLI    │ │  Export/  │
│ Calculations  │ │           │ │               │ │           │ │  Import   │
└───────┬───────┘ └─────┬─────┘ └───────────────┘ └───────────┘ └───────────┘
        │               │
        │               ├───────────────┐
        │               │               │
        ▼               ▼               ▼
┌───────────────┐ ┌───────────┐ ┌───────────────┐
│    TODO 9     │ │  TODO 8   │ │   TODO 10     │
│   Invoice     │ │ Activity  │ │  Help Text    │
│   Display     │ │  Logging  │ │    System     │
└───────────────┘ └───────────┘ └───────┬───────┘
                                        │
                  ┌─────────────────────┼─────────────────────┐
                  │                     │                     │
                  ▼                     ▼                     ▼
          ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
          │    TODO 7     │     │   TODO 11     │     │   TODO 12     │
          │  Django Admin │     │     Edit      │     │Documentation  │
          │               │     │ Restrictions  │     │ (Depends on   │
          └───────────────┘     └───────────────┘     │     ALL)      │
                                                      └───────────────┘
```

**Dependency Rules:**

| TODO | Depends On | Reason |
|------|------------|--------|
| 1 | None | Foundation—must be first |
| 2 | 1 | Needs model to calculate overlaps |
| 3 | 1 | Needs model to display/edit |
| 4 | 1 | Needs model to serialize |
| 5 | 1 | Needs model to query |
| 6 | 1 | Needs model for export/import |
| 7 | 1 | Needs model to register in admin |
| 8 | 3 | Logs activity from web UI views |
| 9 | 2 | Displays billing deductions |
| 10 | 3 | Adds help to web UI |
| 11 | 3 | Modifies web UI edit behavior |
| 12 | All | Documents the completed feature |

**Parallelization Opportunities:**

After TODO 1 completes, TODOs 2-7 can theoretically run in parallel—they all depend only on the model. In practice, sequential execution ensures each task has full context of prior work.

## 4.4 File Organization Preview

The maintenance window feature creates and modifies files across the plugin's directory structure. Here's what changes in each category:

### Files Created

```
coldfront_orcd_direct_charge/
│
├── models/
│   └── maintenance_window.py          # TODO 1: Model definition
│
├── migrations/
│   └── NNNN_add_maintenance_window.py # TODO 1: Database migration
│
├── views/
│   └── maintenance_window.py          # TODO 3: Web UI views
│
├── templates/coldfront_orcd_direct_charge/
│   ├── maintenance_window_list.html   # TODO 3: List template
│   ├── maintenance_window_form.html   # TODO 3: Create/edit form
│   ├── maintenance_window_confirm_delete.html  # TODO 3: Delete confirmation
│   └── help/
│       └── maintenance_windows.md     # TODO 10: Help content
│
├── serializers/
│   └── maintenance_window.py          # TODO 4: API serializer
│
├── management/commands/
│   ├── list_maintenance_windows.py    # TODO 5: CLI list command
│   ├── create_maintenance_window.py   # TODO 5: CLI create command
│   └── delete_maintenance_window.py   # TODO 5: CLI delete command
│
├── backup/
│   ├── exporters/
│   │   └── maintenance_window.py      # TODO 6: Exporter class
│   └── importers/
│       └── maintenance_window.py      # TODO 6: Importer class
│
└── docs/
    └── maintenance-windows.md         # TODO 12: Feature documentation
```

### Files Modified

```
coldfront_orcd_direct_charge/
│
├── models/__init__.py                 # TODO 1: Export new model
│
├── urls.py                            # TODO 3: Add web UI routes
│
├── api_urls.py                        # TODO 4: Register API ViewSet
│
├── admin.py                           # TODO 7: Register admin interface
│
├── utils/billing.py                   # TODO 2: Add maintenance deduction
│
├── templates/coldfront_orcd_direct_charge/
│   ├── invoice_detail.html            # TODO 9: Show maintenance deduction
│   └── partials/navbar.html           # TODO 3: Add nav link
│
├── backup/registry.py                 # TODO 6: Register exporter/importer
│
└── docs/
    ├── data-models.md                 # TODO 12: Document new model
    ├── api-reference.md               # TODO 12: Document API endpoints
    └── README.md                       # TODO 12: Update feature list
```

### File Count Summary

| Category | New Files | Modified Files |
|----------|-----------|----------------|
| Models/Migrations | 2 | 1 |
| Views | 1 | 0 |
| Templates | 4+ | 2 |
| Serializers | 1 | 0 |
| Management Commands | 3 | 0 |
| Backup (Export/Import) | 2 | 1 |
| Admin | 0 | 1 |
| Documentation | 1 | 3 |
| URLs | 0 | 2 |
| Billing | 0 | 1 |
| **Total** | **14+** | **11** |

---

> **Summary:** This section provided a high-level map of the implementation work. The 12 TODOs span all layers of the application—from the data model at the foundation, through business logic for billing and logging, to presentation layer interfaces (web, API, CLI). Section 5 walks through each TODO in detail, explaining the code and design decisions.

---

*Continue to [Section 5: Detailed TODO Walkthroughs](#section-5-detailed-todo-walkthroughs) for step-by-step implementation details of each task.*

---

# Section 5: Detailed TODO Walkthroughs

This section provides a deep dive into each TODO from the implementation plan. For each task, we examine the objective, prerequisites, concepts applied, files modified, step-by-step implementation, pattern parallels for developers coming from other frameworks, design decisions, and verification steps.

## 5.1 TODO 1: Create MaintenanceWindow Model and Migration

This is the foundational TODO—everything else depends on having the MaintenanceWindow model in place. No database table, no feature. This task creates the core data structure that represents a scheduled maintenance period.

### 5.1.1 Objective

Create the `MaintenanceWindow` database model that stores information about scheduled maintenance periods during which node rentals should not be billed. This model must:

- Store the maintenance period's start and end times
- Track who created the maintenance window and when
- Provide computed properties for display and business logic (duration, status)
- Validate that the end time comes after the start time
- Generate the database migration for schema creation

### 5.1.2 Prerequisites

**None.** This is the foundation TODO—it must be completed first before any other TODOs can proceed. The model is the core data structure upon which all other components (views, API, billing, etc.) depend.

### 5.1.3 Concepts Applied

This TODO applies several key concepts from Section 3:

| Concept | Section Reference | Application |
|---------|-------------------|-------------|
| **TimeStampedModel** | 3.1 (Models) | Inherit automatic `created` and `modified` timestamp fields |
| **ForeignKey** | 3.1 (Model Fields) | Link to User model for `created_by` tracking |
| **Model Properties** | 3.1 (Model Properties) | Computed `duration_hours`, `is_upcoming`, `is_in_progress`, `is_completed` |
| **clean() Validation** | 3.1 (Model Validation) | Business rule enforcement: end must be after start |
| **Meta Options** | 3.1 (Model Meta) | Default ordering, verbose names |
| **Migrations** | 2.7, 3.1 | Automatic schema generation via `makemigrations` |

### 5.1.4 Files Modified

| File | Action | Purpose |
|------|--------|---------|
| `models.py` | **Modified** | Add `MaintenanceWindow` class definition |
| `migrations/NNNN_maintenancewindow.py` | **Created** | Database schema migration (auto-generated) |

### 5.1.5 Step-by-Step Implementation

#### The Complete MaintenanceWindow Model

Here is the complete model as implemented in the codebase:

```python
class MaintenanceWindow(TimeStampedModel):
    """Scheduled maintenance period during which rentals are not billed.

    Maintenance windows define time periods when nodes are unavailable for use.
    Any rental time that overlaps with a maintenance window will not be charged.
    This allows researchers to extend rentals through maintenance periods without
    incurring costs for time when nodes cannot be used.

    Attributes:
        start_datetime (datetime): When the maintenance period begins
        end_datetime (datetime): When the maintenance period ends
        title (str): Short title describing the maintenance
        description (str): Optional detailed description
        created_by (User): Rental manager who created this window
    """

    start_datetime = models.DateTimeField(
        help_text="When the maintenance period begins"
    )
    end_datetime = models.DateTimeField(
        help_text="When the maintenance period ends"
    )
    title = models.CharField(
        max_length=200,
        help_text="Short title describing the maintenance"
    )
    description = models.TextField(
        blank=True,
        help_text="Optional detailed description of the maintenance"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_maintenance_windows",
        help_text="Rental manager who created this window"
    )

    class Meta:
        ordering = ["-start_datetime"]
        verbose_name = "Maintenance Window"
        verbose_name_plural = "Maintenance Windows"

    def __str__(self):
        return f"{self.title} ({self.start_datetime.strftime('%Y-%m-%d %H:%M')} - {self.end_datetime.strftime('%Y-%m-%d %H:%M')})"

    @property
    def duration_hours(self):
        """Returns the duration of the maintenance window in hours."""
        delta = self.end_datetime - self.start_datetime
        return delta.total_seconds() / 3600

    @property
    def is_upcoming(self):
        """Returns True if the maintenance window hasn't started yet."""
        from django.utils import timezone
        return self.start_datetime > timezone.now()

    @property
    def is_in_progress(self):
        """Returns True if the maintenance window is currently active."""
        from django.utils import timezone
        now = timezone.now()
        return self.start_datetime <= now < self.end_datetime

    @property
    def is_completed(self):
        """Returns True if the maintenance window has ended."""
        from django.utils import timezone
        return self.end_datetime <= timezone.now()

    def clean(self):
        """Validate that end_datetime is after start_datetime."""
        from django.core.exceptions import ValidationError
        if self.end_datetime and self.start_datetime:
            if self.end_datetime <= self.start_datetime:
                raise ValidationError({
                    'end_datetime': 'End datetime must be after start datetime.'
                })
```

#### Field-by-Field Explanation

**1. Inheriting from TimeStampedModel**

```python
class MaintenanceWindow(TimeStampedModel):
```

By inheriting from `TimeStampedModel` (from the `django-model-utils` package), we automatically get two fields:
- `created`: Auto-set to the current timestamp when the record is first saved
- `modified`: Auto-updated to the current timestamp on every save

This is a common pattern in Django applications—rather than manually adding these fields to every model, you inherit from a base class that provides them. It ensures consistent naming and behavior across all models.

**2. DateTimeField for Temporal Boundaries**

```python
start_datetime = models.DateTimeField(
    help_text="When the maintenance period begins"
)
end_datetime = models.DateTimeField(
    help_text="When the maintenance period ends"
)
```

We use `DateTimeField` rather than `DateField` because maintenance windows need precise timing—a maintenance period might run from "February 15 at 8:00 AM" to "February 15 at 8:00 PM" (12 hours), not just "all of February 15" (24 hours).

The `help_text` parameter provides documentation that appears in Django admin and can be used by API documentation generators.

**3. CharField with max_length for Title**

```python
title = models.CharField(
    max_length=200,
    help_text="Short title describing the maintenance"
)
```

`CharField` requires a `max_length` parameter—Django uses this to create a `VARCHAR(200)` column in the database. We chose 200 characters as a reasonable limit for titles like "Scheduled System Maintenance" or "Emergency Security Patch".

**4. TextField for Optional Description**

```python
description = models.TextField(
    blank=True,
    help_text="Optional detailed description of the maintenance"
)
```

`TextField` has no length limit (stored as `TEXT` in most databases). The `blank=True` parameter means this field is optional in forms—users don't have to provide a description.

**5. ForeignKey with SET_NULL**

```python
created_by = models.ForeignKey(
    User,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="created_maintenance_windows",
    help_text="Rental manager who created this window"
)
```

This is the most complex field. Let's break it down:

| Parameter | Value | Purpose |
|-----------|-------|---------|
| First argument | `User` | Links to Django's built-in User model |
| `on_delete` | `models.SET_NULL` | If the user is deleted, set this field to NULL (preserve the maintenance window) |
| `null=True` | | Allow NULL values in the database column |
| `blank=True` | | Allow empty values in forms |
| `related_name` | `"created_maintenance_windows"` | Enables `user.created_maintenance_windows.all()` reverse lookup |

The `on_delete` choice is critical. We use `SET_NULL` rather than `CASCADE` because:
- `CASCADE` would delete all maintenance windows when a user is deleted
- We want to preserve the maintenance window records even if the creating user leaves the organization
- `SET_NULL` preserves the record but loses the creator reference (acceptable for audit purposes)

#### Property Methods Explained

**1. duration_hours Property**

```python
@property
def duration_hours(self):
    """Returns the duration of the maintenance window in hours."""
    delta = self.end_datetime - self.start_datetime
    return delta.total_seconds() / 3600
```

This is a computed property—it doesn't store a value in the database but calculates it on demand. The calculation:
1. Subtract start from end to get a `timedelta` object
2. Convert to total seconds using `.total_seconds()`
3. Divide by 3600 (seconds per hour) to get hours

Using a property keeps the data normalized (we don't store duration separately) while providing a convenient accessor. In templates, you use it like `{{ window.duration_hours }}`.

**2. Status Properties**

```python
@property
def is_upcoming(self):
    """Returns True if the maintenance window hasn't started yet."""
    from django.utils import timezone
    return self.start_datetime > timezone.now()

@property
def is_in_progress(self):
    """Returns True if the maintenance window is currently active."""
    from django.utils import timezone
    now = timezone.now()
    return self.start_datetime <= now < self.end_datetime

@property
def is_completed(self):
    """Returns True if the maintenance window has ended."""
    from django.utils import timezone
    return self.end_datetime <= timezone.now()
```

These three properties provide mutually exclusive states for any maintenance window:

| State | Condition | Use Case |
|-------|-----------|----------|
| `is_upcoming` | `start > now` | Can edit/delete; show "Upcoming" badge |
| `is_in_progress` | `start <= now < end` | Cannot modify; show "In Progress" badge |
| `is_completed` | `end <= now` | Cannot modify; show "Completed" badge |

The imports are inside the methods to avoid circular import issues—this is a common Django pattern when a model needs to reference `timezone` from `django.utils`.

**Why Three Separate Properties Instead of One Status Method?**

We could have used a single `status` property returning a string:

```python
@property
def status(self):
    if self.is_completed:
        return "completed"
    elif self.is_in_progress:
        return "in_progress"
    else:
        return "upcoming"
```

Instead, we provide individual boolean properties because:
1. **Template readability**: `{% if window.is_upcoming %}` is clearer than `{% if window.status == "upcoming" %}`
2. **Query filtering**: You can't easily filter by a property, but the individual conditions are simple to translate to QuerySet filters
3. **Explicit intent**: Each property's name clearly states what it checks

#### The clean() Validation Method

```python
def clean(self):
    """Validate that end_datetime is after start_datetime."""
    from django.core.exceptions import ValidationError
    if self.end_datetime and self.start_datetime:
        if self.end_datetime <= self.start_datetime:
            raise ValidationError({
                'end_datetime': 'End datetime must be after start datetime.'
            })
```

The `clean()` method is Django's hook for model-level validation. It's called automatically by `ModelForm.is_valid()` and can be called explicitly via `model_instance.full_clean()`.

Key points:
- We check that both fields exist before comparing (avoids errors if one is None)
- The error is a dictionary mapping field name to error message—this allows the form to display the error next to the correct field
- We use `<=` not just `<` because a zero-duration maintenance window is meaningless

**When clean() Is Called:**
- Automatically by `ModelForm` when validating form data
- By `full_clean()` if called explicitly
- **NOT** by `model.save()` alone—this is a common Django gotcha

If you're saving directly without a form:

```python
# This will NOT call clean()
window = MaintenanceWindow(start_datetime=end, end_datetime=start)
window.save()  # Invalid data saved!

# This WILL call clean()
window = MaintenanceWindow(start_datetime=end, end_datetime=start)
window.full_clean()  # Raises ValidationError
window.save()
```

#### The Meta Class

```python
class Meta:
    ordering = ["-start_datetime"]
    verbose_name = "Maintenance Window"
    verbose_name_plural = "Maintenance Windows"
```

The `Meta` inner class configures model-level options:

| Option | Value | Effect |
|--------|-------|--------|
| `ordering` | `["-start_datetime"]` | Default query order: newest first (the `-` means descending) |
| `verbose_name` | `"Maintenance Window"` | Human-readable singular name for admin |
| `verbose_name_plural` | `"Maintenance Windows"` | Human-readable plural name for admin |

The `ordering` default means `MaintenanceWindow.objects.all()` returns windows sorted by start date, newest first. This is overridable with `.order_by()`.

#### The __str__ Method

```python
def __str__(self):
    return f"{self.title} ({self.start_datetime.strftime('%Y-%m-%d %H:%M')} - {self.end_datetime.strftime('%Y-%m-%d %H:%M')})"
```

This method defines how the object appears when converted to a string—in admin dropdowns, log messages, the Python shell, etc. We include both the title and the time range for quick identification.

### 5.1.6 Pattern Parallels

#### In Ruby on Rails

Rails developers would recognize this as a standard ActiveRecord model:

```ruby
# app/models/maintenance_window.rb
class MaintenanceWindow < ApplicationRecord
  # Associations
  belongs_to :created_by, class_name: 'User', optional: true
  
  # Validations
  validates :title, presence: true, length: { maximum: 200 }
  validates :start_datetime, :end_datetime, presence: true
  validate :end_must_be_after_start
  
  # Scopes for ordering
  default_scope { order(start_datetime: :desc) }
  
  # Computed attributes (similar to @property)
  def duration_hours
    (end_datetime - start_datetime) / 1.hour
  end
  
  def upcoming?
    start_datetime > Time.current
  end
  
  def in_progress?
    start_datetime <= Time.current && Time.current < end_datetime
  end
  
  def completed?
    end_datetime <= Time.current
  end
  
  private
  
  def end_must_be_after_start
    if end_datetime.present? && start_datetime.present? && end_datetime <= start_datetime
      errors.add(:end_datetime, 'must be after start datetime')
    end
  end
end

# Migration: db/migrate/XXXXXX_create_maintenance_windows.rb
class CreateMaintenanceWindows < ActiveRecord::Migration[7.0]
  def change
    create_table :maintenance_windows do |t|
      t.datetime :start_datetime, null: false
      t.datetime :end_datetime, null: false
      t.string :title, limit: 200, null: false
      t.text :description
      t.references :created_by, foreign_key: { to_table: :users }, null: true
      
      t.timestamps  # Similar to TimeStampedModel
    end
    
    add_index :maintenance_windows, :start_datetime
  end
end
```

**Key Differences:**
- Rails uses `belongs_to` instead of `ForeignKey`
- Rails `optional: true` is Django's `null=True, blank=True`
- Rails validations are declarative; Django uses `clean()` for cross-field validation
- Rails `?` suffix convention (e.g., `upcoming?`) vs Django's `is_` prefix (e.g., `is_upcoming`)
- Rails migrations are explicit; Django auto-generates them from model changes

#### In Java/JPA (Spring Boot)

Java developers using JPA would write:

```java
// entity/MaintenanceWindow.java
@Entity
@Table(name = "maintenance_windows")
public class MaintenanceWindow {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(nullable = false)
    private LocalDateTime startDatetime;
    
    @Column(nullable = false)
    private LocalDateTime endDatetime;
    
    @Column(length = 200, nullable = false)
    private String title;
    
    @Column(columnDefinition = "TEXT")
    private String description;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "created_by_id")
    private User createdBy;
    
    // Automatic timestamps (similar to TimeStampedModel)
    @CreationTimestamp
    private LocalDateTime created;
    
    @UpdateTimestamp
    private LocalDateTime modified;
    
    // Computed property (transient = not stored in DB)
    @Transient
    public double getDurationHours() {
        return Duration.between(startDatetime, endDatetime).toHours();
    }
    
    @Transient
    public boolean isUpcoming() {
        return startDatetime.isAfter(LocalDateTime.now());
    }
    
    @Transient
    public boolean isInProgress() {
        LocalDateTime now = LocalDateTime.now();
        return !startDatetime.isAfter(now) && endDatetime.isAfter(now);
    }
    
    @Transient
    public boolean isCompleted() {
        return !endDatetime.isAfter(LocalDateTime.now());
    }
    
    // Validation (called before persist)
    @PrePersist
    @PreUpdate
    private void validate() {
        if (endDatetime != null && startDatetime != null) {
            if (!endDatetime.isAfter(startDatetime)) {
                throw new IllegalStateException("End datetime must be after start datetime");
            }
        }
    }
    
    // toString equivalent of __str__
    @Override
    public String toString() {
        DateTimeFormatter fmt = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");
        return String.format("%s (%s - %s)", title, 
            startDatetime.format(fmt), endDatetime.format(fmt));
    }
    
    // Getters and setters omitted for brevity
}
```

**Key Differences:**
- JPA uses annotations (`@Entity`, `@Column`) vs Django's declarative fields
- JPA `@ManyToOne` is Django's `ForeignKey`
- JPA `@Transient` marks computed properties; Django uses `@property`
- JPA `@PrePersist`/`@PreUpdate` lifecycle hooks vs Django's `clean()`
- JPA requires explicit getters/setters; Python properties are simpler
- Hibernate auto-generates migrations differently than Django's `makemigrations`

### 5.1.7 Design Decisions

#### Why Naive Datetimes (Matching Reservation Pattern)

The `MaintenanceWindow` model uses naive datetimes (no explicit timezone specification), matching the existing `Reservation` model pattern:

```python
# From Reservation model
start_date = models.DateField(
    help_text="Reservation starts at 4:00 PM on this date"
)

@property
def start_datetime(self):
    """Returns the start datetime (4:00 PM on start_date)."""
    return datetime.combine(self.start_date, time(self.START_HOUR, 0))
```

**Why this approach:**

1. **Consistency**: Billing calculations compare `MaintenanceWindow` times with `Reservation` times. Using the same datetime semantics avoids timezone conversion bugs.

2. **Simplicity**: The rental system operates within a single institution's timezone. All times are implicitly in the server's local timezone.

3. **Existing Pattern**: The `Reservation` model already uses naive datetimes. Introducing timezone-aware datetimes just for `MaintenanceWindow` would create comparison issues.

**Trade-off Acknowledged**: If the system ever needs to handle multiple timezones (e.g., a multi-region deployment), both models would need to migrate to timezone-aware datetimes.

#### Why SET_NULL for created_by

```python
created_by = models.ForeignKey(
    User,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    ...
)
```

We chose `SET_NULL` over other `on_delete` options:

| Option | Effect | Why Not Used |
|--------|--------|--------------|
| `CASCADE` | Delete maintenance window when user is deleted | Loses billing-critical data |
| `PROTECT` | Prevent user deletion if they created windows | Too restrictive for user management |
| `SET_DEFAULT` | Set to a default user | Misleading—implies someone else created it |
| `SET_NULL` | ✅ Set to NULL | Preserves window, acknowledges unknown creator |

The `created_by` field is for audit/informational purposes only—it doesn't affect billing calculations. Losing the creator reference when a user leaves is acceptable.

#### Why These Specific Properties

The three status properties (`is_upcoming`, `is_in_progress`, `is_completed`) were designed around specific UI and business logic requirements:

| Property | UI Usage | Business Logic Usage |
|----------|----------|---------------------|
| `is_upcoming` | Show "Upcoming" badge; enable Edit/Delete buttons | Allow modifications via web UI |
| `is_in_progress` | Show "In Progress" badge; disable modifications | Prevent changes during active maintenance |
| `is_completed` | Show "Completed" badge; disable modifications | Lock historical records for billing accuracy |

The `duration_hours` property was added because:
- Displayed in the maintenance window list table
- Used in billing deduction displays
- Avoids template-level arithmetic

### 5.1.8 Verification

After implementing the model, verify it works correctly:

#### 1. Check for Syntax Errors

```bash
cd /Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental
python -c "from coldfront_orcd_direct_charge.models import MaintenanceWindow; print('Import successful')"
```

Expected output: `Import successful`

#### 2. Generate the Migration

```bash
python -m django makemigrations coldfront_orcd_direct_charge --name maintenancewindow
```

Expected: A new migration file created in `migrations/` directory.

#### 3. Review the Migration

Check the generated migration file to verify:
- All fields are present (`start_datetime`, `end_datetime`, `title`, `description`, `created_by`)
- The foreign key references the User model correctly
- Field types match your intentions (`DateTimeField`, `CharField`, `TextField`)

#### 4. Apply the Migration (Development Only)

```bash
python -m django migrate coldfront_orcd_direct_charge
```

#### 5. Test in Django Shell

```python
from django.utils import timezone
from datetime import timedelta
from coldfront_orcd_direct_charge.models import MaintenanceWindow

# Create a test window
window = MaintenanceWindow(
    title="Test Maintenance",
    start_datetime=timezone.now() + timedelta(days=1),
    end_datetime=timezone.now() + timedelta(days=1, hours=4),
)

# Test properties
print(f"Duration: {window.duration_hours} hours")  # Should print 4.0
print(f"Upcoming: {window.is_upcoming}")  # Should print True
print(f"In Progress: {window.is_in_progress}")  # Should print False
print(f"Completed: {window.is_completed}")  # Should print False

# Test validation
window.full_clean()  # Should pass

# Test invalid data
bad_window = MaintenanceWindow(
    title="Bad Window",
    start_datetime=timezone.now(),
    end_datetime=timezone.now() - timedelta(hours=1),  # End before start!
)
try:
    bad_window.full_clean()
except Exception as e:
    print(f"Validation error (expected): {e}")
```

#### 6. Verify __str__ Output

```python
print(window)
# Output: "Test Maintenance (2026-02-01 12:00 - 2026-02-01 16:00)"
```

---

> **Summary:** TODO 1 establishes the data foundation for the entire maintenance window feature. The `MaintenanceWindow` model stores temporal boundaries, descriptive metadata, and creator information. Computed properties provide status checks and duration calculations. The `clean()` method enforces the business rule that maintenance periods must have positive duration. With this model in place, all subsequent TODOs can build upon it.

---

*Continue to [5.2 TODO 2: Update Billing Calculations](#52-todo-2-update-billing-calculations) for the integration with the billing system.*

---

## 5.2 TODO 2: Update Billing Calculations

With the `MaintenanceWindow` model in place, the next critical step is integrating it into the billing system. This is where the feature delivers its core value—automatically deducting maintenance hours from billable time. This TODO modifies the existing billing calculation logic to query maintenance windows and subtract any overlap from reservation hours.

### 5.2.1 Objective

Modify the billing calculation logic in `views/billing.py` to:

- Query the `MaintenanceWindow` model for overlapping maintenance periods
- Calculate the exact hours of overlap between maintenance windows and reservation periods
- Deduct maintenance hours from billable time on a day-by-day basis
- Track maintenance deductions at the invoice line level for transparency
- Ensure the deduction calculation handles edge cases (partial overlaps, multiple windows, timezone considerations)

The goal is seamless integration—invoices should automatically reflect reduced hours when maintenance windows exist, without requiring manual adjustments.

### 5.2.2 Prerequisites

| Prerequisite | Reason |
|--------------|--------|
| **TODO 1 completed** | The `MaintenanceWindow` model must exist for querying |
| Understanding of existing billing flow | Modifications integrate with existing calculation methods |

The billing system already calculates hours on a day-by-day basis using the `_get_hours_for_day()` method. Our modifications hook into this existing flow rather than replacing it.

### 5.2.3 Concepts Applied

This TODO applies several key concepts from Section 3:

| Concept | Section Reference | Application |
|---------|-------------------|-------------|
| **QuerySet Filtering** | 3.1 (QuerySets) | Find maintenance windows that overlap with a time period using `filter()` |
| **Datetime Arithmetic** | 3.1 (DateTime handling) | Calculate overlaps using `max()`, `min()`, and `timedelta` operations |
| **Method Composition** | 3.2 (Views) | New helper methods compose with existing billing methods |
| **Timezone Awareness** | 3.1 (DateTime handling) | Handle timezone-aware vs naive datetime comparisons |

### 5.2.4 Files Modified

| File | Action | Purpose |
|------|--------|---------|
| `views/billing.py` | **Modified** | Add maintenance deduction methods and integrate with existing calculations |

### 5.2.5 Step-by-Step Implementation

#### Understanding the Existing Billing Flow

Before modifying the billing system, it's essential to understand how it currently works. The `InvoiceDetailView` class calculates billable hours for reservations on a monthly basis using this flow:

```
InvoiceDetailView.get_context_data()
    │
    ├── For each reservation overlapping the month:
    │   │
    │   ├── _calculate_hours_for_month(reservation, year, month)
    │   │       └── Returns total hours clipped to month boundaries
    │   │
    │   └── _calculate_cost_breakdown(reservation, year, month, hours)
    │           │
    │           └── For each day in the month:
    │               └── _get_hours_for_day(reservation, date, year, month)
    │                       └── Returns hours for that specific day
    │
    └── Build invoice_lines list with hours and cost breakdowns
```

The key insight is that **billing is calculated day-by-day**. The `_calculate_cost_breakdown()` method iterates through each day of a reservation (within a billing month) and calls `_get_hours_for_day()` to get hours for that day. This day-by-day approach exists because cost allocation snapshots can change mid-month—each day might use a different percentage split.

Our modifications leverage this existing structure. Rather than adding a separate maintenance deduction step, we modify `_get_hours_for_day()` to return hours *after* deducting any maintenance overlap for that day.

#### Method 1: _get_maintenance_hours_for_period()

This is the core overlap calculation method. Given a time period, it finds all maintenance windows that overlap and calculates the total overlapping hours.

```582:622:cf-orcd-rental/coldfront_orcd_direct_charge/views/billing.py
    def _get_maintenance_hours_for_period(self, start_dt, end_dt):
        """Calculate total maintenance hours overlapping a time period.
        
        Args:
            start_dt: Period start datetime (naive)
            end_dt: Period end datetime (naive)
            
        Returns:
            float: Total hours of maintenance window overlap
        """
        from coldfront_orcd_direct_charge.models import MaintenanceWindow
        
        # Find all maintenance windows that overlap with this period
        # Note: MaintenanceWindow uses timezone-aware datetimes, but we compare with naive
        # datetimes from Reservation. We need to handle this carefully.
        windows = MaintenanceWindow.objects.filter(
            start_datetime__lt=end_dt,
            end_datetime__gt=start_dt
        )
        
        total_hours = 0
        for window in windows:
            # Convert maintenance window times to naive for comparison
            # (assuming they're stored in the same timezone as reservations)
            window_start = window.start_datetime
            window_end = window.end_datetime
            
            # Make naive if timezone-aware
            if hasattr(window_start, 'tzinfo') and window_start.tzinfo is not None:
                window_start = window_start.replace(tzinfo=None)
            if hasattr(window_end, 'tzinfo') and window_end.tzinfo is not None:
                window_end = window_end.replace(tzinfo=None)
            
            # Calculate the overlap
            overlap_start = max(window_start, start_dt)
            overlap_end = min(window_end, end_dt)
            if overlap_end > overlap_start:
                delta = overlap_end - overlap_start
                total_hours += delta.total_seconds() / 3600
        
        return total_hours
```

**Line-by-Line Explanation:**

**The QuerySet Filter (lines 597-600):**

```python
windows = MaintenanceWindow.objects.filter(
    start_datetime__lt=end_dt,
    end_datetime__gt=start_dt
)
```

This query finds all maintenance windows that overlap with the given period. The logic is:
- A window overlaps if it starts *before* the period ends (`start_datetime__lt=end_dt`)
- AND ends *after* the period starts (`end_datetime__gt=start_dt`)

This handles all overlap scenarios—windows that completely contain the period, windows completely within the period, and partial overlaps on either end.

**Timezone Handling (lines 603-613):**

```python
window_start = window.start_datetime
window_end = window.end_datetime

# Make naive if timezone-aware
if hasattr(window_start, 'tzinfo') and window_start.tzinfo is not None:
    window_start = window_start.replace(tzinfo=None)
if hasattr(window_end, 'tzinfo') and window_end.tzinfo is not None:
    window_end = window_end.replace(tzinfo=None)
```

The `Reservation` model uses naive datetimes (no timezone info), but `MaintenanceWindow` datetimes might be timezone-aware depending on Django settings. We strip the timezone to enable comparison. This is a pragmatic choice—the system operates in a single timezone, so the comparison is valid.

**The Overlap Calculation (lines 615-620):**

```python
overlap_start = max(window_start, start_dt)
overlap_end = min(window_end, end_dt)
if overlap_end > overlap_start:
    delta = overlap_end - overlap_start
    total_hours += delta.total_seconds() / 3600
```

This is the classic interval overlap algorithm:
1. The overlap starts at whichever comes later: the window start or the period start
2. The overlap ends at whichever comes earlier: the window end or the period end
3. If the calculated overlap end is after the overlap start, there's a positive overlap
4. Convert the overlap duration to hours

#### Method 2: _get_hours_for_day() (Modified)

The existing `_get_hours_for_day()` method calculated raw hours for a specific day. We modified it to also deduct maintenance hours:

```651:672:cf-orcd-rental/coldfront_orcd_direct_charge/views/billing.py
    def _get_hours_for_day(self, reservation, target_date, year, month):
        """Calculate hours for a specific day of a reservation, excluding maintenance windows."""
        # Define the day boundaries (naive datetimes to match Reservation)
        day_start = datetime.combine(target_date, time(0, 0))
        day_end = datetime.combine(target_date + timedelta(days=1), time(0, 0))

        # Clip to reservation boundaries (all naive datetimes)
        effective_start = max(reservation.start_datetime, day_start)
        effective_end = min(reservation.end_datetime, day_end)

        if effective_end <= effective_start:
            return 0

        delta = effective_end - effective_start
        raw_hours = delta.total_seconds() / 3600
        
        # Subtract any maintenance window overlap
        maintenance_hours = self._get_maintenance_hours_for_period(
            effective_start, effective_end
        )
        
        return max(0, raw_hours - maintenance_hours)
```

**The Modification:**

The original method returned `raw_hours` directly. The modification adds three lines:

```python
# Subtract any maintenance window overlap
maintenance_hours = self._get_maintenance_hours_for_period(
    effective_start, effective_end
)

return max(0, raw_hours - maintenance_hours)
```

We call `_get_maintenance_hours_for_period()` with the effective start and end times for this day (already clipped to both day and reservation boundaries). The result is subtracted from raw hours.

The `max(0, ...)` ensures we never return negative hours—a safety check in case of floating-point precision issues.

**Why Modify _get_hours_for_day() Instead of a Higher-Level Method?**

The day-by-day approach ensures maintenance deductions are correctly attributed to the right cost allocation period. Consider this scenario:

- Reservation: Feb 10-20 (10 days)
- Cost allocation changes Feb 15: 100% Dept A → 50% Dept A, 50% Dept B
- Maintenance window: Feb 14-16 (spanning the cost allocation change)

By calculating maintenance at the day level:
- Feb 14: 24 hours deducted from Dept A (100%)
- Feb 15: 24 hours deducted from Dept A (50%) and Dept B (50%)
- Feb 16: 24 hours deducted from Dept A (50%) and Dept B (50%)

If we calculated maintenance at a higher level, we couldn't correctly split the deduction across cost allocation changes.

#### Method 3: _get_maintenance_deduction_for_reservation()

For display purposes on the invoice, we also need to show the total maintenance deduction for each reservation in the billing month. This method provides that rollup:

```624:649:cf-orcd-rental/coldfront_orcd_direct_charge/views/billing.py
    def _get_maintenance_deduction_for_reservation(self, reservation, year, month):
        """Calculate total maintenance hours for a reservation in a given month.
        
        Args:
            reservation: The Reservation object
            year: Invoice year
            month: Invoice month
            
        Returns:
            float: Total hours of maintenance window overlap for this reservation in this month
        """
        # Get month boundaries
        month_start = datetime.combine(date(year, month, 1), time(0, 0))
        if month == 12:
            month_end = datetime.combine(date(year + 1, 1, 1), time(0, 0))
        else:
            month_end = datetime.combine(date(year, month + 1, 1), time(0, 0))
        
        # Clip reservation to month
        effective_start = max(reservation.start_datetime, month_start)
        effective_end = min(reservation.end_datetime, month_end)
        
        if effective_end <= effective_start:
            return 0
        
        return self._get_maintenance_hours_for_period(effective_start, effective_end)
```

This method:
1. Defines the month boundaries as datetimes
2. Clips the reservation to those boundaries
3. Calls `_get_maintenance_hours_for_period()` on the clipped period

The result is the total maintenance hours that overlap with this reservation during this specific billing month.

#### Invoice Line Item Updates

The `get_context_data()` method builds invoice line items for display. We added the maintenance deduction to each line:

```457:471:cf-orcd-rental/coldfront_orcd_direct_charge/views/billing.py
            # Calculate maintenance deduction for this reservation in this month
            maintenance_deduction = self._get_maintenance_deduction_for_reservation(
                res, year, month
            )

            invoice_lines.append({
                "reservation": res,
                "excluded": False,
                "override": override,
                "hours_in_month": hours_in_month,
                "maintenance_deduction": round(maintenance_deduction, 2),
                "cost_breakdown": cost_breakdown,
                "daily_breakdown": hours_data.get("daily_breakdown", []),
                "sku": sku,
            })
```

The `maintenance_deduction` field is included in the invoice line dictionary so the template can display it. We round to 2 decimal places for clean display.

### 5.2.6 The Overlap Algorithm

The heart of maintenance deduction is the overlap calculation. Let's visualize how it works for different scenarios.

#### Visual Diagram: The Overlap Formula

```
Given:
  Period:  [period_start ───────────────────── period_end]
  Window:       [window_start ─────────── window_end]
  
Overlap Calculation:
  overlap_start = max(period_start, window_start)
  overlap_end   = min(period_end, window_end)
  
Result:
  If overlap_end > overlap_start:
    overlap = overlap_end - overlap_start  ✓ (positive overlap)
  Else:
    overlap = 0  (no overlap)
```

#### Edge Case 1: Maintenance Window Starts Before Reservation

```
Timeline:     00:00 ─────────────────────────────────── 24:00
                    ╔═════════════╗
Maintenance:        ║  8AM - 8PM  ║  (12 hours)
                    ╚═════════════╝
                              ╔═══════════════════════╗
Reservation:                  ║  4PM - 9AM (next day) ║
                              ╚═══════════════════════╝
                              │←─ overlap ─→│
                              4PM          8PM

Calculation for Feb 15:
  effective_start = max(res.start_datetime, day_start) = 4PM
  effective_end   = min(res.end_datetime, day_end)     = midnight
  
  overlap_start = max(window.start(8AM), effective_start(4PM)) = 4PM
  overlap_end   = min(window.end(8PM), effective_end(midnight)) = 8PM
  
  Overlap = 8PM - 4PM = 4 hours
  Raw hours = midnight - 4PM = 8 hours
  Billable hours = 8 - 4 = 4 hours
```

#### Edge Case 2: Maintenance Window Ends After Reservation

```
Timeline:     00:00 ─────────────────────────────────── 24:00
                              ╔═════════════════════════╗
Maintenance:                  ║  4PM - 8AM (next day)   ║
                              ╚═════════════════════════╝
              ╔═══════════════════════╗
Reservation:  ║  8AM - 6PM            ║
              ╚═══════════════════════╝
                              │← overlap →│
                              4PM        6PM

Calculation:
  effective_start = 8AM,  effective_end = 6PM
  overlap_start = max(4PM, 8AM) = 4PM
  overlap_end   = min(8AM next day, 6PM) = 6PM
  
  Overlap = 6PM - 4PM = 2 hours
  Raw hours = 10 hours
  Billable hours = 10 - 2 = 8 hours
```

#### Edge Case 3: Reservation Completely Within Maintenance Window

```
Timeline:     00:00 ─────────────────────────────────── 24:00
              ╔═══════════════════════════════════════════╗
Maintenance:  ║  midnight - midnight (24 hours)          ║
              ╚═══════════════════════════════════════════╝
                        ╔═══════════════╗
Reservation:            ║  8AM - 6PM    ║
                        ╚═══════════════╝
                        │←── overlap ──→│
                        Full 10 hours

Calculation:
  effective_start = 8AM,  effective_end = 6PM
  overlap_start = max(midnight, 8AM) = 8AM
  overlap_end   = min(midnight, 6PM) = 6PM
  
  Overlap = 6PM - 8AM = 10 hours
  Raw hours = 10 hours
  Billable hours = 10 - 10 = 0 hours
```

#### Edge Case 4: Multiple Overlapping Maintenance Windows

```
Timeline:     Feb 14 ────────── Feb 15 ────────── Feb 16
                    ╔═══════════╗     ╔═══════════╗
Windows:            ║ Window 1  ║     ║ Window 2  ║
                    ║ 14th 8PM  ║     ║ 15th 8PM  ║
                    ║    -      ║     ║    -      ║
                    ║ 15th 8AM  ║     ║ 16th 8AM  ║
                    ╚═══════════╝     ╚═══════════╝
              ╔═════════════════════════════════════════╗
Reservation:  ║  Feb 14 4PM ─────────────── Feb 16 9AM ║
              ╚═════════════════════════════════════════╝

For Feb 14 (4PM-midnight = 8 hours):
  Window 1 overlap: max(8PM, 4PM)=8PM to min(8AM next, midnight)=midnight = 4 hours
  Billable: 8 - 4 = 4 hours

For Feb 15 (midnight-midnight = 24 hours):
  Window 1 overlap: midnight to 8AM = 8 hours
  Window 2 overlap: 8PM to midnight = 4 hours
  Total overlap: 12 hours
  Billable: 24 - 12 = 12 hours

For Feb 16 (midnight-9AM = 9 hours):
  Window 2 overlap: midnight to min(8AM, 9AM) = 8 hours
  Billable: 9 - 8 = 1 hour

Total: 4 + 12 + 1 = 17 billable hours (out of 41 raw hours)
Total deduction: 24 hours
```

### 5.2.7 Pattern Parallels

#### In Ruby on Rails

Rails developers would implement similar logic using scopes and service objects:

```ruby
# app/models/maintenance_window.rb
class MaintenanceWindow < ApplicationRecord
  # Scope to find windows overlapping a period
  scope :overlapping, ->(start_dt, end_dt) {
    where('start_datetime < ? AND end_datetime > ?', end_dt, start_dt)
  }
end

# app/services/billing/maintenance_deduction_calculator.rb
module Billing
  class MaintenanceDeductionCalculator
    def initialize(start_dt, end_dt)
      @start_dt = start_dt
      @end_dt = end_dt
    end
    
    def total_hours
      MaintenanceWindow.overlapping(@start_dt, @end_dt).sum do |window|
        calculate_overlap(window)
      end
    end
    
    private
    
    def calculate_overlap(window)
      overlap_start = [window.start_datetime, @start_dt].max
      overlap_end = [window.end_datetime, @end_dt].min
      
      return 0 if overlap_end <= overlap_start
      
      (overlap_end - overlap_start) / 1.hour
    end
  end
end

# Usage in billing calculation
deduction = Billing::MaintenanceDeductionCalculator.new(
  effective_start, 
  effective_end
).total_hours
```

**Key Differences:**
- Rails typically uses service objects for complex calculations; Django uses view methods
- Rails scopes (`.overlapping()`) are like Django QuerySet methods
- Ruby's `sum` with a block is more idiomatic than Python's loop-and-accumulate

#### In Java/Spring

Java developers would use JPA queries and utility methods:

```java
// MaintenanceWindowRepository.java
@Repository
public interface MaintenanceWindowRepository extends JpaRepository<MaintenanceWindow, Long> {
    
    @Query("SELECT m FROM MaintenanceWindow m WHERE m.startDatetime < :endDt AND m.endDatetime > :startDt")
    List<MaintenanceWindow> findOverlapping(
        @Param("startDt") LocalDateTime startDt,
        @Param("endDt") LocalDateTime endDt
    );
}

// BillingService.java
@Service
public class BillingService {
    
    @Autowired
    private MaintenanceWindowRepository maintenanceWindowRepository;
    
    public double getMaintenanceHoursForPeriod(LocalDateTime startDt, LocalDateTime endDt) {
        List<MaintenanceWindow> windows = maintenanceWindowRepository.findOverlapping(startDt, endDt);
        
        return windows.stream()
            .mapToDouble(window -> calculateOverlap(window, startDt, endDt))
            .sum();
    }
    
    private double calculateOverlap(MaintenanceWindow window, LocalDateTime startDt, LocalDateTime endDt) {
        LocalDateTime overlapStart = window.getStartDatetime().isAfter(startDt) 
            ? window.getStartDatetime() : startDt;
        LocalDateTime overlapEnd = window.getEndDatetime().isBefore(endDt)
            ? window.getEndDatetime() : endDt;
        
        if (overlapEnd.isBefore(overlapStart) || overlapEnd.equals(overlapStart)) {
            return 0;
        }
        
        return Duration.between(overlapStart, overlapEnd).toHours();
    }
}
```

**Key Differences:**
- Java uses repository pattern with JPQL queries; Django uses ORM directly in views
- Java streams (`mapToDouble`, `sum`) vs Python loops
- Java requires explicit type handling; Python is dynamically typed

### 5.2.8 Design Decisions

#### Why Day-by-Day Instead of Period-Based Calculation

We could have calculated maintenance deductions at the period level (once for the entire month overlap) instead of day-by-day:

| Approach | Pros | Cons |
|----------|------|------|
| **Period-based** | Simpler, fewer method calls | Cannot track cost allocation changes mid-period |
| **Day-by-day** | Accurate cost allocation attribution | More complex, more database queries |

We chose day-by-day because **cost allocation snapshots can change mid-month**. If we calculated maintenance at the period level, we couldn't correctly attribute the deduction to the right cost objects when allocations change.

**Example:** A 24-hour maintenance window spans Feb 14-15. The cost allocation changes Feb 15 from 100% Dept A to 50% Dept A / 50% Dept B. Day-by-day calculation correctly attributes:
- Feb 14's deduction: 100% to Dept A
- Feb 15's deduction: 50% to Dept A, 50% to Dept B

Period-based calculation would have to pick one allocation or average them—neither is correct.

#### Handling Timezone-Aware vs Naive Datetimes

The `Reservation` model uses naive datetimes (no timezone info). The `MaintenanceWindow` model, being newer, might have timezone-aware datetimes depending on Django's `USE_TZ` setting.

We made a pragmatic decision to **strip timezone info for comparison**:

```python
if hasattr(window_start, 'tzinfo') and window_start.tzinfo is not None:
    window_start = window_start.replace(tzinfo=None)
```

**Why This Is Acceptable:**

1. **Single-timezone operation**: The rental system operates within one institution's timezone. All times are implicitly in that timezone.

2. **Consistency with existing code**: The `Reservation` model already uses naive datetimes. Converting `MaintenanceWindow` to match maintains consistency.

3. **Avoiding comparison errors**: Python raises `TypeError` when comparing timezone-aware and naive datetimes. Stripping timezone info prevents runtime errors.

**Trade-off Acknowledged**: If the system ever handles multiple timezones, both models would need explicit timezone handling. This would require a data migration and code refactor.

#### Why max(0, hours) for the Return Value

```python
return max(0, raw_hours - maintenance_hours)
```

This safety check prevents negative hours due to:
- **Floating-point precision**: `8.999999999 - 9.0` could theoretically be slightly negative
- **Future bug protection**: If a bug causes `maintenance_hours` to exceed `raw_hours`, we fail gracefully

In practice, maintenance hours should never exceed raw hours for a correctly-bounded period, but defensive programming is good practice.

### 5.2.9 Verification

After implementing the billing modifications, verify they work correctly with these test scenarios:

#### Scenario 1: No Maintenance Windows

```python
# Setup: No maintenance windows in database
# Reservation: Feb 14 4PM - Feb 16 9AM (41 hours)

# Expected: 
#   hours_in_month = 41.0
#   maintenance_deduction = 0.0
```

#### Scenario 2: Full Overlap (Reservation Inside Maintenance)

```python
# Setup:
from coldfront_orcd_direct_charge.models import MaintenanceWindow
MaintenanceWindow.objects.create(
    title="Full System Maintenance",
    start_datetime=datetime(2026, 2, 14, 0, 0),
    end_datetime=datetime(2026, 2, 17, 0, 0)
)

# Reservation: Feb 15 4PM - Feb 16 9AM (17 hours)

# Expected:
#   hours_in_month = 0.0 (all 17 hours deducted)
#   maintenance_deduction = 17.0
```

#### Scenario 3: Partial Overlap

```python
# Setup:
MaintenanceWindow.objects.create(
    title="Morning Maintenance",
    start_datetime=datetime(2026, 2, 15, 8, 0),
    end_datetime=datetime(2026, 2, 15, 20, 0)  # 12 hours
)

# Reservation: Feb 14 4PM - Feb 16 9AM (41 hours)

# Expected:
#   maintenance_deduction = 12.0
#   hours_in_month = 41.0 - 12.0 = 29.0
```

#### Scenario 4: Multiple Maintenance Windows

```python
# Setup:
MaintenanceWindow.objects.create(
    title="First Maintenance",
    start_datetime=datetime(2026, 2, 14, 20, 0),
    end_datetime=datetime(2026, 2, 15, 8, 0)  # 12 hours
)
MaintenanceWindow.objects.create(
    title="Second Maintenance",
    start_datetime=datetime(2026, 2, 15, 20, 0),
    end_datetime=datetime(2026, 2, 16, 8, 0)  # 12 hours
)

# Reservation: Feb 14 4PM - Feb 16 9AM (41 hours)

# Expected:
#   maintenance_deduction = 12.0 + 12.0 = 24.0
#   hours_in_month = 41.0 - 24.0 = 17.0
```

#### Scenario 5: Multi-Month Reservation

```python
# Setup:
MaintenanceWindow.objects.create(
    title="End of January Maintenance",
    start_datetime=datetime(2026, 1, 31, 0, 0),
    end_datetime=datetime(2026, 2, 1, 0, 0)  # 24 hours
)

# Reservation: Jan 30 4PM - Feb 2 9AM

# For January invoice:
#   Raw hours in Jan: Jan 30 4PM - Feb 1 12AM = 32 hours
#   Maintenance overlap in Jan: Jan 31 (24 hours)
#   hours_in_month = 32 - 24 = 8.0

# For February invoice:
#   Raw hours in Feb: Feb 1 12AM - Feb 2 9AM = 33 hours
#   Maintenance overlap in Feb: 0 hours
#   hours_in_month = 33.0
```

#### Verification Commands

Run these in the Django shell to test:

```python
from datetime import datetime, date, time, timedelta
from coldfront_orcd_direct_charge.views.billing import InvoiceDetailView
from coldfront_orcd_direct_charge.models import MaintenanceWindow, Reservation

# Create test view instance
view = InvoiceDetailView()

# Test _get_maintenance_hours_for_period
start = datetime(2026, 2, 15, 8, 0)
end = datetime(2026, 2, 15, 20, 0)
hours = view._get_maintenance_hours_for_period(start, end)
print(f"Maintenance hours from 8AM-8PM: {hours}")

# Test with a reservation (requires an actual reservation in DB)
reservation = Reservation.objects.first()
if reservation:
    deduction = view._get_maintenance_deduction_for_reservation(
        reservation, 2026, 2
    )
    print(f"Maintenance deduction for reservation: {deduction}")
```

---

> **Summary:** TODO 2 integrates maintenance windows into the billing calculation flow. Three new methods were added: `_get_maintenance_hours_for_period()` calculates overlap using the classic interval intersection algorithm, `_get_hours_for_day()` was modified to deduct maintenance hours from daily calculations, and `_get_maintenance_deduction_for_reservation()` provides per-reservation totals for invoice display. The day-by-day approach ensures correct cost allocation attribution even when snapshots change mid-month. With billing integration complete, invoices now automatically reflect reduced hours when maintenance windows exist.

---

*Continue to [5.3 TODO 3: Create Views, URLs, and Templates](#53-todo-3-create-views-urls-and-templates) for the web UI implementation.*

---

## 5.3 TODO 3: Create Web UI Views and Templates

### 5.3.1 Objective

Create a complete web interface that allows rental managers to perform all CRUD (Create, Read, Update, Delete) operations on maintenance windows. The interface must integrate seamlessly with the existing application's look and feel, enforce business rules (only future windows can be edited/deleted), and provide clear feedback to users.

### 5.3.2 Prerequisites

| Requirement | Reason |
|-------------|--------|
| TODO 1 completed | The `MaintenanceWindow` model must exist before we can create views that use it |
| Understanding of Django CBVs | All views use Class-Based Views |
| Familiarity with Bootstrap templates | The UI follows existing application patterns |

### 5.3.3 Concepts Applied

This section applies several core Django web development concepts:

| Concept | Application |
|---------|-------------|
| **Class-Based Views (CBVs)** | ListView, CreateView, UpdateView, DeleteView provide CRUD scaffolding |
| **Mixins** | LoginRequiredMixin and PermissionRequiredMixin enforce access control |
| **Template Inheritance** | All templates extend `common/base.html` for consistent layout |
| **URL Routing** | RESTful URL patterns map to view actions |
| **Form Handling** | Automatic form generation and validation from model fields |
| **Messages Framework** | User feedback via Django's messages system |
| **Template Tags** | Custom tags for modular help text rendering |

### 5.3.4 Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| `views/rentals.py` | Modified | Add four MaintenanceWindow view classes |
| `urls.py` | Modified | Add URL patterns for CRUD operations |
| `templates/.../maintenance_window/list.html` | Created | List view with table and action buttons |
| `templates/.../maintenance_window/form.html` | Created | Shared create/edit form |
| `templates/.../maintenance_window/delete.html` | Created | Delete confirmation page |
| `templates/.../maintenance_window/_help_modal.html` | Created | Reusable help modal component |
| `templates/common/authorized_navbar.html` | Modified | Add dropdown menu entry |

### 5.3.5 The Four CRUD Views

All four views follow the same structural pattern: they inherit from Django's generic views, add authentication/permission mixins, specify the model and template, and override methods where custom behavior is needed.

#### View 1: MaintenanceWindowListView (Read All)

The ListView displays all maintenance windows in a sortable, filterable table:

```700:711:cf-orcd-rental/coldfront_orcd_direct_charge/views/rentals.py
class MaintenanceWindowListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """List all maintenance windows with management controls."""

    model = MaintenanceWindow
    template_name = "coldfront_orcd_direct_charge/maintenance_window/list.html"
    context_object_name = "windows"
    permission_required = "coldfront_orcd_direct_charge.can_manage_rentals"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        return context
```

**Line-by-Line Explanation:**

| Line | Purpose |
|------|---------|
| `LoginRequiredMixin` | Redirects unauthenticated users to login page |
| `PermissionRequiredMixin` | Ensures user has `can_manage_rentals` permission |
| `model = MaintenanceWindow` | Tells the view which model to query |
| `template_name = ...` | Explicit template path (convention would be `maintenancewindow_list.html`) |
| `context_object_name = "windows"` | The template variable name for the queryset |
| `context["now"] = timezone.now()` | Passed to template for status badge logic |

**The Mixin Order Matters:**

```
LoginRequiredMixin → PermissionRequiredMixin → ListView
```

Django processes mixins left-to-right. `LoginRequiredMixin` first checks authentication, then `PermissionRequiredMixin` checks permissions. If we reversed them, the permission check would run on anonymous users and fail confusingly.

#### View 2: MaintenanceWindowCreateView (Create)

The CreateView provides a form for creating new maintenance windows:

```714:749:cf-orcd-rental/coldfront_orcd_direct_charge/views/rentals.py
class MaintenanceWindowCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create a new maintenance window."""

    model = MaintenanceWindow
    template_name = "coldfront_orcd_direct_charge/maintenance_window/form.html"
    fields = ["title", "start_datetime", "end_datetime", "description"]
    permission_required = "coldfront_orcd_direct_charge.can_manage_rentals"
    success_url = reverse_lazy("coldfront_orcd_direct_charge:maintenance-window-list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)

        log_activity(
            action="maintenance_window.created",
            category=ActivityLog.ActionCategory.MAINTENANCE,
            description=f"Created maintenance window: {self.object.title}",
            request=self.request,
            target=self.object,
            extra_data={
                "window_id": self.object.pk,
                "start_datetime": self.object.start_datetime.isoformat(),
                "end_datetime": self.object.end_datetime.isoformat(),
                "duration_hours": self.object.duration_hours,
            },
        )

        messages.success(
            self.request, f"Maintenance window '{self.object.title}' created successfully."
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["action"] = "Create"
        return context
```

**Key Implementation Details:**

| Attribute/Method | Purpose |
|------------------|---------|
| `fields = [...]` | Auto-generates form from these model fields |
| `success_url` | Where to redirect after successful creation |
| `form_valid()` | Hook called when form validation passes |
| `form.instance.created_by = self.request.user` | Set the creator before saving |
| `log_activity()` | Record the action for audit trail |
| `context["action"] = "Create"` | Template uses this for conditional rendering |

**Why `reverse_lazy()` Instead of `reverse()`?**

```python
success_url = reverse_lazy("coldfront_orcd_direct_charge:maintenance-window-list")
```

Class attributes are evaluated at import time, before Django's URL configuration is loaded. `reverse_lazy()` delays URL resolution until the value is actually needed, avoiding `ImproperlyConfigured` errors.

#### View 3: MaintenanceWindowUpdateView (Update)

The UpdateView allows editing existing maintenance windows, but only future ones:

```752:816:cf-orcd-rental/coldfront_orcd_direct_charge/views/rentals.py
class MaintenanceWindowUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Edit an existing maintenance window (future windows only)."""

    model = MaintenanceWindow
    template_name = "coldfront_orcd_direct_charge/maintenance_window/form.html"
    fields = ["title", "start_datetime", "end_datetime", "description"]
    permission_required = "coldfront_orcd_direct_charge.can_manage_rentals"
    success_url = reverse_lazy("coldfront_orcd_direct_charge:maintenance-window-list")

    def get_queryset(self):
        """Only allow editing windows that haven't started yet."""
        return MaintenanceWindow.objects.filter(start_datetime__gt=timezone.now())

    def get(self, request, *args, **kwargs):
        """Handle case where window is not editable."""
        try:
            self.object = self.get_object()
        except Http404:
            messages.error(
                request,
                "This maintenance window has already started or passed and cannot be "
                "modified through the web interface.",
            )
            return redirect("coldfront_orcd_direct_charge:maintenance-window-list")
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Handle case where window is not editable."""
        try:
            self.object = self.get_object()
        except Http404:
            messages.error(
                request,
                "This maintenance window has already started or passed and cannot be "
                "modified through the web interface.",
            )
            return redirect("coldfront_orcd_direct_charge:maintenance-window-list")
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["action"] = "Edit"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)

        log_activity(
            action="maintenance_window.updated",
            category=ActivityLog.ActionCategory.MAINTENANCE,
            description=f"Updated maintenance window: {self.object.title}",
            request=self.request,
            target=self.object,
            extra_data={
                "window_id": self.object.pk,
                "start_datetime": self.object.start_datetime.isoformat(),
                "end_datetime": self.object.end_datetime.isoformat(),
                "duration_hours": self.object.duration_hours,
            },
        )

        messages.success(
            self.request, f"Maintenance window '{self.object.title}' updated successfully."
        )
        return response
```

**The Future-Only Restriction Pattern:**

```python
def get_queryset(self):
    """Only allow editing windows that haven't started yet."""
    return MaintenanceWindow.objects.filter(start_datetime__gt=timezone.now())
```

This is the key business rule enforcement. By restricting the queryset, any attempt to access a past or in-progress window results in a 404. The `get()` and `post()` methods catch this 404 and provide a user-friendly error message instead of Django's default 404 page.

**Why Override Both get() and post()?**

Without both overrides, a crafty user could:
1. Access the edit form for a future window (GET succeeds)
2. Wait until the maintenance window starts
3. Submit the form (POST would need to check again)

By checking in both methods, we ensure the restriction is enforced at form display AND submission time.

#### View 4: MaintenanceWindowDeleteView (Delete)

The DeleteView confirms and executes deletion, again restricted to future windows:

```819:885:cf-orcd-rental/coldfront_orcd_direct_charge/views/rentals.py
class MaintenanceWindowDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Delete a maintenance window (future windows only)."""

    model = MaintenanceWindow
    template_name = "coldfront_orcd_direct_charge/maintenance_window/delete.html"
    permission_required = "coldfront_orcd_direct_charge.can_manage_rentals"
    success_url = reverse_lazy("coldfront_orcd_direct_charge:maintenance-window-list")

    def get_queryset(self):
        """Only allow deleting windows that haven't started yet."""
        return MaintenanceWindow.objects.filter(start_datetime__gt=timezone.now())

    def get(self, request, *args, **kwargs):
        """Handle case where window is not deletable."""
        try:
            self.object = self.get_object()
        except Http404:
            messages.error(
                request,
                "This maintenance window has already started or passed and cannot be "
                "deleted through the web interface.",
            )
            return redirect("coldfront_orcd_direct_charge:maintenance-window-list")
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Handle case where window is not deletable."""
        try:
            self.object = self.get_object()
        except Http404:
            messages.error(
                request,
                "This maintenance window has already started or passed and cannot be "
                "deleted through the web interface.",
            )
            return redirect("coldfront_orcd_direct_charge:maintenance-window-list")
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        # Capture details before deletion
        window_id = self.object.pk
        window_title = self.object.title
        start_datetime = self.object.start_datetime.isoformat()
        end_datetime = self.object.end_datetime.isoformat()
        duration_hours = self.object.duration_hours

        # Log activity before deletion (object will be gone after super())
        log_activity(
            action="maintenance_window.deleted",
            category=ActivityLog.ActionCategory.MAINTENANCE,
            description=f"Deleted maintenance window: {window_title}",
            request=self.request,
            target=None,  # Object is being deleted
            extra_data={
                "window_id": window_id,
                "window_title": window_title,
                "start_datetime": start_datetime,
                "end_datetime": end_datetime,
                "duration_hours": duration_hours,
            },
        )

        response = super().form_valid(form)
        messages.success(
            self.request, f"Maintenance window '{window_title}' deleted successfully."
        )
        return response
```

**Critical Pattern: Logging Before Deletion**

```python
def form_valid(self, form):
    # Capture details before deletion
    window_id = self.object.pk
    window_title = self.object.title
    # ... capture other fields ...

    # Log activity before deletion (object will be gone after super())
    log_activity(...)

    response = super().form_valid(form)  # This deletes the object
```

We must capture object attributes *before* calling `super().form_valid(form)` because that method deletes the object from the database. After deletion, `self.object` still exists in memory but accessing database-derived properties could fail.

The activity log records `target=None` because the object no longer exists—we can't create a foreign key reference to a deleted record.

### 5.3.6 URL Configuration

The URL patterns follow RESTful conventions for resource management:

```64:68:cf-orcd-rental/coldfront_orcd_direct_charge/urls.py
    # Maintenance Windows
    path("maintenance-windows/", views.MaintenanceWindowListView.as_view(), name="maintenance-window-list"),
    path("maintenance-windows/create/", views.MaintenanceWindowCreateView.as_view(), name="maintenance-window-create"),
    path("maintenance-windows/<int:pk>/edit/", views.MaintenanceWindowUpdateView.as_view(), name="maintenance-window-update"),
    path("maintenance-windows/<int:pk>/delete/", views.MaintenanceWindowDeleteView.as_view(), name="maintenance-window-delete"),
```

**URL Pattern Analysis:**

| Pattern | HTTP Method | Action | View |
|---------|-------------|--------|------|
| `maintenance-windows/` | GET | List all windows | MaintenanceWindowListView |
| `maintenance-windows/create/` | GET/POST | Create new window | MaintenanceWindowCreateView |
| `maintenance-windows/<int:pk>/edit/` | GET/POST | Edit window by ID | MaintenanceWindowUpdateView |
| `maintenance-windows/<int:pk>/delete/` | GET/POST | Delete window by ID | MaintenanceWindowDeleteView |

**Key Observations:**

1. **Namespace prefix**: All URLs are namespaced under `coldfront_orcd_direct_charge:` (defined by `app_name` in urls.py)

2. **Integer primary key**: `<int:pk>` captures the database ID and passes it to the view

3. **Verb suffixes**: `/edit/` and `/delete/` explicitly name the action (vs. relying solely on HTTP method)

4. **Consistent base path**: All maintenance window URLs share `maintenance-windows/` prefix

**Template URL Usage:**

```django
{% url 'coldfront_orcd_direct_charge:maintenance-window-create' %}
{% url 'coldfront_orcd_direct_charge:maintenance-window-update' window.pk %}
{% url 'coldfront_orcd_direct_charge:maintenance-window-delete' window.pk %}
```

### 5.3.7 Templates

The templates follow the existing application's patterns, using Bootstrap 4 classes and extending the common base template.

#### Template Structure and Inheritance

```
common/base.html
├── maintenance_window/list.html
├── maintenance_window/form.html (shared by create/edit)
├── maintenance_window/delete.html
└── maintenance_window/_help_modal.html (included partial)
```

All templates extend `common/base.html` which provides:
- HTML document structure
- Bootstrap CSS/JS includes
- Navbar via include
- Messages display
- Content blocks (`title`, `content`, `javascript`)

#### List Template (list.html)

The list template displays all maintenance windows in a DataTables-enhanced table:

```1:40:cf-orcd-rental/coldfront_orcd_direct_charge/templates/coldfront_orcd_direct_charge/maintenance_window/list.html
{% extends "common/base.html" %}
{% load static %}

{% block title %}Maintenance Windows{% endblock %}

{% block content %}
<h2><i class="fas fa-wrench"></i> Maintenance Windows</h2>
<hr>

<div class="card">
  <div class="card-header d-flex justify-content-between align-items-center">
    <h5 class="mb-0">All Maintenance Windows</h5>
    <div>
      {% include "coldfront_orcd_direct_charge/maintenance_window/_help_modal.html" %}
      <a href="{% url 'coldfront_orcd_direct_charge:maintenance-window-create' %}" class="btn btn-primary">
        <i class="fas fa-plus"></i> New Maintenance Window
      </a>
    </div>
  </div>
  <div class="card-body">
    {% if windows %}
    <div class="table-responsive">
      <table class="table table-hover" id="maintenance-windows-table">
        <thead class="thead-light">
          <tr>
            <th>Title</th>
            <th>Start</th>
            <th>End</th>
            <th>Duration</th>
            <th>Status</th>
            <th>Created By</th>
            <th>Actions</th>
          </tr>
        </thead>
        <!-- table body with iteration over windows -->
      </table>
    </div>
    {% else %}
    <p class="text-muted mb-0"><i class="fas fa-info-circle"></i> No maintenance windows have been created.</p>
    {% endif %}
```

**Key Template Patterns:**

**Status Badge Logic:**

```html
{% if window.is_upcoming %}
  <span class="badge badge-success">Upcoming</span>
{% elif window.is_in_progress %}
  <span class="badge badge-warning">In Progress</span>
{% else %}
  <span class="badge badge-secondary">Completed</span>
{% endif %}
```

The model's `is_upcoming`, `is_in_progress`, and `is_completed` properties (implemented in TODO 1) drive the display logic. This keeps the template simple—it just asks "what state is this?" rather than calculating the answer.

**Conditional Action Buttons:**

```html
{% if window.is_upcoming %}
  <a href="{% url 'coldfront_orcd_direct_charge:maintenance-window-update' window.pk %}" 
     class="btn btn-sm btn-outline-primary" title="Edit">
    <i class="fas fa-edit"></i> Edit
  </a>
  <a href="{% url 'coldfront_orcd_direct_charge:maintenance-window-delete' window.pk %}" 
     class="btn btn-sm btn-outline-danger" title="Delete">
    <i class="fas fa-trash"></i> Delete
  </a>
{% else %}
  <span class="text-muted" title="Cannot modify past or in-progress windows">
    <i class="fas fa-lock"></i> Locked
  </span>
{% endif %}
```

This provides immediate visual feedback about which windows can be modified. Even though the views also enforce this restriction, showing it in the UI prevents user confusion.

**DataTables Integration:**

```html
{% block javascript %}
<script>
$(document).ready(function() {
    $('#maintenance-windows-table').DataTable({
        paging: true,
        pageLength: 25,
        searching: true,
        order: [[1, 'desc']], // Sort by Start date descending
        columnDefs: [{ orderable: false, targets: -1 }] // Disable sorting on Actions column
    });
});
</script>
{% endblock %}
```

DataTables provides client-side sorting, searching, and pagination without server-side changes.

#### Form Template (form.html)

A single template handles both create and edit operations:

```1:45:cf-orcd-rental/coldfront_orcd_direct_charge/templates/coldfront_orcd_direct_charge/maintenance_window/form.html
{% extends "common/base.html" %}
{% load static %}

{% block title %}{{ action }} Maintenance Window{% endblock %}

{% block content %}
<h2><i class="fas fa-wrench"></i> {{ action }} Maintenance Window</h2>
<hr>

<div class="card">
  <div class="card-header">
    <h5 class="mb-0">{{ action }} Maintenance Window</h5>
  </div>
  <div class="card-body">
    <form method="post">
      {% csrf_token %}
      
      {% if form.non_field_errors %}
      <div class="alert alert-danger">
        {{ form.non_field_errors }}
      </div>
      {% endif %}

      <div class="form-group">
        <label for="id_title" class="form-label">Title <span class="text-danger">*</span></label>
        <input type="text" name="title" id="id_title" class="form-control {% if form.title.errors %}is-invalid{% endif %}" 
               value="{{ form.title.value|default:'' }}" required
               placeholder="e.g., Scheduled System Maintenance">
        {% if form.title.errors %}
        <div class="invalid-feedback">{{ form.title.errors.0 }}</div>
        {% endif %}
        <small class="form-text text-muted">A short, descriptive title for this maintenance window.</small>
      </div>
      
      <!-- datetime inputs and description textarea -->
    </form>
  </div>
</div>
```

**Shared Template Technique:**

The template works for both create and edit because:
1. The view passes `context["action"]` as either "Create" or "Edit"
2. For edit, Django pre-populates `form.field.value` with existing data
3. For create, `form.field.value` is empty (the `|default:''` filter handles None)

**Manual Form Rendering:**

Rather than using `{{ form.as_p }}` or a form library like `crispy_forms`, this template manually renders each field. This provides maximum control over:
- Bootstrap 4 classes (`.form-control`, `.is-invalid`)
- Custom layout (two-column date/time row)
- Help text styling
- Error message placement

**Datetime Input Type:**

```html
<input type="datetime-local" name="start_datetime" id="id_start_datetime" ...>
```

HTML5's `datetime-local` input type provides a native date/time picker on most browsers, eliminating the need for JavaScript date pickers.

#### Delete Confirmation Template (delete.html)

The delete template emphasizes the destructive nature of the action:

```1:48:cf-orcd-rental/coldfront_orcd_direct_charge/templates/coldfront_orcd_direct_charge/maintenance_window/delete.html
{% extends "common/base.html" %}
{% load static %}

{% block title %}Delete Maintenance Window{% endblock %}

{% block content %}
<h2><i class="fas fa-exclamation-triangle text-danger"></i> Delete Maintenance Window</h2>
<hr>

<div class="card border-danger">
  <div class="card-header bg-danger text-white">
    <h5 class="mb-0">Confirm Deletion</h5>
  </div>
  <div class="card-body">
    <p>Are you sure you want to delete the maintenance window <strong>"{{ object.title }}"</strong>?</p>
    
    <div class="alert alert-secondary">
      <strong>Details:</strong>
      <ul class="mb-0 mt-2">
        <li><strong>Start:</strong> {{ object.start_datetime|date:"M d, Y H:i" }}</li>
        <li><strong>End:</strong> {{ object.end_datetime|date:"M d, Y H:i" }}</li>
        <li><strong>Duration:</strong> {{ object.duration_hours|floatformat:1 }} hours</li>
        {% if object.description %}
        <li><strong>Description:</strong> {{ object.description }}</li>
        {% endif %}
      </ul>
    </div>

    <div class="alert alert-warning">
      <i class="fas fa-exclamation-triangle"></i> <strong>Warning:</strong> 
      This action cannot be undone. If this maintenance window was intended to exclude billing for a specific period, 
      deleting it will cause that time to become billable again.
    </div>

    <form method="post">
      {% csrf_token %}
      <div class="d-flex gap-2">
        <button type="submit" class="btn btn-danger">
          <i class="fas fa-trash"></i> Delete Maintenance Window
        </button>
        <a href="{% url 'coldfront_orcd_direct_charge:maintenance-window-list' %}" class="btn btn-secondary ml-2">
          Cancel
        </a>
      </div>
    </form>
  </div>
</div>
{% endblock %}
```

**UX Best Practices Applied:**

1. **Visual hierarchy**: Red card border and header signal danger
2. **Confirmation details**: Show exactly what will be deleted
3. **Business impact warning**: Explain that billing will be affected
4. **Clear escape hatch**: Cancel button is prominent and easy to find
5. **Action button styling**: Delete button is red, matching the danger theme

#### Help Modal Partial (_help_modal.html)

The help modal is a reusable component included in the list template:

```1:26:cf-orcd-rental/coldfront_orcd_direct_charge/templates/coldfront_orcd_direct_charge/maintenance_window/_help_modal.html
{% load help_text_tags %}

<!-- Help Button -->
<button type="button" class="btn btn-outline-info btn-sm" data-toggle="modal" data-target="#helpModal">
    <i class="fas fa-question-circle"></i> Help
</button>

<!-- Help Modal -->
<div class="modal fade" id="helpModal" tabindex="-1" role="dialog" aria-labelledby="helpModalLabel" aria-hidden="true">
    <div class="modal-dialog modal-lg modal-dialog-scrollable" role="document">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title" id="helpModalLabel">Maintenance Windows Help</h5>
                <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                    <span aria-hidden="true">&times;</span>
                </button>
            </div>
            <div class="modal-body help-content">
                {% load_help_text "maintenance_window" %}
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
            </div>
        </div>
    </div>
</div>
```

**The Custom Template Tag:**

```django
{% load help_text_tags %}
...
{% load_help_text "maintenance_window" %}
```

The `load_help_text` template tag (implemented in TODO 10) loads markdown content from a file and renders it as HTML. This modular approach:
- Keeps help content in version-controlled markdown files
- Allows non-developers to edit help text
- Enables help reuse across multiple templates
- Separates content from presentation

### 5.3.8 Navigation Integration

The maintenance windows link is added to the navbar's Admin Functions dropdown:

```34:38:cf-orcd-rental/coldfront_orcd_direct_charge/templates/common/authorized_navbar.html
              <h6 class="dropdown-header">Admin Functions</h6>
              {% if perms.coldfront_orcd_direct_charge.can_manage_rentals %}
                <a id="navbar-manage-rentals" class="dropdown-item" href="{% url 'coldfront_orcd_direct_charge:rental-manager' %}">Manage Rentals</a>
                <a id="navbar-maintenance-windows" class="dropdown-item" href="{% url 'coldfront_orcd_direct_charge:maintenance-window-list' %}">Maintenance Windows</a>
              {% endif %}
```

**Key Design Decisions:**

1. **Same permission as Manage Rentals**: Users who can manage rentals can also manage maintenance windows—these are logically related admin functions

2. **Grouped under Admin Functions**: Clear separation between user features (My Reservations) and admin features

3. **Placement after Manage Rentals**: Logical grouping—both are rental-related management functions

4. **ID attribute for testing**: `id="navbar-maintenance-windows"` enables reliable Selenium/Playwright selectors

### 5.3.9 Pattern Parallels

#### In Ruby on Rails

Rails developers would achieve similar functionality using the standard MVC pattern:

```ruby
# config/routes.rb
resources :maintenance_windows, except: [:show]

# app/controllers/maintenance_windows_controller.rb
class MaintenanceWindowsController < ApplicationController
  before_action :authenticate_user!
  before_action :authorize_rental_manager!
  before_action :set_maintenance_window, only: [:edit, :update, :destroy]
  before_action :require_future_window, only: [:edit, :update, :destroy]
  
  def index
    @windows = MaintenanceWindow.all.order(start_datetime: :desc)
  end
  
  def new
    @window = MaintenanceWindow.new
  end
  
  def create
    @window = MaintenanceWindow.new(window_params)
    @window.created_by = current_user
    
    if @window.save
      redirect_to maintenance_windows_path, notice: "Maintenance window created."
    else
      render :new
    end
  end
  
  def edit; end
  
  def update
    if @window.update(window_params)
      redirect_to maintenance_windows_path, notice: "Maintenance window updated."
    else
      render :edit
    end
  end
  
  def destroy
    @window.destroy
    redirect_to maintenance_windows_path, notice: "Maintenance window deleted."
  end
  
  private
  
  def set_maintenance_window
    @window = MaintenanceWindow.find(params[:id])
  end
  
  def require_future_window
    unless @window.upcoming?
      redirect_to maintenance_windows_path, alert: "Cannot modify past windows."
    end
  end
  
  def window_params
    params.require(:maintenance_window).permit(:title, :start_datetime, :end_datetime, :description)
  end
end
```

**Key Differences from Django:**

| Aspect | Django CBV | Rails Controller |
|--------|------------|------------------|
| Filtering | Override `get_queryset()` | Use `before_action` callbacks |
| Permissions | Mixin-based composition | Method-based `before_action` |
| Templates | Convention requires explicit paths | Convention: `views/maintenance_windows/*.erb` |
| Forms | Auto-generated from `fields` list | Requires explicit form partial |
| Flash messages | `messages.success()` | `redirect_to ..., notice:` |

#### In Express.js (Node.js)

Express developers would use middleware and route handlers:

```javascript
// routes/maintenanceWindows.js
const express = require('express');
const router = express.Router();
const { MaintenanceWindow } = require('../models');
const { requireAuth, requireRentalManager } = require('../middleware/auth');
const { requireFutureWindow } = require('../middleware/maintenanceWindow');

router.use(requireAuth);
router.use(requireRentalManager);

// List all
router.get('/', async (req, res) => {
  const windows = await MaintenanceWindow.findAll({ order: [['start_datetime', 'DESC']] });
  res.render('maintenance-windows/list', { windows });
});

// Create form
router.get('/create', (req, res) => {
  res.render('maintenance-windows/form', { action: 'Create', window: {} });
});

// Create handler
router.post('/create', async (req, res) => {
  const window = await MaintenanceWindow.create({
    ...req.body,
    created_by: req.user.id
  });
  req.flash('success', `Maintenance window '${window.title}' created.`);
  res.redirect('/maintenance-windows');
});

// Edit form
router.get('/:id/edit', requireFutureWindow, (req, res) => {
  res.render('maintenance-windows/form', { action: 'Edit', window: req.maintenanceWindow });
});

// Update handler
router.post('/:id/edit', requireFutureWindow, async (req, res) => {
  await req.maintenanceWindow.update(req.body);
  req.flash('success', `Maintenance window '${req.maintenanceWindow.title}' updated.`);
  res.redirect('/maintenance-windows');
});

// Delete confirmation
router.get('/:id/delete', requireFutureWindow, (req, res) => {
  res.render('maintenance-windows/delete', { window: req.maintenanceWindow });
});

// Delete handler
router.post('/:id/delete', requireFutureWindow, async (req, res) => {
  const title = req.maintenanceWindow.title;
  await req.maintenanceWindow.destroy();
  req.flash('success', `Maintenance window '${title}' deleted.`);
  res.redirect('/maintenance-windows');
});

module.exports = router;
```

**Key Differences from Django:**

| Aspect | Django CBV | Express.js |
|--------|------------|------------|
| Route definition | Declarative in urls.py | Fluent API on router |
| Middleware | Mixins on class | `router.use()` and per-route |
| Object loading | `get_object()` in CBV | Custom middleware sets `req.maintenanceWindow` |
| Templates | Django template engine | Any engine (EJS, Pug, Handlebars) |
| Async handling | Sync by default | Explicit async/await |

### 5.3.10 Design Decisions

#### Why Class-Based Views Instead of Function-Based Views?

| Consideration | CBV Advantage | FBV Advantage |
|---------------|---------------|---------------|
| **Code reuse** | Mixins compose behavior declaratively | Must duplicate code or create decorators |
| **Consistency** | Follows existing codebase patterns | Simpler for one-off views |
| **Testability** | Can test individual methods | Single function to test |
| **Learning curve** | Steeper, but documented | Immediately understandable |
| **Customization** | Override specific hooks | Full control of flow |

We chose CBVs because:
1. The existing codebase uses CBVs extensively
2. Generic views (ListView, CreateView, etc.) provide significant scaffolding
3. Mixin composition gives clean permission handling
4. Overriding `get_queryset()` elegantly enforces the future-only restriction

#### Why a Shared Form Template Instead of Separate Create/Edit Templates?

The create and edit forms are nearly identical—only the title and action button text differ. A shared template:
- Reduces maintenance burden (one template to update)
- Ensures visual consistency
- Follows DRY principles

The `action` context variable controls the differences:

```django
<h2>{{ action }} Maintenance Window</h2>  <!-- "Create" or "Edit" -->
```

#### Why Manual Form Rendering Instead of Crispy Forms?

The codebase doesn't use `django-crispy-forms`. While Crispy would reduce template code, introducing it for one feature would:
- Add a dependency
- Create inconsistency with existing forms
- Require learning a new API

Manual rendering maintains consistency with other forms in the application.

#### Why DataTables for the List View?

DataTables provides client-side sorting, searching, and pagination without server-side changes. For a list that will typically have tens to hundreds of entries (not thousands), this is more than sufficient.

Server-side pagination would be overkill and would require:
- Additional view logic
- AJAX endpoints
- More complex template code

### 5.3.11 Verification

After implementing the web UI, verify all functionality works:

#### Basic CRUD Operations

| Test | Steps | Expected Result |
|------|-------|-----------------|
| **List View** | Navigate to `/nodes/maintenance-windows/` | See table of all maintenance windows |
| **Create** | Click "New Maintenance Window", fill form, submit | New window appears in list with success message |
| **Edit** | Click "Edit" on a future window, modify, submit | Changes saved, success message shown |
| **Delete** | Click "Delete" on a future window, confirm | Window removed from list with success message |

#### Access Control

| Test | Steps | Expected Result |
|------|-------|-----------------|
| **Unauthenticated access** | Visit list URL when logged out | Redirect to login page |
| **Unprivileged access** | Login as user without `can_manage_rentals` | 403 Forbidden error |
| **Privileged access** | Login as rental manager | Full access to all CRUD operations |

#### Future-Only Restriction

| Test | Steps | Expected Result |
|------|-------|-----------------|
| **Edit button visibility** | View list with past windows | Edit/Delete buttons hidden, shows "Locked" |
| **Direct URL edit attempt** | Manually navigate to `/nodes/maintenance-windows/123/edit/` for past window | Redirect to list with error message |
| **Direct URL delete attempt** | Manually navigate to `/nodes/maintenance-windows/123/delete/` for past window | Redirect to list with error message |

#### Navigation

| Test | Steps | Expected Result |
|------|-------|-----------------|
| **Navbar link visible** | Login as rental manager | "Maintenance Windows" appears under Project > Admin Functions |
| **Navbar link hidden** | Login as regular user | "Admin Functions" section not visible |

#### Form Validation

| Test | Steps | Expected Result |
|------|-------|-----------------|
| **Required fields** | Submit form with empty title | Validation error displayed |
| **End before start** | Enter end datetime before start datetime | Model validation error (from `clean()` method) |
| **Valid submission** | Fill all required fields correctly | Form saves successfully |

#### Verification Commands

```bash
# Run development server
cd /Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental
python manage.py runserver

# Test URLs resolve correctly
python manage.py shell
>>> from django.urls import reverse
>>> reverse('coldfront_orcd_direct_charge:maintenance-window-list')
'/nodes/maintenance-windows/'
>>> reverse('coldfront_orcd_direct_charge:maintenance-window-create')
'/nodes/maintenance-windows/create/'
>>> reverse('coldfront_orcd_direct_charge:maintenance-window-update', args=[1])
'/nodes/maintenance-windows/1/edit/'
>>> reverse('coldfront_orcd_direct_charge:maintenance-window-delete', args=[1])
'/nodes/maintenance-windows/1/delete/'
```

---

> **Summary:** TODO 3 creates a complete web UI for maintenance window management using Django's generic class-based views. Four views (List, Create, Update, Delete) handle all CRUD operations, with Update and Delete restricted to future windows via queryset filtering. Templates follow existing application patterns with Bootstrap 4 styling, DataTables integration for the list view, and a shared form template for create/edit operations. Navigation integration adds a "Maintenance Windows" link to the Admin Functions dropdown for users with the `can_manage_rentals` permission. The implementation emphasizes consistency with the existing codebase, clear user feedback via the messages framework, and proper enforcement of business rules at both the UI and server levels.

---

*Continue to [5.4 TODO 4: Add API Serializer, ViewSet, and Routes](#54-todo-4-add-api-serializer-viewset-and-routes) for the REST API implementation.*

---

## 5.4 TODO 4: Add REST API

This section implements a REST API for maintenance windows using Django REST Framework (DRF). The API provides programmatic access to maintenance window data, enabling integrations with monitoring systems, dashboards, and automation tools.

### 5.4.1 Objective

Create a RESTful API that exposes maintenance window CRUD operations with:
- Full Create, Read, Update, Delete (CRUD) capabilities
- Permission-based access control
- Status-based filtering (upcoming, in progress, completed)
- Computed fields for duration and status
- Consistent JSON response format
- Automatic user tracking for window creation

### 5.4.2 Prerequisites

This TODO requires completion of:

| Prerequisite | Provides |
|--------------|----------|
| **TODO 1: Model** | `MaintenanceWindow` model with `@property` methods (`is_upcoming`, `is_in_progress`, `is_completed`, `duration_hours`) |

### 5.4.3 Concepts Applied

| Concept | Application |
|---------|-------------|
| **Django REST Framework** | Full-featured toolkit for building Web APIs |
| **ModelSerializer** | Automatic serialization from Django models |
| **SerializerMethodField** | Computed/derived values in responses |
| **ModelViewSet** | Complete CRUD operations in one class |
| **DefaultRouter** | Automatic URL pattern generation |
| **Permission Classes** | Declarative access control |
| **QuerySet Filtering** | Dynamic filtering via query parameters |

### 5.4.4 Files Modified

| File | Purpose |
|------|---------|
| `api/serializers.py` | Add `MaintenanceWindowSerializer` |
| `api/views.py` | Add `MaintenanceWindowViewSet` |
| `api/urls.py` | Register viewset with router |

### 5.4.5 The Serializer

The serializer transforms Django model instances to JSON and validates incoming data.

```304:334:cf-orcd-rental/coldfront_orcd_direct_charge/api/serializers.py
class MaintenanceWindowSerializer(serializers.ModelSerializer):
    """Serializer for MaintenanceWindow model."""

    created_by_username = serializers.CharField(
        source="created_by.username",
        read_only=True,
        allow_null=True,
    )
    duration_hours = serializers.FloatField(read_only=True)
    is_upcoming = serializers.BooleanField(read_only=True)
    is_in_progress = serializers.BooleanField(read_only=True)
    is_completed = serializers.BooleanField(read_only=True)

    class Meta:
        model = MaintenanceWindow
        fields = (
            "id",
            "title",
            "description",
            "start_datetime",
            "end_datetime",
            "duration_hours",
            "is_upcoming",
            "is_in_progress",
            "is_completed",
            "created_by_username",
            "created",
            "modified",
        )
        read_only_fields = ("created", "modified")
```

#### Field-by-Field Explanation

| Field | Type | Purpose |
|-------|------|---------|
| `id` | Auto | Primary key, auto-generated |
| `title` | CharField | Main identifier for the window |
| `description` | TextField | Optional detailed information |
| `start_datetime` | DateTimeField | When maintenance begins |
| `end_datetime` | DateTimeField | When maintenance ends |
| `duration_hours` | FloatField | **Computed:** Calculated from model `@property` |
| `is_upcoming` | BooleanField | **Computed:** `start_datetime > now` |
| `is_in_progress` | BooleanField | **Computed:** `start <= now < end` |
| `is_completed` | BooleanField | **Computed:** `end_datetime <= now` |
| `created_by_username` | CharField | **Nested:** Username of creator |
| `created` | DateTimeField | Auto-set on creation |
| `modified` | DateTimeField | Auto-updated on save |

#### Understanding Read-Only Fields

```python
duration_hours = serializers.FloatField(read_only=True)
```

The `read_only=True` parameter means:
- This field appears in **output** (GET responses)
- This field is **ignored** in input (POST/PUT/PATCH requests)
- The value comes from the model's `@property`, not user input

#### Nested Source Syntax

```python
created_by_username = serializers.CharField(
    source="created_by.username",
    read_only=True,
    allow_null=True,
)
```

The `source` parameter navigates object relationships:
- `created_by` is a ForeignKey to the User model
- `.username` accesses the related user's username field
- `allow_null=True` handles cases where `created_by` is None

This pattern avoids nested serializers for simple cases, producing flat JSON:

```json
{
  "id": 1,
  "title": "Scheduled Maintenance",
  "created_by_username": "admin"
}
```

Instead of nested JSON:

```json
{
  "id": 1,
  "title": "Scheduled Maintenance",
  "created_by": { "username": "admin" }
}
```

#### Accessing Model Properties

DRF serializers automatically access model `@property` methods:

```python
# In the model
@property
def is_upcoming(self):
    return timezone.now() < self.start_datetime

# In the serializer - DRF calls the property automatically
is_upcoming = serializers.BooleanField(read_only=True)
```

This works because DRF's field binding uses `getattr()`, which handles both attributes and properties identically.

### 5.4.6 The ViewSet

The ViewSet combines view logic for all CRUD operations into a single class.

```158:190:cf-orcd-rental/coldfront_orcd_direct_charge/api/views.py
class MaintenanceWindowViewSet(viewsets.ModelViewSet):
    """ViewSet for MaintenanceWindow CRUD operations.

    Provides list, create, retrieve, update, and delete actions.
    Requires can_manage_rentals permission.

    Query Parameters:
    - status: Filter by window status (upcoming, in_progress, completed)
    """

    queryset = MaintenanceWindow.objects.all()
    serializer_class = MaintenanceWindowSerializer
    permission_classes = [IsAuthenticated, HasManageRentalsPermission]

    def perform_create(self, serializer):
        """Set created_by to the current user."""
        serializer.save(created_by=self.request.user)

    def get_queryset(self):
        """Optionally filter by upcoming/in_progress/completed windows."""
        queryset = MaintenanceWindow.objects.select_related("created_by").all()

        # Filter by status
        status_filter = self.request.query_params.get("status")
        if status_filter == "upcoming":
            queryset = queryset.filter(start_datetime__gt=timezone.now())
        elif status_filter == "in_progress":
            now = timezone.now()
            queryset = queryset.filter(start_datetime__lte=now, end_datetime__gt=now)
        elif status_filter == "completed":
            queryset = queryset.filter(end_datetime__lte=timezone.now())

        return queryset
```

#### Class Attributes

| Attribute | Purpose |
|-----------|---------|
| `queryset` | Default queryset for all operations |
| `serializer_class` | Serializer for request/response transformation |
| `permission_classes` | List of permission checks (all must pass) |

#### The Permission Class

```43:48:cf-orcd-rental/coldfront_orcd_direct_charge/api/views.py
class HasManageRentalsPermission(permissions.BasePermission):
    """Permission check for can_manage_rentals."""

    def has_permission(self, request, view):
        return request.user.has_perm("coldfront_orcd_direct_charge.can_manage_rentals")
```

This custom permission:
- Extends DRF's `BasePermission` class
- Checks Django's built-in permission system
- Returns `True` (allow) or `False` (deny 403)

The `permission_classes` list is evaluated in order:
1. `IsAuthenticated` - Must be logged in (or 401 Unauthorized)
2. `HasManageRentalsPermission` - Must have the permission (or 403 Forbidden)

#### The `perform_create` Hook

```python
def perform_create(self, serializer):
    """Set created_by to the current user."""
    serializer.save(created_by=self.request.user)
```

This hook intercepts the create process to add server-side data:
- Called after validation, before saving
- `self.request.user` is the authenticated user
- The `created_by` field is excluded from client input

**Why not include `created_by` in the serializer?**

The `created_by` should be:
- Automatically set (not user-provided)
- Based on the authenticated request
- Impossible for clients to forge

Using `perform_create` enforces this server-side, regardless of what the client sends.

#### Dynamic Query Filtering

```python
def get_queryset(self):
    queryset = MaintenanceWindow.objects.select_related("created_by").all()
    
    status_filter = self.request.query_params.get("status")
    if status_filter == "upcoming":
        queryset = queryset.filter(start_datetime__gt=timezone.now())
    # ... other filters
    
    return queryset
```

**Key techniques:**

| Technique | Purpose |
|-----------|---------|
| `select_related("created_by")` | Avoid N+1 queries when serializing `created_by_username` |
| `self.request.query_params` | Access URL query parameters (`?status=upcoming`) |
| Conditional filtering | Apply filters only when requested |
| Always return queryset | Maintain chainability for DRF's pagination/ordering |

**Filter Logic:**

| Status Value | Filter Applied | SQL Equivalent |
|--------------|----------------|----------------|
| `upcoming` | `start_datetime__gt=now()` | `start_datetime > NOW()` |
| `in_progress` | `start_datetime__lte=now, end_datetime__gt=now` | `start <= NOW() < end` |
| `completed` | `end_datetime__lte=now()` | `end_datetime <= NOW()` |

### 5.4.7 URL Registration

The router automatically generates URL patterns for the ViewSet.

```10:13:cf-orcd-rental/coldfront_orcd_direct_charge/api/urls.py
router = routers.DefaultRouter()
router.register(r"rentals", views.ReservationViewSet, basename="rentals")
router.register(r"cost-allocations", views.CostAllocationViewSet, basename="cost-allocations")
router.register(r"maintenance-windows", views.MaintenanceWindowViewSet, basename="maintenance-window")
```

#### How Router Registration Works

```python
router.register(r"maintenance-windows", views.MaintenanceWindowViewSet, basename="maintenance-window")
```

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `prefix` | `"maintenance-windows"` | URL path prefix |
| `viewset` | `MaintenanceWindowViewSet` | ViewSet class to use |
| `basename` | `"maintenance-window"` | Base for URL pattern names |

#### Generated URL Patterns

The `DefaultRouter` automatically generates these endpoints:

| Method | URL | Action | Name |
|--------|-----|--------|------|
| `GET` | `/api/maintenance-windows/` | List all windows | `maintenance-window-list` |
| `POST` | `/api/maintenance-windows/` | Create new window | `maintenance-window-list` |
| `GET` | `/api/maintenance-windows/{id}/` | Retrieve single window | `maintenance-window-detail` |
| `PUT` | `/api/maintenance-windows/{id}/` | Full update | `maintenance-window-detail` |
| `PATCH` | `/api/maintenance-windows/{id}/` | Partial update | `maintenance-window-detail` |
| `DELETE` | `/api/maintenance-windows/{id}/` | Delete window | `maintenance-window-detail` |

The router also adds an API root endpoint that lists all registered endpoints:

```
GET /api/  →  {"rentals": "/api/rentals/", "maintenance-windows": "/api/maintenance-windows/", ...}
```

### 5.4.8 API Usage Examples

#### Authentication

All endpoints require authentication. Use session authentication (for browser) or token authentication (for API clients):

```bash
# Session authentication (use after logging in via web)
curl -b cookies.txt https://example.com/api/maintenance-windows/

# Token authentication (if configured)
curl -H "Authorization: Token YOUR_API_TOKEN" https://example.com/api/maintenance-windows/
```

#### List All Maintenance Windows

```bash
curl -X GET /api/maintenance-windows/ \
  -H "Accept: application/json"
```

**Response:**

```json
[
    {
        "id": 1,
        "title": "Monthly Server Patches",
        "description": "Applying security patches to all servers",
        "start_datetime": "2026-02-15T02:00:00Z",
        "end_datetime": "2026-02-15T06:00:00Z",
        "duration_hours": 4.0,
        "is_upcoming": true,
        "is_in_progress": false,
        "is_completed": false,
        "created_by_username": "admin",
        "created": "2026-01-15T10:30:00Z",
        "modified": "2026-01-15T10:30:00Z"
    },
    {
        "id": 2,
        "title": "Network Upgrade",
        "description": "Upgrading core switches",
        "start_datetime": "2026-01-10T00:00:00Z",
        "end_datetime": "2026-01-10T04:00:00Z",
        "duration_hours": 4.0,
        "is_upcoming": false,
        "is_in_progress": false,
        "is_completed": true,
        "created_by_username": "netops",
        "created": "2026-01-05T14:00:00Z",
        "modified": "2026-01-05T14:00:00Z"
    }
]
```

#### Filter by Status

```bash
# Get only upcoming maintenance windows
curl -X GET "/api/maintenance-windows/?status=upcoming"

# Get windows currently in progress
curl -X GET "/api/maintenance-windows/?status=in_progress"

# Get completed windows
curl -X GET "/api/maintenance-windows/?status=completed"
```

#### Create a Maintenance Window

```bash
curl -X POST /api/maintenance-windows/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Database Migration",
    "description": "Migrating to new database cluster",
    "start_datetime": "2026-03-01T02:00:00Z",
    "end_datetime": "2026-03-01T08:00:00Z"
  }'
```

**Response (201 Created):**

```json
{
    "id": 3,
    "title": "Database Migration",
    "description": "Migrating to new database cluster",
    "start_datetime": "2026-03-01T02:00:00Z",
    "end_datetime": "2026-03-01T08:00:00Z",
    "duration_hours": 6.0,
    "is_upcoming": true,
    "is_in_progress": false,
    "is_completed": false,
    "created_by_username": "admin",
    "created": "2026-01-31T16:45:00Z",
    "modified": "2026-01-31T16:45:00Z"
}
```

Note: `created_by_username` is automatically set from the authenticated user.

#### Retrieve a Single Window

```bash
curl -X GET /api/maintenance-windows/3/
```

**Response:**

```json
{
    "id": 3,
    "title": "Database Migration",
    "description": "Migrating to new database cluster",
    "start_datetime": "2026-03-01T02:00:00Z",
    "end_datetime": "2026-03-01T08:00:00Z",
    "duration_hours": 6.0,
    "is_upcoming": true,
    "is_in_progress": false,
    "is_completed": false,
    "created_by_username": "admin",
    "created": "2026-01-31T16:45:00Z",
    "modified": "2026-01-31T16:45:00Z"
}
```

#### Update a Window (Full Update)

```bash
curl -X PUT /api/maintenance-windows/3/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Database Migration - Extended",
    "description": "Migrating to new database cluster with additional testing",
    "start_datetime": "2026-03-01T02:00:00Z",
    "end_datetime": "2026-03-01T10:00:00Z"
  }'
```

#### Partial Update

```bash
curl -X PATCH /api/maintenance-windows/3/ \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Updated description only"
  }'
```

#### Delete a Window

```bash
curl -X DELETE /api/maintenance-windows/3/
```

**Response:** `204 No Content` (empty body)

#### Error Responses

**401 Unauthorized (not logged in):**

```json
{
    "detail": "Authentication credentials were not provided."
}
```

**403 Forbidden (missing permission):**

```json
{
    "detail": "You do not have permission to perform this action."
}
```

**400 Bad Request (validation error):**

```json
{
    "title": ["This field is required."],
    "end_datetime": ["End datetime must be after start datetime."]
}
```

**404 Not Found:**

```json
{
    "detail": "Not found."
}
```

### 5.4.9 Pattern Parallels

#### In Ruby on Rails with ActiveModelSerializers

```ruby
# app/serializers/maintenance_window_serializer.rb
class MaintenanceWindowSerializer < ActiveModel::Serializer
  attributes :id, :title, :description, :start_datetime, :end_datetime,
             :duration_hours, :is_upcoming, :is_in_progress, :is_completed,
             :created_by_username, :created_at, :updated_at

  def duration_hours
    object.duration_hours  # Calls model method
  end

  def is_upcoming
    object.upcoming?
  end

  def created_by_username
    object.created_by&.username
  end
end

# app/controllers/api/maintenance_windows_controller.rb
class Api::MaintenanceWindowsController < ApplicationController
  before_action :authenticate_user!
  before_action :authorize_rental_manager!
  
  def index
    windows = MaintenanceWindow.all
    windows = apply_status_filter(windows)
    render json: windows
  end
  
  def create
    window = MaintenanceWindow.new(window_params)
    window.created_by = current_user
    
    if window.save
      render json: window, status: :created
    else
      render json: { errors: window.errors }, status: :unprocessable_entity
    end
  end
  
  private
  
  def apply_status_filter(scope)
    case params[:status]
    when "upcoming" then scope.upcoming
    when "in_progress" then scope.in_progress
    when "completed" then scope.completed
    else scope
    end
  end
  
  def window_params
    params.require(:maintenance_window).permit(:title, :description, :start_datetime, :end_datetime)
  end
end

# config/routes.rb
namespace :api do
  resources :maintenance_windows, only: [:index, :show, :create, :update, :destroy]
end
```

**Key Differences:**

| Aspect | DRF | Rails |
|--------|-----|-------|
| Serializer inheritance | `ModelSerializer` provides field introspection | Explicit attribute declaration |
| Computed fields | Automatic from model properties | Must define methods in serializer |
| URL generation | Router generates all patterns | Explicit `resources` in routes |
| ViewSet vs Controller | Single class for all actions | One method per action |

#### In Express.js with a Controller Pattern

```javascript
// controllers/maintenanceWindowController.js
const { MaintenanceWindow } = require('../models');
const { Op } = require('sequelize');

exports.list = async (req, res) => {
  const where = {};
  const now = new Date();
  
  switch (req.query.status) {
    case 'upcoming':
      where.start_datetime = { [Op.gt]: now };
      break;
    case 'in_progress':
      where.start_datetime = { [Op.lte]: now };
      where.end_datetime = { [Op.gt]: now };
      break;
    case 'completed':
      where.end_datetime = { [Op.lte]: now };
      break;
  }
  
  const windows = await MaintenanceWindow.findAll({ where, include: ['createdBy'] });
  res.json(windows.map(serialize));
};

exports.create = async (req, res) => {
  const window = await MaintenanceWindow.create({
    ...req.body,
    createdById: req.user.id
  });
  res.status(201).json(serialize(window));
};

// Helper to serialize with computed fields
function serialize(window) {
  const now = new Date();
  return {
    id: window.id,
    title: window.title,
    description: window.description,
    start_datetime: window.start_datetime,
    end_datetime: window.end_datetime,
    duration_hours: (window.end_datetime - window.start_datetime) / 3600000,
    is_upcoming: window.start_datetime > now,
    is_in_progress: window.start_datetime <= now && window.end_datetime > now,
    is_completed: window.end_datetime <= now,
    created_by_username: window.createdBy?.username,
    created: window.createdAt,
    modified: window.updatedAt
  };
}
```

**Key Differences:**

| Aspect | DRF | Express |
|--------|-----|---------|
| Serialization | Declarative in serializer class | Manual in helper function |
| Computed fields | Automatic from model properties | Calculated in serialize function |
| Permission handling | Declarative `permission_classes` | Middleware functions |
| URL patterns | Auto-generated by router | Manual route definitions |

### 5.4.10 Design Decisions

#### Why ModelViewSet Instead of Individual Views?

| Option | Pros | Cons |
|--------|------|------|
| **ModelViewSet** | All CRUD in one class, router generates URLs | Less explicit, magic can be confusing |
| **Individual APIViews** | Very explicit, easy to understand | More code, manual URL configuration |
| **GenericAPIView + Mixins** | Composable behavior | Verbose, requires understanding mixins |

We chose `ModelViewSet` because:
1. Standard CRUD operations are needed
2. No special action-specific logic
3. Router integration simplifies URL configuration
4. Consistent with other ViewSets in the codebase (`ReservationViewSet`, `CostAllocationViewSet`)

#### Why Custom Permission Class vs Inline Check?

```python
# Our approach - reusable permission class
class HasManageRentalsPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm("coldfront_orcd_direct_charge.can_manage_rentals")

# Alternative - inline in ViewSet (not recommended)
class MaintenanceWindowViewSet(viewsets.ModelViewSet):
    def check_permissions(self, request):
        if not request.user.has_perm("coldfront_orcd_direct_charge.can_manage_rentals"):
            self.permission_denied(request)
```

The custom permission class:
- Is reusable across ViewSets
- Keeps permission logic declarative
- Follows DRF conventions
- Is easier to test independently

#### Why Filter in get_queryset() Instead of Custom Action?

```python
# Our approach - filter in get_queryset()
def get_queryset(self):
    queryset = MaintenanceWindow.objects.all()
    if self.request.query_params.get("status") == "upcoming":
        queryset = queryset.filter(...)
    return queryset

# Alternative - separate endpoints
@action(detail=False, methods=['get'])
def upcoming(self, request):
    windows = MaintenanceWindow.objects.filter(...)
    serializer = self.get_serializer(windows, many=True)
    return Response(serializer.data)
```

Filtering in `get_queryset()`:
- Keeps one endpoint with optional filtering
- More RESTful (`?status=upcoming` vs `/upcoming/`)
- Works with DRF's pagination automatically
- Consistent with DRF conventions (see django-filter)

#### Why Not Use django-filter?

The codebase uses `django-filter` for `ReservationFilter` and `CostAllocationFilter`. For maintenance windows, we used manual filtering because:
- Only one filter parameter (`status`)
- The filter logic is time-based, not simple field matching
- Adding `django-filter` would be overkill for one filter

For more complex filtering needs, `django-filter` would be preferable.

### 5.4.11 Verification

After implementing the API, verify all functionality works:

#### API Endpoint Tests

| Test | Command | Expected Result |
|------|---------|-----------------|
| **List (authenticated)** | `curl -X GET /api/maintenance-windows/` | 200 OK with JSON array |
| **List (unauthenticated)** | `curl -X GET /api/maintenance-windows/` (no auth) | 401 Unauthorized |
| **List (no permission)** | Login as unprivileged user | 403 Forbidden |
| **Create** | `POST /api/maintenance-windows/` with JSON | 201 Created, `created_by_username` set |
| **Retrieve** | `GET /api/maintenance-windows/1/` | 200 OK with single object |
| **Update** | `PUT /api/maintenance-windows/1/` | 200 OK with updated object |
| **Partial Update** | `PATCH /api/maintenance-windows/1/` | 200 OK, only specified fields changed |
| **Delete** | `DELETE /api/maintenance-windows/1/` | 204 No Content |

#### Filter Tests

| Test | Query | Expected Result |
|------|-------|-----------------|
| **Upcoming filter** | `?status=upcoming` | Only windows with `start_datetime > now` |
| **In progress filter** | `?status=in_progress` | Only windows with `start <= now < end` |
| **Completed filter** | `?status=completed` | Only windows with `end_datetime <= now` |
| **No filter** | (no query param) | All windows |
| **Invalid filter** | `?status=invalid` | All windows (ignored) |

#### Computed Field Tests

| Test | Scenario | Expected Result |
|------|----------|-----------------|
| **duration_hours** | Window from 2:00 to 6:00 | `4.0` in response |
| **is_upcoming** | Window starts tomorrow | `true` |
| **is_in_progress** | Window started 1 hour ago, ends in 3 hours | `true` |
| **is_completed** | Window ended yesterday | `true` |
| **created_by_username** | Create as "admin" | `"admin"` in response |

#### Verification Commands

```bash
# Start development server
cd /Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental
python manage.py runserver

# Test URL resolution
python manage.py shell
>>> from django.urls import reverse
>>> reverse('coldfront_orcd_direct_charge:maintenance-window-list')
'/api/maintenance-windows/'
>>> reverse('coldfront_orcd_direct_charge:maintenance-window-detail', args=[1])
'/api/maintenance-windows/1/'

# Browse the API (after login)
# Open browser to: http://localhost:8000/api/maintenance-windows/
# DRF provides a browsable HTML interface for testing

# Test with curl (requires authentication cookie or token)
curl -X GET http://localhost:8000/api/maintenance-windows/ \
  -H "Accept: application/json"
```

#### Automated Testing

```python
# tests/test_api.py
from django.test import TestCase
from django.contrib.auth.models import User, Permission
from rest_framework.test import APIClient
from coldfront_orcd_direct_charge.models import MaintenanceWindow
from django.utils import timezone
from datetime import timedelta

class MaintenanceWindowAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user('testuser', password='testpass')
        permission = Permission.objects.get(codename='can_manage_rentals')
        self.user.user_permissions.add(permission)
        self.client.force_authenticate(user=self.user)
        
    def test_list_windows(self):
        response = self.client.get('/api/maintenance-windows/')
        self.assertEqual(response.status_code, 200)
        
    def test_create_window(self):
        data = {
            'title': 'Test Window',
            'start_datetime': (timezone.now() + timedelta(days=1)).isoformat(),
            'end_datetime': (timezone.now() + timedelta(days=1, hours=4)).isoformat(),
        }
        response = self.client.post('/api/maintenance-windows/', data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['created_by_username'], 'testuser')
        
    def test_filter_upcoming(self):
        # Create upcoming and completed windows
        MaintenanceWindow.objects.create(
            title='Upcoming',
            start_datetime=timezone.now() + timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=1, hours=2),
        )
        MaintenanceWindow.objects.create(
            title='Completed',
            start_datetime=timezone.now() - timedelta(days=2),
            end_datetime=timezone.now() - timedelta(days=1),
        )
        
        response = self.client.get('/api/maintenance-windows/?status=upcoming')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Upcoming')
```

---

> **Summary:** TODO 4 creates a REST API for maintenance windows using Django REST Framework. The `MaintenanceWindowSerializer` transforms model instances to JSON, exposing both database fields and computed properties (`duration_hours`, `is_upcoming`, `is_in_progress`, `is_completed`). The `MaintenanceWindowViewSet` provides full CRUD operations with permission-based access control via `HasManageRentalsPermission`. The `perform_create` hook automatically sets the `created_by` field from the authenticated user. Query parameter filtering (`?status=upcoming|in_progress|completed`) enables dynamic list filtering. URL registration with DRF's `DefaultRouter` automatically generates standard REST endpoints. The implementation follows DRF best practices and maintains consistency with existing API patterns in the codebase.

---

*Continue to [5.5 TODO 5: Create Management Commands](#55-todo-5-create-management-commands) for CLI tools.*

---

## 5.5 TODO 5: Create Management Commands

This section implements Django management commands for maintenance window administration. Management commands provide CLI tools for operations that don't require a web interface, enabling scripting, automation, and administrative tasks from the terminal.

### 5.5.1 Objective

Create command-line tools for maintenance window lifecycle management:
- **Create** new maintenance windows with datetime validation
- **List** existing windows with filtering by status
- **Delete** windows with confirmation safeguards
- Support automation through scriptable interfaces
- Enable dry-run mode for testing operations

### 5.5.2 Prerequisites

This TODO requires completion of:

| Prerequisite | Provides |
|--------------|----------|
| **TODO 1: Model** | `MaintenanceWindow` model with `@property` methods (`is_upcoming`, `is_in_progress`, `is_completed`, `duration_hours`) |

### 5.5.3 Concepts Applied

| Concept | Application |
|---------|-------------|
| **BaseCommand** | Foundation class for all Django management commands |
| **ArgumentParser** | Command-line argument definition and parsing |
| **Output Styling** | Colored terminal output with `self.style` methods |
| **Dry-Run Pattern** | Preview operations without making changes |
| **Confirmation Pattern** | Interactive prompts for destructive operations |
| **Force Flag** | Skip confirmation for automation scenarios |

### 5.5.4 Files Created

| File | Purpose |
|------|---------|
| `management/commands/create_maintenance_window.py` | Create new maintenance windows |
| `management/commands/list_maintenance_windows.py` | List windows with filtering |
| `management/commands/delete_maintenance_window.py` | Delete windows with confirmation |

### 5.5.5 Command Structure Overview

#### Django Management Command Anatomy

Every Django management command follows a standard structure:

```python
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Description shown in 'manage.py help'"
    
    def add_arguments(self, parser):
        """Define command-line arguments using argparse."""
        parser.add_argument('--flag', help='Description')
    
    def handle(self, *args, **options):
        """Execute the command logic."""
        # Access arguments via options dict
        self.stdout.write("Output message")
```

**Key Components:**

| Component | Purpose |
|-----------|---------|
| `class Command` | Must be named exactly `Command` (Django convention) |
| `help` attribute | Short description for `--help` output |
| `add_arguments()` | Defines CLI arguments using argparse |
| `handle()` | Contains main command logic |
| `self.stdout` | Output stream (use instead of `print()`) |
| `self.style` | Terminal styling (SUCCESS, ERROR, WARNING) |

#### File Naming Convention

Commands are discovered by their **file location** and **filename**:

```
app_name/
└── management/
    └── commands/
        └── my_command.py  → python manage.py my_command
```

- The filename becomes the command name (without `.py`)
- Underscores in filenames become the command invocation
- The `management/commands/` directory structure is required
- An `__init__.py` in each directory enables Python package discovery

### 5.5.6 create_maintenance_window Command

This command creates new maintenance windows with comprehensive validation.

```python
# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Django management command to create maintenance windows.

Creates a maintenance window with a start datetime, end datetime, and title.
Maintenance windows define periods when node rentals are not billed.

Examples:
    coldfront create_maintenance_window --start "2026-02-15 00:00" --end "2026-02-16 12:00" --title "Scheduled maintenance"
    coldfront create_maintenance_window --start "2026-02-15 00:00" --end "2026-02-16 12:00" --title "Emergency fix" --description "Fixing power issue"
    coldfront create_maintenance_window --start "2026-02-15 00:00" --end "2026-02-16 12:00" --title "Test window" --dry-run
"""

from datetime import datetime

from django.core.management.base import BaseCommand

from coldfront_orcd_direct_charge.models import MaintenanceWindow


class Command(BaseCommand):
    help = "Create a maintenance window"

    def add_arguments(self, parser):
        parser.add_argument(
            "--start",
            type=str,
            required=True,
            help="Start datetime (YYYY-MM-DD HH:MM format)",
        )
        parser.add_argument(
            "--end",
            type=str,
            required=True,
            help="End datetime (YYYY-MM-DD HH:MM format)",
        )
        parser.add_argument(
            "--title",
            type=str,
            required=True,
            help="Title for the maintenance window",
        )
        parser.add_argument(
            "--description",
            type=str,
            default="",
            help="Optional description for the maintenance window",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without making changes",
        )

    def handle(self, *args, **options):
        start_str = options["start"]
        end_str = options["end"]
        title = options["title"]
        description = options["description"]
        dry_run = options["dry_run"]

        # Parse start datetime
        try:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M")
        except ValueError:
            self.stdout.write(
                self.style.ERROR(
                    f"Invalid start datetime format: '{start_str}'. "
                    "Expected YYYY-MM-DD HH:MM (e.g., '2026-02-15 00:00')"
                )
            )
            return

        # Parse end datetime
        try:
            end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M")
        except ValueError:
            self.stdout.write(
                self.style.ERROR(
                    f"Invalid end datetime format: '{end_str}'. "
                    "Expected YYYY-MM-DD HH:MM (e.g., '2026-02-16 12:00')"
                )
            )
            return

        # Validate end > start
        if end_dt <= start_dt:
            self.stdout.write(
                self.style.ERROR("End datetime must be after start datetime")
            )
            return

        # Calculate duration
        duration_hours = (end_dt - start_dt).total_seconds() / 3600

        # Dry-run mode
        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY-RUN] Would create:"))
            self.stdout.write(f"  Title: {title}")
            self.stdout.write(f"  Start: {start_dt.strftime('%Y-%m-%d %H:%M')}")
            self.stdout.write(f"  End: {end_dt.strftime('%Y-%m-%d %H:%M')}")
            self.stdout.write(f"  Duration: {duration_hours:.1f} hours")
            if description:
                self.stdout.write(f"  Description: {description}")
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("[DRY-RUN] No changes made."))
            return

        # Create the maintenance window
        window = MaintenanceWindow.objects.create(
            title=title,
            description=description,
            start_datetime=start_dt,
            end_datetime=end_dt,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created maintenance window #{window.pk}: {window.title}"
            )
        )
        self.stdout.write(f"  Start: {window.start_datetime.strftime('%Y-%m-%d %H:%M')}")
        self.stdout.write(f"  End: {window.end_datetime.strftime('%Y-%m-%d %H:%M')}")
        self.stdout.write(f"  Duration: {window.duration_hours:.1f} hours")
```

#### Argument Breakdown

| Argument | Type | Required | Purpose |
|----------|------|----------|---------|
| `--start` | string | Yes | Start datetime in `YYYY-MM-DD HH:MM` format |
| `--end` | string | Yes | End datetime in `YYYY-MM-DD HH:MM` format |
| `--title` | string | Yes | Descriptive title for the window |
| `--description` | string | No | Optional detailed description |
| `--dry-run` | flag | No | Preview without creating |

#### Datetime Parsing Pattern

```python
try:
    start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M")
except ValueError:
    self.stdout.write(
        self.style.ERROR(
            f"Invalid start datetime format: '{start_str}'. "
            "Expected YYYY-MM-DD HH:MM (e.g., '2026-02-15 00:00')"
        )
    )
    return
```

**Key Design Decisions:**

1. **String Input**: Arguments are strings, not datetime objects, for shell compatibility
2. **Explicit Format**: `%Y-%m-%d %H:%M` provides unambiguous parsing
3. **Helpful Errors**: Error messages include the invalid input AND an example of valid input
4. **Early Return**: Invalid input stops execution immediately (fail fast)

#### Dry-Run Pattern

```python
if dry_run:
    self.stdout.write(self.style.WARNING("[DRY-RUN] Would create:"))
    # ... show what would happen ...
    self.stdout.write(self.style.WARNING("[DRY-RUN] No changes made."))
    return
```

The dry-run pattern enables:
- **Testing**: Verify command behavior before committing changes
- **Automation**: Preview operations in CI/CD pipelines
- **Documentation**: Show users exactly what will happen
- **Safety**: Catch configuration errors before database changes

The `[DRY-RUN]` prefix in output clearly distinguishes preview from actual execution.

#### Output Styling

```python
self.stdout.write(self.style.SUCCESS("Success message"))
self.stdout.write(self.style.ERROR("Error message"))
self.stdout.write(self.style.WARNING("Warning message"))
```

| Style | Color | Use Case |
|-------|-------|----------|
| `SUCCESS` | Green | Operation completed successfully |
| `ERROR` | Red | Operation failed |
| `WARNING` | Yellow | Caution, dry-run, or attention needed |
| `NOTICE` | Cyan | Informational highlights |

### 5.5.7 list_maintenance_windows Command

This command displays maintenance windows with flexible filtering options.

```python
# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Django management command to list maintenance windows.

Lists maintenance windows with their ID, title, dates, duration, and status.
Supports filtering by status (upcoming, in_progress, completed).

Examples:
    coldfront list_maintenance_windows
    coldfront list_maintenance_windows --upcoming
    coldfront list_maintenance_windows --status in_progress
    coldfront list_maintenance_windows --status completed
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from coldfront_orcd_direct_charge.models import MaintenanceWindow


class Command(BaseCommand):
    help = "List maintenance windows"

    def add_arguments(self, parser):
        parser.add_argument(
            "--upcoming",
            action="store_true",
            help="Show only upcoming (future) windows",
        )
        parser.add_argument(
            "--status",
            type=str,
            choices=["upcoming", "in_progress", "completed"],
            help="Filter by status: upcoming, in_progress, or completed",
        )

    def handle(self, *args, **options):
        queryset = MaintenanceWindow.objects.all()
        now = timezone.now()

        # Apply filters
        if options["upcoming"] or options["status"] == "upcoming":
            queryset = queryset.filter(start_datetime__gt=now)
            filter_label = "upcoming"
        elif options["status"] == "in_progress":
            queryset = queryset.filter(start_datetime__lte=now, end_datetime__gt=now)
            filter_label = "in progress"
        elif options["status"] == "completed":
            queryset = queryset.filter(end_datetime__lte=now)
            filter_label = "completed"
        else:
            filter_label = None

        # Order by start datetime (most recent first for completed, earliest first for upcoming)
        if options["status"] == "completed":
            queryset = queryset.order_by("-start_datetime")
        else:
            queryset = queryset.order_by("start_datetime")

        if not queryset.exists():
            if filter_label:
                self.stdout.write(f"No {filter_label} maintenance windows found.")
            else:
                self.stdout.write("No maintenance windows found.")
            return

        # Header
        count = queryset.count()
        if filter_label:
            self.stdout.write(f"Found {count} {filter_label} maintenance window(s):")
        else:
            self.stdout.write(f"Found {count} maintenance window(s):")
        self.stdout.write("")

        # List windows
        for window in queryset:
            # Determine status
            if window.is_upcoming:
                status = "UPCOMING"
                status_style = self.style.SUCCESS
            elif window.is_in_progress:
                status = "IN PROGRESS"
                status_style = self.style.WARNING
            else:
                status = "COMPLETED"
                status_style = lambda x: x  # noqa: E731 - no styling for completed

            start_str = window.start_datetime.strftime("%Y-%m-%d %H:%M")
            end_str = window.end_datetime.strftime("%Y-%m-%d %H:%M")

            self.stdout.write(
                f"#{window.pk}: {window.title}"
            )
            self.stdout.write(
                f"    {start_str} - {end_str} | "
                f"{window.duration_hours:.1f}h | "
                f"{status_style(status)}"
            )
            if window.description:
                # Truncate long descriptions
                desc = window.description[:80]
                if len(window.description) > 80:
                    desc += "..."
                self.stdout.write(f"    {desc}")
            self.stdout.write("")
```

#### Argument Breakdown

| Argument | Type | Purpose |
|----------|------|---------|
| `--upcoming` | flag | Shortcut for `--status upcoming` |
| `--status` | choice | Filter: `upcoming`, `in_progress`, or `completed` |

#### Filter Logic

```python
if options["upcoming"] or options["status"] == "upcoming":
    queryset = queryset.filter(start_datetime__gt=now)
```

The `--upcoming` flag provides a convenient shorthand. Both `--upcoming` and `--status upcoming` produce identical results, offering flexibility in usage.

#### Status-Aware Ordering

```python
if options["status"] == "completed":
    queryset = queryset.order_by("-start_datetime")  # Most recent first
else:
    queryset = queryset.order_by("start_datetime")   # Earliest first
```

**Ordering Rationale:**
- **Completed**: Most recent completions are typically more relevant
- **Upcoming/In-Progress**: Earliest (soonest) events need attention first

#### Dynamic Status Styling

```python
if window.is_upcoming:
    status = "UPCOMING"
    status_style = self.style.SUCCESS
elif window.is_in_progress:
    status = "IN PROGRESS"
    status_style = self.style.WARNING
else:
    status = "COMPLETED"
    status_style = lambda x: x  # No styling
```

The styling function is assigned dynamically, then applied:

```python
f"{status_style(status)}"
```

This pattern allows consistent styling application regardless of status type. The `lambda x: x` identity function applies no styling for completed windows.

#### Output Formatting

```
#1: Scheduled Maintenance
    2026-02-15 00:00 - 2026-02-16 12:00 | 36.0h | UPCOMING
    Power system upgrade for the cluster

#2: Emergency Fix
    2026-02-10 08:00 - 2026-02-10 14:00 | 6.0h | COMPLETED
```

The format provides:
- **ID prefix** (`#1`): Easy reference for delete/update operations
- **Title**: Primary identifier
- **Date range**: Start and end times
- **Duration**: Calculated hours
- **Status**: Color-coded current state
- **Description**: Truncated to 80 characters if present

### 5.5.8 delete_maintenance_window Command

This command safely deletes maintenance windows with confirmation prompts.

```python
# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Django management command to delete maintenance windows.

Deletes a maintenance window by ID. Requires confirmation unless --force is used.

Examples:
    coldfront delete_maintenance_window 1
    coldfront delete_maintenance_window 1 --force
"""

from django.core.management.base import BaseCommand

from coldfront_orcd_direct_charge.models import MaintenanceWindow


class Command(BaseCommand):
    help = "Delete a maintenance window"

    def add_arguments(self, parser):
        parser.add_argument(
            "window_id",
            type=int,
            help="ID of the maintenance window to delete",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip confirmation prompt",
        )

    def handle(self, *args, **options):
        window_id = options["window_id"]
        force = options["force"]

        # Look up the maintenance window
        try:
            window = MaintenanceWindow.objects.get(pk=window_id)
        except MaintenanceWindow.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Maintenance window #{window_id} not found")
            )
            return

        # Display window details
        start_str = window.start_datetime.strftime("%Y-%m-%d %H:%M")
        end_str = window.end_datetime.strftime("%Y-%m-%d %H:%M")

        # Determine status for display
        if window.is_upcoming:
            status = "UPCOMING"
        elif window.is_in_progress:
            status = "IN PROGRESS"
        else:
            status = "COMPLETED"

        if not force:
            self.stdout.write("About to delete maintenance window:")
            self.stdout.write(f"  ID: #{window.pk}")
            self.stdout.write(f"  Title: {window.title}")
            self.stdout.write(f"  Period: {start_str} - {end_str}")
            self.stdout.write(f"  Duration: {window.duration_hours:.1f} hours")
            self.stdout.write(f"  Status: {status}")
            if window.description:
                self.stdout.write(f"  Description: {window.description}")
            self.stdout.write("")

            confirm = input("Type 'yes' to confirm deletion: ")
            if confirm.lower() != "yes":
                self.stdout.write("Cancelled.")
                return

        # Store for message after deletion
        window_title = window.title

        # Delete the window
        window.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted maintenance window #{window_id}: {window_title}"
            )
        )
```

#### Argument Breakdown

| Argument | Type | Position | Purpose |
|----------|------|----------|---------|
| `window_id` | int | Positional | ID of window to delete (required) |
| `--force` | flag | Optional | Skip confirmation prompt |

#### Positional vs Named Arguments

```python
parser.add_argument(
    "window_id",        # No leading dashes = positional argument
    type=int,
    help="ID of the maintenance window to delete",
)
```

Positional arguments:
- Are **required** by default
- Must appear in order on the command line
- Don't use `--` prefix in invocation
- Example: `delete_maintenance_window 42` (not `--window-id 42`)

#### Confirmation Pattern

```python
if not force:
    self.stdout.write("About to delete maintenance window:")
    # ... display details ...
    confirm = input("Type 'yes' to confirm deletion: ")
    if confirm.lower() != "yes":
        self.stdout.write("Cancelled.")
        return
```

**Confirmation Design:**

1. **Show Details First**: User sees exactly what will be deleted
2. **Explicit Confirmation**: Typing "yes" is intentional (not just pressing Enter)
3. **Case Insensitive**: Accepts "yes", "Yes", "YES"
4. **Cancellation Message**: Confirms the operation was aborted

#### Force Flag for Automation

```python
parser.add_argument(
    "--force",
    action="store_true",
    help="Skip confirmation prompt",
)
```

The `--force` flag enables:
- **Scripting**: Automated cleanup without interactive prompts
- **CI/CD**: Programmatic deletion in pipelines
- **Bulk Operations**: Combined with shell loops for mass deletion

```bash
# Delete multiple windows in a script
for id in 1 2 3 4 5; do
    python manage.py delete_maintenance_window $id --force
done
```

#### Error Handling for Missing Records

```python
try:
    window = MaintenanceWindow.objects.get(pk=window_id)
except MaintenanceWindow.DoesNotExist:
    self.stdout.write(
        self.style.ERROR(f"Maintenance window #{window_id} not found")
    )
    return
```

Using `get()` with exception handling is preferred over `filter().first()` because:
- Clear intent: expecting exactly one result
- Explicit error handling for the "not found" case
- Appropriate for ID-based lookups where existence is uncertain

### 5.5.9 Usage Examples

#### Creating Maintenance Windows

```bash
# Basic creation
python manage.py create_maintenance_window \
    --start "2026-02-15 00:00" \
    --end "2026-02-16 12:00" \
    --title "Scheduled Maintenance"

# With description
python manage.py create_maintenance_window \
    --start "2026-02-15 00:00" \
    --end "2026-02-16 12:00" \
    --title "Emergency Fix" \
    --description "Repairing failed storage controller"

# Dry-run to preview
python manage.py create_maintenance_window \
    --start "2026-02-15 00:00" \
    --end "2026-02-16 12:00" \
    --title "Test Window" \
    --dry-run
```

#### Listing Maintenance Windows

```bash
# List all windows
python manage.py list_maintenance_windows

# Only upcoming windows
python manage.py list_maintenance_windows --upcoming

# Filter by status
python manage.py list_maintenance_windows --status in_progress
python manage.py list_maintenance_windows --status completed
```

#### Deleting Maintenance Windows

```bash
# Interactive deletion (with confirmation)
python manage.py delete_maintenance_window 1

# Force deletion (no prompt)
python manage.py delete_maintenance_window 1 --force
```

#### Combined Workflow

```bash
# 1. Preview creation
python manage.py create_maintenance_window \
    --start "2026-03-01 00:00" \
    --end "2026-03-01 08:00" \
    --title "Network Upgrade" \
    --dry-run

# 2. Actually create
python manage.py create_maintenance_window \
    --start "2026-03-01 00:00" \
    --end "2026-03-01 08:00" \
    --title "Network Upgrade"

# 3. Verify creation
python manage.py list_maintenance_windows --upcoming

# 4. If needed, delete
python manage.py delete_maintenance_window 3
```

### 5.5.10 Pattern Parallels

This implementation follows patterns from existing management commands in the ColdFront ecosystem:

| Pattern | Our Implementation | Existing Example |
|---------|-------------------|------------------|
| Datetime string parsing | `--start "YYYY-MM-DD HH:MM"` | Billing period commands |
| Dry-run mode | `--dry-run` flag | `calculate_billing --dry-run` |
| Force deletion | `--force` flag | Various cleanup commands |
| Status filtering | `--status upcoming` | Allocation list commands |
| Styled output | `self.style.SUCCESS/ERROR` | All ColdFront commands |
| Positional ID argument | `delete_maintenance_window 1` | User/allocation commands |

### 5.5.11 Design Decisions

#### Why Management Commands Instead of Just API?

| Consideration | Management Command | REST API |
|---------------|-------------------|----------|
| **Shell scripting** | Native integration | Requires curl/httpie |
| **Authentication** | Uses Django settings | Requires tokens/sessions |
| **Database access** | Direct, no HTTP overhead | HTTP + serialization |
| **Cron jobs** | Simple invocation | Needs API client setup |
| **Interactive use** | Prompts supported | No interaction |
| **Bulk operations** | Shell loops | Multiple HTTP requests |

Both interfaces are valuable; they serve different use cases.

#### Why String Arguments for Datetimes?

```python
parser.add_argument("--start", type=str, ...)  # Not type=datetime
```

1. **Shell Compatibility**: Shells pass strings; argparse custom types add complexity
2. **Error Handling**: Custom parsing provides better error messages
3. **Flexibility**: Easier to add multiple format support later
4. **Explicitness**: User sees exact format expectation in help

#### Why Separate Commands vs Subcommands?

We use three separate commands:
- `create_maintenance_window`
- `list_maintenance_windows`
- `delete_maintenance_window`

Instead of subcommands:
- `maintenance_window create`
- `maintenance_window list`
- `maintenance_window delete`

**Rationale:**
- Django's management command system doesn't natively support subcommands
- Separate files are easier to maintain and test independently
- Tab completion works better with full command names
- Follows existing ColdFront patterns

### 5.5.12 Verification

#### Command Discovery

```bash
# Verify commands are registered
python manage.py help | grep maintenance

# Expected output:
#     create_maintenance_window
#     delete_maintenance_window
#     list_maintenance_windows
```

#### Help Text

```bash
# View command help
python manage.py create_maintenance_window --help
python manage.py list_maintenance_windows --help
python manage.py delete_maintenance_window --help
```

#### Functional Testing

```bash
# Create a test window (dry-run first)
python manage.py create_maintenance_window \
    --start "2026-12-01 00:00" \
    --end "2026-12-01 04:00" \
    --title "Verification Test" \
    --dry-run

# Create for real
python manage.py create_maintenance_window \
    --start "2026-12-01 00:00" \
    --end "2026-12-01 04:00" \
    --title "Verification Test"

# List to find the ID
python manage.py list_maintenance_windows --upcoming

# Delete (note the ID from list output)
python manage.py delete_maintenance_window <ID>
```

#### Unit Testing

```python
# tests/test_management_commands.py
from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from coldfront_orcd_direct_charge.models import MaintenanceWindow


class CreateMaintenanceWindowCommandTest(TestCase):
    def test_create_window(self):
        out = StringIO()
        call_command(
            'create_maintenance_window',
            '--start', '2026-12-01 00:00',
            '--end', '2026-12-01 04:00',
            '--title', 'Test Window',
            stdout=out,
        )
        self.assertIn('Created maintenance window', out.getvalue())
        self.assertEqual(MaintenanceWindow.objects.count(), 1)
        
    def test_dry_run_does_not_create(self):
        out = StringIO()
        call_command(
            'create_maintenance_window',
            '--start', '2026-12-01 00:00',
            '--end', '2026-12-01 04:00',
            '--title', 'Test Window',
            '--dry-run',
            stdout=out,
        )
        self.assertIn('DRY-RUN', out.getvalue())
        self.assertEqual(MaintenanceWindow.objects.count(), 0)
        
    def test_invalid_datetime_format(self):
        out = StringIO()
        call_command(
            'create_maintenance_window',
            '--start', 'invalid',
            '--end', '2026-12-01 04:00',
            '--title', 'Test',
            stdout=out,
        )
        self.assertIn('Invalid start datetime', out.getvalue())


class ListMaintenanceWindowsCommandTest(TestCase):
    def setUp(self):
        now = timezone.now()
        # Create windows in different states
        MaintenanceWindow.objects.create(
            title='Upcoming',
            start_datetime=now + timedelta(days=1),
            end_datetime=now + timedelta(days=1, hours=4),
        )
        MaintenanceWindow.objects.create(
            title='Completed',
            start_datetime=now - timedelta(days=2),
            end_datetime=now - timedelta(days=1),
        )
        
    def test_list_all(self):
        out = StringIO()
        call_command('list_maintenance_windows', stdout=out)
        self.assertIn('2 maintenance window(s)', out.getvalue())
        
    def test_filter_upcoming(self):
        out = StringIO()
        call_command('list_maintenance_windows', '--upcoming', stdout=out)
        self.assertIn('Upcoming', out.getvalue())
        self.assertNotIn('Completed', out.getvalue())


class DeleteMaintenanceWindowCommandTest(TestCase):
    def test_delete_with_force(self):
        window = MaintenanceWindow.objects.create(
            title='To Delete',
            start_datetime=timezone.now() + timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=1, hours=4),
        )
        out = StringIO()
        call_command(
            'delete_maintenance_window',
            str(window.pk),
            '--force',
            stdout=out,
        )
        self.assertIn('Deleted maintenance window', out.getvalue())
        self.assertEqual(MaintenanceWindow.objects.count(), 0)
        
    def test_delete_nonexistent(self):
        out = StringIO()
        call_command('delete_maintenance_window', '99999', '--force', stdout=out)
        self.assertIn('not found', out.getvalue())
```

---

> **Summary:** TODO 5 creates Django management commands for maintenance window administration. Three commands provide CLI access to core operations: `create_maintenance_window` handles window creation with datetime validation and dry-run preview capability; `list_maintenance_windows` displays windows with status-based filtering and colored output; `delete_maintenance_window` removes windows with interactive confirmation or force mode for automation. The commands follow Django conventions (BaseCommand inheritance, add_arguments/handle methods, styled output) and implement common CLI patterns (dry-run, force flags, positional arguments). These tools enable scripting, cron job integration, and quick administrative tasks without requiring web interface access.

---

*Continue to [5.6 TODO 6: Add Export/Import to Backup System](#56-todo-6-add-exportimport-to-backup-system) for data portability.*

---

## 5.6 TODO 6: Add Export/Import to Backup System

This section implements export and import functionality for maintenance windows within the portal's backup system. This enables data portability between portal instances, disaster recovery, and staging-to-production data synchronization.

### 5.6.1 Objective

Enable data portability for maintenance windows:
- **Export** maintenance window data to portable JSON format
- **Import** maintenance windows from backup files into new or existing systems
- Integrate with the existing component-based backup architecture
- Support round-trip data migration without data loss
- Handle conflict resolution for duplicate records

### 5.6.2 Prerequisites

This TODO requires completion of:

| Prerequisite | Provides |
|--------------|----------|
| **TODO 1: Model** | `MaintenanceWindow` model with all fields to export/import |

### 5.6.3 Concepts Applied

| Concept | Application |
|---------|-------------|
| **Registry Pattern** | Auto-registration via `@ExporterRegistry.register` decorator |
| **BaseExporter** | Abstract base class defining export interface |
| **BaseImporter** | Abstract base class defining import interface |
| **Natural Keys** | Database-agnostic record identification (title + start_datetime) |
| **FK Resolution** | Resolving `created_by` foreign key by username |
| **Conflict Resolution** | Create vs update logic based on natural key matching |
| **Dependency Declaration** | Empty dependencies list (standalone model) |

### 5.6.4 Files Created/Modified

| File | Purpose |
|------|---------|
| `backup/exporters/maintenance.py` | MaintenanceWindowExporter class |
| `backup/importers/maintenance.py` | MaintenanceWindowImporter class |
| `backup/__init__.py` | Registry exports (already configured) |

### 5.6.5 Backup System Architecture

#### How the Registry Pattern Works

The backup system uses a **registry pattern** to discover and manage exporters/importers automatically. This eliminates manual configuration and ensures all components are processed in the correct dependency order.

```
                    ┌─────────────────────────────────────────┐
                    │          ExporterRegistry               │
                    │  ┌────────────────────────────────────┐ │
                    │  │ _exporters = {                     │ │
                    │  │   "node_types": NodeTypeExporter,  │ │
                    │  │   "reservations": ReservationExp., │ │
                    │  │   "maintenance_windows": MaintExp. │ │
                    │  │ }                                  │ │
                    │  └────────────────────────────────────┘ │
                    └─────────────────────────────────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
            @register            @register          @register
    ┌───────────────────┐ ┌──────────────────┐ ┌──────────────────┐
    │ NodeTypeExporter  │ │ ReservationExp.  │ │ MaintenanceExp.  │
    │ dependencies: []  │ │ deps: [nodes]    │ │ dependencies: [] │
    └───────────────────┘ └──────────────────┘ └──────────────────┘
```

**Registration Mechanism:**

```python
@ExporterRegistry.register
class MaintenanceWindowExporter(BaseExporter):
    model_name = "maintenance_windows"  # Unique identifier
    dependencies = []                    # What must be exported first
```

The `@register` decorator:
1. Validates that `model_name` is defined
2. Adds the exporter class to the registry dictionary
3. Returns the class unchanged (transparent decoration)

#### Component-Based Export/Import

The backup system organizes exporters/importers into components:

| Component | Registry | Models |
|-----------|----------|--------|
| `coldfront_core` | `CoreExporterRegistry` | Users, Projects, Allocations |
| `orcd_plugin` | `PluginExporterRegistry` | NodeTypes, Reservations, MaintenanceWindows |

MaintenanceWindow uses `PluginExporterRegistry` since it's part of the ORCD plugin, not ColdFront core.

#### Dependency Resolution

When exporting/importing, the registry performs **topological sorting** to ensure dependencies are processed first:

```python
# Registry sorts exporters by dependencies
exporters = PluginExporterRegistry.get_ordered_exporters()
# Result: [NodeTypeExporter, MaintenanceWindowExporter, ...]
# (dependencies first, then dependents)
```

MaintenanceWindow has `dependencies = []` because it doesn't reference other plugin models (only Django's auth.User, which is in a different component).

### 5.6.6 The Exporter

The exporter transforms MaintenanceWindow model instances into portable JSON format.

```python
# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Exporters for maintenance-related models.

Models exported:
    - MaintenanceWindow: Scheduled maintenance periods
"""

from typing import Any, Dict

from ..base import BaseExporter
from ..registry import ExporterRegistry
from ..utils import serialize_datetime
from ...models import MaintenanceWindow


@ExporterRegistry.register
class MaintenanceWindowExporter(BaseExporter):
    """Exporter for MaintenanceWindow model.
    
    MaintenanceWindow defines scheduled maintenance periods during which
    rentals are not billed. Uses a composite natural key of title and
    start_datetime for uniqueness.
    """
    
    model_name = "maintenance_windows"
    dependencies = []
    
    def get_queryset(self):
        """Return all maintenance windows ordered by start datetime."""
        return MaintenanceWindow.objects.select_related(
            "created_by"
        ).order_by("-start_datetime")
    
    def serialize_record(self, instance: MaintenanceWindow) -> Dict[str, Any]:
        """Serialize MaintenanceWindow to dict.
        
        Uses a tuple of (title, start_datetime ISO string) as natural key
        since the combination is typically unique.
        """
        return {
            "natural_key": (
                instance.title,
                serialize_datetime(instance.start_datetime),
            ),
            "fields": {
                "title": instance.title,
                "description": instance.description,
                "start_datetime": serialize_datetime(instance.start_datetime),
                "end_datetime": serialize_datetime(instance.end_datetime),
                "created_by_username": (
                    instance.created_by.username if instance.created_by else None
                ),
                "created": serialize_datetime(instance.created),
                "modified": serialize_datetime(instance.modified),
            }
        }
```

#### Required Attributes

| Attribute | Value | Purpose |
|-----------|-------|---------|
| `model_name` | `"maintenance_windows"` | Unique identifier for registry and output filename |
| `dependencies` | `[]` | Empty list—no other plugin models required first |

#### get_queryset Method

```python
def get_queryset(self):
    return MaintenanceWindow.objects.select_related(
        "created_by"
    ).order_by("-start_datetime")
```

**Key Decisions:**

1. **select_related("created_by")**: Pre-fetches the User object in a single query, avoiding N+1 queries when serializing many records
2. **order_by("-start_datetime")**: Most recent first provides deterministic ordering for diff comparisons between exports
3. **No filtering**: Exports all windows (completed, in-progress, upcoming) for complete backup

#### serialize_record Method

This method converts a single MaintenanceWindow instance to a dictionary suitable for JSON serialization.

**Structure:**

```python
{
    "natural_key": ("February Maintenance", "2026-02-15T00:00:00+00:00"),
    "fields": {
        "title": "February Maintenance",
        "description": "Scheduled downtime",
        "start_datetime": "2026-02-15T00:00:00+00:00",
        "end_datetime": "2026-02-16T12:00:00+00:00",
        "created_by_username": "admin",
        "created": "2026-01-10T14:30:00+00:00",
        "modified": "2026-01-10T14:30:00+00:00"
    }
}
```

#### Natural Key Design

Natural keys identify records across databases without relying on auto-increment primary keys:

```python
"natural_key": (
    instance.title,
    serialize_datetime(instance.start_datetime),
)
```

**Why (title, start_datetime)?**

| Alternative | Problem |
|-------------|---------|
| Primary key (pk) | Different between databases |
| Title alone | Could have duplicate titles |
| start_datetime alone | Unlikely but could overlap |
| **Title + start_datetime** | Practically unique—same maintenance event won't have same title and exact start time |

**Datetime Serialization:**

```python
from ..utils import serialize_datetime
# Converts datetime to ISO 8601 string: "2026-02-15T00:00:00+00:00"
```

Using ISO format ensures:
- Timezone information is preserved
- Cross-platform compatibility
- Human readability in export files
- Precise round-trip parsing

#### Foreign Key Handling

```python
"created_by_username": (
    instance.created_by.username if instance.created_by else None
),
```

Foreign keys are serialized as natural keys (username, not user ID) because:
- User IDs differ between database instances
- Usernames are stable identifiers across systems
- `None` is valid (optional foreign key)

### 5.6.7 The Importer

The importer reads JSON data and creates or updates MaintenanceWindow records.

```python
# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Importers for maintenance-related models.

Models imported:
    - MaintenanceWindow: Scheduled maintenance periods
"""

from typing import Any, Dict, Optional
import logging

from ..base import BaseImporter
from ..registry import ImporterRegistry
from ..utils import deserialize_datetime, get_user_by_username
from ...models import MaintenanceWindow

logger = logging.getLogger(__name__)


@ImporterRegistry.register
class MaintenanceWindowImporter(BaseImporter):
    """Importer for MaintenanceWindow model.
    
    Uses a composite natural key of (title, start_datetime) for matching.
    The created_by field is resolved by username if provided.
    """
    
    model_name = "maintenance_windows"
    dependencies = []
    
    def get_existing(self, natural_key) -> Optional[MaintenanceWindow]:
        """Find existing MaintenanceWindow by title and start_datetime.
        
        The natural key is a tuple of (title, start_datetime ISO string).
        """
        if natural_key is None:
            return None
        
        if isinstance(natural_key, (list, tuple)) and len(natural_key) >= 2:
            title = natural_key[0]
            start_datetime_str = natural_key[1]
            start_datetime = deserialize_datetime(start_datetime_str)
            
            if title and start_datetime:
                try:
                    return MaintenanceWindow.objects.get(
                        title=title,
                        start_datetime=start_datetime,
                    )
                except MaintenanceWindow.DoesNotExist:
                    return None
        
        return None
    
    def deserialize_record(self, data: Dict[str, Any]) -> MaintenanceWindow:
        """Create unsaved MaintenanceWindow from data."""
        fields = data.get("fields", {})
        
        # Resolve created_by foreign key by username
        created_by = None
        created_by_username = fields.get("created_by_username")
        if created_by_username:
            created_by = get_user_by_username(created_by_username)
        
        return MaintenanceWindow(
            title=fields["title"],
            description=fields.get("description", ""),
            start_datetime=deserialize_datetime(fields["start_datetime"]),
            end_datetime=deserialize_datetime(fields["end_datetime"]),
            created_by=created_by,
        )
    
    def create_record(self, data: Dict[str, Any]) -> MaintenanceWindow:
        """Create and save new MaintenanceWindow."""
        instance = self.deserialize_record(data)
        instance.save()
        logger.debug(f"Created MaintenanceWindow: {instance.title}")
        return instance
    
    def update_record(
        self, existing: MaintenanceWindow, data: Dict[str, Any]
    ) -> MaintenanceWindow:
        """Update existing MaintenanceWindow."""
        fields = data.get("fields", {})
        
        existing.title = fields.get("title", existing.title)
        existing.description = fields.get("description", existing.description)
        
        start_datetime = deserialize_datetime(fields.get("start_datetime"))
        if start_datetime:
            existing.start_datetime = start_datetime
        
        end_datetime = deserialize_datetime(fields.get("end_datetime"))
        if end_datetime:
            existing.end_datetime = end_datetime
        
        # Update created_by if username is provided
        created_by_username = fields.get("created_by_username")
        if created_by_username:
            created_by = get_user_by_username(created_by_username)
            if created_by:
                existing.created_by = created_by
        
        existing.save()
        
        logger.debug(f"Updated MaintenanceWindow: {existing.title}")
        return existing
```

#### Conflict Resolution via get_existing

The `get_existing` method determines whether an imported record already exists:

```python
def get_existing(self, natural_key) -> Optional[MaintenanceWindow]:
    # Parse composite natural key
    if isinstance(natural_key, (list, tuple)) and len(natural_key) >= 2:
        title = natural_key[0]
        start_datetime_str = natural_key[1]
        start_datetime = deserialize_datetime(start_datetime_str)
        
        # Look up by both fields
        try:
            return MaintenanceWindow.objects.get(
                title=title,
                start_datetime=start_datetime,
            )
        except MaintenanceWindow.DoesNotExist:
            return None
```

**Conflict Resolution Flow:**

```
Import Record
     │
     ▼
get_existing(natural_key)
     │
     ├── Found? ──────────► update_record()
     │
     └── Not Found? ──────► create_record()
```

The base `import_records` method uses this to decide:
- **Create mode**: Only create if not found
- **Update mode**: Only update if found
- **Create-or-update mode**: Create if new, update if exists (default)

#### FK Resolution by Username

```python
def deserialize_record(self, data: Dict[str, Any]) -> MaintenanceWindow:
    fields = data.get("fields", {})
    
    # Resolve created_by foreign key by username
    created_by = None
    created_by_username = fields.get("created_by_username")
    if created_by_username:
        created_by = get_user_by_username(created_by_username)
```

The `get_user_by_username` utility:
1. Looks up User by username in the target database
2. Returns `None` if user doesn't exist (graceful degradation)
3. Allows import even when referenced user is missing

**Why not fail on missing user?**

- Import might happen before user sync
- Missing FK is acceptable (nullable field)
- Better to import with warning than fail entirely

#### Update Record with Partial Updates

```python
def update_record(self, existing: MaintenanceWindow, data: Dict[str, Any]):
    fields = data.get("fields", {})
    
    # Update fields with fallback to existing values
    existing.title = fields.get("title", existing.title)
    existing.description = fields.get("description", existing.description)
```

This pattern:
- Updates only fields present in import data
- Preserves existing values if field is missing
- Handles partial exports gracefully

### 5.6.8 Registry Registration

Both exporter and importer use decorator-based registration:

```python
# Exporter registration
from ..registry import ExporterRegistry

@ExporterRegistry.register
class MaintenanceWindowExporter(BaseExporter):
    model_name = "maintenance_windows"
    ...

# Importer registration
from ..registry import ImporterRegistry

@ImporterRegistry.register
class MaintenanceWindowImporter(BaseImporter):
    model_name = "maintenance_windows"
    ...
```

**What the Decorator Does:**

```python
# Inside registry.py (simplified)
class ExporterRegistry:
    _exporters: Dict[str, Type[BaseExporter]] = {}
    
    @classmethod
    def register(cls, exporter_class):
        # Validate model_name is defined
        if not exporter_class.model_name:
            raise ValueError("model_name required")
        
        # Store in registry dict
        cls._exporters[exporter_class.model_name] = exporter_class
        
        # Return class unchanged
        return exporter_class
```

**Benefits of Decorator Registration:**

| Benefit | Explanation |
|---------|-------------|
| Self-documenting | Registration is visible at class definition |
| No configuration file | No need to maintain separate registry config |
| Automatic discovery | Just import the module to register |
| Fail-fast validation | Missing model_name caught at import time |

### 5.6.9 Usage Examples

#### Export Command

```bash
# Export all portal data including maintenance windows
python manage.py export_portal_data --output /path/to/backup/

# Export only ORCD plugin data
python manage.py export_portal_data --output /path/to/backup/ \
    --component orcd_plugin

# Export without configuration
python manage.py export_portal_data --output /path/to/backup/ --no-config
```

**Output Structure:**

```
/path/to/backup/
├── manifest.json              # Export metadata and checksums
├── coldfront_core/
│   ├── users.json
│   └── projects.json
├── orcd_plugin/
│   ├── node_types.json
│   ├── reservations.json
│   └── maintenance_windows.json    # ← Our export
└── config/
    └── settings.json
```

**Example maintenance_windows.json:**

```json
{
  "model": "maintenance_windows",
  "count": 2,
  "records": [
    {
      "natural_key": ["February Maintenance", "2026-02-15T00:00:00+00:00"],
      "fields": {
        "title": "February Maintenance",
        "description": "Scheduled power system upgrade",
        "start_datetime": "2026-02-15T00:00:00+00:00",
        "end_datetime": "2026-02-16T12:00:00+00:00",
        "created_by_username": "admin",
        "created": "2026-01-10T14:30:00+00:00",
        "modified": "2026-01-10T14:30:00+00:00"
      }
    },
    {
      "natural_key": ["Emergency Fix", "2026-01-05T08:00:00+00:00"],
      "fields": {
        "title": "Emergency Fix",
        "description": "Urgent storage repair",
        "start_datetime": "2026-01-05T08:00:00+00:00",
        "end_datetime": "2026-01-05T14:00:00+00:00",
        "created_by_username": null,
        "created": "2026-01-05T07:45:00+00:00",
        "modified": "2026-01-05T14:30:00+00:00"
      }
    }
  ]
}
```

#### Import Command

```bash
# Preview import (dry-run)
python manage.py import_portal_data /path/to/backup/ --dry-run

# Import all data
python manage.py import_portal_data /path/to/backup/

# Import ignoring configuration differences
python manage.py import_portal_data /path/to/backup/ --ignore-config-diff

# Check compatibility before import
python manage.py check_import_compatibility /path/to/backup/
```

**Import Output:**

```
Importing maintenance_windows...
  Created: 2, Updated: 0, Skipped: 0
  
Import complete:
  maintenance_windows: 2 created, 0 updated, 0 skipped
```

#### Round-Trip Verification

```bash
# 1. Create test data
python manage.py create_maintenance_window \
    --start "2026-06-01 00:00" \
    --end "2026-06-01 08:00" \
    --title "Round-Trip Test"

# 2. Export
python manage.py export_portal_data --output /tmp/backup-test/

# 3. Verify export file exists and contains data
cat /tmp/backup-test/orcd_plugin/maintenance_windows.json | python -m json.tool

# 4. Clear database (for testing - BE CAREFUL IN PRODUCTION)
python manage.py shell -c "
from coldfront_orcd_direct_charge.models import MaintenanceWindow
MaintenanceWindow.objects.filter(title='Round-Trip Test').delete()
"

# 5. Import
python manage.py import_portal_data /tmp/backup-test/

# 6. Verify data restored
python manage.py list_maintenance_windows | grep "Round-Trip Test"
```

### 5.6.10 Pattern Parallels

The MaintenanceWindow exporter/importer follows patterns established by other models:

| Pattern | MaintenanceWindow | Existing Example |
|---------|-------------------|------------------|
| Composite natural key | `(title, start_datetime)` | Reservation: `(allocation_id, start_date)` |
| FK by username | `created_by_username` | All models with user FKs |
| Datetime serialization | ISO 8601 format | All datetime fields |
| Empty dependencies | `dependencies = []` | NodeType (no plugin deps) |
| select_related | `select_related("created_by")` | All FK-containing models |
| Ordering by datetime | `-start_datetime` | Reservation: `-start_date` |

### 5.6.11 Design Decisions

#### Why Natural Keys Instead of Primary Keys?

| Consideration | Primary Key | Natural Key |
|---------------|-------------|-------------|
| Cross-database portability | ✗ Different auto-increment values | ✓ Same business meaning |
| Merge conflict detection | ✗ Always creates duplicates | ✓ Detects existing records |
| Human readability | ✗ Opaque integers | ✓ Meaningful values |
| Dependency resolution | ✗ Complex FK remapping | ✓ Simple lookup |

#### Why Tuple Natural Key vs Single Field?

```python
# Tuple provides uniqueness
natural_key = (instance.title, serialize_datetime(instance.start_datetime))
```

Single-field alternatives:
- **Title only**: Risk of collision ("Scheduled Maintenance" used multiple times)
- **UUID**: Requires adding UUID field to model, loses human readability
- **Slug**: Same collision risk as title

The tuple approach mirrors how Django's `get_by_natural_key` works for built-in models.

#### Why Store Username Instead of User Natural Key?

```python
"created_by_username": instance.created_by.username if instance.created_by else None
```

Alternatives considered:
- **User PK**: Not portable across databases
- **User natural key tuple**: Django's User model uses username as natural key anyway
- **Email**: Could change; username is more stable

Using username directly is simpler and follows the User model's own natural key convention.

#### Why Empty Dependencies?

```python
dependencies = []
```

MaintenanceWindow references:
- `created_by` → Django User (different component: `coldfront_core`)
- No other plugin models

Dependencies only list **same-component** models. Cross-component dependencies are handled by component ordering (core before plugin).

### 5.6.12 Verification

#### Verify Exporter Registration

```python
# Django shell
from coldfront_orcd_direct_charge.backup import ExporterRegistry

# Check maintenance_windows is registered
print(ExporterRegistry.get_all_model_names())
# Should include: 'maintenance_windows'

# Get the exporter class
exporter = ExporterRegistry.get_exporter("maintenance_windows")
print(exporter.model_name)  # 'maintenance_windows'
print(exporter.dependencies)  # []
```

#### Verify Importer Registration

```python
from coldfront_orcd_direct_charge.backup import ImporterRegistry

# Check maintenance_windows is registered
print(ImporterRegistry.get_all_model_names())
# Should include: 'maintenance_windows'

# Get the importer class
importer = ImporterRegistry.get_importer("maintenance_windows")
print(importer.model_name)  # 'maintenance_windows'
```

#### Test Export Manually

```python
from coldfront_orcd_direct_charge.backup import ExporterRegistry
from coldfront_orcd_direct_charge.models import MaintenanceWindow
from django.utils import timezone
from datetime import timedelta
import tempfile
import json

# Create test data
window = MaintenanceWindow.objects.create(
    title="Export Test",
    start_datetime=timezone.now() + timedelta(days=1),
    end_datetime=timezone.now() + timedelta(days=1, hours=4),
)

# Export
exporter_class = ExporterRegistry.get_exporter("maintenance_windows")
exporter = exporter_class()

with tempfile.TemporaryDirectory() as tmpdir:
    result = exporter.export(tmpdir)
    print(f"Exported {result.count} records to {result.file_path}")
    print(f"Success: {result.success}")
    
    # Read and verify
    with open(result.file_path) as f:
        data = json.load(f)
        print(f"Records: {data['count']}")
        for record in data['records']:
            print(f"  - {record['natural_key'][0]}")

# Cleanup
window.delete()
```

#### Test Import Manually

```python
from coldfront_orcd_direct_charge.backup import ImporterRegistry
from coldfront_orcd_direct_charge.models import MaintenanceWindow

# Sample import data
test_records = [
    {
        "natural_key": ["Import Test", "2026-06-15T00:00:00+00:00"],
        "fields": {
            "title": "Import Test",
            "description": "Testing import functionality",
            "start_datetime": "2026-06-15T00:00:00+00:00",
            "end_datetime": "2026-06-15T08:00:00+00:00",
            "created_by_username": None,
        }
    }
]

# Import with dry-run first
importer_class = ImporterRegistry.get_importer("maintenance_windows")
importer = importer_class()

result = importer.import_records(test_records, dry_run=True)
print(f"Dry-run: Would create {result.created}, update {result.updated}")

# Actual import
result = importer.import_records(test_records)
print(f"Created: {result.created}, Updated: {result.updated}")

# Verify
window = MaintenanceWindow.objects.get(title="Import Test")
print(f"Imported: {window.title} ({window.start_datetime} - {window.end_datetime})")

# Cleanup
window.delete()
```

#### Automated Testing

```python
# tests/test_backup.py
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
import tempfile
import json

from coldfront_orcd_direct_charge.models import MaintenanceWindow
from coldfront_orcd_direct_charge.backup import (
    ExporterRegistry,
    ImporterRegistry,
)


class MaintenanceWindowExporterTest(TestCase):
    def setUp(self):
        self.window = MaintenanceWindow.objects.create(
            title="Test Export Window",
            description="For export testing",
            start_datetime=timezone.now() + timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=1, hours=4),
        )
    
    def test_exporter_registered(self):
        self.assertIn(
            "maintenance_windows",
            ExporterRegistry.get_all_model_names()
        )
    
    def test_export_creates_file(self):
        exporter = ExporterRegistry.get_exporter("maintenance_windows")()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = exporter.export(tmpdir)
            
            self.assertTrue(result.success)
            self.assertEqual(result.count, 1)
            
            with open(result.file_path) as f:
                data = json.load(f)
            
            self.assertEqual(data["model"], "maintenance_windows")
            self.assertEqual(len(data["records"]), 1)
    
    def test_natural_key_format(self):
        exporter = ExporterRegistry.get_exporter("maintenance_windows")()
        
        for instance in exporter.get_queryset():
            record = exporter.serialize_record(instance)
            
            self.assertIn("natural_key", record)
            self.assertIsInstance(record["natural_key"], tuple)
            self.assertEqual(len(record["natural_key"]), 2)


class MaintenanceWindowImporterTest(TestCase):
    def test_importer_registered(self):
        self.assertIn(
            "maintenance_windows",
            ImporterRegistry.get_all_model_names()
        )
    
    def test_import_creates_record(self):
        importer = ImporterRegistry.get_importer("maintenance_windows")()
        
        records = [{
            "natural_key": ["Imported Window", "2026-07-01T00:00:00+00:00"],
            "fields": {
                "title": "Imported Window",
                "description": "Created via import",
                "start_datetime": "2026-07-01T00:00:00+00:00",
                "end_datetime": "2026-07-01T08:00:00+00:00",
                "created_by_username": None,
            }
        }]
        
        result = importer.import_records(records)
        
        self.assertEqual(result.created, 1)
        self.assertEqual(result.updated, 0)
        self.assertTrue(
            MaintenanceWindow.objects.filter(title="Imported Window").exists()
        )
    
    def test_import_updates_existing(self):
        # Create existing record
        existing = MaintenanceWindow.objects.create(
            title="Existing Window",
            description="Original description",
            start_datetime=timezone.make_aware(
                timezone.datetime(2026, 8, 1, 0, 0)
            ),
            end_datetime=timezone.make_aware(
                timezone.datetime(2026, 8, 1, 8, 0)
            ),
        )
        
        importer = ImporterRegistry.get_importer("maintenance_windows")()
        
        # Import with same natural key but updated description
        records = [{
            "natural_key": ["Existing Window", "2026-08-01T00:00:00+00:00"],
            "fields": {
                "title": "Existing Window",
                "description": "Updated description",
                "start_datetime": "2026-08-01T00:00:00+00:00",
                "end_datetime": "2026-08-01T08:00:00+00:00",
                "created_by_username": None,
            }
        }]
        
        result = importer.import_records(records)
        
        self.assertEqual(result.created, 0)
        self.assertEqual(result.updated, 1)
        
        existing.refresh_from_db()
        self.assertEqual(existing.description, "Updated description")
    
    def test_dry_run_no_changes(self):
        importer = ImporterRegistry.get_importer("maintenance_windows")()
        
        records = [{
            "natural_key": ["Dry Run Window", "2026-09-01T00:00:00+00:00"],
            "fields": {
                "title": "Dry Run Window",
                "start_datetime": "2026-09-01T00:00:00+00:00",
                "end_datetime": "2026-09-01T08:00:00+00:00",
            }
        }]
        
        result = importer.import_records(records, dry_run=True)
        
        self.assertEqual(result.created, 1)  # Would create
        self.assertFalse(
            MaintenanceWindow.objects.filter(title="Dry Run Window").exists()
        )
```

---

> **Summary:** TODO 6 adds export/import support for maintenance windows to the portal's backup system. The `MaintenanceWindowExporter` serializes records to JSON using a composite natural key of `(title, start_datetime)` for database-agnostic identification, with foreign keys serialized by username rather than ID. The `MaintenanceWindowImporter` handles conflict resolution by looking up existing records via natural key, supporting create-only, update-only, and create-or-update modes. Both classes use decorator-based registration (`@ExporterRegistry.register`, `@ImporterRegistry.register`) for automatic discovery. The implementation follows the established backup system patterns, enabling round-trip data migration between portal instances for disaster recovery, staging-to-production sync, and multi-site deployments.

---

*Continue to [5.7 TODO 7: Register Django Admin](#57-todo-7-register-django-admin) for the admin interface implementation.*

---

## 5.7 TODO 7: Register Django Admin

This section registers the MaintenanceWindow model with Django's admin interface, providing administrators with a powerful web-based tool for viewing, creating, editing, and managing maintenance windows—including historical records that may need correction.

### 5.7.1 Objective

Provide a comprehensive admin interface for maintenance window management:
- **View** all maintenance windows with key information at a glance
- **Filter and search** to quickly find specific windows
- **Create and edit** windows with organized form layouts
- **Manage historical data** including past windows (for billing corrections)
- **Display computed values** like duration and status dynamically

### 5.7.2 Prerequisites

This TODO requires completion of:

| Prerequisite | Provides |
|--------------|----------|
| **TODO 1: Model** | `MaintenanceWindow` model with fields, properties (`duration_hours`, `is_upcoming`, `is_in_progress`) |

### 5.7.3 Concepts Applied

| Concept | Application |
|---------|-------------|
| **@admin.register** | Decorator-based model registration |
| **ModelAdmin** | Base class for admin customization |
| **list_display** | Columns shown in list view, including computed methods |
| **list_filter** | Sidebar filters for narrowing results |
| **search_fields** | Fields searched by the search box |
| **readonly_fields** | Fields displayed but not editable |
| **fieldsets** | Organized form sections with collapsible groups |
| **@admin.display** | Decorator for computed display methods |

### 5.7.4 Files Modified

| File | Purpose |
|------|---------|
| `admin.py` | Add `MaintenanceWindowAdmin` class with `@admin.register` decorator |

### 5.7.5 The Admin Class

```python
@admin.register(MaintenanceWindow)
class MaintenanceWindowAdmin(admin.ModelAdmin):
    """Admin interface for MaintenanceWindow model."""

    list_display = (
        "title",
        "start_datetime",
        "end_datetime",
        "duration_hours_display",
        "status_display",
        "created_by",
        "created",
    )
    list_filter = ("start_datetime", "created")
    search_fields = ("title", "description")
    readonly_fields = ("created", "modified", "duration_hours_display", "status_display")
    ordering = ("-start_datetime",)

    fieldsets = (
        (None, {
            "fields": ("title", "description")
        }),
        ("Schedule", {
            "fields": ("start_datetime", "end_datetime", "duration_hours_display")
        }),
        ("Metadata", {
            "fields": ("created_by", "created", "modified", "status_display"),
            "classes": ("collapse",)
        }),
    )

    @admin.display(description="Duration")
    def duration_hours_display(self, obj):
        """Display duration in hours."""
        return f"{obj.duration_hours:.1f} hours"

    @admin.display(description="Status")
    def status_display(self, obj):
        """Display current status."""
        if obj.is_upcoming:
            return "Upcoming"
        elif obj.is_in_progress:
            return "In Progress"
        else:
            return "Completed"
```

#### list_display Configuration

The `list_display` tuple controls which columns appear in the admin list view:

| Column | Source | Purpose |
|--------|--------|---------|
| `"title"` | Model field | Primary identifier |
| `"start_datetime"` | Model field | When maintenance begins |
| `"end_datetime"` | Model field | When maintenance ends |
| `"duration_hours_display"` | Computed method | Human-readable duration |
| `"status_display"` | Computed method | Current state (Upcoming/In Progress/Completed) |
| `"created_by"` | FK field | Who created the window |
| `"created"` | Model field | When created |

**Key Pattern:** Mixing model fields (strings) with computed method names (strings matching method names) provides both raw data and derived information.

#### list_filter Configuration

```python
list_filter = ("start_datetime", "created")
```

Creates sidebar filters allowing admins to:
- **start_datetime**: Filter by "Today", "Past 7 days", "This month", "This year", or custom date ranges
- **created**: Similar date-based filtering for record creation time

Django automatically generates appropriate filter widgets based on field types (DateTimeField gets date hierarchy filters).

#### search_fields Configuration

```python
search_fields = ("title", "description")
```

The search box searches across both `title` and `description` fields using case-insensitive substring matching. This enables finding maintenance windows by:
- Event name: "firmware update"
- Description content: "network switch"

#### ordering Configuration

```python
ordering = ("-start_datetime",)
```

The minus prefix indicates descending order—most recent maintenance windows appear first. This makes the default view show upcoming and recent windows at the top.

#### readonly_fields Configuration

```python
readonly_fields = ("created", "modified", "duration_hours_display", "status_display")
```

These fields appear in the detail form but cannot be edited:

| Field | Reason Read-Only |
|-------|------------------|
| `created` | Auto-set by `auto_now_add`, should never be changed |
| `modified` | Auto-set by `auto_now`, updated automatically |
| `duration_hours_display` | Computed from start/end times, not a stored value |
| `status_display` | Computed from current time vs window times |

**Important:** Computed methods (`duration_hours_display`, `status_display`) must be in `readonly_fields` to appear in the detail view—otherwise they only appear in the list view.

#### fieldsets Organization

Fieldsets organize the edit form into logical sections:

```python
fieldsets = (
    (None, {                           # Section 1: No header (main content)
        "fields": ("title", "description")
    }),
    ("Schedule", {                     # Section 2: "Schedule" header
        "fields": ("start_datetime", "end_datetime", "duration_hours_display")
    }),
    ("Metadata", {                     # Section 3: "Metadata" header (collapsed)
        "fields": ("created_by", "created", "modified", "status_display"),
        "classes": ("collapse",)
    }),
)
```

| Section | Fields | Behavior |
|---------|--------|----------|
| (None) | title, description | Always visible, no header—primary content |
| Schedule | start/end times, duration | Grouped timing information |
| Metadata | created_by, timestamps, status | Collapsed by default—secondary info |

The `"collapse"` class hides the Metadata section initially, reducing visual clutter while keeping the information accessible.

### 5.7.6 Computed Display Methods

#### duration_hours_display Method

```python
@admin.display(description="Duration")
def duration_hours_display(self, obj):
    """Display duration in hours."""
    return f"{obj.duration_hours:.1f} hours"
```

**How it works:**
1. `obj.duration_hours` calls the model's `@property` method (defined in TODO 1)
2. `:.1f` formats the float to one decimal place
3. Returns a human-readable string like "4.0 hours"

**Why use a property wrapper?** The model property returns a raw float; the admin method adds formatting and units for display.

#### status_display Method

```python
@admin.display(description="Status")
def status_display(self, obj):
    """Display current status."""
    if obj.is_upcoming:
        return "Upcoming"
    elif obj.is_in_progress:
        return "In Progress"
    else:
        return "Completed"
```

**How it works:**
1. `obj.is_upcoming` and `obj.is_in_progress` are model properties that compare window times to `timezone.now()`
2. Returns a categorical status string based on temporal state

**Why not store status?** Status is derived from time—a window that's "Upcoming" now will be "In Progress" later without any database change. Storing it would create data staleness.

#### The @admin.display Decorator

```python
@admin.display(description="Duration")
```

This decorator configures how the method appears in the admin:

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `description` | Column header text | "Duration" instead of "duration_hours_display" |
| `ordering` | Enable sorting by this field (optional) | `ordering="start_datetime"` |
| `boolean` | Render as checkmark/X icons (optional) | `boolean=True` |

**Historical note:** Before Django 3.2, this was done with function attributes like `method.short_description = "Duration"`.

### 5.7.7 Why Admin Allows Past Window Edits

Unlike the web UI (TODO 11), the admin interface allows editing maintenance windows that have already started or completed.

#### Administrative Corrections Rationale

| Scenario | Example | Why Allow? |
|----------|---------|------------|
| **Data entry error** | End time entered as 2 PM instead of 2 AM | Billing would be incorrect without fix |
| **Retroactive documentation** | Adding description after the fact | No billing impact, improves records |
| **Duration correction** | Maintenance ended early/late | Billing accuracy requires actual times |
| **Billing dispute resolution** | Customer questions charges | May need adjustment after invoice |

#### Difference from Web UI Restrictions

| Interface | Can Edit Past Windows? | Rationale |
|-----------|------------------------|-----------|
| **Web UI** | No | Prevents accidental changes to historical billing data |
| **Django Admin** | Yes | Administrators need flexibility for corrections |
| **API** | Configurable | Depends on permission level |

**Trust Model:** The admin interface assumes trusted superusers who understand billing implications. The web UI assumes operational users who might accidentally modify historical data.

#### Implementation Note

No code is required to enable past-window editing in admin—it's the default behavior. The web UI restrictions (TODO 11) are implemented there, not here.

### 5.7.8 Pattern Parallels

The MaintenanceWindowAdmin follows patterns established by other model admins in the plugin:

| Pattern | MaintenanceWindow | Existing Example |
|---------|-------------------|------------------|
| Computed display method | `duration_hours_display()` | ReservationAdmin: `get_billable_hours()` |
| Status display method | `status_display()` | ActivityLogAdmin: `user_display()` |
| @admin.display decorator | `description="Duration"` | All computed methods |
| readonly_fields for computed | `duration_hours_display` in readonly | ReservationAdmin: `get_end_datetime` |
| Collapsed metadata section | `"classes": ("collapse",)` | ReservationAdmin, RentalSKUAdmin |
| Descending date ordering | `ordering = ("-start_datetime",)` | ReservationAdmin: `("-created",)` |
| Date-based list_filter | `("start_datetime", "created")` | ReservationAdmin: similar |

### 5.7.9 Verification

#### Verify Admin Registration

```python
# Django shell
from django.contrib import admin
from coldfront_orcd_direct_charge.models import MaintenanceWindow

# Check MaintenanceWindow is registered
print(MaintenanceWindow in admin.site._registry)
# Should print: True

# Get the admin class
admin_class = admin.site._registry[MaintenanceWindow]
print(admin_class.__class__.__name__)
# Should print: MaintenanceWindowAdmin
```

#### Verify List Display

```python
from django.contrib import admin
from coldfront_orcd_direct_charge.models import MaintenanceWindow

admin_class = admin.site._registry[MaintenanceWindow]

print(admin_class.list_display)
# Should include: 'title', 'start_datetime', 'duration_hours_display', 'status_display'
```

#### Visual Verification in Browser

1. Start the development server: `python manage.py runserver`
2. Navigate to `/admin/`
3. Log in as a superuser
4. Click "Maintenance windows" in the sidebar

**Expected List View:**
- Columns: Title, Start datetime, End datetime, Duration, Status, Created by, Created
- Sidebar filters for Start datetime and Created
- Search box above the list
- Rows ordered by start datetime (most recent first)

**Expected Detail View:**
- Main section: Title and Description fields
- Schedule section: Start/End datetime pickers, Duration display
- Metadata section: Collapsed by default, click to expand
- Save buttons at bottom

#### Test Computed Methods

```python
from django.utils import timezone
from datetime import timedelta
from coldfront_orcd_direct_charge.models import MaintenanceWindow

# Create test windows in different states
now = timezone.now()

upcoming = MaintenanceWindow.objects.create(
    title="Future Window",
    start_datetime=now + timedelta(days=1),
    end_datetime=now + timedelta(days=1, hours=4),
)

in_progress = MaintenanceWindow.objects.create(
    title="Current Window",
    start_datetime=now - timedelta(hours=1),
    end_datetime=now + timedelta(hours=3),
)

completed = MaintenanceWindow.objects.create(
    title="Past Window",
    start_datetime=now - timedelta(days=1),
    end_datetime=now - timedelta(days=1) + timedelta(hours=8),
)

# Verify computed values via admin methods
from django.contrib import admin
admin_instance = admin.site._registry[MaintenanceWindow]

print(admin_instance.duration_hours_display(upcoming))     # "4.0 hours"
print(admin_instance.status_display(upcoming))            # "Upcoming"
print(admin_instance.status_display(in_progress))         # "In Progress"
print(admin_instance.status_display(completed))           # "Completed"

# Cleanup
upcoming.delete()
in_progress.delete()
completed.delete()
```

---

> **Summary:** TODO 7 registers the MaintenanceWindow model with Django's admin interface using `@admin.register` and a customized `ModelAdmin` subclass. The `list_display` tuple shows key fields plus computed methods (`duration_hours_display`, `status_display`) that derive values from model properties. The `fieldsets` configuration organizes the edit form into logical sections with collapsible metadata. Unlike the web UI, the admin intentionally allows editing past maintenance windows to enable administrative corrections for billing accuracy. The implementation follows established patterns from other admin classes in the plugin, including the use of `@admin.display` decorators, readonly computed fields, and collapsed sections for secondary information.

---

## 5.8 TODO 8: Add Activity Logging

This section adds audit trail logging for all maintenance window operations. Every create, update, and delete action is recorded with full context, providing accountability and enabling forensic analysis of billing-related changes.

### 5.8.1 Objective

Add comprehensive activity logging for maintenance window operations:
- **Record all changes** to maintenance windows (create, update, delete)
- **Capture full context** including user, timestamp, IP address, and window details
- **Enable audit trail queries** for billing disputes and compliance
- **Preserve deleted data** in log records even after window removal

### 5.8.2 Prerequisites

This TODO requires completion of:

| Prerequisite | Provides |
|--------------|----------|
| **TODO 1: Model** | `MaintenanceWindow` model with fields and properties |
| **TODO 3: Views** | `CreateView`, `UpdateView`, `DeleteView` where logging is added |

The `ActivityLog` model and `log_activity` function already exist in the codebase—they were implemented for reservation logging. This TODO extends their use to maintenance windows.

### 5.8.3 Concepts Applied

| Concept | Application |
|---------|-------------|
| **Activity logging** | Recording user actions for audit purposes |
| **Audit trails** | Preserving history of changes for accountability |
| **log_activity function** | Centralized logging helper that captures context |
| **ActionCategory enum** | Categorization of log entries for filtering |
| **extra_data JSON** | Flexible storage for action-specific details |
| **Delete timing** | Logging before deletion to preserve object data |

### 5.8.4 Files Modified

| File | Purpose |
|------|---------|
| `views/rentals.py` | Add `log_activity` calls to maintenance window views |

### 5.8.5 The log_activity Function

The `log_activity` function is a centralized helper that creates `ActivityLog` records with consistent structure. Understanding its signature is essential for using it correctly.

#### Function Signature

```python
def log_activity(
    action,          # Machine-readable identifier (e.g., "maintenance_window.created")
    category,        # ActionCategory enum value
    description,     # Human-readable description
    user=None,       # User who performed action (extracted from request if not provided)
    request=None,    # HTTP request (provides user, IP, user-agent)
    target=None,     # Target model instance (optional)
    extra_data=None, # Additional JSON data (optional dict)
):
```

#### Parameters Explained

| Parameter | Type | Purpose | Example |
|-----------|------|---------|---------|
| `action` | string | Machine-readable action ID for programmatic filtering | `"maintenance_window.updated"` |
| `category` | ActionCategory | Enum value for grouping related actions | `ActivityLog.ActionCategory.MAINTENANCE` |
| `description` | string | Human-readable text for display | `"Updated maintenance window: Network Upgrade"` |
| `request` | HttpRequest | Django request object for context extraction | `self.request` from view |
| `target` | Model instance | Object being acted upon (or None for deletes) | `self.object` |
| `extra_data` | dict | Additional structured data to preserve | `{"window_id": 5, "duration_hours": 4.0}` |

#### ActionCategory Enum

The `ActionCategory` enum defines categories for filtering and organizing log entries:

```python
class ActionCategory(models.TextChoices):
    AUTH = "auth", "Authentication"
    RESERVATION = "reservation", "Reservation"
    PROJECT = "project", "Project"
    MEMBER = "member", "Member Management"
    COST_ALLOCATION = "cost_allocation", "Cost Allocation"
    BILLING = "billing", "Billing"
    INVOICE = "invoice", "Invoice"
    MAINTENANCE = "maintenance", "Maintenance Status"
    RATE = "rate", "Rate Management"
    API = "api", "API Access"
    VIEW = "view", "Page View"
```

**Why MAINTENANCE category?** Maintenance windows directly affect billing calculations. Grouping them under `MAINTENANCE` allows administrators to filter for all maintenance-related activity when investigating billing discrepancies.

### 5.8.6 Logging in Each View

Each maintenance window view requires slightly different logging logic due to the nature of the operation.

#### CreateView: Log After Save

```python
def form_valid(self, form):
    form.instance.created_by = self.request.user
    response = super().form_valid(form)

    log_activity(
        action="maintenance_window.created",
        category=ActivityLog.ActionCategory.MAINTENANCE,
        description=f"Created maintenance window: {self.object.title}",
        request=self.request,
        target=self.object,
        extra_data={
            "window_id": self.object.pk,
            "start_datetime": self.object.start_datetime.isoformat(),
            "end_datetime": self.object.end_datetime.isoformat(),
            "duration_hours": self.object.duration_hours,
        },
    )

    messages.success(
        self.request, f"Maintenance window '{self.object.title}' created successfully."
    )
    return response
```

**Why log after save?**
- `self.object` is only available after `super().form_valid(form)` creates the database record
- The object's `pk` is assigned during save—logging before save would record `pk=None`
- If save fails, no log entry is created (correct behavior)

#### UpdateView: Log After Save

```python
def form_valid(self, form):
    response = super().form_valid(form)

    log_activity(
        action="maintenance_window.updated",
        category=ActivityLog.ActionCategory.MAINTENANCE,
        description=f"Updated maintenance window: {self.object.title}",
        request=self.request,
        target=self.object,
        extra_data={
            "window_id": self.object.pk,
            "start_datetime": self.object.start_datetime.isoformat(),
            "end_datetime": self.object.end_datetime.isoformat(),
            "duration_hours": self.object.duration_hours,
        },
    )

    messages.success(
        self.request, f"Maintenance window '{self.object.title}' updated successfully."
    )
    return response
```

**Key difference from CreateView:** No need to set `created_by` since it was set during creation and shouldn't change on updates.

#### DeleteView: Log Before Delete (Why Timing Matters)

```python
def form_valid(self, form):
    # Capture details before deletion
    window_id = self.object.pk
    window_title = self.object.title
    start_datetime = self.object.start_datetime.isoformat()
    end_datetime = self.object.end_datetime.isoformat()
    duration_hours = self.object.duration_hours

    # Log activity before deletion (object will be gone after super())
    log_activity(
        action="maintenance_window.deleted",
        category=ActivityLog.ActionCategory.MAINTENANCE,
        description=f"Deleted maintenance window: {window_title}",
        request=self.request,
        target=None,  # Object is being deleted
        extra_data={
            "window_id": window_id,
            "window_title": window_title,
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "duration_hours": duration_hours,
        },
    )

    response = super().form_valid(form)
    messages.success(
        self.request, f"Maintenance window '{window_title}' deleted successfully."
    )
    return response
```

**Why log BEFORE delete?**

This is the critical pattern difference for delete operations:

| Timing | Problem |
|--------|---------|
| **After delete** | `self.object` no longer exists in database—all properties return stale/invalid data |
| **Before delete** | Full object data is available for capture |

**Why target=None?**

The `target` parameter normally stores the object type, ID, and string representation. For a delete:
- The object will be gone moments later
- Setting `target=self.object` would record an ID that no longer exists
- Using `target=None` and storing details in `extra_data` is more semantically correct

**The Capture Pattern:**

```python
# Step 1: Capture all needed values while object exists
window_id = self.object.pk
window_title = self.object.title
# ... more captures ...

# Step 2: Log with captured values (object still exists)
log_activity(..., extra_data={"window_id": window_id, ...})

# Step 3: Delete object
response = super().form_valid(form)  # Object deleted here
```

### 5.8.7 Extra Data

The `extra_data` parameter stores action-specific details as a JSON dictionary. This data is preserved in the database and can be queried or displayed.

#### What to Include in extra_data

| Field | Purpose | Example |
|-------|---------|---------|
| `window_id` | Primary key for lookups (especially useful for deleted records) | `5` |
| `window_title` | Human-readable identifier (preserved even after deletion) | `"Network Upgrade"` |
| `start_datetime` | When maintenance begins (ISO format for parsing) | `"2026-02-15T08:00:00"` |
| `end_datetime` | When maintenance ends | `"2026-02-15T12:00:00"` |
| `duration_hours` | Computed duration (billing impact) | `4.0` |

#### Why ISO Format for Datetimes?

```python
"start_datetime": self.object.start_datetime.isoformat()
```

- **JSON serialization**: Python `datetime` objects aren't directly JSON-serializable
- **Standard format**: ISO 8601 is universally recognized and parseable
- **Timezone preservation**: Includes timezone offset if present
- **Human readable**: `"2026-02-15T08:00:00"` is understandable in log displays

#### Why Include Computed Properties?

```python
"duration_hours": self.object.duration_hours
```

The `duration_hours` property can be recalculated from start/end times. Why store it?

1. **Query convenience**: Filter for "all windows longer than 8 hours" without recalculating
2. **Historical accuracy**: If the calculation logic changes, old logs show what was computed at the time
3. **Delete records**: After deletion, there's no object to call `duration_hours` on

### 5.8.8 Pattern Parallels

The logging pattern follows established conventions from reservation logging:

| Aspect | MaintenanceWindow | Reservation (Existing) |
|--------|-------------------|------------------------|
| **Action naming** | `maintenance_window.created` | `reservation.approved` |
| **Category** | `ActionCategory.MAINTENANCE` | `ActionCategory.RESERVATION` |
| **target parameter** | `self.object` (or None for delete) | `reservation` |
| **extra_data contents** | window_id, title, start/end times | project_id, project_title, node |
| **Delete capture pattern** | Capture before super() | Same pattern |

Example from existing reservation logging:

```python
# From ReservationApproveView
log_activity(
    action="reservation.approved",
    category=ActivityLog.ActionCategory.RESERVATION,
    description=f"Reservation #{reservation.pk} approved by {request.user.username}",
    request=request,
    target=reservation,
    extra_data={
        "project_id": reservation.project.pk,
        "project_title": reservation.project.title,
        "node": reservation.node_instance.associated_resource_address,
    },
)
```

### 5.8.9 Design Decisions

#### Why the MAINTENANCE Category?

The `ActionCategory.MAINTENANCE` category groups all maintenance-related actions together:

| Alternative | Problem |
|-------------|---------|
| `BILLING` | Too broad—includes invoice operations, cost allocations |
| `RESERVATION` | Semantically incorrect—maintenance windows aren't reservations |
| New category | Already exists and is appropriate |

The existing `MAINTENANCE` category was created for user maintenance status changes. Maintenance windows fit naturally here since they also affect billing.

#### Timing of Log Calls

| View Type | Timing | Rationale |
|-----------|--------|-----------|
| **CreateView** | After `super().form_valid()` | Object doesn't exist until save |
| **UpdateView** | After `super().form_valid()` | Ensures changes are persisted before logging |
| **DeleteView** | Before `super().form_valid()` | Object data must be captured before deletion |

**Consistency vs. Correctness**: While it might seem more consistent to always log after the operation, correctness requires logging before delete. The asymmetry is intentional.

#### Why Not Log Original Values on Update?

The update logging records the new values but not the original values:

```python
extra_data={
    "window_id": self.object.pk,
    "start_datetime": self.object.start_datetime.isoformat(),  # New value
    ...
}
```

**Design trade-off:**

| Approach | Pros | Cons |
|----------|------|------|
| Log new values only | Simpler, matches existing patterns | Can't see what changed |
| Log old and new values | Full change history | Requires fetching old values before save, more complex |

The current implementation follows the existing pattern from reservation logging. Future enhancement could add old value tracking if needed.

### 5.8.10 Verification

#### Verify Log Entries are Created

```python
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from coldfront_orcd_direct_charge.models import MaintenanceWindow, ActivityLog

# Get or create a test user
user = User.objects.get(username='admin')

# Create a maintenance window
window = MaintenanceWindow.objects.create(
    title="Test Window",
    start_datetime=timezone.now() + timedelta(days=1),
    end_datetime=timezone.now() + timedelta(days=1, hours=4),
    created_by=user,
)

# Manually call log_activity (simulating what the view does)
from coldfront_orcd_direct_charge.models import log_activity

log_activity(
    action="maintenance_window.created",
    category=ActivityLog.ActionCategory.MAINTENANCE,
    description=f"Created maintenance window: {window.title}",
    user=user,
    target=window,
    extra_data={
        "window_id": window.pk,
        "start_datetime": window.start_datetime.isoformat(),
        "end_datetime": window.end_datetime.isoformat(),
        "duration_hours": window.duration_hours,
    },
)

# Verify log entry exists
log = ActivityLog.objects.filter(
    action="maintenance_window.created",
    target_id=window.pk
).first()

print(f"Log entry found: {log is not None}")
print(f"Description: {log.description}")
print(f"Extra data: {log.extra_data}")

# Cleanup
window.delete()
```

#### Verify Logging via Web UI

1. Log in as a user with `can_manage_rentals` permission
2. Navigate to Maintenance Windows list
3. Create a new maintenance window
4. View the activity log (Admin → Activity Logs or dedicated view)
5. Confirm entry with action `maintenance_window.created`
6. Edit the window and verify `maintenance_window.updated` entry
7. Delete the window and verify `maintenance_window.deleted` entry

#### Verify Delete Captures Data

```python
from coldfront_orcd_direct_charge.models import ActivityLog

# Find a delete log entry
delete_log = ActivityLog.objects.filter(
    action="maintenance_window.deleted"
).first()

if delete_log:
    print(f"Deleted window title: {delete_log.extra_data.get('window_title')}")
    print(f"Deleted window ID: {delete_log.extra_data.get('window_id')}")
    print(f"Duration was: {delete_log.extra_data.get('duration_hours')} hours")
    print(f"Target is None: {delete_log.target_id is None}")
```

#### Query Maintenance Activity

```python
from coldfront_orcd_direct_charge.models import ActivityLog

# All maintenance window activity
maint_logs = ActivityLog.objects.filter(
    category=ActivityLog.ActionCategory.MAINTENANCE,
    action__startswith="maintenance_window."
).order_by("-timestamp")

for log in maint_logs[:5]:
    print(f"{log.timestamp}: {log.action} - {log.description}")
```

---

> **Summary:** TODO 8 adds activity logging to maintenance window operations using the existing `log_activity` function and `ActivityLog` model. The `MAINTENANCE` category groups these entries with other maintenance-related activity. CreateView and UpdateView log after save when the object data is finalized, while DeleteView logs before deletion to capture object data that would otherwise be lost. The `extra_data` JSON field preserves key details (window_id, title, times, duration) for audit queries and billing dispute resolution. This pattern mirrors the existing reservation logging implementation, ensuring consistency across the codebase.

---

*Continue to [5.9 TODO 9: Update Invoice Templates](#59-todo-9-update-invoice-templates) for billing display integration.*

---

## 5.9 TODO 9: Update Invoice Templates

This section updates the invoice templates to display maintenance deductions. When maintenance windows overlap with reservation billing periods, users need to see exactly how much time was deducted from their charges.

### 5.9.1 Objective

Display maintenance window deductions on invoice pages so that:
- **Users understand billing adjustments**: Clear visibility of hours deducted due to maintenance
- **Billing transparency**: Customers see exactly why their charged hours differ from reservation duration
- **Audit support**: Documentation of deductions for dispute resolution

### 5.9.2 Prerequisites

This TODO requires completion of:

| Prerequisite | Provides |
|--------------|----------|
| **TODO 2: Billing Logic** | The `maintenance_deduction` field in invoice line data computed by `calculate_monthly_billing` |

The billing logic in TODO 2 calculates `maintenance_deduction` for each reservation line. This TODO simply displays that pre-computed value.

### 5.9.3 Concepts Applied

| Concept | Application |
|---------|-------------|
| **Template conditionals** | Show deduction only when it exists and is greater than zero |
| **Django filters** | `floatformat` for consistent decimal display |
| **UX considerations** | Subtle but visible indication that doesn't overwhelm |
| **Tooltip patterns** | Provide context on hover without cluttering the UI |

### 5.9.4 Files Modified

| File | Purpose |
|------|---------|
| `templates/.../invoice_detail.html` | Show deductions in the hours column |
| `templates/.../invoice_edit.html` | Show deductions on the override editing page |

### 5.9.5 Displaying Deductions

The templates display maintenance deductions using a consistent pattern: only show when the value exists and is positive, use subtle styling to avoid visual clutter, and provide context via tooltip.

#### Conditional Display Logic

```django
{% if line.maintenance_deduction and line.maintenance_deduction > 0 %}
  <!-- Display deduction -->
{% endif %}
```

**Why two conditions?**

| Condition | Purpose |
|-----------|---------|
| `line.maintenance_deduction` | Guards against `None` values (template safety) |
| `line.maintenance_deduction > 0` | Only display if there's actually a deduction |

This prevents displaying "0.00h maintenance" when no maintenance windows overlapped the billing period.

#### When to Show vs. Hide

| Scenario | `maintenance_deduction` Value | Display |
|----------|-------------------------------|---------|
| No maintenance windows overlap | `0` or `None` | Hidden |
| Single window overlaps | `4.0` | "-4.00h maintenance" |
| Multiple windows overlap | `12.5` | "-12.50h maintenance" |
| Excluded reservation | N/A | Hidden (entire line is muted) |

#### Visual Design

The deduction display uses several visual techniques:

| Element | Purpose |
|---------|---------|
| `<br>` | Places deduction on a new line below the hours |
| `<small>` | Reduces font size to indicate secondary information |
| `text-muted` | Gray color signals supplementary data |
| `fas fa-wrench` | Icon provides instant recognition (tools = maintenance) |
| `-` prefix | Negative sign emphasizes this is a deduction |
| `title` attribute | Tooltip explains the deduction on hover |

### 5.9.6 Template Code

#### Invoice Detail Template

The main invoice report shows deductions in the "Hours (this month)" column:

```html
<td>
  {% if line.excluded %}
    <span class="text-muted">-</span>
  {% else %}
    {{ line.hours_in_month|floatformat:2 }}
    {% if line.maintenance_deduction and line.maintenance_deduction > 0 %}
      <br>
      <small class="text-muted" title="Hours deducted due to scheduled maintenance windows">
        <i class="fas fa-wrench"></i> 
        -{{ line.maintenance_deduction|floatformat:2 }}h maintenance
      </small>
    {% endif %}
  {% endif %}
</td>
```

**Key elements:**
- The primary hours value appears first (`hours_in_month`)
- Deduction appears below in smaller, muted text
- Tooltip provides full explanation on hover

#### Invoice Edit Template

The override editing page shows the original hours with any maintenance deduction:

```html
<p>
  <strong>Original Hours (this month):</strong> {{ original_hours|floatformat:2 }}
  {% if maintenance_deduction and maintenance_deduction > 0 %}
    <br>
    <small class="text-muted">
      <i class="fas fa-wrench"></i> 
      -{{ maintenance_deduction|floatformat:2 }}h maintenance window deduction
    </small>
  {% endif %}
</p>
```

**Note:** The edit template uses a slightly longer description ("maintenance window deduction") since it has more visual space.

#### The floatformat Filter

```django
{{ line.maintenance_deduction|floatformat:2 }}
```

| Input | Output |
|-------|--------|
| `4.0` | `4.00` |
| `12.5` | `12.50` |
| `0.333...` | `0.33` |

The `floatformat:2` filter ensures consistent two-decimal display, matching the formatting of the primary hours value.

### 5.9.7 UX Considerations

#### Why Subtle vs. Prominent?

The deduction display intentionally uses subdued styling:

| Design Choice | Rationale |
|---------------|-----------|
| **Small text** | Deduction is supplementary to the main hours value |
| **Muted color** | Doesn't compete for attention with primary data |
| **Icon only** | Wrench is universally recognized; no label needed |
| **Same row** | Logically groups deduction with its parent hours |

**Alternative considered (rejected):**

```html
<!-- Rejected: Too prominent -->
<span class="badge badge-warning">
  <i class="fas fa-wrench"></i> -4.00h MAINTENANCE
</span>
```

This would draw excessive attention to what is typically a minor adjustment.

#### Maintaining Clarity

The display preserves invoice readability by:
1. **Not showing zero deductions** - Avoids visual noise
2. **Inline placement** - No additional columns or sections needed
3. **Consistent formatting** - Matches existing numerical styling
4. **Tooltip for context** - Details available on demand, not forced

### 5.9.8 Pattern Parallels

The maintenance deduction display follows patterns used elsewhere in the invoice templates:

| Pattern | Maintenance Deduction | Cost Object Breakdown |
|---------|----------------------|----------------------|
| **Conditional display** | `{% if maintenance_deduction %}` | `{% for co in line.cost_breakdown %}` |
| **Secondary styling** | `<small class="text-muted">` | `<span class="badge badge-light">` |
| **Icon prefix** | `fas fa-wrench` | Badge color coding |
| **Number formatting** | `floatformat:2` | `floatformat:2` |

The template also mirrors patterns from the reservation list view, where status badges and supplementary information appear inline with primary content.

### 5.9.9 Verification

#### Visual Verification

| Test | Steps | Expected Result |
|------|-------|-----------------|
| **No maintenance windows** | View invoice for month with no maintenance | No deduction displayed |
| **With maintenance window** | Create window overlapping billing period, view invoice | Deduction appears below hours |
| **Hover tooltip** | Hover over deduction text | Tooltip explains deduction |
| **Edit page display** | Click edit for reservation with deduction | Deduction shown in reservation details |

#### Data Verification

```python
# In Django shell
from coldfront_orcd_direct_charge.utils import calculate_monthly_billing
from datetime import date

# Generate billing data for a month with maintenance windows
billing = calculate_monthly_billing(year=2026, month=2)

# Find a line with maintenance deduction
for project in billing['projects']:
    for line in project['lines']:
        if line.get('maintenance_deduction', 0) > 0:
            print(f"Reservation #{line['reservation'].pk}")
            print(f"  Hours: {line['hours_in_month']}")
            print(f"  Maintenance deduction: {line['maintenance_deduction']}")
            break
```

#### Template Rendering Test

```bash
# Run development server
cd /Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental
python manage.py runserver

# Navigate to invoice for a month with maintenance windows
# http://localhost:8000/nodes/invoices/2026/2/
# Verify deduction appears for affected reservations
```

---

> **Summary:** TODO 9 updates the invoice templates (`invoice_detail.html` and `invoice_edit.html`) to display maintenance deductions calculated in TODO 2. The display uses Django's template conditionals to show deductions only when they exist and are positive, the `floatformat` filter for consistent decimal formatting, and subtle styling (small muted text with wrench icon) to avoid overwhelming the primary invoice data. A tooltip provides context on hover. The pattern matches existing invoice display conventions for supplementary information, maintaining visual consistency across the billing interface.

---

*Continue to [5.10 TODO 10: Create Help Text System](#510-todo-10-create-help-text-system) for user documentation integration.*

---

## 5.10 TODO 10: Create Help Text System

This section implements a modular, reusable help text system that provides contextual documentation to users directly within the application interface. The system loads Markdown content from files and renders it in a Bootstrap modal.

### 5.10.1 Objective

Create a help text system that provides:
- **In-context documentation**: Users can access help without leaving the page
- **Maintainable content**: Documentation stored as Markdown files, easily editable by non-developers
- **Reusable infrastructure**: Template tag and modal pattern usable across features
- **Graceful degradation**: Works even if the Markdown library isn't installed

### 5.10.2 Prerequisites

This TODO requires completion of:

| Prerequisite | Provides |
|--------------|----------|
| **TODO 3: Templates** | The `list.html` template where the help button will be placed |

The template structure from TODO 3 provides the page header where the help button appears alongside other action buttons.

### 5.10.3 Concepts Applied

| Concept | Application |
|---------|-------------|
| **Custom template tags** | `@register.simple_tag` for loading and rendering content |
| **Markdown rendering** | Converting `.md` files to HTML for rich formatting |
| **Modular content** | Separating help text from templates for maintainability |
| **Partial templates** | `_help_modal.html` as an includable component |
| **Graceful degradation** | Fallback rendering if dependencies are missing |

### 5.10.4 Files Created

| File | Purpose |
|------|---------|
| `help_text/maintenance_window.md` | Markdown content for maintenance window help |
| `templatetags/help_text_tags.py` | Custom template tag for loading help content |
| `templates/.../maintenance_window/_help_modal.html` | Bootstrap modal with help button |

### 5.10.5 The Markdown Content

Help content is stored as a Markdown file separate from templates:

```markdown
# Maintenance Windows

## Purpose

Maintenance windows allow rental managers to define scheduled maintenance periods 
during which **node rentals are not billed**. This feature ensures researchers 
are not charged for time when nodes are unavailable due to planned maintenance.

## How It Works

- Rentals can extend through maintenance windows without interruption
- Billable hours are automatically reduced to exclude any overlap with maintenance periods
- The adjustment appears on invoices showing original hours and maintenance deductions

## When to Use

Create a maintenance window when:
- Scheduled system maintenance will make nodes unavailable
- Emergency maintenance requires taking nodes offline
- Planned upgrades or infrastructure work affects node availability

## Billing Impact

**Example:** A rental spans Feb 14-16 (41 hours total). A maintenance window 
covers Feb 15 8AM-8PM (12 hours). The invoice will show:
- Original hours: 41
- Maintenance deduction: 12  
- Billable hours: 29

## Important Notes

- Maintenance windows apply system-wide to all nodes
- Only future maintenance windows can be edited or deleted via this page
- Past and in-progress windows are locked to preserve billing accuracy
- For corrections to past windows, contact a system administrator
```

#### Why Markdown for Help Content?

| Consideration | Markdown | HTML | Django Template |
|---------------|----------|------|-----------------|
| **Readability** | Easy to read/write | Verbose tags | Mixed logic and content |
| **Non-developer editing** | Accessible | Requires HTML knowledge | Requires Django knowledge |
| **Version control** | Clean diffs | Noisy diffs | Complex diffs |
| **Portability** | Can render elsewhere | Web-only | Django-only |
| **Formatting** | Rich (headers, lists, bold) | Full control | Requires filters |

Markdown strikes the ideal balance: rich enough for documentation, simple enough for anyone to edit.

### 5.10.6 The Template Tag

The custom template tag loads Markdown files and renders them to HTML:

```python
"""Template tags for loading and rendering help text from markdown files."""

from pathlib import Path

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def load_help_text(feature_name):
    """Load and render help text markdown for a feature.

    Args:
        feature_name: Name of the help text file (without .md extension)

    Returns:
        str: Rendered HTML from the markdown file, or raw text as fallback,
             or empty string if file not found
    """
    help_dir = Path(__file__).parent.parent / "help_text"
    help_file = help_dir / f"{feature_name}.md"

    if not help_file.exists():
        return ""

    content = help_file.read_text()

    try:
        import markdown

        html = markdown.markdown(content, extensions=["tables", "fenced_code"])
        return mark_safe(html)
    except ImportError:
        # If markdown not installed, return raw text wrapped in pre tag
        return mark_safe(f"<pre>{content}</pre>")
```

#### Key Implementation Details

| Element | Purpose |
|---------|---------|
| `@register.simple_tag` | Creates a tag that returns a value directly to the template |
| `Path(__file__).parent.parent` | Navigates from `templatetags/` up to the app root, then to `help_text/` |
| `mark_safe()` | Tells Django the returned HTML is safe to render (not user input) |
| `extensions=["tables", "fenced_code"]` | Enables Markdown extensions for richer formatting |

#### The Fallback Pattern

```python
try:
    import markdown
    html = markdown.markdown(content, extensions=["tables", "fenced_code"])
    return mark_safe(html)
except ImportError:
    return mark_safe(f"<pre>{content}</pre>")
```

This try/except pattern ensures:
1. **Production**: If `markdown` package is installed, content renders as formatted HTML
2. **Fallback**: If package is missing, raw Markdown displays in a `<pre>` block (still readable)
3. **No crashes**: Missing dependency doesn't break the application

#### Why `mark_safe` Is Appropriate Here

`mark_safe` tells Django not to escape the HTML. This is safe because:
- Content comes from **files we control** (not user input)
- Files are in the codebase, reviewed through version control
- No user-submitted data flows through this path

**Never use `mark_safe` on user-provided content.**

### 5.10.7 The Modal Template

The help modal is a reusable partial template:

```html
{% load help_text_tags %}

<!-- Help Button -->
<button type="button" class="btn btn-outline-info btn-sm" data-toggle="modal" data-target="#helpModal">
    <i class="fas fa-question-circle"></i> Help
</button>

<!-- Help Modal -->
<div class="modal fade" id="helpModal" tabindex="-1" role="dialog" aria-labelledby="helpModalLabel" aria-hidden="true">
    <div class="modal-dialog modal-lg modal-dialog-scrollable" role="document">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title" id="helpModalLabel">Maintenance Windows Help</h5>
                <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                    <span aria-hidden="true">&times;</span>
                </button>
            </div>
            <div class="modal-body help-content">
                {% load_help_text "maintenance_window" %}
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
            </div>
        </div>
    </div>
</div>
```

#### Template Structure

| Section | Purpose |
|---------|---------|
| `{% load help_text_tags %}` | Imports the custom template tag |
| Help Button | Trigger button with question mark icon |
| Modal wrapper | Bootstrap modal with accessibility attributes |
| Modal header | Title and close button |
| Modal body | Contains the rendered Markdown content |
| Modal footer | Close button for explicit dismissal |

#### Bootstrap Modal Classes

| Class | Effect |
|-------|--------|
| `modal fade` | Enables fade-in animation |
| `modal-lg` | Larger modal for comfortable reading |
| `modal-dialog-scrollable` | Scrolls content if it exceeds viewport height |
| `btn-outline-info` | Light blue outline button that doesn't compete with primary actions |

#### Accessibility Attributes

| Attribute | Purpose |
|-----------|---------|
| `role="dialog"` | Indicates modal is a dialog to assistive technologies |
| `aria-labelledby` | Associates modal with its title for screen readers |
| `aria-hidden="true"` | Hides modal from screen readers when closed |
| `aria-label="Close"` | Labels the close button for screen readers |

### 5.10.8 Integration

The help modal is included in the list template using Django's `{% include %}` tag:

```html
<div class="card-header d-flex justify-content-between align-items-center">
  <h5 class="mb-0">All Maintenance Windows</h5>
  <div>
    {% include "coldfront_orcd_direct_charge/maintenance_window/_help_modal.html" %}
    <a href="{% url 'coldfront_orcd_direct_charge:maintenance-window-create' %}" class="btn btn-primary">
      <i class="fas fa-plus"></i> New Maintenance Window
    </a>
  </div>
</div>
```

**Placement rationale:**
- Help button appears next to action buttons (logical grouping)
- Uses `btn-outline-info` to differentiate from primary `btn-primary` action
- Positioned first so it doesn't compete visually with the primary action

### 5.10.9 Extensibility

The help text system is designed for easy extension to other features.

#### Adding Help for Another Feature

1. **Create the Markdown file:**

```bash
# Create help content for reservations
cat > coldfront_orcd_direct_charge/help_text/reservations.md << 'EOF'
# Node Reservations

## Purpose
Reservations allow researchers to reserve dedicated computing nodes...

## How It Works
...
EOF
```

2. **Create a modal template (or make a generic one):**

```html
<!-- templates/.../reservations/_help_modal.html -->
{% load help_text_tags %}

<button type="button" class="btn btn-outline-info btn-sm" data-toggle="modal" data-target="#helpModal">
    <i class="fas fa-question-circle"></i> Help
</button>

<div class="modal fade" id="helpModal" tabindex="-1" role="dialog">
    <div class="modal-dialog modal-lg modal-dialog-scrollable" role="document">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Reservations Help</h5>
                <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                    <span aria-hidden="true">&times;</span>
                </button>
            </div>
            <div class="modal-body help-content">
                {% load_help_text "reservations" %}
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
            </div>
        </div>
    </div>
</div>
```

3. **Include in the feature's template:**

```html
{% include "coldfront_orcd_direct_charge/reservations/_help_modal.html" %}
```

#### Creating a Generic Help Modal

For multiple features, consider a parameterized modal:

```html
<!-- templates/.../partials/_generic_help_modal.html -->
{% load help_text_tags %}

<button type="button" class="btn btn-outline-info btn-sm" data-toggle="modal" data-target="#helpModal-{{ feature_name }}">
    <i class="fas fa-question-circle"></i> Help
</button>

<div class="modal fade" id="helpModal-{{ feature_name }}" tabindex="-1" role="dialog">
    <div class="modal-dialog modal-lg modal-dialog-scrollable" role="document">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">{{ help_title }}</h5>
                <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                    <span aria-hidden="true">&times;</span>
                </button>
            </div>
            <div class="modal-body help-content">
                {% load_help_text feature_name %}
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
            </div>
        </div>
    </div>
</div>
```

**Usage:**

```html
{% include "coldfront_orcd_direct_charge/partials/_generic_help_modal.html" with feature_name="maintenance_window" help_title="Maintenance Windows Help" %}
```

### 5.10.10 Pattern Parallels

This help text system follows established patterns in Django and ColdFront:

| Pattern | Our Implementation | Existing Example |
|---------|-------------------|------------------|
| **Custom template tags** | `load_help_text` | ColdFront's `common_tags.py` |
| **Partial templates** | `_help_modal.html` | ColdFront's `_pagination.html` |
| **Content files** | `help_text/*.md` | Django's `locale/*.po` files |
| **Graceful degradation** | Fallback if no markdown | Django's template fallbacks |
| **Bootstrap modals** | Help modal | ColdFront's confirmation dialogs |

#### Comparison to Other Documentation Approaches

| Approach | Pros | Cons |
|----------|------|------|
| **Our approach (in-app Markdown)** | In-context, version-controlled, easy to update | Requires deployment for changes |
| **External wiki** | Non-developers can edit, no deployment | Separate from app, can get out of sync |
| **Inline tooltips** | Immediate context | Limited space, clutters UI |
| **PDF documentation** | Printable, formal | Quickly outdated, not searchable in-app |

Our approach optimizes for developer-maintained documentation that stays close to the code it documents.

### 5.10.11 Verification

#### File Verification

```bash
# Verify help text file exists
ls -la coldfront_orcd_direct_charge/help_text/maintenance_window.md

# Verify template tag module exists
ls -la coldfront_orcd_direct_charge/templatetags/help_text_tags.py

# Verify modal template exists
ls -la coldfront_orcd_direct_charge/templates/coldfront_orcd_direct_charge/maintenance_window/_help_modal.html
```

#### Template Tag Loading

```python
# In Django shell
from django.template import Template, Context

template = Template('''
{% load help_text_tags %}
{% load_help_text "maintenance_window" %}
''')
result = template.render(Context({}))
print(result[:500])  # Should show rendered HTML
```

#### Visual Verification

| Test | Steps | Expected Result |
|------|-------|-----------------|
| **Button appears** | Navigate to maintenance windows list | Help button visible next to "New" button |
| **Modal opens** | Click Help button | Modal opens with formatted content |
| **Content renders** | View modal content | Markdown rendered as HTML (headers, lists, bold) |
| **Modal closes** | Click Close or X button | Modal dismisses |
| **Scroll works** | View with long content | Modal body scrolls if content exceeds viewport |

#### Accessibility Verification

```bash
# Check for accessibility attributes in the template
grep -E "aria-|role=" coldfront_orcd_direct_charge/templates/coldfront_orcd_direct_charge/maintenance_window/_help_modal.html
```

#### Fallback Verification

```python
# Temporarily test without markdown package
# (In a test environment only)
import sys
sys.modules['markdown'] = None  # Simulate missing package

from coldfront_orcd_direct_charge.templatetags.help_text_tags import load_help_text
result = load_help_text("maintenance_window")
print(result)  # Should show <pre>...</pre> wrapped content
```

---

> **Summary:** TODO 10 creates a modular help text system using three components: Markdown files in `help_text/` for maintainable content, a custom template tag (`load_help_text`) that loads and renders these files to HTML, and a Bootstrap modal template (`_help_modal.html`) that presents the help to users. The system uses `mark_safe` appropriately since content comes from controlled files, includes graceful degradation if the Markdown library is unavailable, and provides a reusable pattern for adding contextual help to other features. The modal integrates seamlessly with existing UI patterns, appearing as a subtle help button alongside primary actions.

---

*Continue to [5.11 TODO 11: Implement Edit Restrictions](#511-todo-11-implement-edit-restrictions) for protecting historical data.*

---

## 5.11 TODO 11: Implement Edit Restrictions

This section implements server-side restrictions that prevent editing or deleting maintenance windows that have already started or completed. These restrictions protect billing integrity by ensuring historical records cannot be accidentally modified through the web interface.

### 5.11.1 Objective

Prevent modification of past and in-progress maintenance windows via the web UI:
- **Protect billing accuracy**: Past windows have already affected invoices; changes would create inconsistencies
- **Preserve audit integrity**: Historical records should reflect what actually happened
- **Defense in depth**: Server-side enforcement complements template-level hiding
- **Graceful user experience**: Clear error messages instead of confusing 404 pages

### 5.11.2 Prerequisites

This TODO requires completion of:

| Prerequisite | Provides |
|--------------|----------|
| **TODO 3: Views and Templates** | `UpdateView`, `DeleteView` base classes; list template with edit/delete buttons |

The list template from TODO 3 already conditionally hides edit/delete buttons for non-future windows. This TODO adds server-side enforcement.

### 5.11.3 Concepts Applied

| Concept | Application |
|---------|-------------|
| **get_queryset filtering** | Restricting which objects are accessible via the view |
| **Graceful error handling** | Catching Http404 and redirecting with user-friendly message |
| **Defense in depth** | Multiple layers of protection (template + server) |
| **Http404 exception** | Django's standard "not found" exception |
| **messages framework** | Displaying feedback to users after redirects |

### 5.11.4 Files Modified

| File | Purpose |
|------|---------|
| `views/rentals.py` | Add `get_queryset`, `get`, and `post` overrides to `MaintenanceWindowUpdateView` and `MaintenanceWindowDeleteView` |

### 5.11.5 The Restriction Pattern

#### Why Restrict Past Windows?

| Scenario | Risk Without Restriction |
|----------|--------------------------|
| **Past window edited** | Invoices already sent would become inaccurate |
| **In-progress window modified** | Billing calculations mid-period could change unexpectedly |
| **Accidental deletion** | No record of maintenance that affected billing |
| **Audit discrepancies** | Activity logs wouldn't match current data |

Maintenance windows directly affect billing calculations. Once a window's time period has begun, any changes would create discrepancies between:
- What users were actually billed
- What the current data shows
- What the activity logs recorded

#### Defense in Depth Strategy

The restriction is implemented at two layers:

| Layer | Implementation | Purpose |
|-------|----------------|---------|
| **Template (TODO 3)** | Conditionally hide edit/delete buttons | Prevents accidental clicks, improves UX |
| **Server (This TODO)** | Filter queryset, catch 404, redirect with message | Enforces restriction even with direct URL access |

**Why both layers?**

Template-only protection fails when users:
- Bookmark an edit URL while the window was still future
- Manually construct URLs from patterns observed elsewhere
- Use browser history to revisit old edit pages
- Access links from notification emails sent earlier

Server-side validation is the authoritative enforcement; template hiding is a UX convenience.

### 5.11.6 get_queryset Override

The `get_queryset` method controls which objects are accessible through the view.

```python
class MaintenanceWindowUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Edit an existing maintenance window (future windows only)."""

    model = MaintenanceWindow
    # ... other attributes ...

    def get_queryset(self):
        """Only allow editing windows that haven't started yet."""
        return MaintenanceWindow.objects.filter(start_datetime__gt=timezone.now())
```

#### How It Works

| Step | What Happens |
|------|--------------|
| 1 | User requests `/maintenance-windows/5/edit/` |
| 2 | Django calls `get_queryset()` to get base queryset |
| 3 | Queryset is filtered to `start_datetime > now` |
| 4 | Django calls `get_object()` to find pk=5 in filtered queryset |
| 5 | If window 5 has already started → **Not in queryset → Http404** |
| 6 | If window 5 is still future → Object returned normally |

#### The Filter Condition

```python
MaintenanceWindow.objects.filter(start_datetime__gt=timezone.now())
```

| Operator | Meaning | Windows Included |
|----------|---------|------------------|
| `__gt` | Greater than | Only windows starting **after** current time |
| `timezone.now()` | Current datetime with timezone | Evaluated at request time |

**Why not `end_datetime`?**

Using `start_datetime` means:
- A window that has **started but not ended** (in-progress) is NOT editable
- This is intentional—once maintenance begins, the record should be locked

**Why not `__gte` (greater than or equal)?**

Using `__gt` (strictly greater than) means:
- A window starting at exactly this moment is NOT editable
- This prevents race conditions at window start time

### 5.11.7 Graceful Error Handling

Without additional handling, the filtered queryset would cause Django to display a generic 404 page. This is confusing because:
- The object exists in the database
- The user has permission to manage windows
- The only issue is temporal restrictions

The solution: override `get()` and `post()` to catch the 404 and redirect with a helpful message.

#### Overriding get() Method

```python
def get(self, request, *args, **kwargs):
    """Handle case where window is not editable."""
    try:
        self.object = self.get_object()
    except Http404:
        messages.error(
            request,
            "This maintenance window has already started or passed and cannot be "
            "modified through the web interface.",
        )
        return redirect("coldfront_orcd_direct_charge:maintenance-window-list")
    return super().get(request, *args, **kwargs)
```

**Flow diagram:**

```
GET /maintenance-windows/5/edit/
         │
         ▼
    get_queryset()
    (filtered to future only)
         │
         ▼
    get_object() for pk=5
         │
         ├── Window is future ──────► super().get() ──► Render form
         │
         └── Window has started ────► Http404
                     │
                     ▼
              Catch exception
                     │
                     ▼
              messages.error()
                     │
                     ▼
              redirect(list page)
```

#### Overriding post() Method

```python
def post(self, request, *args, **kwargs):
    """Handle case where window is not editable."""
    try:
        self.object = self.get_object()
    except Http404:
        messages.error(
            request,
            "This maintenance window has already started or passed and cannot be "
            "modified through the web interface.",
        )
        return redirect("coldfront_orcd_direct_charge:maintenance-window-list")
    return super().post(request, *args, **kwargs)
```

**Why override both methods?**

| Method | When Called | Why Override |
|--------|-------------|--------------|
| `get()` | User navigates to edit page | Prevent seeing form for non-editable window |
| `post()` | User submits form | Prevent processing form if window became non-editable while user was on page |

The POST override handles a timing edge case: user loads edit form while window is still future, waits, then submits after window has started.

#### The Error Message

```python
"This maintenance window has already started or passed and cannot be "
"modified through the web interface."
```

Key message elements:

| Element | Purpose |
|---------|---------|
| "already started or passed" | Explains the condition that triggered the error |
| "cannot be modified" | Clear statement of what's not allowed |
| "through the web interface" | Hints that admin access may still work |

#### Why Redirect Instead of Showing 404?

| Approach | User Experience |
|----------|-----------------|
| **404 page** | Confusing—user knows the window exists |
| **403 Forbidden** | Implies permission issue, not temporal restriction |
| **Redirect with message** | Returns user to familiar context with clear explanation |

The redirect approach maintains the user's mental model of the application while clearly communicating why the action failed.

### 5.11.8 Template-Level Hiding

The list template (implemented in TODO 3) already hides edit/delete buttons for windows that have started:

```html
{% if window.is_upcoming %}
    <a href="{% url 'coldfront_orcd_direct_charge:maintenance-window-update' window.pk %}" 
       class="btn btn-sm btn-outline-secondary">
        <i class="fas fa-edit"></i> Edit
    </a>
    <a href="{% url 'coldfront_orcd_direct_charge:maintenance-window-delete' window.pk %}" 
       class="btn btn-sm btn-outline-danger">
        <i class="fas fa-trash"></i> Delete
    </a>
{% endif %}
```

#### Why Both Layers Are Needed

| Scenario | Template Only | Server Only | Both |
|----------|---------------|-------------|------|
| Normal browsing | ✓ Works | Works but buttons visible | ✓ Best UX |
| Direct URL access | ✗ Fails | ✓ Works | ✓ Works |
| Bookmarked URL | ✗ Fails | ✓ Works | ✓ Works |
| Stale browser tab | ✗ Fails | ✓ Works | ✓ Works |
| Malicious access attempt | ✗ Fails | ✓ Works | ✓ Works |

**Template hiding improves UX** by not showing actions users can't take. **Server validation enforces security** regardless of how the request arrives.

### 5.11.9 The Admin Escape Hatch

Unlike the web UI, Django Admin allows editing all maintenance windows including past ones.

#### Why Admin Allows Edits

| Use Case | Why Admin Access Needed |
|----------|-------------------------|
| **Data entry correction** | Typo in end time discovered after window passed |
| **Billing dispute resolution** | Customer questions charges, needs adjustment |
| **Audit response** | External auditor requires documentation correction |
| **Emergency rollback** | Accidental creation of incorrect window |

#### Implementation Note

No code explicitly enables admin editing—it's the default behavior. The restrictions we implemented are:
- **Only in web views** (`UpdateView`, `DeleteView`)
- **Not in ModelAdmin** (no `get_queryset` override in admin)

The `MaintenanceWindowAdmin` class (from TODO 7) uses the default queryset that includes all records.

#### Trust Model Comparison

| Interface | Assumed User | Editing Restrictions |
|-----------|--------------|---------------------|
| Web UI | Operational rental manager | Future windows only |
| Django Admin | System administrator | All windows (with audit logging) |
| Management commands | DevOps/automation | Depends on command design |

### 5.11.10 Pattern Parallels

This restriction pattern appears elsewhere in the codebase:

| Feature | Restriction | Implementation |
|---------|-------------|----------------|
| **Maintenance windows** | Cannot edit past/in-progress | `get_queryset` + `get`/`post` override |
| **Reservation approval** | Cannot approve already-processed | Status check in `post()` |
| **Invoice finalization** | Cannot edit finalized invoices | Status-based queryset filter |

The pattern of "filter queryset + catch 404 + redirect with message" is reusable for any temporal or state-based editing restriction.

### 5.11.11 Verification

#### Verify get_queryset Filtering

```python
# Django shell
from django.utils import timezone
from datetime import timedelta
from coldfront_orcd_direct_charge.models import MaintenanceWindow

# Create test windows
now = timezone.now()

future_window = MaintenanceWindow.objects.create(
    title="Future Window",
    start_datetime=now + timedelta(days=1),
    end_datetime=now + timedelta(days=1, hours=4),
)

past_window = MaintenanceWindow.objects.create(
    title="Past Window",
    start_datetime=now - timedelta(days=1),
    end_datetime=now - timedelta(days=1) + timedelta(hours=4),
)

# Simulate view's get_queryset
editable_windows = MaintenanceWindow.objects.filter(start_datetime__gt=timezone.now())

print(f"Future window in queryset: {future_window in editable_windows}")  # True
print(f"Past window in queryset: {past_window in editable_windows}")      # False

# Cleanup
future_window.delete()
past_window.delete()
```

#### Verify Redirect Behavior

| Test | Steps | Expected Result |
|------|-------|-----------------|
| **Edit past window URL** | Navigate to `/maintenance-windows/{past_pk}/edit/` | Redirect to list with error message |
| **Delete past window URL** | Navigate to `/maintenance-windows/{past_pk}/delete/` | Redirect to list with error message |
| **Edit future window URL** | Navigate to `/maintenance-windows/{future_pk}/edit/` | Form displays normally |
| **Error message displayed** | After redirect from past window | Red alert with explanation |

#### Verify Template Hiding

| Test | Steps | Expected Result |
|------|-------|-----------------|
| **Future window in list** | View maintenance window list | Edit/Delete buttons visible |
| **Past window in list** | View maintenance window list | No Edit/Delete buttons |
| **In-progress window** | Create window starting now | No Edit/Delete buttons |

#### Verify Admin Still Works

```python
# In Django admin or shell
from django.contrib import admin
from coldfront_orcd_direct_charge.models import MaintenanceWindow

# Verify admin can access all windows
admin_class = admin.site._registry[MaintenanceWindow]
all_windows = admin_class.get_queryset(request=None)

# Should include both past and future windows
print(f"Total windows accessible in admin: {all_windows.count()}")
```

#### Edge Case: Window Starts While User on Edit Page

| Step | What Happens |
|------|--------------|
| 1 | User loads edit form for window starting in 5 minutes |
| 2 | User spends 10 minutes editing |
| 3 | User submits form |
| 4 | Server checks `get_object()` against filtered queryset |
| 5 | Window has now started → Http404 caught |
| 6 | User sees error message and redirect |

This edge case is handled by the `post()` override, which re-validates the window's eligibility at submission time.

---

> **Summary:** TODO 11 implements server-side restrictions preventing modification of past and in-progress maintenance windows. The `get_queryset` method filters to future windows only (`start_datetime__gt=timezone.now()`), and the `get()` and `post()` methods catch the resulting `Http404` exception to provide a user-friendly error message and redirect. This defense-in-depth approach complements the template-level button hiding from TODO 3, ensuring protection even when users access edit URLs directly. The Django Admin intentionally retains full editing capability for administrative corrections, following a trust model where web UI users are restricted but system administrators have override access.

## 5.12 TODO 12: Create Documentation

### 5.12.1 Objective

Create comprehensive documentation for the maintenance windows feature that serves multiple audiences: developers who need to understand the implementation, operators who need to use the feature, and API consumers who need programmatic access.

### 5.12.2 Prerequisites

Completion of all previous TODOs:
- TODO 1-2: Model and migrations
- TODO 3: List view with templates
- TODO 4: Create/Edit/Delete views
- TODO 5-6: Billing integration
- TODO 7: Django Admin
- TODO 8: Activity logging
- TODO 9: REST API
- TODO 10: Management commands
- TODO 11: Edit/delete restrictions

### 5.12.3 Concepts Applied

| Concept | Application |
|---------|-------------|
| **Audience-appropriate documentation** | Different sections for different users (UI, API, commands) |
| **Example-driven explanations** | Billing calculations shown through concrete scenarios |
| **Progressive disclosure** | Overview first, then detailed specifications |
| **Cross-referencing** | Documentation links between related docs |
| **Living documentation** | Updates to existing docs when adding features |

### 5.12.4 Files Created/Modified

| File | Purpose |
|------|---------|
| `developer_docs/maintenance-windows.md` | **New** - Main feature documentation |
| `developer_docs/data-models.md` | **Updated** - Added MaintenanceWindow model |
| `developer_docs/api-reference.md` | **Updated** - Added API endpoints and serializer |
| `README.md` | **Updated** - Feature overview and quick reference |

### 5.12.5 The Main Documentation File

The `maintenance-windows.md` file serves as the authoritative reference for the feature.

#### Document Structure

```
maintenance-windows.md
├── Overview                    # What and why
├── Model Schema                # Database structure
├── Billing Calculation Algorithm  # Technical deep-dive
├── Invoicing Examples          # Concrete scenarios
├── Web UI                      # User-facing documentation
├── REST API                    # Programmatic access
├── Management Commands         # CLI automation
├── Activity Logging            # Audit trail
├── Export/Import               # Backup integration
├── Django Admin                # Admin interface
└── Related Documentation       # Cross-references
```

#### Key Documentation Sections

| Section | Audience | Content |
|---------|----------|---------|
| **Model Schema** | Developers | Table structure, field types, computed properties |
| **Billing Algorithm** | Developers, Operators | Step-by-step calculation with pseudocode |
| **Invoicing Examples** | Operators, Users | Four concrete scenarios with numbers |
| **Web UI** | Operators | Status badges, restrictions, help system |
| **REST API** | API consumers | Endpoints, authentication, request/response examples |
| **Management Commands** | DevOps | Command syntax with all arguments |

#### Example-Driven Billing Documentation

Rather than abstract descriptions, the documentation includes four numbered examples:

```markdown
### Example 2: Rental Partially Overlapping

Rental: Feb 14 4PM - Feb 16 9AM (41 hours)
Maintenance Window: Feb 15 8AM - Feb 15 8PM (12 hours)

Calculation:
  - Raw hours: 41
  - Overlap: Feb 15 8AM - Feb 15 8PM = 12 hours
  - Deduction: 12 hours

Result: 29 billable hours
```

This approach shows exact inputs, calculations, and outputs—making the algorithm verifiable.

### 5.12.6 Updates to Existing Documentation

#### data-models.md Additions

Added a new "Maintenance Window Models" section to the table of contents and model documentation:

```markdown
## Maintenance Window Models

### MaintenanceWindow

Scheduled maintenance periods during which rentals are not billed.

**Table**: `coldfront_orcd_direct_charge_maintenancewindow`

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `title` | CharField(200) | Short title describing the maintenance |
| `start_datetime` | DateTimeField | When the maintenance period begins |
| `end_datetime` | DateTimeField | When the maintenance period ends |
...
```

Also included usage examples showing common queries:

```python
# Query upcoming windows
upcoming = MaintenanceWindow.objects.filter(
    start_datetime__gt=timezone.now()
)

# Get windows overlapping a time period
overlapping = MaintenanceWindow.objects.filter(
    start_datetime__lt=end_dt,
    end_datetime__gt=start_dt
)
```

#### api-reference.md Additions

Added complete API documentation including:

1. **Endpoint table** in the overview section
2. **Full CRUD documentation** with request/response examples
3. **Query parameters** for filtering by status
4. **Serializer definition** showing all fields

```markdown
### Maintenance Windows API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/nodes/api/maintenance-windows/` | List all maintenance windows |
| POST | `/nodes/api/maintenance-windows/` | Create a new maintenance window |
| GET | `/nodes/api/maintenance-windows/{id}/` | Get maintenance window detail |
| PUT | `/nodes/api/maintenance-windows/{id}/` | Update a maintenance window |
| PATCH | `/nodes/api/maintenance-windows/{id}/` | Partially update |
| DELETE | `/nodes/api/maintenance-windows/{id}/` | Delete a maintenance window |
```

#### README.md Additions

Updated the main README with:

1. **Features Overview** - Added "Maintenance Windows" bullet points
2. **URL Endpoints** - New table section for maintenance window URLs
3. **Management Commands** - Command examples for create/list/delete

### 5.12.7 Documentation Best Practices

#### Example-Driven Approach

| Principle | Application |
|-----------|-------------|
| **Show, don't tell** | Billing examples with actual numbers |
| **Cover edge cases** | Multiple windows, no overlap, full overlap scenarios |
| **Executable examples** | curl commands that actually work |
| **Copy-pasteable** | Code blocks formatted for easy reuse |

#### Keeping Documentation in Sync

| Strategy | Implementation |
|----------|----------------|
| **Document alongside code** | Write docs as features are implemented |
| **Single source of truth** | Main doc with cross-references, not duplication |
| **Update all affected docs** | When adding feature, update data-models, api-reference, README |
| **Version with code** | Documentation in same repo as code |

#### Cross-Referencing Strategy

The documentation uses relative links between files:

```markdown
## Related Documentation

- [Data Models Reference](data-models.md) - MaintenanceWindow model details
- [API Reference](api-reference.md) - REST API endpoints
- [Activity Logging](signals.md) - Activity log integration
```

This allows readers to navigate based on their needs without duplicating content.

### 5.12.8 Pattern Parallels

The documentation structure mirrors existing feature documentation:

| Document Section | Maintenance Windows | Reservations | Cost Allocations |
|------------------|---------------------|--------------|------------------|
| Model schema | ✓ Table + properties | ✓ Table + properties | ✓ Table + properties |
| API endpoints | ✓ Full CRUD | ✓ List + detail | ✓ List + detail |
| Management commands | ✓ 3 commands | N/A | N/A |
| Usage examples | ✓ Billing scenarios | ✓ Time calculations | ✓ Percentage splits |
| Admin interface | ✓ Documented | ✓ Documented | ✓ Documented |

This consistency helps developers find information quickly by following established patterns.

### 5.12.9 Verification

#### Documentation Completeness Checklist

| Item | File | Status |
|------|------|--------|
| Model schema documented | maintenance-windows.md | ✓ |
| Billing algorithm explained | maintenance-windows.md | ✓ |
| Concrete examples provided | maintenance-windows.md | ✓ |
| Web UI documented | maintenance-windows.md | ✓ |
| API endpoints documented | maintenance-windows.md + api-reference.md | ✓ |
| Management commands documented | maintenance-windows.md + README.md | ✓ |
| Data models updated | data-models.md | ✓ |
| README updated | README.md | ✓ |
| Cross-references in place | All docs | ✓ |

#### Verify Links Work

```bash
# Check that cross-referenced files exist
ls developer_docs/maintenance-windows.md
ls developer_docs/data-models.md
ls developer_docs/api-reference.md
ls README.md
```

#### Verify Examples Are Accurate

| Example Type | How to Verify |
|--------------|---------------|
| **Billing calculations** | Run through actual billing code with same inputs |
| **API requests** | Execute curl commands against running server |
| **Management commands** | Run with `--dry-run` or `--help` |
| **Model properties** | Check against actual model definition |

---

> **Summary:** TODO 12 creates comprehensive documentation for the maintenance windows feature. The main documentation file (`maintenance-windows.md`) follows an audience-aware structure with model schema, billing algorithm, concrete examples, UI documentation, API reference, and CLI commands. Existing documentation files (`data-models.md`, `api-reference.md`, `README.md`) are updated to incorporate the new feature. The documentation follows best practices including example-driven explanations, cross-referencing between documents, and consistency with existing documentation patterns. This ensures the feature is discoverable, understandable, and usable by developers, operators, and API consumers.

---

# Section 6: Agentic Development Process

This section explains how AI agents were used to implement the maintenance window feature. It provides insight into the planning phase, the structure of the implementation plan, how agents were directed, and lessons learned from the agentic development approach.

---

## 6.1 The Planning Phase

### 6.1.1 Initial User Request

The development session began with a user request to add a "maintenance window" feature. The original requirements were expressed naturally:

> "Add a maintenance window feature that allows rental managers to define time periods when nodes are under maintenance. During these periods, rentals should not be billed. Users should be able to create, view, edit, and delete maintenance windows through the web interface, API, and command line."

This request contained several implicit requirements that needed to be extracted and made explicit during planning.

### 6.1.2 Codebase Exploration Strategy

Before creating the implementation plan, extensive codebase exploration was conducted to understand:

| Exploration Goal | Discovery Method |
|------------------|------------------|
| **Existing patterns** | Semantic search for similar features (e.g., "How are reservations modeled?") |
| **File structure** | Directory listing and glob patterns |
| **Naming conventions** | Grep for existing model names, URL patterns, template locations |
| **Integration points** | Reading billing.py, urls.py, serializers.py to find extension points |
| **Plugin architecture** | Understanding how ColdFront plugins hook into the core system |

**Parallel Discovery Agents**

Multiple exploratory searches were conducted simultaneously to build context quickly:

```
Agent 1: "What models exist in coldfront_orcd_direct_charge?"
Agent 2: "How does the billing calculation work in views/billing.py?"
Agent 3: "What is the pattern for Django admin registration in this codebase?"
Agent 4: "How are management commands structured in this plugin?"
```

This parallel exploration provided comprehensive context within seconds rather than sequential exploration taking multiple iterations.

### 6.1.3 Requirements Extraction

From the natural language request, explicit requirements were derived:

**Functional Requirements:**

1. CRUD operations for maintenance windows (create, read, update, delete)
2. Multiple access interfaces (web UI, REST API, CLI)
3. Automatic billing adjustment when rentals overlap maintenance periods
4. Visibility of deductions on invoices
5. Audit trail for maintenance window changes

**Non-Functional Requirements:**

1. Follow existing codebase patterns and conventions
2. Integrate with the existing backup/export system
3. Maintain billing accuracy (restrict editing of past windows)
4. Provide in-context help for users

**Derived Requirements (Not Explicitly Stated):**

| Requirement | Derivation Source |
|-------------|-------------------|
| Activity logging | Existing pattern for all CRUD operations |
| Export/import support | Existing backup system includes all models |
| Django admin registration | Existing pattern for all plugin models |
| Help text modal | Requested as improvement for user experience |
| Edit restrictions | Implied by "billing accuracy" concern |

### 6.1.4 Plan Document Creation

The planning phase produced a structured plan document (`maintenance_window_feature_21286014.plan.md`) containing:

1. **Overview**: High-level description of the feature
2. **Execution model**: How agents should process the plan
3. **12 TODOs**: Self-contained implementation tasks
4. **File changes summary**: Complete list of files to create/modify
5. **PR description template**: Ready-to-use pull request content

### 6.1.5 Iterative Refinement

The initial plan underwent several refinements based on user feedback:

| Iteration | Feedback | Plan Adjustment |
|-----------|----------|-----------------|
| 1 | "Should maintenance windows affect all nodes or specific ones?" | Clarified system-wide application |
| 2 | "What about editing past windows?" | Added TODO 11 for edit restrictions |
| 3 | "Users need help understanding the feature" | Added TODO 10 for modular help text system |
| 4 | "How will users discover this feature?" | Specified navbar integration in TODO 3 |

This iterative refinement ensured the plan addressed all user concerns before execution began.

---

## 6.2 Plan Structure

### 6.2.1 Organization into 12 TODOs

The implementation was decomposed into 12 discrete tasks:

| TODO | Scope | Estimated Size |
|------|-------|----------------|
| 1: Model & Migration | Database layer | ~60 lines |
| 2: Billing Calculations | Business logic | ~80 lines |
| 3: Web UI Views & Templates | Presentation layer | ~200 lines |
| 4: REST API | External interface | ~80 lines |
| 5: Management Commands | CLI interface | ~150 lines |
| 6: Export/Import | Data portability | ~60 lines |
| 7: Django Admin | Admin interface | ~50 lines |
| 8: Activity Logging | Audit trail | ~40 lines |
| 9: Invoice Display | User feedback | ~30 lines |
| 10: Help Text System | Documentation | ~100 lines |
| 11: Edit Restrictions | Business rules | ~70 lines |
| 12: Documentation | Reference material | ~300 lines |

### 6.2.2 Self-Contained Task Units

Each TODO was designed as a self-contained unit with:

```markdown
## TODO N: [Title]

**Agent Instructions:** [One-sentence summary]

### Prerequisites
- [List of TODOs that must be completed first]

### Files to Create/Modify
1. `[Full path to file 1]`
2. `[Full path to file 2]`

### Steps
1. [Specific instruction with code example]
2. [Specific instruction with code example]
...

### Verification
- [How to confirm completion]
```

This structure enabled agents to:
- Understand scope without reading other TODOs
- Know exactly which files to touch
- Have code examples to follow
- Verify their own work

### 6.2.3 Dependency Management

The plan explicitly defined dependencies between TODOs:

```
TODO 1 (Model)
    ├── TODO 2 (Billing) ──► TODO 9 (Invoice Display)
    ├── TODO 3 (Web UI) ──► TODO 8 (Activity Log)
    │       ├── TODO 10 (Help Text)
    │       └── TODO 11 (Edit Restrictions)
    ├── TODO 4 (API)
    ├── TODO 5 (Commands)
    ├── TODO 6 (Export/Import)
    └── TODO 7 (Admin)
            └── TODO 12 (Documentation) [depends on all]
```

**Dependency Rules Applied:**

| Rule | Example |
|------|---------|
| **Foundation first** | TODO 1 (model) before any feature using it |
| **Layer dependencies** | TODO 2 (billing logic) before TODO 9 (display) |
| **Integration dependencies** | TODO 3 (views) before TODO 8 (activity logging in views) |
| **Documentation last** | TODO 12 after all features implemented |

### 6.2.4 File Paths and Code Examples

Each TODO included:

**Complete File Paths:**

```markdown
### Files to Modify

1. **`/Users/cnh/projects/orcd-rental-portal-002/cf-orcd-rental/coldfront_orcd_direct_charge/models.py`**
```

Using absolute paths eliminated ambiguity about file locations.

**Inline Code Examples:**

```markdown
### Steps

2. Add the `MaintenanceWindow` model after the `ReservationMetadataEntry` class (around line 376):

```python
class MaintenanceWindow(TimeStampedModel):
    """Scheduled maintenance period during which rentals are not billed."""
    
    start_datetime = models.DateTimeField(
        help_text="When the maintenance period begins"
    )
    # ... full model code ...
```

Code examples served as templates that agents could adapt based on actual file contents.

---

## 6.3 Agent Execution Model

### 6.3.1 One Agent Per TODO

Each TODO was executed by a separate agent instance. This provided:

| Benefit | Explanation |
|---------|-------------|
| **Clean context** | Each agent started with fresh context, no accumulated confusion |
| **Focused attention** | Agent concentrated on single, well-defined task |
| **Error isolation** | Mistakes in one TODO didn't propagate to others |
| **Parallel potential** | Independent TODOs could theoretically run simultaneously |

### 6.3.2 Sequential Execution

Despite parallel potential, TODOs were executed sequentially to:

1. **Respect dependencies**: Ensure prerequisite code exists
2. **Enable learning**: Later agents could reference patterns established by earlier ones
3. **Simplify verification**: Each TODO verified before proceeding
4. **Handle conflicts**: Avoid multiple agents modifying same files

**Execution Flow:**

```
┌──────────────┐
│ Read Plan    │
└──────┬───────┘
       │
       ▼
┌──────────────┐     ┌──────────────┐
│ TODO 1 Agent │────►│ Verify TODO 1│
└──────┬───────┘     └──────┬───────┘
       │                    │
       ▼                    ▼
┌──────────────┐     ┌──────────────┐
│ TODO 2 Agent │────►│ Verify TODO 2│
└──────┬───────┘     └──────┬───────┘
       │                    │
      ...                  ...
       │                    │
       ▼                    ▼
┌──────────────┐     ┌──────────────┐
│ TODO 12 Agent│────►│ Final Review │
└──────────────┘     └──────────────┘
```

### 6.3.3 Agent Prompt Structure

Each agent prompt included:

| Component | Purpose |
|-----------|---------|
| **Plan reference** | "Read the implementation plan at [path]" |
| **TODO identification** | "Execute TODO N: [title]" |
| **Context setting** | Summary of what previous TODOs accomplished |
| **Success criteria** | "Verify that [specific outcomes]" |
| **Constraint reminders** | "Follow existing patterns in the codebase" |

### 6.3.4 Example Agent Prompts

**Example 1: TODO 1 (Model) Prompt**

```
Read the implementation plan at /Users/cnh/.cursor/plans/maintenance_window_feature_21286014.plan.md

Execute TODO 1: Create MaintenanceWindow Model and Migration

This is the first TODO and has no prerequisites.

Instructions:
1. Read the existing models.py to understand patterns (TimeStampedModel, ForeignKey usage, etc.)
2. Add the MaintenanceWindow model as specified in the plan
3. Generate the migration using makemigrations
4. Verify the model can be imported without errors

Success criteria:
- MaintenanceWindow class exists in models.py
- Migration file created in migrations/ directory
- No syntax errors or import failures
```

**Example 2: TODO 3 (Web UI) Prompt**

```
Read the implementation plan at /Users/cnh/.cursor/plans/maintenance_window_feature_21286014.plan.md

Execute TODO 3: Create Views, URLs, and Templates for Maintenance Window CRUD

Prerequisites completed:
- TODO 1: MaintenanceWindow model exists in models.py
- TODO 2: Billing calculations updated

Instructions:
1. Read existing views in views/rentals.py to understand patterns (mixins, permissions)
2. Create the four view classes (List, Create, Update, Delete)
3. Add URL patterns to urls.py following existing naming conventions
4. Create templates matching the existing template structure
5. Add navbar entry for rental managers

Success criteria:
- All four views render without errors
- URLs resolve correctly
- Templates extend the correct base template
- Navbar shows "Maintenance Windows" for authorized users
```

**Example 3: TODO 8 (Activity Logging) Prompt**

```
Read the implementation plan at /Users/cnh/.cursor/plans/maintenance_window_feature_21286014.plan.md

Execute TODO 8: Add Activity Logging for Maintenance Window Actions

Prerequisites completed:
- TODO 1: MaintenanceWindow model exists
- TODO 3: Views exist in views/rentals.py

Instructions:
1. Read how log_activity is used in other views (search for existing usage patterns)
2. Import log_activity and ActivityLog in views/rentals.py
3. Add logging calls to form_valid() methods in Create, Update, and Delete views
4. Use category=ActivityLog.ActionCategory.MAINTENANCE

Success criteria:
- Activity log entries created for create, update, delete actions
- Log entries visible in admin or activity log view
- Extra data includes relevant window information
```

---

## 6.4 Prompt Engineering Patterns

### 6.4.1 Context Setting Pattern

Begin prompts with clear context about the current state:

```
Prerequisites completed:
- TODO 1: MaintenanceWindow model exists in models.py
- TODO 2: Billing calculations updated with maintenance deduction logic
- TODO 3: Views, URLs, and templates created

Current state:
- Four view classes exist but lack activity logging
- No audit trail when users create/modify/delete windows
```

This pattern prevents agents from making assumptions about codebase state.

### 6.4.2 File Reference Pattern

Provide explicit file paths with contextual hints:

```
### Files to Modify

1. **`/Users/cnh/projects/.../views/rentals.py`**
   - Add imports at the top of file
   - Modify MaintenanceWindowCreateView.form_valid() method

2. **`/Users/cnh/projects/.../models.py`**
   - The log_activity function is defined here (import it)
   - ActivityLog.ActionCategory enum is also here
```

This pattern tells agents both WHERE and WHAT to change.

### 6.4.3 Pattern Matching Pattern

Instruct agents to learn from existing code:

```
1. Read existing views in views/rentals.py to understand patterns:
   - How are permissions enforced (which mixins)?
   - What is the naming convention for success URLs?
   - How are success messages created?

2. Create your views following the same patterns
```

This pattern ensures consistency without specifying every detail.

### 6.4.4 Verification Request Pattern

End instructions with explicit verification steps:

```
### Verification

After completing this TODO, verify:
- [ ] All four URL patterns resolve without errors
- [ ] Templates render when views are accessed
- [ ] Permissions restrict access to rental managers only
- [ ] Form submissions save to database correctly

Test commands:
```bash
python manage.py check  # No errors
python manage.py test coldfront_orcd_direct_charge.tests.test_views  # If tests exist
```
```

This pattern enables agents to self-verify their work.

### 6.4.5 Constraint Specification Pattern

Explicitly state what NOT to do:

```
Constraints:
- Do NOT modify the billing algorithm itself
- Do NOT create new template base classes
- Do NOT add dependencies to requirements.txt
- Follow the existing form styling (Bootstrap classes)
- Use existing message framework, don't create custom notifications
```

This pattern prevents scope creep and unintended changes.

---

## 6.5 Agent Coordination

### 6.5.1 TODO Status Tracking

The plan file used YAML frontmatter to track TODO status:

```yaml
---
name: Maintenance Window Feature
todos:
  - id: 1-model
    content: "TODO 1: Create MaintenanceWindow model and migration"
    status: completed
  - id: 2-billing
    content: "TODO 2: Update billing.py to deduct maintenance hours"
    status: completed
  - id: 3-web-ui
    content: "TODO 3: Create views, URLs, and templates"
    status: in_progress
  - id: 4-api
    content: "TODO 4: Add serializer, viewset, and API routes"
    status: pending
  ...
---
```

Status transitions:

| Status | Meaning |
|--------|---------|
| `pending` | Not yet started |
| `in_progress` | Currently being executed by an agent |
| `completed` | Successfully finished and verified |
| `blocked` | Cannot proceed due to dependency or issue |

### 6.5.2 Agent Result Reporting

After completing a TODO, agents reported:

1. **Files modified**: List of files changed with line counts
2. **Summary of changes**: Bullet-point description of what was implemented
3. **Verification results**: Outcome of test commands or manual checks
4. **Issues encountered**: Any deviations from the plan
5. **Notes for subsequent TODOs**: Information needed by dependent tasks

**Example Result Report:**

```
## TODO 3 Completed

### Files Modified
- views/rentals.py: +120 lines (4 view classes)
- urls.py: +6 lines (4 URL patterns)
- templates/.../maintenance_window/list.html: +60 lines (new file)
- templates/.../maintenance_window/form.html: +45 lines (new file)
- templates/.../maintenance_window/delete.html: +25 lines (new file)
- templates/common/authorized_navbar.html: +1 line (dropdown entry)

### Summary
- Created MaintenanceWindowListView, CreateView, UpdateView, DeleteView
- Added URL patterns with names for reverse lookups
- Templates extend common/base.html with card-based layout
- Navbar entry added under Admin Functions dropdown

### Verification
- `python manage.py check`: No errors
- Manual testing: All views render correctly
- Permission check: Non-managers get 403 Forbidden

### Notes for TODO 8
- Views are in views/rentals.py after line 450
- form_valid() methods exist but have no logging yet
```

### 6.5.3 Handling Agent Output

Agent output was processed in several ways:

| Output Type | Processing |
|-------------|------------|
| **Code changes** | Automatically written to files via tool calls |
| **Status updates** | Plan file updated with new TODO status |
| **Verification failures** | Agent instructed to fix issues before proceeding |
| **Blockers** | User notified, plan adjusted if needed |

**Error Recovery Flow:**

```
┌─────────────────┐
│ Agent executes  │
│ TODO            │
└────────┬────────┘
         │
         ▼
    ┌────────────┐
    │ Verify     │
    └────┬───────┘
         │
    ┌────┴────┐
    │         │
Success    Failure
    │         │
    ▼         ▼
┌────────┐ ┌────────────────┐
│ Update │ │ Agent fixes    │
│ status │ │ and re-verifies│
│ to     │ └───────┬────────┘
│complete│         │
└────────┘         ▼
              ┌────────────┐
              │ Still      │
              │ failing?   │
              └────┬───────┘
                   │
              ┌────┴────┐
              │         │
             No        Yes
              │         │
              ▼         ▼
         ┌────────┐ ┌───────────────┐
         │Continue│ │Escalate to    │
         │to next │ │user for help  │
         │TODO    │ └───────────────┘
         └────────┘
```

---

## 6.6 Lessons Learned

### 6.6.1 What Worked Well

**1. Detailed Planning Paid Off**

| Investment | Return |
|------------|--------|
| 2 hours planning | 12 TODOs executed with minimal issues |
| Explicit file paths | Zero confusion about file locations |
| Code examples in plan | Consistent implementation style |
| Verification criteria | Self-correcting agents |

**2. Pattern Matching Instructions**

Telling agents "read existing X to understand patterns" was more effective than specifying every detail. Agents learned from the codebase and produced consistent code.

**3. Self-Contained TODOs**

Each TODO having its own prerequisites, files, steps, and verification enabled:
- Clean handoffs between agents
- Easy status tracking
- Parallel debugging (could examine one TODO in isolation)

**4. Iterative Plan Refinement**

User feedback during planning caught issues before implementation:
- Added TODO 10 (help text) based on UX concern
- Added TODO 11 (edit restrictions) based on data integrity concern
- Clarified scope of TODO 2 (billing) to avoid over-complexity

### 6.6.2 Challenges Encountered

**1. Cross-TODO Dependencies Not Always Clear**

| Issue | Impact | Resolution |
|-------|--------|------------|
| TODO 8 needed to know TODO 3's class names | Agent had to read TODO 3's output first | Added "Notes for subsequent TODOs" to result reports |
| TODO 9 needed billing context variable names | Agent made assumptions | Standardized naming in plan |

**2. Template Inheritance Complexity**

Agents sometimes struggled with Django template inheritance when:
- Base template had multiple block regions
- Block names weren't intuitive
- Multiple levels of extension existed

Resolution: Added explicit block names and inheritance chain to plan.

**3. Testing Gaps**

The plan focused on implementation but not automated tests:
- No unit test TODOs included
- Verification was manual or basic
- Regression detection relied on future work

Future Improvement: Include test writing as explicit TODOs.

**4. Import Statement Ordering**

Multiple agents adding imports to the same file caused:
- Inconsistent import grouping
- Potential duplicate imports
- PEP 8 style violations

Resolution: Later agents instructed to review and clean up imports.

### 6.6.3 Improvements for Future Sessions

| Improvement | Benefit |
|-------------|---------|
| **Include test TODOs** | Automated verification, regression prevention |
| **Specify import conventions** | Consistent file headers |
| **Add code review TODO** | Final cleanup pass for style/consistency |
| **Create rollback instructions** | Recovery path if feature needs reverting |
| **Document agent handoff protocol** | Formalize information passing between TODOs |

### 6.6.4 When to Split vs Combine Tasks

**Split Tasks When:**

| Indicator | Example |
|-----------|---------|
| **Different skill domains** | Model (DB) vs Template (HTML) vs API (DRF) |
| **Different files** | views.py vs urls.py vs templates |
| **Sequential dependencies** | Model before views that use model |
| **High complexity** | Billing algorithm deserves focused attention |
| **Verification needed mid-way** | Model must work before building on it |

**Combine Tasks When:**

| Indicator | Example |
|-----------|---------|
| **Tightly coupled changes** | View + its template + its URL |
| **Single concept** | All three management commands (one CLI interface) |
| **Minimal context switching** | Updates to same file section |
| **Low complexity** | Simple admin registration |

**Task Sizing Heuristics:**

| Size | Lines of Code | Complexity | Files |
|------|---------------|------------|-------|
| **Too small** | <20 lines | Trivial | 1 file |
| **Ideal** | 50-150 lines | Moderate | 1-3 files |
| **Too large** | >300 lines | High | >5 files |

Too-small tasks have high overhead (agent startup, context loading). Too-large tasks risk agent context exhaustion and error accumulation.

---

## 6.7 Document Summary

This tutorial document has provided a comprehensive walkthrough of the maintenance window feature, from abstract concepts to concrete implementation details, and finally to the agentic development process that produced it.

### What We Covered

| Section | Content | Audience |
|---------|---------|----------|
| **Section 1: Introduction** | Problem statement, requirements, session overview | All readers |
| **Section 2: Foundations** | Django fundamentals, ColdFront architecture | Non-Django developers |
| **Section 3: Key Concepts** | Django patterns, plugin patterns, billing system | Intermediate readers |
| **Section 4: TODO Overview** | Architecture, dependencies, concept mapping | All readers |
| **Section 5: Detailed Walkthroughs** | 12 TODO implementations with code | Developers |
| **Section 6: Agentic Process** | Planning, prompts, coordination, lessons | AI practitioners |

### The Complete Feature

The maintenance window feature, as implemented across 12 TODOs, provides:

**Core Functionality:**
- `MaintenanceWindow` model with start/end times, title, description
- Automatic billing deduction for rental-maintenance overlap
- Multi-day, multi-window overlap handling

**User Interfaces:**
- Web UI with list, create, edit, delete views
- Status badges (Upcoming, In Progress, Completed)
- In-context help modal with markdown rendering
- Navbar integration under Admin Functions
- Edit/delete restrictions for past windows

**Programmatic Access:**
- REST API with full CRUD and status filtering
- Management commands for CLI automation
- Export/import integration for backups

**Operational Features:**
- Activity logging for audit trails
- Invoice display of maintenance deductions
- Django Admin for administrative overrides

**Documentation:**
- Developer documentation with billing examples
- API reference with request/response samples
- Model reference in data-models.md
- README updates with feature overview

### Key Takeaways

**For Django Developers:**
- Class-based views with mixins provide reusable, composable behavior
- Template inheritance enables consistent UI across pages
- Custom template tags extend Django's template language
- QuerySet filtering in `get_queryset()` enables row-level security

**For ColdFront Plugin Developers:**
- Follow existing patterns in models.py, views/, api/, and templates/
- Register models in admin.py for administrative access
- Add exporters/importers to the backup system
- Use log_activity() for audit trail compliance

**For AI-Assisted Development Practitioners:**
- Detailed plans with file paths and code examples reduce agent errors
- Pattern-matching instructions leverage codebase consistency
- Self-contained TODOs enable clean agent handoffs
- Verification criteria enable agent self-correction
- Post-execution result reports maintain coordination

---

> **Final Summary:** The maintenance window feature demonstrates how a substantial Django feature can be systematically implemented through plan-driven, agentic development. The 12-TODO structure provided clear organization, explicit dependencies, and measurable verification criteria. The agentic approach—one agent per TODO, pattern-matching instructions, explicit context setting—produced consistent, well-integrated code that follows existing codebase conventions. This tutorial serves as both a learning resource for Django/ColdFront development and a reference for agentic software engineering practices.

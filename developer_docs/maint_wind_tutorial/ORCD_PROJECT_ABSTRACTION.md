# ORCD Project Abstraction: Extending ColdFront's Project Model

## Overview

This document explains how the ORCD Direct Charge plugin extends ColdFront's base project model with domain-specific role management. Understanding this layered architecture is essential for developers working with the rental portal system.

---

## The Layered Architecture

The ORCD Rental Portal follows a layered plugin architecture where each layer adds domain-specific functionality:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Django Framework                                │
│                                                                              │
│  • User model (django.contrib.auth)                                          │
│  • Group and Permission models                                               │
│  • ORM and migrations                                                        │
│  • Admin interface                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ▲
                                      │ extends
                                      │
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ColdFront Core                                  │
│                                                                              │
│  • Project model (title, PI, status, description)                            │
│  • ProjectUser model (links users to projects with ColdFront roles)          │
│  • Allocation model (grants project access to resources)                     │
│  • Resource model (computing assets)                                         │
│  • ProjectStatusChoice, ProjectUserRoleChoice, ProjectUserStatusChoice       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ▲
                                      │ extends
                                      │
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ORCD Direct Charge Plugin                            │
│                                                                              │
│  • ProjectMemberRole model (ORCD-specific roles per user)                    │
│  • Reservation model (GPU node rentals)                                      │
│  • MaintenanceWindow model (scheduled downtime)                              │
│  • ProjectCostAllocation model (billing configuration)                       │
│  • InvoicePeriod, InvoiceLineOverride (billing records)                      │
│  • RentalSKU, RentalRate (pricing)                                           │
│  • GPUNode, NodeType (hardware inventory)                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ColdFront's Base Project Model

ColdFront provides the foundation for project management in research computing environments.

### Project Entity

The `Project` model is the core organizational unit in ColdFront:

```python
# From coldfront.core.project.models

class Project(models.Model):
    """A research project that can request resource allocations."""
    
    title = models.CharField(max_length=255)  # Unique project name
    pi = models.ForeignKey(User, ...)         # Principal Investigator (owner)
    status = models.ForeignKey(ProjectStatusChoice, ...)
    description = models.TextField(blank=True)
    # ... other fields
```

**Key Characteristics:**
- Every project has a Principal Investigator (PI) who owns the project
- Projects have a lifecycle status (New, Active, Archived)
- Projects can request allocations for various computing resources

### ProjectUser: ColdFront's Membership Model

ColdFront tracks project membership through `ProjectUser`:

```python
class ProjectUser(models.Model):
    """Links a user to a project with a ColdFront role."""
    
    project = models.ForeignKey(Project, ...)
    user = models.ForeignKey(User, ...)
    role = models.ForeignKey(ProjectUserRoleChoice, ...)  # "Manager" or "User"
    status = models.ForeignKey(ProjectUserStatusChoice, ...)  # "Active", "Pending", etc.
```

**ColdFront Roles:**

| Role | Description |
|------|-------------|
| **Manager** | Can manage project membership and request allocations |
| **User** | Basic project member, can use allocated resources |

These roles are **generic** and apply across all ColdFront functionality. They don't provide the granular permissions needed for GPU rental billing and management.

### ProjectStatusChoice and ProjectUserStatusChoice

ColdFront uses choice models for flexibility:

```python
class ProjectStatusChoice(models.Model):
    """Possible project statuses (New, Active, Archived)."""
    name = models.CharField(max_length=64, unique=True)

class ProjectUserStatusChoice(models.Model):
    """Possible membership statuses (Active, Pending Removal, etc.)."""
    name = models.CharField(max_length=64, unique=True)

class ProjectUserRoleChoice(models.Model):
    """Possible ColdFront roles (Manager, User)."""
    name = models.CharField(max_length=64, unique=True)
```

These are loaded via fixtures and referenced by foreign key, allowing administrators to customize status options without code changes.

---

## ORCD's Extension: ProjectMemberRole

The ORCD plugin extends ColdFront's project system with domain-specific roles for GPU rental billing.

### Why Extend?

ColdFront's "Manager" and "User" roles are too generic for rental billing:

| Requirement | ColdFront's Model | Problem |
|-------------|-------------------|---------|
| Financial management | Manager/User | No distinction between financial and technical duties |
| Technical oversight | Manager/User | No role for technical admins who shouldn't see billing |
| Billing exclusion | N/A | Some roles (financial_admin) shouldn't be billed for maintenance fees |
| Multiple roles | One role per user | Users may need both financial and technical permissions |

### ProjectMemberRole Model

The ORCD plugin adds a separate role model that works alongside `ProjectUser`:

```python
# From coldfront_orcd_direct_charge/models.py

class ProjectMemberRole(TimeStampedModel):
    """ORCD-specific role assignment for project members.
    
    This is SEPARATE from ColdFront's ProjectUser model. A user must have BOTH:
    1. A ProjectUser record (ColdFront requirement)
    2. One or more ProjectMemberRole records (ORCD requirement)
    """
    
    class RoleChoices(models.TextChoices):
        FINANCIAL_ADMIN = "financial_admin", "Financial Admin"
        TECHNICAL_ADMIN = "technical_admin", "Technical Admin"
        MEMBER = "member", "Member"
    
    project = models.ForeignKey(
        "coldfront.core.project.models.Project",
        on_delete=models.CASCADE,
        related_name="orcd_member_roles"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="orcd_project_roles"
    )
    role = models.CharField(
        max_length=20,
        choices=RoleChoices.choices
    )
    
    class Meta:
        unique_together = [("project", "user", "role")]
```

### ORCD Roles and Their Permissions

| Role | Description | Permissions | Billed for AMF? |
|------|-------------|-------------|-----------------|
| **financial_admin** | Financial oversight | Manage cost allocations, manage all roles, create reservations | **No** |
| **technical_admin** | Technical oversight | Manage members and technical admins, create reservations | Yes |
| **member** | Basic user | Create reservations only | Yes |

**Key Design Decisions:**

1. **Users can have multiple roles**: A user can be both `financial_admin` and `technical_admin` if needed

2. **Financial admins are excluded from AMF billing**: They manage billing but aren't considered "users" of the compute resources

3. **Roles are additive**: Each role grants permissions; having multiple roles grants all associated permissions

4. **Owner role is implicit**: The project PI (owner) has full control and doesn't need explicit role assignments

### Relationship to ColdFront's ProjectUser

Both records are required for a user to participate in an ORCD project:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           User: jsmith                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
        ┌─────────────────────────────┴─────────────────────────────┐
        │                                                           │
        ▼                                                           ▼
┌───────────────────────────────────┐       ┌───────────────────────────────────┐
│          ProjectUser              │       │       ProjectMemberRole(s)        │
│     (ColdFront Requirement)       │       │       (ORCD Requirement)          │
├───────────────────────────────────┤       ├───────────────────────────────────┤
│ project: research_lab             │       │ project: research_lab             │
│ user: jsmith                      │       │ user: jsmith                      │
│ role: User                        │       │ role: technical_admin             │
│ status: Active                    │       └───────────────────────────────────┘
└───────────────────────────────────┘       ┌───────────────────────────────────┐
                                            │       ProjectMemberRole           │
                                            ├───────────────────────────────────┤
                                            │ project: research_lab             │
                                            │ user: jsmith                      │
                                            │ role: financial_admin             │
                                            └───────────────────────────────────┘
```

In this example, jsmith has:
- One `ProjectUser` record with ColdFront role "User"
- Two `ProjectMemberRole` records granting both technical and financial admin permissions

---

## Creating ORCD Projects: The Dual-Record Pattern

When creating an ORCD project with members, both types of records must be created:

### Using the Management Command

The `create_orcd_project` command handles this automatically:

```bash
# Create project with owner and members
coldfront create_orcd_project jsmith \
    --project-name "Research Lab" \
    --add-member auser:financial_admin \
    --add-member buser:technical_admin \
    --add-member cuser:member
```

This command:
1. Creates the `Project` record with jsmith as PI
2. Creates a `ProjectUser` record for jsmith with role "Manager"
3. For each member:
   - Creates a `ProjectMemberRole` with the specified ORCD role
   - Creates a `ProjectUser` with role "User" (if not already exists)

### Programmatic Creation

When creating projects in code, follow this pattern:

```python
from django.contrib.auth.models import User
from coldfront.core.project.models import (
    Project,
    ProjectUser,
    ProjectUserRoleChoice,
    ProjectUserStatusChoice,
    ProjectStatusChoice,
)
from coldfront_orcd_direct_charge.models import ProjectMemberRole


def create_orcd_project(owner_username, title, members=None):
    """Create an ORCD project with optional members.
    
    Args:
        owner_username: Username of the project owner (PI)
        title: Project title
        members: List of (username, role) tuples, e.g., [("auser", "financial_admin")]
    """
    owner = User.objects.get(username=owner_username)
    
    # 1. Create the Project
    project = Project.objects.create(
        title=title,
        pi=owner,
        status=ProjectStatusChoice.objects.get(name="Active"),
        description=f"Project for {owner_username}",
    )
    
    # 2. Create ProjectUser for owner (ColdFront requirement)
    ProjectUser.objects.create(
        project=project,
        user=owner,
        role=ProjectUserRoleChoice.objects.get(name="Manager"),
        status=ProjectUserStatusChoice.objects.get(name="Active"),
    )
    
    # 3. Add members with ORCD roles
    for username, role in (members or []):
        member_user = User.objects.get(username=username)
        
        # Create ORCD role
        ProjectMemberRole.objects.create(
            project=project,
            user=member_user,
            role=role,  # "financial_admin", "technical_admin", or "member"
        )
        
        # Create ColdFront ProjectUser (if not exists)
        ProjectUser.objects.get_or_create(
            project=project,
            user=member_user,
            defaults={
                "role": ProjectUserRoleChoice.objects.get(name="User"),
                "status": ProjectUserStatusChoice.objects.get(name="Active"),
            }
        )
    
    return project
```

---

## Permission Checking in ORCD Views

Views that need to check ORCD roles use the `ProjectMemberRole` model:

### Checking Role Membership

```python
from coldfront_orcd_direct_charge.models import ProjectMemberRole


def user_has_role(user, project, role):
    """Check if user has a specific ORCD role in a project."""
    return ProjectMemberRole.objects.filter(
        user=user,
        project=project,
        role=role
    ).exists()


def user_can_manage_billing(user, project):
    """Check if user can manage cost allocations."""
    # Financial admins can manage billing
    if user_has_role(user, project, ProjectMemberRole.RoleChoices.FINANCIAL_ADMIN):
        return True
    # Project owner (PI) always can
    if project.pi == user:
        return True
    return False


def user_can_create_reservation(user, project):
    """Check if user can create GPU reservations."""
    # Any ORCD role can create reservations
    return ProjectMemberRole.objects.filter(
        user=user,
        project=project
    ).exists() or project.pi == user


def user_is_billable(user, project):
    """Check if user should be billed for account maintenance fees."""
    # Financial admins are NOT billable
    if user_has_role(user, project, ProjectMemberRole.RoleChoices.FINANCIAL_ADMIN):
        # Only financial_admin role = not billable
        if not ProjectMemberRole.objects.filter(
            user=user,
            project=project
        ).exclude(role=ProjectMemberRole.RoleChoices.FINANCIAL_ADMIN).exists():
            return False
    # All other roles are billable
    return True
```

### In Templates

```django
{% if user in project.pi %}
  {# Owner has full access #}
  <a href="{% url 'cost-allocation' project.pk %}">Manage Billing</a>
{% elif user_is_financial_admin %}
  {# Financial admin can manage billing #}
  <a href="{% url 'cost-allocation' project.pk %}">Manage Billing</a>
{% endif %}
```

---

## How Maintenance Windows Integrate with Projects

The MaintenanceWindow model is project-agnostic—maintenance windows affect all rentals regardless of project. However, billing deductions are calculated per-project on invoices:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MaintenanceWindow                                     │
│                    (Global - affects all nodes)                              │
│                                                                              │
│  • start_datetime: Feb 15 00:00                                              │
│  • end_datetime: Feb 16 12:00                                                │
│  • title: "Scheduled Maintenance"                                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Billing calculation queries all
                                      │ overlapping maintenance windows
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Reservation                                         │
│                      (Linked to Project)                                     │
│                                                                              │
│  • project: research_lab                                                     │
│  • requesting_user: jsmith                                                   │
│  • start_date: Feb 14                                                        │
│  • end_date: Feb 17                                                          │
│  • num_blocks: 6 (72 hours)                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Billing deduction calculated
                                      │ based on overlap
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Invoice Line                                        │
│                                                                              │
│  • reservation: [above]                                                      │
│  • hours_in_month: 72.0                                                      │
│  • maintenance_deduction: 36.0  (Feb 15 00:00 - Feb 16 12:00)                │
│  • billable_hours: 36.0                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Charges allocated per
                                      │ ProjectCostAllocation
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     ProjectCostAllocation                                    │
│                   (Project's billing config)                                 │
│                                                                              │
│  • project: research_lab                                                     │
│  • cost_objects: [ABC-123: 50%, DEF-456: 50%]                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Summary

The ORCD project abstraction follows a layered extension pattern:

1. **Django** provides the User model and authentication
2. **ColdFront** provides Project and ProjectUser for basic project management
3. **ORCD Plugin** adds ProjectMemberRole for domain-specific role-based access control

Key design principles:

- **Dual records required**: Both ProjectUser (ColdFront) and ProjectMemberRole (ORCD) are needed
- **Multiple roles per user**: Users can have multiple ORCD roles in the same project
- **Role-based billing**: Some roles (financial_admin) are excluded from maintenance fee billing
- **Implicit owner**: The project PI has full permissions without explicit role assignment
- **Additive permissions**: Each role adds capabilities; roles don't conflict

This architecture allows the ORCD plugin to add specialized functionality without modifying ColdFront's core models, ensuring clean separation of concerns and easier upgrades.

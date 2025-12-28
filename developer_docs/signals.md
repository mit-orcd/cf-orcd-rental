# Signals and Auto-Configuration

This document describes the Django signal handlers and auto-configuration features in the ORCD Direct Charge plugin.

**Sources**:
- [`coldfront_orcd_direct_charge/signals.py`](../coldfront_orcd_direct_charge/signals.py)
- [`coldfront_orcd_direct_charge/apps.py`](../coldfront_orcd_direct_charge/apps.py)

---

## Table of Contents

- [Overview](#overview)
- [Signal Registration](#signal-registration)
- [User Auto-Configuration](#user-auto-configuration)
- [Maintenance Status Management](#maintenance-status-management)
- [Authentication Logging](#authentication-logging)
- [Activity Logging Signals](#activity-logging-signals)
- [App Configuration](#app-configuration)
- [Settings](#settings)

---

## Overview

The plugin uses Django signals to:

1. **Auto-configure new users** - Set PI status, create default projects, initialize maintenance status
2. **Maintain data integrity** - Reset maintenance status when users lose project access
3. **Audit logging** - Log all significant actions for compliance and debugging

**Warning**: Auto-configuration features are **IRREVERSIBLE**. Once enabled, changes persist even if the feature is later disabled.

---

## Signal Registration

Signals are registered in two places:

### 1. Decorator-based Registration (`signals.py`)

```python
@receiver(post_save, sender=User)
def auto_configure_user(sender, instance, created, **kwargs):
    ...

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    ...
```

### 2. Deferred Registration (`apps.py` → `signals.py`)

To avoid circular imports, some signals are connected via functions called from `apps.py`:

```python
# In apps.py
def ready(self):
    from coldfront_orcd_direct_charge import signals
    signals.connect_member_role_signals()
    signals.connect_activity_log_signals()

# In signals.py
def connect_member_role_signals():
    from coldfront_orcd_direct_charge.models import ProjectMemberRole
    post_save.connect(check_maintenance_on_role_change, sender=ProjectMemberRole)
    post_delete.connect(check_maintenance_on_role_delete, sender=ProjectMemberRole)
```

---

## User Auto-Configuration

### auto_configure_user

**Signal**: `post_save` on `User`  
**Trigger**: When a new user is created (`created=True`)

```python
@receiver(post_save, sender=User)
def auto_configure_user(sender, instance, created, **kwargs):
    """Apply auto-PI, auto-default-project, and maintenance status to new users."""
    if not created:
        return

    # Always create maintenance status for new users
    create_maintenance_status_for_user(instance)

    # Auto-PI: set is_pi=True if enabled
    if getattr(settings, "AUTO_PI_ENABLE", False):
        if hasattr(instance, "userprofile"):
            instance.userprofile.is_pi = True
            instance.userprofile.save()

    # Auto Default Projects: create USERNAME_personal and USERNAME_group
    if getattr(settings, "AUTO_DEFAULT_PROJECT_ENABLE", False):
        create_default_project_for_user(instance)
        create_group_project_for_user(instance)
```

### Helper Functions

#### create_maintenance_status_for_user

```python
def create_maintenance_status_for_user(user):
    """Create UserMaintenanceStatus for a user if it doesn't exist."""
    UserMaintenanceStatus.objects.get_or_create(
        user=user,
        defaults={"status": UserMaintenanceStatus.StatusChoices.INACTIVE},
    )
```

#### create_default_project_for_user

```python
def create_default_project_for_user(user):
    """Create USERNAME_personal project for a user."""
    project_title = f"{user.username}_personal"
    
    if Project.objects.filter(title=project_title, pi=user).exists():
        return
    
    # Set user as PI
    if hasattr(user, "userprofile"):
        user.userprofile.is_pi = True
        user.userprofile.save()
    
    # Create project with user as PI and Manager
    project = Project.objects.create(
        title=project_title,
        pi=user,
        status=ProjectStatusChoice.objects.get(name="Active"),
        description=f"Personal project for {user.username}",
    )
    
    ProjectUser.objects.create(
        project=project,
        user=user,
        role=ProjectUserRoleChoice.objects.get(name="Manager"),
        status=ProjectUserStatusChoice.objects.get(name="Active"),
    )
```

#### create_group_project_for_user

Similar to `create_default_project_for_user` but creates `USERNAME_group` project.

---

## Maintenance Status Management

These signals ensure data integrity when users lose access to their billing project.

### check_maintenance_status_on_project_user_change

**Signal**: `post_save` on `ProjectUser` (ColdFront model)  
**Trigger**: When a ProjectUser record is saved

```python
@receiver(post_save, sender=ProjectUser)
def check_maintenance_status_on_project_user_change(sender, instance, **kwargs):
    """Reset maintenance status if user's billing project membership becomes inactive."""
    if instance.status.name == "Active":
        return
    reset_maintenance_if_billing_project(instance.user, instance.project)
```

### check_maintenance_status_on_project_user_delete

**Signal**: `post_delete` on `ProjectUser`  
**Trigger**: When a ProjectUser record is deleted

```python
@receiver(post_delete, sender=ProjectUser)
def check_maintenance_status_on_project_user_delete(sender, instance, **kwargs):
    """Reset maintenance status if user is deleted from their billing project."""
    reset_maintenance_if_billing_project(instance.user, instance.project)
```

### check_maintenance_on_role_change

**Signal**: `post_save` on `ProjectMemberRole`  
**Trigger**: When a ProjectMemberRole is created or updated

```python
def check_maintenance_on_role_change(sender, instance, **kwargs):
    """Reset maintenance status if user's role changes to financial_admin."""
    if instance.role == ProjectMemberRole.RoleChoices.FINANCIAL_ADMIN:
        reset_maintenance_if_billing_project(instance.user, instance.project)
```

### check_maintenance_on_role_delete

**Signal**: `post_delete` on `ProjectMemberRole`  
**Trigger**: When a ProjectMemberRole is deleted

```python
def check_maintenance_on_role_delete(sender, instance, **kwargs):
    """Reset maintenance status if user is removed from project."""
    reset_maintenance_if_billing_project(instance.user, instance.project)
```

### reset_maintenance_if_billing_project

Core helper function that resets maintenance status when eligibility is lost:

```python
def reset_maintenance_if_billing_project(user, project):
    """Reset user's maintenance status if they can no longer use project for billing."""
    try:
        maintenance_status = UserMaintenanceStatus.objects.get(
            user=user,
            billing_project=project,
        )
        
        if not can_use_for_maintenance_fee(user, project):
            logger.info(
                "Resetting maintenance status: user=%s lost eligibility for project=%s",
                user.username, project.title
            )
            maintenance_status.status = UserMaintenanceStatus.StatusChoices.INACTIVE
            maintenance_status.billing_project = None
            maintenance_status.save()
    except UserMaintenanceStatus.DoesNotExist:
        pass
```

**Business Rules**:
- Users can only use a project for maintenance billing if they have an eligible role
- Eligible roles: owner, technical_admin, member
- Ineligible: financial_admin alone (they manage billing, shouldn't be billed)
- When eligibility is lost, status resets to `inactive` and billing_project is cleared

---

## Authentication Logging

### log_user_login

**Signal**: `user_logged_in` (Django auth)  
**Trigger**: Successful user login

```python
@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Log successful user login."""
    log_activity(
        action="auth.login",
        category=ActivityLog.ActionCategory.AUTH,
        description=f"User {user.username} logged in",
        user=user,
        request=request,
        extra_data={"username": user.username},
    )
```

### log_user_logout

**Signal**: `user_logged_out` (Django auth)  
**Trigger**: User logout

```python
@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Log user logout."""
    if user:
        log_activity(
            action="auth.logout",
            category=ActivityLog.ActionCategory.AUTH,
            description=f"User {user.username} logged out",
            user=user,
            request=request,
        )
```

### log_user_login_failed

**Signal**: `user_login_failed` (Django auth)  
**Trigger**: Failed login attempt

```python
@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    """Log failed login attempts."""
    username = credentials.get("username", "unknown")
    log_activity(
        action="auth.login_failed",
        category=ActivityLog.ActionCategory.AUTH,
        description=f"Failed login attempt for {username}",
        request=request,
        extra_data={"attempted_username": username},
    )
```

---

## Activity Logging Signals

These signals create audit trail entries for model changes.

### log_reservation_change

**Signal**: `post_save` on `Reservation`  
**Trigger**: Reservation created or updated

```python
def log_reservation_change(sender, instance, created, **kwargs):
    """Log reservation creation and status changes."""
    if created:
        log_activity(
            action="reservation.created",
            category=ActivityLog.ActionCategory.RESERVATION,
            description=f"Reservation #{instance.pk} created for project {instance.project.title}",
            user=instance.requesting_user,
            target=instance,
            extra_data={
                "status": instance.status,
                "project_id": instance.project.pk,
                "project_title": instance.project.title,
                "node": instance.node_instance.associated_resource_address,
                "start_date": str(instance.start_date),
                "num_blocks": instance.num_blocks,
            },
        )
    else:
        log_activity(
            action="reservation.updated",
            category=ActivityLog.ActionCategory.RESERVATION,
            description=f"Reservation #{instance.pk} updated (status: {instance.get_status_display()})",
            target=instance,
            extra_data={"status": instance.status, "project_id": instance.project.pk},
        )
```

### log_member_role_change

**Signal**: `post_save` on `ProjectMemberRole`  
**Trigger**: Role added

```python
def log_member_role_change(sender, instance, created, **kwargs):
    """Log member role additions."""
    if created:
        log_activity(
            action="member.role_added",
            category=ActivityLog.ActionCategory.MEMBER,
            description=f"Role {instance.get_role_display()} added for {instance.user.username}",
            target=instance,
            extra_data={
                "user_id": instance.user.pk,
                "username": instance.user.username,
                "project_id": instance.project.pk,
                "role": instance.role,
            },
        )
```

### log_member_role_delete

**Signal**: `post_delete` on `ProjectMemberRole`  
**Trigger**: Role removed

```python
def log_member_role_delete(sender, instance, **kwargs):
    """Log member role removals."""
    log_activity(
        action="member.role_removed",
        category=ActivityLog.ActionCategory.MEMBER,
        description=f"Role {instance.get_role_display()} removed for {instance.user.username}",
        target=instance.project,
        extra_data={...},
    )
```

### log_cost_allocation_change

**Signal**: `post_save` on `ProjectCostAllocation`  
**Trigger**: Allocation created or updated

```python
def log_cost_allocation_change(sender, instance, created, **kwargs):
    """Log cost allocation changes."""
    action = "cost_allocation.created" if created else "cost_allocation.updated"
    log_activity(
        action=action,
        category=ActivityLog.ActionCategory.COST_ALLOCATION,
        description=f"Cost allocation {action.split('.')[1]} for project {instance.project.title}",
        target=instance,
        extra_data={
            "project_id": instance.project.pk,
            "status": instance.status,
        },
    )
```

### log_maintenance_status_change

**Signal**: `post_save` on `UserMaintenanceStatus`  
**Trigger**: Status created or updated

```python
def log_maintenance_status_change(sender, instance, created, **kwargs):
    """Log maintenance status changes."""
    action = "maintenance.created" if created else "maintenance.updated"
    log_activity(
        action=action,
        category=ActivityLog.ActionCategory.MAINTENANCE,
        description=f"Maintenance status {action.split('.')[1]} for {instance.user.username}",
        user=instance.user,
        target=instance,
        extra_data={
            "status": instance.status,
            "billing_project": instance.billing_project.title if instance.billing_project else None,
        },
    )
```

---

## App Configuration

### OrcdDirectChargeConfig

**Source**: [`apps.py`](../coldfront_orcd_direct_charge/apps.py)

The `AppConfig.ready()` method performs startup configuration:

```python
class OrcdDirectChargeConfig(AppConfig):
    name = "coldfront_orcd_direct_charge"
    verbose_name = "ORCD Direct Charge"

    def ready(self):
        # 1. Import signals to register handlers
        from coldfront_orcd_direct_charge import signals
        
        # 2. Connect deferred signals
        signals.connect_member_role_signals()
        signals.connect_activity_log_signals()
        
        # 3. Inject plugin templates directory
        plugin_templates_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "templates"
        )
        for template_setting in settings.TEMPLATES:
            if plugin_templates_dir not in template_setting["DIRS"]:
                template_setting["DIRS"] = [plugin_templates_dir] + list(
                    template_setting["DIRS"]
                )
        
        # 4. Set default settings
        if not hasattr(settings, "CENTER_SUMMARY_ENABLE"):
            settings.CENTER_SUMMARY_ENABLE = False
        if not hasattr(settings, "HOME_PAGE_ALLOCATIONS_ENABLE"):
            settings.HOME_PAGE_ALLOCATIONS_ENABLE = True
        
        # 5. Configure auto-settings from environment
        if not hasattr(settings, "AUTO_PI_ENABLE"):
            settings.AUTO_PI_ENABLE = os.environ.get("AUTO_PI_ENABLE", "").lower() == "true"
        if not hasattr(settings, "AUTO_DEFAULT_PROJECT_ENABLE"):
            settings.AUTO_DEFAULT_PROJECT_ENABLE = (
                os.environ.get("AUTO_DEFAULT_PROJECT_ENABLE", "").lower() == "true"
            )
        
        # 6. Export settings to templates
        for setting in ["CENTER_SUMMARY_ENABLE", "HOME_PAGE_ALLOCATIONS_ENABLE", "AUTO_PI_ENABLE"]:
            if setting not in settings.SETTINGS_EXPORT:
                settings.SETTINGS_EXPORT.append(setting)
        
        # 7. Apply auto features to existing users
        self._ensure_maintenance_status_if_ready()
        if settings.AUTO_PI_ENABLE or settings.AUTO_DEFAULT_PROJECT_ENABLE:
            self._apply_auto_features_if_ready()
```

### Startup Auto-Configuration

When the app starts, it applies auto-configuration to existing users:

```python
def _apply_auto_features(self):
    """Apply auto features to existing users."""
    # AUTO_PI_ENABLE: Set all users as PIs
    if settings.AUTO_PI_ENABLE:
        UserProfile.objects.filter(is_pi=False).update(is_pi=True)

    # AUTO_DEFAULT_PROJECT_ENABLE: Create projects
    if settings.AUTO_DEFAULT_PROJECT_ENABLE:
        for user in User.objects.all():
            create_default_project_for_user(user)
            create_group_project_for_user(user)
```

---

## Settings

### AUTO_PI_ENABLE

**Type**: Boolean  
**Default**: `False`

When `True`, all users are automatically set as PIs (`is_pi=True`).

**Configuration Priority**:
1. `local_settings.py` - `AUTO_PI_ENABLE = True`
2. Environment variable - `export AUTO_PI_ENABLE=true`
3. Default - `False`

**Behavior**:
- On app startup: Updates all existing UserProfiles where `is_pi=False`
- On new user creation: Signal sets `is_pi=True` on UserProfile

**Template Effect**:
- When `True`, PI Status is hidden on user profile page

### AUTO_DEFAULT_PROJECT_ENABLE

**Type**: Boolean  
**Default**: `False`

When `True`, creates `USERNAME_personal` and `USERNAME_group` projects for each user.

**Configuration Priority**:
1. `local_settings.py` - `AUTO_DEFAULT_PROJECT_ENABLE = True`
2. Environment variable - `export AUTO_DEFAULT_PROJECT_ENABLE=true`
3. Default - `False`

**Behavior**:
- On app startup: Creates projects for all existing users (if they don't exist)
- On new user creation: Signal creates both projects

**Side Effects**:
- User is set as PI (required to own projects)
- User is added as Manager on their own projects

### CENTER_SUMMARY_ENABLE

**Type**: Boolean  
**Default**: `False`

When `False`, hides the "Center Summary" link from the navigation bar.

### HOME_PAGE_ALLOCATIONS_ENABLE

**Type**: Boolean  
**Default**: `True`

When `False`, hides the "Allocations" section from the home page.

---

## Signal Summary Table

| Signal | Sender | Handler | Purpose |
|--------|--------|---------|---------|
| `post_save` | User | `auto_configure_user` | Auto-PI, projects, maintenance |
| `post_save` | ProjectUser | `check_maintenance_status_on_project_user_change` | Reset maintenance if inactive |
| `post_delete` | ProjectUser | `check_maintenance_status_on_project_user_delete` | Reset maintenance if removed |
| `post_save` | ProjectMemberRole | `check_maintenance_on_role_change` | Reset if role becomes financial_admin |
| `post_delete` | ProjectMemberRole | `check_maintenance_on_role_delete` | Reset if role removed |
| `user_logged_in` | - | `log_user_login` | Log successful login |
| `user_logged_out` | - | `log_user_logout` | Log logout |
| `user_login_failed` | - | `log_user_login_failed` | Log failed attempts |
| `post_save` | Reservation | `log_reservation_change` | Log reservation CRUD |
| `post_save` | ProjectMemberRole | `log_member_role_change` | Log role additions |
| `post_delete` | ProjectMemberRole | `log_member_role_delete` | Log role removals |
| `post_save` | ProjectCostAllocation | `log_cost_allocation_change` | Log allocation changes |
| `post_save` | UserMaintenanceStatus | `log_maintenance_status_change` | Log status changes |

---

## Related Documentation

- [Data Models](data-models.md) - Model definitions including ActivityLog
- [Views & URLs](views-urls.md) - Activity log view
- [API Reference](api-reference.md) - Activity log API endpoint
- [Django Signals](https://docs.djangoproject.com/en/4.2/topics/signals/) - Framework documentation



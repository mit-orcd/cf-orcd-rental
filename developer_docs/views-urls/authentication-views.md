# Authentication Views

This document describes authentication-related views.

---

## PasswordLoginView

**URL**: `/nodes/user/login?opt=password`  
**Name**: `coldfront_orcd_direct_charge:password-login`  
**Template**: `user/login_password.html`  
**Module**: `views/auth.py`

Optional password-based login view as an alternative to OIDC/Touchstone authentication.

**Activation Requirements**:
1. `password_login_enable` must be `True` in `plugin_config.yaml`
2. URL must include the query parameter `?opt=password`

If either condition is not met, the view redirects to OIDC authentication.

```python
class PasswordLoginView(View):
    """Handle password login when enabled via runtime config.
    
    Provides an alternative username/password login form that
    bypasses OIDC authentication when enabled.
    """
```

**Dispatch Behavior**:
- Checks `config.get("password_login_enable", False)` at runtime
- Reads directly from config module (not Django settings) to pick up runtime config changes via SIGHUP
- If disabled or missing query param, redirects to `oidc_authentication_init`

**Use Cases**:
- Development and testing environments
- Emergency access when OIDC is unavailable
- Administrative access for support

---

[← Back to Views and URL Routing](README.md)

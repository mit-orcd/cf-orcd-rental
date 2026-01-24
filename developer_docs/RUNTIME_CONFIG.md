# Runtime Configuration

This document describes the runtime configuration system for the ORCD Direct Charge plugin, including hot-reloading support via SIGHUP signal handling.

**Sources**:
- [`coldfront_orcd_direct_charge/config.py`](../coldfront_orcd_direct_charge/config.py)
- [`coldfront_orcd_direct_charge/apps.py`](../coldfront_orcd_direct_charge/apps.py)
- [`coldfront_orcd_direct_charge/signals.py`](../coldfront_orcd_direct_charge/signals.py)
- [`example_plugin_config.yaml`](../example_plugin_config.yaml)

---

## Table of Contents

- [Overview](#overview)
- [Configuration File](#configuration-file)
- [Configuration Precedence](#configuration-precedence)
- [Available Options](#available-options)
- [Hot-Reloading with SIGHUP](#hot-reloading-with-sighup)
- [Using Configuration in Code](#using-configuration-in-code)
- [Adding New Configuration Options](#adding-new-configuration-options)
- [Deployment Integration](#deployment-integration)
- [Troubleshooting](#troubleshooting)

---

## Overview

The runtime configuration system provides:

1. **File-based configuration** - Settings stored in a YAML file for easy editing
2. **Hot-reloading** - Configuration can be reloaded without restarting the service
3. **Thread-safe access** - Safe to read configuration from any thread
4. **Graceful fallbacks** - Defaults are used when no config file exists
5. **Backward compatibility** - Environment variables still work as fallbacks

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Configuration Flow                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Startup:                                                            │
│    apps.py ready() ──► config.load_config() ──► Read YAML file      │
│          │                     │                                     │
│          └──► _apply_runtime_config() ──► Update Django settings    │
│                                                                      │
│  Reload (SIGHUP):                                                    │
│    systemctl reload ──► Gunicorn master ──► SIGHUP to workers       │
│          │                                                           │
│          └──► handle_sighup() ──► config.reload_config()            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Configuration File

### Location

The configuration file location is determined by:

1. **Environment variable**: `ORCD_PLUGIN_CONFIG` (if set)
2. **Default path**: `/srv/coldfront/plugin_config.yaml`

```bash
# Check current config path
python -c "from coldfront_orcd_direct_charge import config; print(config.get_config_path())"
```

### File Format

Configuration is stored in YAML format:

```yaml
# /srv/coldfront/plugin_config.yaml

# UI Options
center_summary_enable: false
home_page_allocations_enable: true

# Auto-configuration features
auto_pi_enable: true
auto_default_project_enable: true
```

### Example Configuration

See [`example_plugin_config.yaml`](../example_plugin_config.yaml) for a fully documented example with all available options.

---

## Configuration Precedence

Configuration values are resolved in the following order (highest priority first):

| Priority | Source | Reloadable? | Description |
|----------|--------|-------------|-------------|
| 1 | Django `local_settings.py` | No | Requires service restart |
| 2 | `plugin_config.yaml` | **Yes** | Via `systemctl reload` |
| 3 | Environment variables | No | Backward compatibility |
| 4 | Code defaults | N/A | Fallback values in `config.py` |

### How Precedence Works

```python
# In apps.py _apply_runtime_config()

# Django settings take highest priority (checked via hasattr)
if not hasattr(settings, "CENTER_SUMMARY_ENABLE"):
    # If no Django setting, use config file value (or default)
    settings.CENTER_SUMMARY_ENABLE = config.get('center_summary_enable', False)
```

For auto-configuration features (`auto_pi_enable`, `auto_default_project_enable`), environment variables are only used when no config file exists:

```python
if config_file_exists:
    # Config file takes precedence
    settings.AUTO_PI_ENABLE = config.get('auto_pi_enable', False)
else:
    # Backward compatibility: use env var when no config file
    settings.AUTO_PI_ENABLE = os.environ.get("AUTO_PI_ENABLE", "").lower() == "true"
```

---

## Available Options

### UI Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `center_summary_enable` | bool | `false` | Show "Center Summary" link in navigation bar |
| `home_page_allocations_enable` | bool | `true` | Show Allocations section on home page |

### Auto-Configuration Features

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `auto_pi_enable` | bool | `false` | Automatically set all users as PIs (`is_pi=True`) |
| `auto_default_project_enable` | bool | `false` | Automatically create `USERNAME_group` project for each user |

**Warning**: Auto-configuration changes are **IRREVERSIBLE**. Once applied to a user account, the settings persist even if the feature is later disabled:
- Users set to `is_pi=True` remain as PIs
- Created `USERNAME_group` projects persist

### Authentication Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `password_login_enable` | bool | `false` | Enable username/password login via `/user/login?opt=password` |

When enabled, users can access a traditional username/password login form by visiting `/user/login?opt=password`. The standard OIDC/Touchstone login remains available at `/user/login` (without the query parameter). This provides an alternative authentication method for:
- Service accounts without OIDC credentials
- Local development and testing
- Fallback authentication when OIDC is unavailable

When disabled (default), any attempt to access `/user/login?opt=password` redirects to the standard OIDC authentication flow.

### Production vs Development Defaults

The code defaults are conservative (features disabled) for safe development and testing. Production deployments typically enable auto-features:

| Option | Code Default | Typical Production |
|--------|--------------|-------------------|
| `auto_pi_enable` | `false` | `true` |
| `auto_default_project_enable` | `false` | `true` |
| `password_login_enable` | `false` | `false` |

---

## Hot-Reloading with SIGHUP

### Overview

The plugin registers a SIGHUP signal handler that reloads configuration when the signal is received. This follows Unix daemon conventions and integrates with systemd and Gunicorn.

### Reload Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. Admin edits /srv/coldfront/plugin_config.yaml                   │
│                                                                      │
│  2. Admin runs: systemctl reload coldfront                          │
│         │                                                            │
│         ▼                                                            │
│  3. systemd sends SIGHUP to Gunicorn master (ExecReload directive)  │
│         │                                                            │
│         ▼                                                            │
│  4. Gunicorn gracefully restarts workers                            │
│         │                                                            │
│         ▼                                                            │
│  5. Each worker calls config.reload_config()                        │
│         │                                                            │
│         ▼                                                            │
│  6. New configuration values are active                              │
└─────────────────────────────────────────────────────────────────────┘
```

### Usage

```bash
# Edit the configuration file
sudo vim /srv/coldfront/plugin_config.yaml

# Apply changes without downtime
sudo systemctl reload coldfront

# Verify the reload in logs
sudo journalctl -u coldfront -f
# Should see: "Received SIGHUP, reloading configuration..."
# Should see: "Plugin configuration reloaded"
```

### SIGHUP Handler Implementation

The handler is registered in `signals.py`:

```python
def register_sighup_handler():
    """Register SIGHUP handler for runtime configuration reload."""
    import signal
    from coldfront_orcd_direct_charge import config

    def handle_sighup(signum, frame):
        """Handle SIGHUP signal by reloading configuration."""
        logger.info("Received SIGHUP, reloading configuration...")
        config.reload_config()

    signal.signal(signal.SIGHUP, handle_sighup)
    logger.info("SIGHUP handler registered for config reload")
```

---

## Using Configuration in Code

### Reading Configuration Values

```python
from coldfront_orcd_direct_charge import config

# Get a single value (with default fallback)
value = config.get('center_summary_enable', False)

# Get all configuration values
all_config = config.get_all()
```

### Thread Safety

All configuration access is thread-safe. The module uses a lock to protect the internal configuration dictionary:

```python
_config_lock = Lock()

def get(key, default=None):
    """Get a configuration value (thread-safe)."""
    with _config_lock:
        if default is None and key in DEFAULT_CONFIG:
            default = DEFAULT_CONFIG[key]
        return _config.get(key, default)
```

### Configuration in Templates

Settings are exported to templates via Django's settings export mechanism:

```python
# In apps.py
if "CENTER_SUMMARY_ENABLE" not in settings.SETTINGS_EXPORT:
    settings.SETTINGS_EXPORT.append("CENTER_SUMMARY_ENABLE")
```

Use in templates:

```html
{% if settings.CENTER_SUMMARY_ENABLE %}
  <a href="{% url 'center-summary' %}">Center Summary</a>
{% endif %}
```

---

## Adding New Configuration Options

### Step 1: Add Default Value

Add the new option to `DEFAULT_CONFIG` in `config.py`:

```python
DEFAULT_CONFIG = {
    # Existing options...
    'center_summary_enable': False,
    
    # New option
    'my_new_feature_enable': False,
}
```

### Step 2: Use the Option

Reference it using `config.get()`:

```python
from coldfront_orcd_direct_charge import config

if config.get('my_new_feature_enable', False):
    # Feature-specific code
    pass
```

### Step 3: Export to Django Settings (if needed)

If the option needs to be available in templates or other Django components, add it to `_apply_runtime_config()` in `apps.py`:

```python
def _apply_runtime_config(self):
    # ...existing code...
    
    # MY_NEW_FEATURE_ENABLE
    if not hasattr(settings, "MY_NEW_FEATURE_ENABLE"):
        settings.MY_NEW_FEATURE_ENABLE = config.get('my_new_feature_enable', False)
    
    if "MY_NEW_FEATURE_ENABLE" not in settings.SETTINGS_EXPORT:
        settings.SETTINGS_EXPORT.append("MY_NEW_FEATURE_ENABLE")
```

### Step 4: Document the Option

Add documentation to `example_plugin_config.yaml`:

```yaml
# My New Feature
# When true, enables the new feature functionality.
# Default: false
my_new_feature_enable: false
```

---

## Deployment Integration

### systemd Service Configuration

The systemd service file requires an `ExecReload` directive:

```ini
# /etc/systemd/system/coldfront.service

[Service]
# ... existing configuration ...

# Graceful reload - sends HUP to Gunicorn master
ExecReload=/bin/kill -s HUP $MAINPID
```

### Environment Variable for Config Path

Set the config file location in the environment file:

```bash
# /srv/coldfront/coldfront.env
ORCD_PLUGIN_CONFIG=/srv/coldfront/plugin_config.yaml
```

### PyYAML Dependency

The configuration system requires PyYAML. It's listed in `pyproject.toml`:

```toml
dependencies = [
    "pyyaml>=6.0",
    # ... other dependencies ...
]
```

If PyYAML is not installed, the configuration module logs a warning and uses defaults:

```
WARNING - PyYAML not installed - cannot load config file /srv/coldfront/plugin_config.yaml. Install with: pip install pyyaml
```

---

## Troubleshooting

### Configuration Not Loading

**Symptom**: Changes to `plugin_config.yaml` have no effect.

**Check**:
1. Verify the file path:
   ```bash
   echo $ORCD_PLUGIN_CONFIG
   ls -la /srv/coldfront/plugin_config.yaml
   ```

2. Check for YAML syntax errors:
   ```bash
   python -c "import yaml; yaml.safe_load(open('/srv/coldfront/plugin_config.yaml'))"
   ```

3. Verify reload was received:
   ```bash
   sudo journalctl -u coldfront | grep -i sighup
   ```

### SIGHUP Not Working

**Symptom**: `systemctl reload coldfront` doesn't reload configuration.

**Check**:
1. Verify `ExecReload` directive exists in service file:
   ```bash
   systemctl cat coldfront | grep ExecReload
   ```

2. Check that Gunicorn master received the signal:
   ```bash
   sudo journalctl -u coldfront | grep -i "reloading\|sighup"
   ```

3. Verify the SIGHUP handler is registered:
   ```bash
   sudo journalctl -u coldfront | grep "SIGHUP handler registered"
   ```

### PyYAML Import Error

**Symptom**: Warning about PyYAML not installed.

**Fix**:
```bash
source /srv/coldfront/venv/bin/activate
pip install pyyaml
sudo systemctl restart coldfront
```

### Configuration Precedence Issues

**Symptom**: Config file values are ignored.

**Check**: Django `local_settings.py` may have a static setting that takes precedence:

```python
# In local_settings.py - this overrides the config file
CENTER_SUMMARY_ENABLE = True
```

Remove the setting from `local_settings.py` to allow runtime configuration.

---

## API Reference

### config.py Module

#### `get_config_path() -> str`

Returns the path to the plugin configuration file.

```python
from coldfront_orcd_direct_charge import config
path = config.get_config_path()
# Returns: "/srv/coldfront/plugin_config.yaml" (or ORCD_PLUGIN_CONFIG env value)
```

#### `load_config() -> dict`

Loads configuration from the YAML file. Called automatically at startup.

```python
config.load_config()
```

#### `reload_config() -> dict`

Reloads configuration from file. Called by SIGHUP handler.

```python
config.reload_config()
```

#### `get(key: str, default=None) -> Any`

Gets a configuration value (thread-safe).

```python
value = config.get('center_summary_enable', False)
```

#### `get_all() -> dict`

Returns a copy of all configuration values (thread-safe).

```python
all_values = config.get_all()
```

---

## Related Documentation

- [Signals](signals.md) - Signal handlers including SIGHUP registration
- [Views & URLs](views-urls.md) - Views that use configuration values
- [Django Settings](https://docs.djangoproject.com/en/4.2/topics/settings/) - Framework documentation
- [Gunicorn Signal Handling](https://docs.gunicorn.org/en/stable/signals.html) - SIGHUP behavior in Gunicorn

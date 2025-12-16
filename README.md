# ColdFront ORCD Direct Charge Plugin

A ColdFront plugin providing ORCD-specific customizations for direct charge resource allocation management.

## Features

- Removes "Center Summary" from the navigation bar
- Optionally hides "Allocations" section from the home page

## Installation

### Directory Structure

This plugin is designed to live as a sibling directory to your ColdFront installation:

```
your-project/
├── coldfront/                          # ColdFront installation
│   ├── pyproject.toml
│   ├── local_settings.py               # Your local settings
│   └── coldfront/
│       └── ...
└── coldfront-orcd-direct-charge/       # This plugin (sibling directory)
    ├── pyproject.toml
    └── coldfront_orcd_direct_charge/
        └── ...
```

### Step 1: Install the Plugin Package

The plugin must be installed into your Python environment so that Django can import it. From your **ColdFront directory**, install the plugin in editable mode:

```bash
cd /path/to/coldfront
uv pip install -e ../coldfront-orcd-direct-charge
```

Or with pip:

```bash
cd /path/to/coldfront
pip install -e ../coldfront-orcd-direct-charge
```

The `-e` (editable) flag means changes to the plugin code take effect immediately without reinstalling.

### Step 2: Configure ColdFront

Add the plugin to your `local_settings.py` (in the ColdFront project root):

```python
INSTALLED_APPS += ['coldfront_orcd_direct_charge']

# Set to True to re-enable Center Summary in the navigation bar
# CENTER_SUMMARY_ENABLE = False

# Set to False to hide Allocations section from home page
# HOME_PAGE_ALLOCATIONS_ENABLE = True
```

### Step 3: Restart ColdFront

```bash
DEBUG=True uv run coldfront runserver
```

The "Center Summary" link should now be hidden from the navigation bar.

## Using COLDFRONT_CONFIG Environment Variable

ColdFront supports specifying the path to your `local_settings.py` file via the `COLDFRONT_CONFIG` environment variable. This is useful when your settings file is outside the standard locations.

```bash
export COLDFRONT_CONFIG=/path/to/your/local_settings.py
```

ColdFront searches for local settings in the following order:

1. `coldfront/config/local_settings.py` (relative to coldfront package)
2. `/etc/coldfront/local_settings.py` (system-wide)
3. `local_settings.py` (in the project root)
4. Path specified by `COLDFRONT_CONFIG` environment variable

Settings files loaded later override earlier ones, so `COLDFRONT_CONFIG` takes highest precedence.

## Plugin Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `CENTER_SUMMARY_ENABLE` | `False` | When `False`, hides the Center Summary link from the navigation bar |
| `HOME_PAGE_ALLOCATIONS_ENABLE` | `True` | When `False`, hides the Allocations section from the user home page |

### Note on Allocations vs Allocation Accounts

`HOME_PAGE_ALLOCATIONS_ENABLE` controls the visibility of the **Allocations** section on the home page. This is different from `ALLOCATION_ACCOUNT_ENABLED` (a core ColdFront setting), which controls the optional "Allocation Accounts" billing feature.

Setting `HOME_PAGE_ALLOCATIONS_ENABLE = False`:
- Hides the Allocations table from the home page
- Expands the Projects section to full width
- Does NOT disable access to allocations via the navbar "Project > Allocations" menu

## Template Overrides

This plugin overrides the following ColdFront templates:

| Template | Purpose |
|----------|---------|
| `common/authorized_navbar.html` | Navbar for logged-in users (hides Center Summary) |
| `common/nonauthorized_navbar.html` | Navbar for anonymous users (hides Center Summary) |
| `portal/authorized_home.html` | Home page for logged-in users (conditionally hides Allocations) |

## Development

This plugin follows ColdFront's plugin architecture:

- **Template overrides**: Place templates in `coldfront_orcd_direct_charge/templates/` to override core templates
- **Models**: Add `models.py` for database schema extensions
- **Views**: Add `views.py` and `urls.py` for custom endpoints
- **Signals**: Add `signals.py` to hook into ColdFront events

## License

AGPL-3.0-or-later (same as ColdFront)


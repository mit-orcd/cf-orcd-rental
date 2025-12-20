# ColdFront ORCD Direct Charge Plugin

A ColdFront plugin providing ORCD-specific customizations for direct charge resource allocation management, including GPU/CPU node tracking and a rental reservation system for H200x8 GPU nodes.

## Features Overview

### UI Customizations
- Removes "Center Summary" from the navigation bar
- Optionally hides "Allocations" section from the home page
- Adds "Node Instances" and "Manage Rentals" links to navigation

### User Auto-Configuration (Optional)
- **Auto-PI**: Automatically set all users as PIs (`is_pi=True`)
- **Auto Default Projects**: Create `USERNAME_personal` and `USERNAME_group` projects for each user
- Configured via environment variables or `local_settings.py`
- Changes are irreversible (persist when features are disabled)

### Node Instance Management
- **GPU Node Instances**: Track H200x8, L40Sx4, and other GPU node types
- **CPU Node Instances**: Track CPU_384G, CPU_1500G, and other CPU node types
- NodeType model for constrained node type definitions
- Natural key support for fixture-based updates
- Django admin interface for node management

### Rental Calendar & Reservation System
- Visual calendar showing H200x8 node availability by month
- Reservation request submission linked to ColdFront projects
- Rental manager dashboard for approving/declining requests
- Partial rental visualization (AM/PM periods with diagonal split)
- 7-day advance booking requirement
- 3-month forward visibility limit
- 9 AM end time cap (reservations must end by 9 AM on final day)

### REST API
- JSON API for querying reservation data
- Token-based authentication
- Filtering by status, node, project, user, and date

### Management Tools
- Django management command for Rental Manager group setup
- CLI tool for querying rentals API
- Helper programs for fixture generation from Slurm data

---

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
    ├── README.md
    ├── helper_programs/                # Utility tools
    └── coldfront_orcd_direct_charge/
        ├── models.py                   # NodeType, GpuNodeInstance, CpuNodeInstance, Reservation
        ├── views.py                    # Node instance + rental calendar views
        ├── api/                        # REST API
        ├── fixtures/                   # Node instance data
        └── templates/                  # Template overrides
```

### Step 1: Install the Plugin Package

From your **ColdFront directory**, install the plugin in editable mode:

```bash
cd /path/to/coldfront
uv pip install -e ../coldfront-orcd-direct-charge
```

Or with pip:

```bash
pip install -e ../coldfront-orcd-direct-charge
```

### Step 2: Configure ColdFront

Add the plugin to your `local_settings.py`:

```python
INSTALLED_APPS += ['coldfront_orcd_direct_charge']

# Optional: Re-enable Center Summary in the navigation bar
# CENTER_SUMMARY_ENABLE = True

# Optional: Hide Allocations section from home page
# HOME_PAGE_ALLOCATIONS_ENABLE = False
```

### Step 3: Add Plugin URLs

In `coldfront/coldfront/config/urls.py`, add:

```python
if "coldfront_orcd_direct_charge" in settings.INSTALLED_APPS:
    urlpatterns.append(path("nodes/", include("coldfront_orcd_direct_charge.urls")))
```

### Step 4: Apply Migrations

```bash
coldfront migrate
```

### Step 5: Load Fixtures

Load fixtures in this order (due to ForeignKey dependencies):

```bash
coldfront loaddata node_types           # NodeType definitions
coldfront loaddata gpu_node_instances   # GPU node instances
coldfront loaddata cpu_node_instances   # CPU node instances
coldfront loaddata node_resource_types  # Optional: ColdFront ResourceType entries
```

### Step 6: Set Up Rental Manager (Optional)

Create the Rental Manager group and add users:

```bash
coldfront setup_rental_manager --create-group
coldfront setup_rental_manager --add-user <username>
```

### Step 7: Restart ColdFront

```bash
DEBUG=True coldfront runserver
```

---

## URL Endpoints

### Node Instance Pages

| URL | Description |
|-----|-------------|
| `/nodes/` | List all GPU and CPU node instances |
| `/nodes/gpu/<pk>/` | GPU node detail page |
| `/nodes/cpu/<pk>/` | CPU node detail page |

### Rental Calendar & Reservations

| URL | Description |
|-----|-------------|
| `/nodes/renting/` | Calendar view showing H200x8 availability |
| `/nodes/renting/request/` | Submit reservation request form |
| `/nodes/renting/manage/` | Manager dashboard (requires permission) |
| `/nodes/renting/manage/<pk>/approve/` | Approve reservation |
| `/nodes/renting/manage/<pk>/decline/` | Decline reservation |
| `/nodes/renting/manage/<pk>/metadata/` | Add booking management metadata |

### REST API

| URL | Description |
|-----|-------------|
| `/nodes/api/rentals/` | List all reservations (requires `can_manage_rentals` permission) |
| `/nodes/api/rentals/<pk>/` | Get single reservation detail |

---

## Rental Calendar Features

### Calendar Display

The calendar shows availability for H200x8 nodes across days in the month. Each day is divided into two periods:

- **AM Period**: 4:00 AM - 4:00 PM
- **PM Period**: 4:00 PM - 4:00 AM (next day)

### Color Coding

| Color | Meaning |
|-------|---------|
| Gray | Not Available (within 7-day advance booking window) |
| Green | Available |
| Red | Rented |
| Diagonal split | Partial rental (AM or PM only) |
| Person icon | Your project has a rental on this day |
| White "P" | Pending reservation exists |

### Reservation Time Rules

- **Start time**: Always 4:00 PM on the start date
- **Duration**: 12-hour blocks (12h to 168h / 7 days)
- **End time cap**: Reservations must end no later than 9:00 AM on the final day
- **Advance booking**: Minimum 7 days in advance
- **Visibility**: Calendar shows up to 3 months ahead

### Duration Examples (with 9 AM cap)

| Blocks | Raw Hours | Actual Billable | End Time |
|--------|-----------|-----------------|----------|
| 1 | 12h | 12h | 4 AM next day |
| 2 | 24h | 17h | 9 AM next day (truncated from 4 PM) |
| 3 | 36h | 36h | 4 AM in 2 days |
| 4 | 48h | 41h | 9 AM in 2 days (truncated from 4 PM) |
| 6 | 72h | 65h | 9 AM in 3 days (truncated from 4 PM) |

---

## Booking Management Metadata

Rental managers can add multiple timestamped metadata notes to each reservation:

- Click the gear icon on any reservation to open the "Booking Management Metadata" modal
- View existing entries with timestamps
- Add new entries (one or multiple at a time)
- Entries are stored separately with creation timestamps
- Only visible to rental managers

---

## REST API Usage

### Authentication

Generate an API token:

```bash
export PLUGIN_API=True
coldfront drf_create_token <username>
```

### Example Request

```bash
curl -H "Authorization: Token YOUR_TOKEN" \
     http://localhost:8000/nodes/api/rentals/
```

### Response Format

```json
{
  "id": 6,
  "node": "node2433",
  "node_type": "H200x8",
  "project_id": 1,
  "project_title": "Angular momentum in QGP holography",
  "requesting_user": "cgray",
  "start_date": "2025-12-30",
  "start_datetime": "2025-12-30T16:00:00-05:00",
  "end_datetime": "2026-01-03T09:00:00-05:00",
  "num_blocks": 8,
  "billable_hours": 89,
  "status": "APPROVED",
  "manager_notes": "",
  "rental_notes": "Benchmark testing",
  "rental_metadata_entries": [
    {
      "id": 1,
      "content": "Approved for credit",
      "created": "2025-12-19T16:44:27.824686-05:00",
      "modified": "2025-12-19T16:44:27.824686-05:00"
    }
  ],
  "created": "2025-12-19T16:32:39.260668-05:00",
  "modified": "2025-12-19T16:33:06.467894-05:00"
}
```

### CLI Tool

A command-line tool is included for querying the API:

```bash
cd helper_programs/orcd_dc_cli

# Set environment variables
export COLDFRONT_API_TOKEN="your_token_here"

# Query rentals
python rentals.py                        # All rentals
python rentals.py --status PENDING       # Filter by status
python rentals.py --node node2433        # Filter by node
python rentals.py --format table         # Table output
```

---

## Data Models

### NodeType

Defines the allowed node types (constrained set):

```python
class NodeType(TimeStampedModel):
    name = CharField(max_length=64, unique=True)  # e.g., "H200x8", "CPU_384G"
    category = CharField(choices=["GPU", "CPU"])
    description = TextField(blank=True)
    is_active = BooleanField(default=True)
```

### GpuNodeInstance / CpuNodeInstance

Track individual physical node instances:

```python
class GpuNodeInstance(TimeStampedModel):
    node_type = ForeignKey(NodeType)
    is_rentable = BooleanField(default=False)
    status = CharField(choices=["AVAILABLE", "PLACEHOLDER"])
    associated_resource_address = CharField(unique=True)  # e.g., "node3401"
```

### Reservation

Tracks rental reservations:

```python
class Reservation(TimeStampedModel):
    node_instance = ForeignKey(GpuNodeInstance)
    project = ForeignKey(Project)
    requesting_user = ForeignKey(User)
    start_date = DateField()
    num_blocks = PositiveIntegerField()
    status = CharField(choices=["PENDING", "APPROVED", "DECLINED", "CANCELLED"])
    manager_notes = TextField(blank=True)
    rental_notes = TextField(blank=True)
```

### ReservationMetadataEntry

Stores multiple metadata notes per reservation:

```python
class ReservationMetadataEntry(TimeStampedModel):
    reservation = ForeignKey(Reservation, related_name="metadata_entries")
    content = TextField()
```

---

## Plugin Settings

### UI Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `CENTER_SUMMARY_ENABLE` | `False` | When `False`, hides the Center Summary link from navigation |
| `HOME_PAGE_ALLOCATIONS_ENABLE` | `True` | When `False`, hides the Allocations section from home page |

### Auto-Configuration Features

These optional features automatically configure user accounts. **Changes are IRREVERSIBLE** - once applied, accounts keep their settings even if the feature is disabled.

| Setting | Env Variable | Default | Description |
|---------|--------------|---------|-------------|
| `AUTO_PI_ENABLE` | `AUTO_PI_ENABLE` | `False` | Set `is_pi=True` for all users |
| `AUTO_DEFAULT_PROJECT_ENABLE` | `AUTO_DEFAULT_PROJECT_ENABLE` | `False` | Create `USERNAME_personal` and `USERNAME_group` projects for each user |

**Precedence**: `local_settings.py` > Environment Variable > Default

#### Option 1: Environment Variables (Recommended)

No code changes needed - just set environment variables before starting ColdFront:

```bash
export AUTO_PI_ENABLE=true
export AUTO_DEFAULT_PROJECT_ENABLE=true
coldfront runserver
```

#### Option 2: local_settings.py

Add to your `local_settings.py`:

```python
# ORCD Auto-Configuration Features (IRREVERSIBLE once applied)
AUTO_PI_ENABLE = True              # Set all users as PIs
AUTO_DEFAULT_PROJECT_ENABLE = True  # Create USERNAME_personal and USERNAME_group projects
```

#### Behavior

**When AUTO_PI_ENABLE is True:**
- All existing users have `is_pi` set to `True` on app startup
- All new users automatically get `is_pi=True` via signal
- Users can create projects without manual PI approval

**When AUTO_DEFAULT_PROJECT_ENABLE is True:**
- All existing users get `USERNAME_personal` and `USERNAME_group` projects on app startup
- All new users automatically get the project via signal
- User is set as PI (required to own a project)
- User is added as Manager on their project with Active status

**Irreversibility:**
- Turning off features does NOT revert changes
- Users keep their `is_pi=True` status
- Projects remain in the system

---

## Management Commands

### setup_rental_manager

Manage the Rental Manager group:

```bash
# Create the group with can_manage_rentals permission
coldfront setup_rental_manager --create-group

# Add user to group
coldfront setup_rental_manager --add-user <username>

# Remove user from group
coldfront setup_rental_manager --remove-user <username>

# List all rental managers
coldfront setup_rental_manager --list
```

---

## Helper Programs

Located in `helper_programs/`:

### csv_to_fixtures

Convert CSV files to Django fixture JSON:

```bash
cd helper_programs/csv_to_fixtures
python csv_to_node_fixtures.py nodes.csv --rentable-percent 30
```

### mk_gpucpunode_csv

Convert Slurm `scontrol` output to CSV:

```bash
cd helper_programs/mk_gpucpunode_csv
scontrol show node -o | ./json_to_node_csv.sh > nodes.csv
```

### orcd_dc_cli

Command-line tools for API access (see CLI Tool section above).

---

## Django Admin

Access at `/admin/coldfront_orcd_direct_charge/`:

- **Node Types**: Manage GPU/CPU node type definitions
- **GPU Node Instances**: Manage individual GPU nodes
- **CPU Node Instances**: Manage individual CPU nodes
- **Reservations**: View/edit reservations with bulk approve/decline actions
- **Reservation Metadata Entries**: Manage metadata notes

---

## Template Overrides

This plugin overrides the following ColdFront templates:

| Template | Purpose |
|----------|---------|
| `common/authorized_navbar.html` | Navbar with "Node Instances" and "Manage Rentals" links |
| `common/nonauthorized_navbar.html` | Navbar for anonymous users |
| `portal/authorized_home.html` | Home page (conditionally hides Allocations) |

---

## Permissions

| Permission | Description |
|------------|-------------|
| `can_manage_rentals` | Access to rental manager dashboard, approve/decline reservations, add metadata |

Assign via Django admin or using the `setup_rental_manager` command.

---

## Development

### Adding New Node Types

1. Create a new NodeType in Django admin or add to `fixtures/node_types.json`
2. Create node instances in the appropriate fixture file
3. Reload fixtures: `coldfront loaddata node_types gpu_node_instances`

### Schema Changes

1. Modify models in `models.py`
2. Create migration: `coldfront makemigrations coldfront_orcd_direct_charge`
3. Apply migration: `coldfront migrate`
4. Update fixtures if needed

### Plugin Structure

```
coldfront_orcd_direct_charge/
├── __init__.py
├── apps.py                     # AppConfig, template injection, settings, auto-config
├── signals.py                  # Signal handlers for user auto-configuration
├── models.py                   # Data models
├── admin.py                    # Django admin registration
├── forms.py                    # Form classes
├── views.py                    # View classes
├── urls.py                     # URL routing
├── api/
│   ├── serializers.py          # DRF serializers
│   ├── views.py                # API viewsets
│   └── urls.py                 # API routing
├── management/commands/        # Django management commands
├── templatetags/               # Custom template filters
├── migrations/                 # Database migrations
├── fixtures/                   # Initial/seed data
└── templates/                  # Template overrides
```

---

## License

AGPL-3.0-or-later (same as ColdFront)

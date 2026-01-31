# Management Commands

This directory contains Django management commands for the ORCD Direct Charge plugin. These commands are invoked via the `coldfront` management command wrapper.

## Shell Environment Setup

**IMPORTANT:** Environment variables MUST be set BEFORE running any Django commands. These variables are read when ColdFront's settings are loaded, which determines which apps are installed and which migrations run. Setting them after import has no effect.

Run the following commands to configure your shell before executing any management commands:

```bash
cd /srv/coldfront
source venv/bin/activate

# Load secrets from environment file (required for SECRET_KEY, OIDC credentials)
# The coldfront.env file also contains PLUGIN_API, AUTO_PI_ENABLE, and
# AUTO_DEFAULT_PROJECT_ENABLE which enable the ORCD plugin features.
set -a
source /srv/coldfront/coldfront.env
set +a

export PYTHONPATH=/srv/coldfront
export DJANGO_SETTINGS_MODULE=local_settings
```


After this setup, you can run any of the commands documented below.

**Note:** To upgrade available commands during development use

```
pip install --no-cache-dir --force-reinstall 'git+https://github.com/mit-orcd/cf-orcd-rental.git@BRANCH_OR_TAG
```

where `BRANCH_OR_TAG` is a branch or tag for the repo. 

---

## Quick Reference

| Command | Description |
|---------|-------------|
| [`add_user_to_project`](#add_user_to_project) | Add a user to an ORCD project with a specified role |
| [`check_import_compatibility`](#check_import_compatibility) | Validate an export before importing |
| [`create_node_rental`](#create_node_rental) | Create a node rental reservation for a GPU node instance |
| [`create_orcd_project`](#create_orcd_project) | Create ORCD projects with member roles |
| [`create_user`](#create_user) | Create user accounts with optional API tokens and group membership |
| [`export_portal_data`](#export_portal_data) | Export portal data to JSON files for backup or migration |
| [`import_portal_data`](#import_portal_data) | Import portal data from a JSON export |
| [`set_project_cost_allocation`](#set_project_cost_allocation) | Set cost allocation for a project with cost objects and percentages |
| [`set_user_amf`](#set_user_amf) | Set account maintenance fee status and billing project for a user |
| [`setup_billing_manager`](#setup_billing_manager) | Manage the Billing Manager group and its members |
| [`setup_rate_manager`](#setup_rate_manager) | Manage the Rate Manager group and its members |
| [`setup_rental_manager`](#setup_rental_manager) | Manage the Rental Manager group and its members |
| [`sync_node_skus`](#sync_node_skus) | Synchronize RentalSKU records with NodeTypes |

---

## Data Export/Import Commands

### check_import_compatibility

Validates an export directory and checks whether it can be safely imported into the current portal instance. Supports both v2.0 (two-directory structure) and v1.0 (flat) export formats.

**Usage:**

```bash
coldfront check_import_compatibility <export_path> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `export_path` | Path to the export directory containing `manifest.json` |

**Options:**

| Option | Description |
|--------|-------------|
| `--verbose`, `-v` | Show detailed information including software versions |
| `--verify-checksum` | Also verify data integrity via checksum |

**Examples:**

```bash
# Basic compatibility check
coldfront check_import_compatibility /backups/portal/export_20260117/

# Verbose output with checksum verification
coldfront check_import_compatibility /backups/portal/export_20260117/ --verbose --verify-checksum
```

---

### export_portal_data

Exports portal data to a directory structure with separate directories for ColdFront core data, plugin data, and configuration settings. Each component has its own manifest for tracking.

**Export Structure:**

```
export_YYYYMMDD_HHMMSS/
├── manifest.json           # Root manifest
├── config/                 # Configuration settings
│   ├── manifest.json
│   ├── plugin_config.json
│   ├── coldfront_config.json
│   ├── django_config.json
│   └── environment.json
├── coldfront_core/
│   ├── manifest.json
│   └── *.json              # Core data files
└── orcd_plugin/
    ├── manifest.json
    └── *.json              # Plugin data files
```

**Usage:**

```bash
coldfront export_portal_data --output <path> [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--output`, `-o` | **Required.** Output directory (timestamped subdirectory created automatically) |
| `--component` | Component to export: `coldfront_core`, `orcd_plugin`, or `all` (default: `all`) |
| `--models` | Comma-separated list of models to export (use `--list-models` to see available) |
| `--exclude` | Comma-separated list of models to exclude |
| `--list-models` | List available models for each component and exit |
| `--no-timestamp` | Use output path directly without creating timestamped subdirectory |
| `--no-config` | Skip exporting configuration settings |
| `--dry-run` | Show what would be exported without writing files |
| `--source-url` | URL of this portal instance (for manifest metadata) |
| `--source-name` | Name of this portal instance (default: "ORCD Rental Portal") |

**Examples:**

```bash
# Export all data (core + plugin + config)
coldfront export_portal_data -o /backups/portal/

# Export only ColdFront core data
coldfront export_portal_data -o /backups/portal/ --component coldfront_core

# Export only plugin data without configuration
coldfront export_portal_data -o /backups/portal/ --component orcd_plugin --no-config

# Preview what would be exported
coldfront export_portal_data -o /backups/portal/ --dry-run

# List available models
coldfront export_portal_data -o /tmp --list-models
```

---

### import_portal_data

Imports portal data from a previously exported directory. Supports both v2.0 (two-directory structure) and legacy v1.0 flat exports. Before importing, the command compares exported configuration settings against the current instance and displays any differences.

**Usage:**

```bash
coldfront import_portal_data <export_path> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `export_path` | Path to export directory containing `manifest.json` |

**Options:**

| Option | Description |
|--------|-------------|
| `--component` | Component to import: `coldfront_core`, `orcd_plugin`, or `all` (default: `all`) |
| `--mode` | Import mode: `create-only`, `update-only`, or `create-or-update` (default) |
| `--models` | Comma-separated list of models to import |
| `--dry-run` | Validate and show what would be imported without making changes |
| `--validate` | Only validate the export, don't import |
| `--skip-conflicts` | Skip records that would cause conflicts instead of failing |
| `--force` | Proceed even with compatibility warnings |
| `--no-verify-checksum` | Skip checksum verification |
| `--ignore-config-diff` | Skip configuration comparison check |
| `--config-diff-report` | Write configuration diff report to specified JSON file |

**Examples:**

```bash
# Preview what would be imported (dry run)
coldfront import_portal_data /backups/portal/export_20260117/ --dry-run

# Import only ColdFront core data
coldfront import_portal_data /backups/portal/export_20260117/ --component coldfront_core

# Import only new records (skip existing)
coldfront import_portal_data /backups/portal/export_20260117/ --mode create-only

# Import with config diff report
coldfront import_portal_data /backups/portal/export_20260117/ --config-diff-report /tmp/diff.json

# Force import despite warnings
coldfront import_portal_data /backups/portal/export_20260117/ --force
```

---

## Project Management Commands

### create_orcd_project

Creates ORCD projects with support for ORCD-specific member roles. By default, creates a project following the `USERNAME_group` naming convention.

**ORCD Member Roles:**

| Role | Description |
|------|-------------|
| Owner | Full control (implicit via project PI) |
| `financial_admin` | Can manage cost allocation |
| `technical_admin` | Can manage technical aspects |
| `member` | Basic project member |

**Usage:**

```bash
coldfront create_orcd_project <username> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `username` | Username of the project owner (PI) |

**Options:**

| Option | Description |
|--------|-------------|
| `--project-name` | Project name/title (default: `USERNAME_group`) |
| `--description` | Project description (default: `"Group project for USERNAME"`) |
| `--status` | Project status: `New`, `Active`, `Archived` (default: `Active`) |
| `--add-member` | Add member with ORCD role: `user:role` (repeatable) |
| `--force` | Update existing project instead of reporting error |
| `--dry-run` | Show Django ORM commands that would be executed |
| `--quiet` | Suppress non-essential output |

**Examples:**

```bash
# Create default group project for user
coldfront create_orcd_project jsmith

# Create project with custom name
coldfront create_orcd_project jsmith --project-name "Research Lab"

# Create project with members
coldfront create_orcd_project jsmith --add-member auser:financial_admin
coldfront create_orcd_project jsmith --add-member buser:technical_admin --add-member cuser:member

# Preview what would be done
coldfront create_orcd_project jsmith --dry-run

# Update existing project
coldfront create_orcd_project jsmith --description "Updated description" --force
```

---

### add_user_to_project

Adds a user to an existing ORCD project with a specified role. This command creates both a ColdFront `ProjectUser` record (required for ColdFront's project membership) and an ORCD-specific `ProjectMemberRole` record that defines the user's permissions within the ORCD plugin.

**ORCD Member Roles:**

| Role | Description |
|------|-------------|
| `financial_admin` | Can manage cost allocations, manage all roles, create reservations. NOT included in reservations or maintenance fee billing. |
| `technical_admin` | Can manage members and technical admins, create reservations. Included in reservations and maintenance fee billing. |
| `member` | Can create reservations only. Included in reservations and maintenance fee billing. |

**Usage:**

```bash
coldfront add_user_to_project <username> <project> --role <role> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `username` | Username of the user to add to the project |
| `project` | Project name (e.g., `jsmith_group`) or project ID |

**Options:**

| Option | Description |
|--------|-------------|
| `--role` | **Required.** ORCD role to assign: `financial_admin`, `technical_admin`, or `member` |
| `--force` | Update existing role assignment instead of reporting error |
| `--dry-run` | Show Django ORM commands that would be executed |
| `--quiet` | Suppress non-essential output |

**Examples:**

```bash
# Add a user as a member
coldfront add_user_to_project auser research_lab --role member

# Add a user as financial admin
coldfront add_user_to_project buser research_lab --role financial_admin

# Add a user as technical admin using project ID
coldfront add_user_to_project cuser 42 --role technical_admin

# Preview what would be done
coldfront add_user_to_project auser research_lab --role member --dry-run

# Add a role (user can have multiple roles)
coldfront add_user_to_project auser research_lab --role technical_admin
```

**Notes:**

- Users can have multiple roles in the same project. Each role grants different permissions.
- The project owner (PI) cannot be added as a member because the owner role is implicit.
- A ColdFront `ProjectUser` record is automatically created if it doesn't exist.
- Use `create_orcd_project --add-member` to add members when creating a new project.

**Dependencies:**

- Requires an existing user (create with `create_user` if needed)
- Requires an existing project (create with `create_orcd_project` if needed)
- Uses `ProjectMemberRole` model from the ORCD plugin
- Uses `ProjectUser`, `ProjectUserRoleChoice`, and `ProjectUserStatusChoice` from ColdFront core

---

### set_project_cost_allocation

Sets cost allocation for a project by specifying cost objects and their percentage allocations. Cost allocations are required before a project can be used for reservations.

**Cost Object Format:**

Each allocation is specified as `CO:NNN` where:
- `CO` is the cost object identifier (alphanumeric characters and hyphens only)
- `NNN` is the percentage allocation (must be a positive number)

All percentages must sum to exactly 100.

**Usage:**

```bash
coldfront set_project_cost_allocation <project> <CO:PERCENT> [CO:PERCENT ...] [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `project` | Project name (e.g., `jsmith_group`) or project ID |
| `CO:PERCENT` | One or more cost object allocations (e.g., `ABC-123:50`) |

**Options:**

| Option | Description |
|--------|-------------|
| `--notes` | Notes about the cost allocation |
| `--status` | Initial status: `PENDING`, `APPROVED`, `REJECTED` (default: `PENDING`) |
| `--reviewed-by` | Username or user ID of the Billing Manager who approved the allocation. The user must be a member of the Billing Manager group. Sets `reviewed_at` automatically. |
| `--review-notes` | Optional notes from the reviewer about the approval decision |
| `--force` | Replace existing cost allocation instead of reporting error |
| `--dry-run` | Show Django ORM commands that would be executed |
| `--quiet` | Suppress non-essential output |

**Examples:**

```bash
# Set a single cost object (100%)
coldfront set_project_cost_allocation jsmith_group ABC-123:100

# Split between multiple cost objects
coldfront set_project_cost_allocation jsmith_group ABC-123:50 DEF-456:30 GHI-789:20

# Set allocation with notes
coldfront set_project_cost_allocation jsmith_group ABC-123:100 --notes "FY26 Q1 allocation"

# Replace existing allocation
coldfront set_project_cost_allocation jsmith_group NEW-001:100 --force

# Set as pre-approved with reviewer information (recommended)
coldfront set_project_cost_allocation jsmith_group ABC-123:100 \
    --status APPROVED --reviewed-by billing_admin --review-notes "Approved for FY26"

# Set as approved using reviewer's user ID
coldfront set_project_cost_allocation jsmith_group ABC-123:100 \
    --status APPROVED --reviewed-by 42

# Preview what would be done
coldfront set_project_cost_allocation jsmith_group ABC-123:50 DEF-456:50 --dry-run
```

**Notes:**

- When using `--force` to replace an existing allocation, the previous cost objects are deleted and new ones are created.
- When `--reviewed-by` is specified, `reviewed_at` is automatically set to the current timestamp.
- The `--reviewed-by` user must be a Billing Manager (member of the "Billing Manager" group, have `can_manage_billing` permission, or be a superuser).
- By default, new allocations have status `PENDING` and require Billing Manager approval before the project can be used for reservations.
- When using `--status APPROVED`, it's recommended to also specify `--reviewed-by` to properly record who approved the allocation.

---

### set_user_amf

Sets the account maintenance fee (AMF) status and billing project for a user. Account maintenance fees are recurring charges based on the user's maintenance tier (basic or advanced) and are billed to a specified project.

**Maintenance Status Levels:**

| Status | Description |
|--------|-------------|
| `inactive` | No maintenance fees (default for new accounts) |
| `basic` | Basic account maintenance (requires billing project) |
| `advanced` | Advanced account maintenance (requires billing project) |

**Billing Project Requirements:**

- The user must have an eligible role in the project: `owner`, `technical_admin`, or `member`
- Users with only `financial_admin` role cannot use a project for maintenance fees
- The project should have an approved cost allocation for billing to function

**Usage:**

```bash
coldfront set_user_amf <username> <status> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `username` | Username of the user to configure |
| `status` | Maintenance status: `inactive`, `basic`, or `advanced` |

**Options:**

| Option | Description |
|--------|-------------|
| `--project` | Project name or ID to charge maintenance fees to (required for basic/advanced) |
| `--force` | Update existing configuration instead of reporting error |
| `--dry-run` | Show Django ORM commands that would be executed |
| `--quiet` | Suppress non-essential output |

**Examples:**

```bash
# Set a user to inactive (no maintenance fees)
coldfront set_user_amf jsmith inactive

# Set a user to basic maintenance level
coldfront set_user_amf jsmith basic --project jsmith_group

# Set a user to advanced maintenance level
coldfront set_user_amf jsmith advanced --project research_lab

# Update existing configuration (requires --force)
coldfront set_user_amf jsmith basic --project new_project --force

# Preview what would be done
coldfront set_user_amf jsmith advanced --project jsmith_group --dry-run
```

**Notes:**

- New users automatically start with `inactive` status and no billing project.
- Changing status from `inactive` to `basic` or `advanced` requires specifying a billing project.
- If a user is removed from a project that is their maintenance billing project, their status is automatically reset to `inactive`.
- The project's cost allocation must be approved by a Billing Manager before maintenance fees can actually be invoiced.

---

## Reservation Management Commands

### create_node_rental

Creates a node rental reservation for a GPU node instance. This command creates a `Reservation` record associating a specific GPU node with a project and requesting user for a specified time period.

**Reservation Timing Rules:**

| Rule | Description |
|------|-------------|
| Start Time | Reservations always start at 4:00 PM on the start date |
| Duration | Measured in 12-hour blocks (1 block = 12 hours) |
| End Time | Calculated as start + (blocks * 12 hours), capped at 9:00 AM |
| Maximum Duration | 14 blocks (7 days) |

**Reservation Statuses:**

| Status | Description |
|--------|-------------|
| `PENDING` | Awaiting approval from a Rental Manager (default) |
| `APPROVED` | Confirmed and scheduled |
| `DECLINED` | Rejected by a Rental Manager |
| `CANCELLED` | Cancelled by user or manager |

**Usage:**

```bash
coldfront create_node_rental <node_address> <project> <username> --start-date <YYYY-MM-DD> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `node_address` | Associated resource address of the GPU node instance (e.g., `gpu-h200x8-001`) |
| `project` | Project name (e.g., `jsmith_group`) or project ID |
| `username` | Username of the requesting user |

**Options:**

| Option | Description |
|--------|-------------|
| `--start-date` | **Required.** Start date in YYYY-MM-DD format (reservation starts at 4:00 PM) |
| `--num-blocks` | Number of 12-hour blocks (default: 1, min: 1, max: 14) |
| `--status` | Reservation status: `PENDING`, `APPROVED`, `DECLINED`, `CANCELLED` (default: `PENDING`) |
| `--rental-notes` | Notes from the requester about this reservation |
| `--manager-notes` | Notes from the rental manager (for approved/declined reservations) |
| `--processed-by` | Username of the rental manager who processed this reservation |
| `--skip-validation` | Skip validation checks (cost allocation, user eligibility, node rentability) |
| `--force` | Create reservation even if there are overlapping reservations |
| `--dry-run` | Show Django ORM commands that would be executed |
| `--quiet` | Suppress non-essential output |

**Examples:**

```bash
# Create a basic reservation (pending approval)
coldfront create_node_rental gpu-h200x8-001 jsmith_group jsmith --start-date 2026-02-15

# Create a 3-block (36-hour) reservation
coldfront create_node_rental gpu-h200x8-001 jsmith_group jsmith --start-date 2026-02-15 --num-blocks 3

# Create a pre-approved reservation with manager notes
coldfront create_node_rental gpu-h200x8-001 jsmith_group jsmith --start-date 2026-02-15 \
    --status APPROVED --processed-by rental_admin --manager-notes "Approved for urgent research"

# Create a reservation with requester notes
coldfront create_node_rental gpu-h200x8-001 jsmith_group jsmith --start-date 2026-02-15 \
    --rental-notes "Need GPU for model training deadline"

# Preview what would be created
coldfront create_node_rental gpu-h200x8-001 jsmith_group jsmith --start-date 2026-02-15 --dry-run

# Force creation despite overlapping reservations
coldfront create_node_rental gpu-h200x8-001 jsmith_group jsmith --start-date 2026-02-15 --force

# Skip validation checks (for testing/migration)
coldfront create_node_rental gpu-h200x8-001 jsmith_group jsmith --start-date 2026-02-15 --skip-validation
```

**Notes:**

- By default, the command validates that:
  - The project has an approved cost allocation
  - The requesting user is eligible to make reservations (owner, technical admin, or member)
  - The GPU node is marked as rentable
  - No overlapping reservations exist for the same node and time period
- Use `--skip-validation` to bypass cost allocation, user eligibility, and rentability checks
- Use `--force` to create a reservation even when overlapping reservations exist
- When creating pre-approved reservations, use `--status APPROVED` with `--processed-by` to record who approved it
- Overlapping reservations are detected for `PENDING` and `APPROVED` reservations only; `DECLINED` and `CANCELLED` reservations are ignored

**Dependencies:**

- Requires an existing GPU node instance (loaded via fixtures or created in admin)
- Requires an existing project (create with `create_orcd_project` if needed)
- Requires an existing user (create with `create_user` if needed)
- For validation to pass, requires:
  - Approved project cost allocation (create with `set_project_cost_allocation`)
  - User must have an eligible role in the project (add with `add_user_to_project`)
  - Node must have `is_rentable=True`

---

## User Management Commands

### create_user

Creates user accounts with optional API token generation and manager group assignment. Supports OIDC/SSO-only accounts (no password).

**Environment Variables:**

| Variable | Description |
|----------|-------------|
| `ORCD_EMAIL_DOMAIN` | Default email domain (e.g., `example.edu`) |
| `ORCD_USER_PASSWORD` | Default password for new users (optional) |

**Usage:**

```bash
coldfront create_user <username> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `username` | Username to create |

**Options:**

| Option | Description |
|--------|-------------|
| `--email` | Email address (defaults to `{username}@{ORCD_EMAIL_DOMAIN}`) |
| `--password` | Password (defaults to `$ORCD_USER_PASSWORD` or generates random) |
| `--no-password` | Create OIDC/SSO-only account with no password authentication |
| `--with-token` | Generate and display an API token for the user |
| `--add-to-group` | Add user to a manager group: `rental`, `billing`, or `rate` (repeatable) |
| `--active` | Set user as active (default) |
| `--inactive` | Set user as inactive |
| `--force` | Update existing user instead of reporting error |
| `--dry-run` | Show Django ORM commands that would be executed |
| `--quiet` | Suppress non-essential output |

**Examples:**

```bash
# Create a basic user
coldfront create_user jsmith

# Create user with specific email and API token
coldfront create_user jsmith --email jsmith@university.edu --with-token

# Create user and add to rental manager group
coldfront create_user jsmith --with-token --add-to-group rental

# Create OIDC/SSO-only account (no password login)
coldfront create_user jsmith --no-password --with-token

# Preview what would be done
coldfront create_user jsmith --dry-run

# Update existing user
coldfront create_user jsmith --email newemail@example.edu --force
```

---

## Group Setup Commands

These three commands share a similar interface for managing permission groups. Each command handles a specific manager role with its associated permission.

### setup_billing_manager

Manages the "Billing Manager" group with the `can_manage_billing` permission.

**Usage:**

```bash
coldfront setup_billing_manager [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--create-group` | Create the Billing Manager group with permissions |
| `--add-user <username>` | Add a user to the group |
| `--remove-user <username>` | Remove a user from the group |
| `--list` | List all users in the group |

**Examples:**

```bash
# Initial setup - create the group
coldfront setup_billing_manager --create-group

# Add a user to the group
coldfront setup_billing_manager --add-user jsmith

# List current members
coldfront setup_billing_manager --list

# Remove a user
coldfront setup_billing_manager --remove-user jsmith
```

---

### setup_rate_manager

Manages the "Rate Manager" group with the `can_manage_rates` permission.

**Usage:**

```bash
coldfront setup_rate_manager [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--create-group` | Create the Rate Manager group with permissions |
| `--add-user <username>` | Add a user to the group |
| `--remove-user <username>` | Remove a user from the group |
| `--list` | List all users in the group |

**Examples:**

```bash
# Initial setup - create the group
coldfront setup_rate_manager --create-group

# Add a user to the group
coldfront setup_rate_manager --add-user jsmith

# List current members
coldfront setup_rate_manager --list
```

---

### setup_rental_manager

Manages the "Rental Manager" group with the `can_manage_rentals` permission. This command also handles migration from the legacy "Rental Managers" (plural) group name.

**Usage:**

```bash
coldfront setup_rental_manager [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--create-group` | Create the Rental Manager group with permissions |
| `--add-user <username>` | Add a user to the group |
| `--remove-user <username>` | Remove a user from the group |
| `--list` | List all users in the group |

**Examples:**

```bash
# Initial setup - create the group
coldfront setup_rental_manager --create-group

# Add a user to the group
coldfront setup_rental_manager --add-user jsmith

# List current members
coldfront setup_rental_manager --list
```

---

## Synchronization Commands

### sync_node_skus

Synchronizes RentalSKU records with NodeTypes. Creates missing RentalSKU records for NodeTypes that don't have corresponding SKUs, and updates existing SKUs if their linked NodeType has changed.

This is useful for:
- Initial setup after loading NodeType fixtures
- Recovering from migration issues where SKUs weren't created
- Verifying SKU/NodeType consistency

**Usage:**

```bash
coldfront sync_node_skus [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--all` | Include inactive NodeTypes (default: only active) |
| `--dry-run` | Show what would be done without making changes |

**Examples:**

```bash
# Sync all active NodeTypes
coldfront sync_node_skus

# Include inactive NodeTypes
coldfront sync_node_skus --all

# Preview changes without applying
coldfront sync_node_skus --dry-run
```

**Note:** Newly created SKUs are assigned a placeholder rate of $0.01. Use the Rate Management interface to set actual rates after syncing.

---

## Common Patterns

### Dry Run Mode

Most commands support `--dry-run` to preview changes without modifying the database:

```bash
coldfront export_portal_data -o /backups/ --dry-run
coldfront import_portal_data /backups/export_20260117/ --dry-run
coldfront create_user jsmith --dry-run
coldfront create_orcd_project jsmith --dry-run
coldfront set_project_cost_allocation jsmith_group ABC-123:100 --dry-run
coldfront sync_node_skus --dry-run
```

### Setting Up a New Instance

Typical setup sequence for a new portal instance:

```bash
# 1. Create manager groups
coldfront setup_rental_manager --create-group
coldfront setup_billing_manager --create-group
coldfront setup_rate_manager --create-group

# 2. Sync NodeTypes to SKUs
coldfront sync_node_skus

# 3. Create admin users
coldfront create_user admin --with-token --add-to-group rental --add-to-group billing --add-to-group rate

# 4. Create projects with team members
coldfront create_orcd_project admin --project-name "Admin Project" --add-member billing_user:financial_admin

# 4b. Add additional users to existing projects
coldfront add_user_to_project researcher1 admin_group --role member
coldfront add_user_to_project researcher2 admin_group --role technical_admin

# 5. Set cost allocation for projects (required for reservations)
coldfront set_project_cost_allocation admin_group ABC-COST-001:100 --status APPROVED

# 6. Set up account maintenance fees for users
coldfront set_user_amf admin basic --project admin_group
```

### Backup and Restore

```bash
# Export data
coldfront export_portal_data -o /backups/portal/

# Check compatibility before import
coldfront check_import_compatibility /backups/portal/export_20260117/ --verbose

# Import data
coldfront import_portal_data /backups/portal/export_20260117/ --dry-run
coldfront import_portal_data /backups/portal/export_20260117/
```

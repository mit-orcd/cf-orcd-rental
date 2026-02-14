# System Test Workflow (Script-Based)

This document describes the script-driven system test workflow for the ORCD Rental Portal.
It replaces the pytest-heavy approach with per-module shell scripts that are YAML-controlled,
CI-friendly, and easy to run locally.

## Overview

### Purpose
- Provide repeatable workflows for provisioning users, projects, reservations, billing data, and APIs.
- Keep data and parameters in human-editable YAML.
- Make scripts usable outside CI (manual setup, approval flows, ad-hoc testing).

### Design Principles
1. **YAML-driven**: test data and module selection are declared in `tests/setup/config`.
2. **Script-first**: each module is a shell script with clear inputs/outputs.
3. **Reusable**: scripts can be run locally or in CI without bespoke harnesses.
4. **Idempotent**: scripts should be safe to re-run (use `--force` where appropriate).
5. **Observable**: every module writes JSON/log outputs under `tests/setup/output/`.

## Architecture & Directory Structure

```
tests/setup/
├── user_smoke_test.sh           # Single-user smoke test (refactored to use common.sh)
├── run_workflow.sh              # Orchestrator for module scripts
├── lib/
│   └── common.sh                # Shared helpers (env setup, server, API, YAML)
├── modules/
│   ├── 01_users.sh
│   ├── 02_projects.sh
│   ├── 03_members.sh
│   ├── 04_1_attach_cost_allocations.sh   # Stage 1: submit as PENDING
│   ├── 04_2_confirm_cost_allocations.sh  # Stage 2: approve as billing manager
│   ├── 05_rates.sh
│   ├── 06_add_amf.sh                   # Account maintenance fees
│   ├── 07_1_create_reservations.sh     # Stage 1: submit as PENDING
│   ├── 07_2_confirm_reservations.sh    # Stage 2: approve as rental manager
│   ├── 08_maintenance.sh
│   ├── 09_invoices.sh
│   ├── 10_api.sh
│   └── 11_activity_log.sh
├── config/
│   ├── test_config.yaml
│   ├── users.yaml / users_multi.yaml
│   ├── projects.yaml
│   ├── members.yaml
│   ├── cost_allocations.yaml
│   ├── rates.yaml
│   ├── amf.yaml
│   ├── reservations.yaml
│   ├── invoices.yaml
│   └── maintenance_windows.yaml
└── output/
    └── <module>/                # Raw + pretty JSON, logs, tokens
```

## Execution Model (Script Runner)

`tests/setup/run_workflow.sh`:
- Reads `tests/setup/config/test_config.yaml` for enabled modules and config file paths.
- Runs modules in order and writes artifacts to `tests/setup/output/<module>/`.
- Supports `--module`, `--skip`, `--output-dir`, and `--dry-run`.

```bash
# Run full workflow (modules.enabled)
bash tests/setup/run_workflow.sh

# Run a single module
bash tests/setup/run_workflow.sh --module 01_users

# Skip one or more modules
bash tests/setup/run_workflow.sh --skip 02_projects,03_members
```

### Flow (shared helpers)

```mermaid
flowchart TD
  yamlConfig["YAML_Config"] --> runWorkflow["run_workflow.sh"]
  commonLib["common.sh"] --> moduleScripts["module_XX_*.sh"]
  runWorkflow --> moduleScripts
  moduleScripts --> coldfrontCLI["coldfrontCLI"]
  moduleScripts --> coldfrontAPI["coldfrontAPI"]
  moduleScripts --> outputs["output_artifacts"]
```

## Shared Library (`tests/setup/lib/common.sh`)

All scripts source `common.sh` for:
- `common_init`: workspace and path discovery.
- `ensure_env`: calls `setup_environment.sh`, reuses DB when present.
- `activate_env`: activates virtualenv and ensures API migrations are applied.
- `start_server_if_needed`, `wait_for_server`, `server_ready`.
- `api_get`: authenticated API requests.
- `pretty_json`: pretty-print output artifacts.
- `yaml_list`: extract values from YAML (requires PyYAML).
- `resolve_relative_date`: convert relative date expressions (`today+N`) to `YYYY-MM-DD`.

`tests/setup/user_smoke_test.sh` is refactored to use these helpers to keep the code consistent.

## Module Scripts & Dependencies

| Module | Script | Purpose | Depends On |
|---|---|---|---|
| 01 | `01_users.sh` | Create users, generate tokens, verify user search API | None |
| 02 | `02_projects.sh` | Create projects, add members | 01 |
| 03 | `03_members.sh` | Manage member roles | 01, 02 |
| 04_1 | `04_1_attach_cost_allocations.sh` | Submit cost allocations as PENDING | 02, 03 |
| 04_2 | `04_2_confirm_cost_allocations.sh` | Approve cost allocations as billing manager | 04_1 |
| 05 | `05_rates.sh` | Manage SKUs and rates | 01 |
| 06 | `06_add_amf.sh` | Set account maintenance fees | 01-05 |
| 07_1 | `07_1_create_reservations.sh` | Create reservations as PENDING | 04_2, 05, 06 |
| 07_2 | `07_2_confirm_reservations.sh` | Approve reservations as rental manager | 07_1 |
| 08 | `08_maintenance.sh` | Create maintenance windows from schedules | 01 |
| 09 | `09_invoices.sh` | Generate invoice reports via API | 01, 07, 08 |
| 10 | `10_api.sh` | API endpoint checks | All |
| 11 | `11_activity_log.sh` | Activity log verification | All |

Notes:
- Implemented modules: 01 (users), 02 (projects), 03 (members), 04_1/04_2 (cost allocations), 05 (rates), 06 (AMF), 07_1/07_2 (reservations), 08 (maintenance windows), 09 (invoices).
- Modules 10-11 are placeholders that return exit code `2` and log a message until implemented.

## YAML Configuration

### `tests/setup/config/test_config.yaml`
```yaml
version: "1.0"
environment:
  base_url: "${TEST_BASE_URL:-http://localhost:8000}"

modules:
  enabled:
    - 01_users
    - 02_projects
  skip: []

includes:
  users: "users.yaml"
  projects: "projects.yaml"
  reservations: "reservations.yaml"
  invoices: "invoices.yaml"
  maintenance_windows: "maintenance_windows.yaml"
```

### Users (`users.yaml`)
- Defines manager and regular users.
- `groups` supports `billing`, `rental`, `rate` aliases for `create_user --add-to-group`.

### Projects (`projects.yaml`)
- Defines projects, owners, and member roles.
- Roles map to `create_orcd_project --add-member <username:role>`.

### Account Maintenance Fees (`amf.yaml`)

Drives the AMF enrollment workflow (module 06):

```yaml
version: "1.0"
defaults:
  status: "basic"
entries:
  - username: "orcd_u0"
    status: "basic"
    project: "orcd_u0_p1"
```

**Fields:**
- `username`: User to configure
- `status`: Maintenance level (`basic` for MAINT_STANDARD, `advanced` for MAINT_ADVANCED)
- `project`: Billing project (user must be owner, technical_admin, or member; must have approved cost allocation)

**Management command:**
- `coldfront set_user_amf <username> <status> --project <project> --force`

### Reservations (`reservations.yaml`)

Drives the two-stage reservation workflow (module 07):

**Stage 1** (`07_1_create_reservations.sh`): Creates reservations as PENDING using `coldfront create_node_rental`.

**Stage 2** (`07_2_confirm_reservations.sh`): Approves all reservations using `coldfront approve_node_rental`.

```yaml
version: "1.0"
defaults:
  status: "PENDING"
  num_blocks: 2
approval:
  processed_by: "orcd_rem"
  manager_notes: "Approved during test setup"
reservations:
  - node_address: "node2433"
    project: "orcd_u0_p1"
    requesting_user: "orcd_u0"
    start_date: "today+7"
    num_blocks: 2
    rental_notes: "Owner-submitted reservation"
```

**Fields:**
- `node_address`: GPU node instance address (must be rentable)
- `project`: Project name (must have APPROVED cost allocation)
- `requesting_user`: User submitting the request (must be owner, technical_admin, or member)
- `start_date`: Relative date expression resolved at runtime by `resolve_relative_date` (from `lib/common.sh`). Supported formats: `"today+7"`, `"today + 7 days"`, `"today"`, or `"YYYY-MM-DD"` passthrough.
- `num_blocks`: Duration in 12-hour blocks (default from `defaults.num_blocks`)
- `rental_notes`: Optional notes from the requester

**Constraints:**
- No two reservations on the same `node_address` may overlap in time.
- Reservations start at 4:00 PM and last `num_blocks * 12` hours (capped at 9:00 AM on the final day).
- Relative dates ensure the config works regardless of when scripts are run.

**Management commands:**
- `coldfront create_node_rental <node> <project> <user> --start-date <date> --num-blocks <n> --status PENDING --force`
- `coldfront approve_node_rental <node> <project> --start-date <date> --processed-by <user> --force`

### Maintenance Windows (`maintenance_windows.yaml`)

Drives the maintenance window creation workflow (module 08). Uses a **schedule-based format** where each entry defines a recurring pattern that is expanded into concrete dates at runtime.

```yaml
version: "1.0"
defaults:
  months_ahead: 3
  start_time: "06:00"
  end_time: "18:00"
schedules:
  - title: "Monthly scheduled maintenance"
    weekday: "tuesday"
    week_of_month: 3
    months_ahead: 3
    description: "3rd Tuesday of every month"
```

**Schedule fields:**
- `title`: Base title; the computed date is appended, e.g. "Monthly scheduled maintenance (Mar 18, 2026)"
- `weekday`: Day of the week (`monday` through `sunday`)
- `week_of_month`: Which occurrence in the month (1-4, or `last`)
- `start_time` / `end_time`: Time of day for the window (defaults from `defaults` section)
- `months_ahead`: How many months to generate from today (default from `defaults`)
- `description`: Optional description

**Expansion:** The inline Python in the script uses `calendar.monthcalendar` to find the Nth weekday of each month, skipping past dates. Each schedule at 3 months produces ~3 concrete windows.

**Management command:**
- `coldfront create_maintenance_window --start "YYYY-MM-DD HH:MM" --end "YYYY-MM-DD HH:MM" --title "..." [--description "..."]`

### Invoices (`invoices.yaml`)

Drives the invoice generation workflow (module 09). Uses the **REST API** rather than management commands, since invoices are computed on-the-fly.

```yaml
version: "1.0"
defaults:
  billing_user: "orcd_bim"
invoice_periods:
  - "today - 2 months"
  - "today - 1 month"
  - "today"
  - "today + 1 month"
  - "today + 2 months"
```

**Fields:**
- `billing_user`: Username whose API token authenticates the requests (must have `can_manage_billing` permission)
- `invoice_periods`: Relative month expressions resolved at runtime. Supported: `"today"`, `"today - N months"`, `"today + N months"`

**API endpoints:**
- `GET /nodes/api/invoice/YYYY/MM/` - Combined report: reservations, AMF, and QoS per project
- `GET /nodes/api/invoice/reservations/YYYY/MM/` - Reservation-only report
- `GET /nodes/api/invoice/amf/YYYY/MM/` - Account maintenance fee-only report
- `GET /nodes/api/invoice/qos/YYYY/MM/` - QoS subscription-only report

The combined endpoint returns full invoice JSON including node rental hours, cost breakdowns, maintenance deductions, overrides, AMF entries with `activated_at` for partial-month billing, and QoS entries with `start_date`/`end_date` for partial-month billing. The script saves raw and pretty-printed JSON to the output directory.

**Output files:** `output/09_invoices/invoice_YYYY_MM.json` and `invoice_YYYY_MM_pretty.json` for each month.

### Future Modules
Modules 10 (API checks) and 11 (activity log) are placeholders for the upcoming module scripts.

## CI/CD Integration (Script-Based)

### GitHub Actions Example
```yaml
- name: Setup Environment
  run: |
    cd coldfront-orcd-direct-charge
    ./tests/setup/setup_environment.sh

- name: Run Script Workflow
  run: |
    cd coldfront-orcd-direct-charge
    bash tests/setup/run_workflow.sh

- name: Upload Outputs
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: system-test-output
    path: coldfront-orcd-direct-charge/tests/setup/output/
```

For minimal CI validation, `tests/setup/user_smoke_test.sh` can be used instead of the full workflow.

## Local Usage

```bash
# Minimal smoke test
bash tests/setup/user_smoke_test.sh

# Full workflow (enabled modules)
bash tests/setup/run_workflow.sh
```

## Implementation Notes
- YAML parsing requires PyYAML (`pip install pyyaml`).
- Module scripts should write raw and pretty JSON outputs per module.
- Scripts should be safe to re-run (use `--force` for create/update commands).

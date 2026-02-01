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
│   ├── 04_cost_allocation.sh
│   ├── 05_rates.sh
│   ├── 06_reservations.sh
│   ├── 07_maintenance.sh
│   ├── 08_invoices.sh
│   ├── 09_api.sh
│   └── 10_activity_log.sh
├── config/
│   ├── test_config.yaml
│   ├── users.yaml
│   ├── projects.yaml
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

`tests/setup/user_smoke_test.sh` is refactored to use these helpers to keep the code consistent.

## Module Scripts & Dependencies

| Module | Script | Purpose | Depends On |
|---|---|---|---|
| 01 | `01_users.sh` | Create users, generate tokens, verify user search API | None |
| 02 | `02_projects.sh` | Create projects, add members | 01 |
| 03 | `03_members.sh` | Manage member roles | 01, 02 |
| 04 | `04_cost_allocation.sh` | Create/approve cost allocations | 02, 03 |
| 05 | `05_rates.sh` | Manage SKUs and rates | 01 |
| 06 | `06_reservations.sh` | Reservation workflows | 04, 05 |
| 07 | `07_maintenance.sh` | Maintenance windows | 01 |
| 08 | `08_invoices.sh` | Invoice generation and overrides | 06, 07 |
| 09 | `09_api.sh` | API endpoint checks | All |
| 10 | `10_activity_log.sh` | Activity log verification | All |

Notes:
- `01_users.sh` and `02_projects.sh` are implemented and produce artifacts.
- Modules 03–10 are placeholders that return exit code `2` and log a message until implemented.

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

### Future Modules
`reservations.yaml`, `maintenance_windows.yaml`, and `invoices.yaml` provide placeholders for the upcoming module scripts.

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

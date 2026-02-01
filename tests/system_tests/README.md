# System Tests - Module 01: User Management

This directory contains system-level tests for the ORCD Rental Portal plugin, focusing on user management functionality via management commands.

## Important: Environment Setup Approach

**All tests in this repository use the shared setup infrastructure from `tests/setup/`.**

This is a deliberate architectural decision:

1. **Portability**: The `tests/setup/setup_environment.sh` script works across GitHub Actions, GitLab CI, Woodpecker CI, and local development environments.

2. **Maintainability**: A single, validated recipe for environment setup means changes are made in one place and automatically apply to all tests.

3. **Clarity**: The setup scripts are written in plain bash, not obscure CI-specific YAML syntax that varies between platforms.

4. **Validation**: The setup scripts are exercised regularly through actual test runs, ensuring they remain functional.

**For developers and AI agents**: Do not create inline environment setup in workflow files. Always use `tests/setup/setup_environment.sh` and extend it if new capabilities are needed.

## Directory Structure

```
tests/system_tests/
├── README.md                 # This file - overview and guidance
├── test.sh                   # Entry point for run_all_tests.sh discovery
├── run_tests.py              # Main test runner with multiple modes
├── requirements.txt          # Python dependencies for system tests
├── config/
│   ├── users.yaml.example    # Example user definitions (copy to users.yaml)
│   └── projects.yaml.example # Example project definitions (copy to projects.yaml)
├── modules/
│   ├── __init__.py
│   ├── base.py               # BaseSystemTest class with command helpers
│   └── test_01_users.py      # User management test cases
└── utils/
    ├── __init__.py
    ├── yaml_loader.py        # YAML configuration parser
    └── command_generator.py  # Shell script generator from YAML config
```

## File Descriptions

### Entry Points

| File | Description |
|------|-------------|
| `test.sh` | Bash script discovered by `tests/run_all_tests.sh`. Activates the ColdFront environment and runs tests. |
| `run_tests.py` | Python test runner with multiple execution modes (CI/CD, dry-run, command generation). |

### Configuration

| File | Description |
|------|-------------|
| `config/users.yaml.example` | Template for user definitions. Copy to `users.yaml` and customize. |
| `config/projects.yaml.example` | Template for project definitions. Copy to `projects.yaml` and customize. |
| `requirements.txt` | Python packages needed for system tests (pytest, pyyaml, etc.). |

### Modules

| File | Description |
|------|-------------|
| `modules/base.py` | `BaseSystemTest` class providing `run_command()` for executing management commands and `generate_command_script()` for creating runnable shell scripts. |
| `modules/test_01_users.py` | Test cases for user creation, group management, and account maintenance fee (AMF) configuration. |

### Utilities

| File | Description |
|------|-------------|
| `utils/yaml_loader.py` | Loads and parses YAML config files with defaults and variable substitution. |
| `utils/command_generator.py` | `CommandGenerator` class that generates coldfront management commands from YAML configuration. |

## Quick Start

### 1. Setup Environment (Required)

```bash
# From the plugin root directory
./tests/setup/setup_environment.sh
```

This sets up ColdFront with the plugin installed. See `tests/setup/README.md` for details.

### 2. Configure Test Data

```bash
cd tests/system_tests/config
cp users.yaml.example users.yaml
cp projects.yaml.example projects.yaml
# Edit users.yaml and projects.yaml with your test data
```

### 3. Run Tests

```bash
# Option A: Via the master test runner (runs all tests)
./tests/run_all_tests.sh

# Option B: Run system tests directly
./tests/system_tests/test.sh

# Option C: Via Python runner with options
cd tests/system_tests
python run_tests.py --verbose
```

## Execution Modes

The `run_tests.py` script supports three execution modes:

### CI/CD Mode (Default)

Runs tests using pytest against the configured ColdFront environment.

```bash
python run_tests.py
python run_tests.py --verbose
python run_tests.py --module test_01_users
```

### Dry-Run Mode

Runs tests but appends `--dry-run` to all management commands, so no actual changes are made.

```bash
python run_tests.py --dry-run
```

### Command Generation Mode

Generates a shell script with all the management commands, without running tests. Useful for manual execution or review.

```bash
python run_tests.py --generate-commands-only --output setup_users.sh
./setup_users.sh  # Run the generated script manually
```

## CI/CD Integration

### GitHub Actions

The workflow at `.github/workflows/user-management-tests.yml` runs these tests. It:

1. Uses `tests/setup/setup_environment.sh` for environment setup
2. Installs system test dependencies
3. Runs tests via `run_tests.py`

The workflow can be triggered manually with options for dry-run or command generation modes.

### Other CI Systems

For GitLab CI, Woodpecker, or other systems, follow the pattern:

```yaml
# 1. Setup environment using shared script
- ./tests/setup/setup_environment.sh

# 2. Activate and run system tests
- source ../coldfront/.venv/bin/activate
- pip install -r tests/system_tests/requirements.txt
- python tests/system_tests/run_tests.py
```

## Adding New Tests

### Adding Test Cases

1. Add test methods to `modules/test_01_users.py` or create new test modules (`test_02_*.py`)
2. Inherit from `BaseSystemTest` and `unittest.TestCase`
3. Use `self.run_command()` to execute management commands

```python
from .base import BaseSystemTest
import unittest

class TestNewFeature(BaseSystemTest, unittest.TestCase):
    def test_something(self):
        code, stdout, stderr = self.run_command("my_command --option value")
        self.assertEqual(code, 0)
```

### Adding Configuration

1. Update `config/users.yaml.example` or `config/projects.yaml.example`
2. Update `utils/yaml_loader.py` if new parsing logic is needed
3. Update `utils/command_generator.py` if new command types are needed

### Extending Environment Setup

If tests need new environment capabilities:

1. **Prefer extending `tests/setup/setup_environment.sh`** with new environment variables or steps
2. Document new options in `tests/setup/README.md`
3. This ensures all tests benefit from the enhancement

## Design Principles

1. **Shared Infrastructure**: All tests use `tests/setup/` for environment setup
2. **YAML-Driven Data**: Test data is defined in YAML files, not hardcoded
3. **Command Generation**: Tests can generate runnable scripts for manual execution
4. **Dry-Run Support**: All tests support a dry-run mode for safe validation
5. **CI-Agnostic**: Works on any CI system, not just GitHub Actions

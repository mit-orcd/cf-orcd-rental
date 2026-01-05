# Testing Framework

This directory contains automated tests for the coldfront-orcd-direct-charge plugin. Tests are designed to work with CI/CD pipelines including GitHub Actions, GitLab CI/CD, and Woodpecker CI.

## Directory Structure

Each test lives in its own subdirectory with:
- `test.sh` - The executable test script
- `README.md` - Documentation for the test

```
tests/
├── README.md              # This file
├── run_all_tests.sh       # Master script to run all tests
├── setup/                 # Environment setup scripts
│   ├── README.md          # Setup documentation
│   ├── setup_environment.sh        # Main setup script
│   └── local_settings.py.template  # ColdFront config template
└── smoke_http/            # HTTP connectivity smoke test
    ├── README.md
    └── test.sh
```

## Setting Up the Test Environment

For CI/CD or fresh development environments, use the setup script:

```bash
./tests/setup/setup_environment.sh
```

This clones ColdFront, installs dependencies, configures settings, and starts the server.
See `tests/setup/README.md` for full documentation.

## Running Tests

### Run All Tests

```bash
./tests/run_all_tests.sh
```

### Run Individual Test

```bash
./tests/smoke_http/test.sh
```

## Exit Code Conventions

All tests follow standard Unix exit code conventions for CI/CD compatibility:
- **Exit 0**: Test passed
- **Non-zero exit**: Test failed

## Environment Variables

Tests support configuration via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | `http://localhost:8000` | Base URL of the server to test |

Example:
```bash
BASE_URL=http://staging.example.com:8000 ./tests/run_all_tests.sh
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Start server
        run: |
          # Start your server in background
          # Example: docker-compose up -d
          
      - name: Wait for server
        run: sleep 10
        
      - name: Run tests
        run: ./tests/run_all_tests.sh
```

### GitLab CI/CD

```yaml
stages:
  - test

smoke_tests:
  stage: test
  script:
    - # Start server or use services
    - ./tests/run_all_tests.sh
  variables:
    BASE_URL: "http://localhost:8000"
```

### Woodpecker CI

[Woodpecker CI](https://woodpecker-ci.org/) is a simple, powerful CI/CD engine based on Docker containers.

```yaml
steps:
  - name: test
    image: alpine
    commands:
      - apk add --no-cache curl bash
      - ./tests/run_all_tests.sh
```

## Writing New Tests

1. Create a new subdirectory: `tests/your_test_name/`
2. Add `test.sh` with executable permission
3. Add `README.md` documenting the test
4. Follow this template for `test.sh`:

```bash
#!/usr/bin/env bash
set -e  # Exit on first error

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8000}"

# Test logic here...
echo "Running your_test_name..."

# Perform checks
# Use 'exit 1' or let 'set -e' handle failures

echo "PASSED: your_test_name"
exit 0
```

## Available Tests

| Test | Description |
|------|-------------|
| `smoke_http` | Verifies server responds to HTTP requests |

## Requirements

- `bash` (available on Linux, macOS, WSL2)
- `curl` (for HTTP tests)


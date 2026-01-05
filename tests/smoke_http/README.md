# Smoke Test: HTTP Connectivity and Content Verification

This test verifies that the server is running, responding to HTTP requests, and serving the expected welcome page content.

## What It Tests

1. **HTTP Connectivity**: Server is reachable and responds with success status (2xx/3xx)
2. **Content Verification**: Response contains expected patterns from plugin templates

## Prerequisites

- Server must be running (default: `http://localhost:8000`)
- `curl` must be installed

## Usage

### Basic Usage

```bash
./test.sh
```

### Custom Server URL

```bash
BASE_URL=http://staging.example.com:8000 ./test.sh
```

### Custom Timeout

```bash
TIMEOUT=30 ./test.sh
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | `http://localhost:8000` | Base URL of server to test |
| `TIMEOUT` | `10` | Connection timeout in seconds |

## Content Patterns

The test verifies these patterns exist in the response:

| Pattern | Source Template |
|---------|-----------------|
| `ORCD Rental Portal` | `templates/common/base.html:44` |
| `Log In To MIT ORCD Rental Portal` | `templates/portal/nonauthorized_home.html:7` |
| `About the Rental Portal` | `templates/portal/nonauthorized_home.html:18` |
| `The Rental Portal lets you rent dedicated GPU and CPU resources` | `templates/portal/nonauthorized_home.html:20` |

### Keeping Patterns in Sync

If you modify the source templates and the test fails:

1. Check if the content change was intentional
2. Update the `PATTERNS` array in `test.sh` to match the new content
3. Update this README's pattern table

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Test passed - HTTP success and all patterns found |
| 1 | Test failed - connection error, HTTP error, or missing patterns |

## Example Output

### Passing Test

```
========================================
  Smoke Test: HTTP Connectivity
========================================

Testing: http://localhost:8000/
Timeout: 10s

HTTP Status: 200

========================================
  Content Verification
========================================

  ✓ Found: "ORCD Rental Portal"
  ✓ Found: "Log In To MIT ORCD Rental Portal"
  ✓ Found: "About the Rental Portal"
  ✓ Found: "The Rental Portal lets you rent dedicated GPU and CPU resources"

Patterns: 4 passed, 0 failed

PASSED: Server responded with HTTP 200 and all content patterns verified
```

### Failing Test (Missing Pattern)

```
========================================
  Smoke Test: HTTP Connectivity
========================================

Testing: http://localhost:8000/
Timeout: 10s

HTTP Status: 200

========================================
  Content Verification
========================================

  ✓ Found: "ORCD Rental Portal"
  ✗ Missing: "Log In To MIT ORCD Rental Portal" (from templates/portal/nonauthorized_home.html:7)
  ✓ Found: "About the Rental Portal"
  ✓ Found: "The Rental Portal lets you rent dedicated GPU and CPU resources"

Patterns: 3 passed, 1 failed

FAILED: Some expected content patterns were not found

Missing patterns:
    - Log In To MIT ORCD Rental Portal

If templates have changed, update the PATTERNS array in this test.
```

## Platform Compatibility

This test works on:
- Linux
- macOS
- Windows WSL2
- GitHub Actions runners (ubuntu-latest, macos-latest)

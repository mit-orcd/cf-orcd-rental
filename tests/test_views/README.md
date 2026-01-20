# View Tests

This directory contains Django view tests for the coldfront_orcd_direct_charge plugin.

## Test Files

- `test_cost_allocation.py` - Tests for ProjectCostAllocationView
  - Verifies that viewing (GET) the page does NOT create a database record
  - Verifies that submitting (POST) a valid form creates a PENDING allocation
  - Verifies that existing allocations are preserved when viewing
  - Verifies activity logging behavior

## Requirements

These tests require a full Django environment with:
- ColdFront installed and configured
- This plugin installed
- Database migrations applied
- `pytest-django` for pytest-based testing

## Running Tests

### Using Django's test runner

From the ColdFront installation directory:

```bash
# Run all view tests
python manage.py test coldfront_orcd_direct_charge.tests.test_views

# Run specific test file
python manage.py test coldfront_orcd_direct_charge.tests.test_views.test_cost_allocation

# Run specific test class
python manage.py test coldfront_orcd_direct_charge.tests.test_views.test_cost_allocation.TestCancelDoesNotCreateAllocation

# Run with verbosity
python manage.py test coldfront_orcd_direct_charge.tests.test_views -v 2
```

### Using pytest (with pytest-django)

```bash
# Install pytest-django
pip install pytest-django

# Run from cf-orcd-rental directory
DJANGO_SETTINGS_MODULE=coldfront.config.settings pytest tests/test_views/ -v

# Run specific test
pytest tests/test_views/test_cost_allocation.py::TestCancelDoesNotCreateAllocation -v
```

## Test Coverage

### TestCancelDoesNotCreateAllocation

Tests the main bug fix:
- `test_get_page_does_not_create_allocation` - Core test for the fix
- `test_multiple_gets_do_not_create_allocation` - Edge case verification

### TestSubmitCreatesAllocation

Tests that valid submissions work correctly:
- `test_valid_post_creates_pending_allocation` - Normal submission flow
- `test_invalid_post_does_not_create_allocation` - Validation error handling

### TestExistingAllocationPreserved

Tests behavior with existing allocations:
- `test_get_preserves_approved_status` - No status change on view
- `test_submit_changes_approved_to_pending` - Status change on edit
- `test_existing_cost_objects_displayed` - Data displayed correctly

### TestActivityLogging

Tests audit trail behavior:
- `test_get_does_not_log_creation` - No spurious logs on view
- `test_post_logs_creation` - Proper logging on submission

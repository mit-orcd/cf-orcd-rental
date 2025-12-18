# Helper Programs

This directory contains utility scripts and tools for managing the ORCD Direct Charge ColdFront plugin.

## Available Tools

### csv_to_fixtures

Converts CSV files containing GPU and CPU node instance definitions into Django fixture JSON files.

**Location:** `csv_to_fixtures/`

**Purpose:** Simplifies bulk creation and updates of node instance fixtures by allowing you to define nodes in a spreadsheet-friendly CSV format, then convert them to the JSON fixture format required by Django's `loaddata` command.

**Usage:**
```bash
cd csv_to_fixtures
python3 csv_to_node_fixtures.py nodes.csv -o ../../coldfront_orcd_direct_charge/fixtures/
```

See `csv_to_fixtures/README.md` for detailed documentation.

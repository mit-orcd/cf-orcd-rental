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

### mk_gpucpunode_csv

Converts Slurm node JSON data to CSV format for the csv_to_fixtures tool.

**Location:** `mk_gpucpunode_csv/`

**Purpose:** Extracts node information from Slurm's JSON output (`scontrol show nodes --json`), filters by partition, classifies nodes as GPU or CPU types, and generates a CSV file that can be processed by the csv_to_fixtures converter.

**Usage:**
```bash
cd mk_gpucpunode_csv
./json_to_node_csv.sh nodes.json "partition1,partition2" output.csv
```

See `mk_gpucpunode_csv/README.md` for detailed documentation.

## Workflow

The tools are designed to work together in a pipeline:

```
Slurm JSON --> mk_gpucpunode_csv --> CSV --> csv_to_fixtures --> Django Fixtures
```

1. Export node data from Slurm: `scontrol show nodes --json > nodes.json`
2. Convert to CSV: `./mk_gpucpunode_csv/json_to_node_csv.sh nodes.json "partitions" nodes.csv`
3. Generate fixtures: `python3 csv_to_fixtures/csv_to_node_fixtures.py nodes.csv -o ../coldfront_orcd_direct_charge/fixtures/`
4. Load into ColdFront: `coldfront loaddata gpu_node_instances cpu_node_instances`




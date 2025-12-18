# CSV to Node Fixtures Converter

This helper program converts CSV files containing GPU and CPU node instance definitions into Django fixture JSON files that can be loaded into ColdFront.

## Usage

```bash
python csv_to_node_fixtures.py input.csv [--output-dir OUTPUT_DIR]
```

### Options

- `csv_file`: Path to the input CSV file (required)
- `--output-dir, -o`: Output directory for fixture files (default: same as CSV file location)
- `--gpu-output`: Filename for GPU fixtures (default: `gpu_node_instances.json`)
- `--cpu-output`: Filename for CPU fixtures (default: `cpu_node_instances.json`)
- `--rentable-percent, -rp`: Percentage (0-100) of nodes per type to mark as rentable (optional)

### Examples

```bash
# Basic usage - outputs to same directory as CSV
python csv_to_node_fixtures.py nodes.csv

# Specify output directory
python csv_to_node_fixtures.py nodes.csv --output-dir ../fixtures/

# Output directly to the plugin fixtures directory
python csv_to_node_fixtures.py nodes.csv -o ../../coldfront_orcd_direct_charge/fixtures/

# Mark only 30% of each node type as rentable
python csv_to_node_fixtures.py nodes.csv --rentable-percent 30
```

## Rentable Percentage

The `--rentable-percent` option allows you to override the `rentable` column from the CSV and instead mark only a percentage of nodes as rentable. This is applied **per node type**, so each type gets the specified percentage.

### How it works

- The percentage is applied using floor rounding
- For example, with `--rentable-percent 30`:
  - 10 H200x8 nodes → 3 rentable, 7 not rentable (30% of 10 = 3)
  - 50 L40Sx4 nodes → 15 rentable, 35 not rentable (30% of 50 = 15)
  - 4 CPU_1500G nodes → 1 rentable, 3 not rentable (30% of 4 = 1.2 → 1)

### Example output

```
$ python csv_to_node_fixtures.py nodes.csv --rentable-percent 30

Applying rentable percentage: 30%
GPU nodes:
  L40Sx4: 15 rentable, 35 not rentable (of 50 total)
  H200x8: 3 rentable, 9 not rentable (of 12 total)
CPU nodes:
  CPU_384G: 13 rentable, 33 not rentable (of 46 total)
  CPU_1500G: 1 rentable, 3 not rentable (of 4 total)

Wrote 62 entries to gpu_node_instances.json
Wrote 50 entries to cpu_node_instances.json

Summary: 62 GPU instances, 50 CPU instances
```

## CSV Format

The CSV file must contain the following columns:

| Column | Description | Valid Values |
|--------|-------------|--------------|
| `type` | Node type name | See valid types below |
| `resource_address` | Unique resource identifier | Any string (e.g., `gpu-h200x8-001`) |
| `status` | Current node status | `AVAILABLE`, `PLACEHOLDER` |
| `rentable` | Whether node can be rented | `true`, `false`, `yes`, `no`, `1`, `0` |

### Valid Node Types

**GPU Types:**
- `H200x8` - NVIDIA H200 node with 8 GPUs
- `H200x4` - NVIDIA H200 node with 4 GPUs
- `H200x2` - NVIDIA H200 node with 2 GPUs
- `H200x1` - NVIDIA H200 node with 1 GPU
- `L40Sx4` - NVIDIA L40S node with 4 GPUs
- `L40Sx2` - NVIDIA L40S node with 2 GPUs
- `L40Sx1` - NVIDIA L40S node with 1 GPU

**CPU Types:**
- `CPU_384G` - CPU node with 384G memory configuration
- `CPU_1500G` - CPU node with 1500G memory configuration

### Sample CSV

```csv
type,resource_address,status,rentable
H200x8,gpu-h200x8-001,AVAILABLE,true
H200x8,gpu-h200x8-002,AVAILABLE,true
H200x4,gpu-h200x4-001,AVAILABLE,true
L40Sx4,gpu-l40sx4-001,PLACEHOLDER,false
CPU_384G,cpu-384g-001,AVAILABLE,true
CPU_1500G,cpu-1500g-001,AVAILABLE,true
```

## Output

The script generates two JSON fixture files:

1. `gpu_node_instances.json` - Contains all GPU node instances
2. `cpu_node_instances.json` - Contains all CPU node instances

These files are formatted for Django's `loaddata` command and use natural keys for the `node_type` foreign key relationship.

## Loading Fixtures into ColdFront

After generating the fixture files, copy them to the plugin fixtures directory and load them:

```bash
# Copy to fixtures directory
cp gpu_node_instances.json ../../coldfront_orcd_direct_charge/fixtures/
cp cpu_node_instances.json ../../coldfront_orcd_direct_charge/fixtures/

# Load into ColdFront (node_types must be loaded first)
coldfront loaddata node_types
coldfront loaddata gpu_node_instances
coldfront loaddata cpu_node_instances
```

## Notes

- The `node_types` fixture must be loaded before loading node instances
- Node instances use `associated_resource_address` as a natural key, allowing `loaddata` to update existing records
- Invalid node types or status values will cause the script to exit with an error

# JSON to Node CSV Converter

This helper script converts Slurm node JSON data into CSV format compatible with the `csv_to_fixtures` converter.

## Prerequisites

- `jq` - Command-line JSON processor (install via `brew install jq` or `apt install jq`)

## Usage

```bash
./json_to_node_csv.sh <input.json> <partition1,partition2,...> [output.csv]
```

### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `input.json` | Path to JSON file containing Slurm node data | Yes |
| `partitions` | Comma-separated list of partitions to filter by | Yes |
| `output.csv` | Output CSV file path (default: `nodes.csv`) | No |

### Examples

```bash
# Filter nodes in GPU partitions
./json_to_node_csv.sh example_input.json "sched_bu_orcd_h200,sched_bu_orcd_l40s"

# Filter nodes and specify output file
./json_to_node_csv.sh example_input.json "sched_bu_orcd_h200" h200_nodes.csv

# Filter multiple partitions
./json_to_node_csv.sh example_input.json "sched_opportunist,newnodes" cpu_nodes.csv
```

## Input Format

The script expects JSON output from Slurm's `scontrol show nodes --json` command:

```json
{
  "nodes": [
    {
      "name": "node2433",
      "partitions": ["sched_bu_orcd_h200", "sched_system_all"],
      "gres": "gpu:h200:8(S:0-1)",
      "real_memory": 1546000
    },
    ...
  ]
}
```

### Generating Input

To generate the input JSON from a Slurm cluster:

```bash
scontrol show nodes --json > nodes.json
```

## Output Format

The script generates a CSV file with the following columns:

```csv
type,resource_address,status,rentable
H200x8,node2433,AVAILABLE,true
L40Sx4,node1632,AVAILABLE,true
CPU_384G,node001,AVAILABLE,true
CPU_1500G,node002,AVAILABLE,true
```

### Node Type Classification

**GPU Nodes** (when `gres` field contains `gpu:`):
- `H200x<N>` - H200 GPU nodes with N GPUs (parsed from `gres: "gpu:h200:N"`)
- `L40Sx<N>` - L40S GPU nodes with N GPUs (parsed from `gres: "gpu:l40s:N"`)

**CPU Nodes** (when `gres` is empty or doesn't contain GPU):
- `CPU_1500G` - Nodes with >= 1TB memory (`real_memory >= 1000000`)
- `CPU_384G` - Nodes with < 1TB memory

### Output Rules

- All nodes are marked as `AVAILABLE` status
- All nodes are marked as `rentable: true`
- The node `name` is used as the `resource_address`

## Workflow

This script is designed to work with the `csv_to_fixtures` converter:

```bash
# Step 1: Generate CSV from Slurm JSON
./json_to_node_csv.sh nodes.json "sched_bu_orcd_h200,sched_bu_orcd_l40s" filtered_nodes.csv

# Step 2: Convert CSV to Django fixtures
cd ../csv_to_fixtures
python3 csv_to_node_fixtures.py ../mk_gpucpunode_csv/filtered_nodes.csv \
    -o ../../coldfront_orcd_direct_charge/fixtures/

# Step 3: Load fixtures into ColdFront
coldfront loaddata node_types
coldfront loaddata gpu_node_instances
coldfront loaddata cpu_node_instances
```

## Notes

- Nodes with unrecognized GPU types (not h200 or l40s) are skipped
- Nodes with generic GPU specification (e.g., `gpu:1` without type) are skipped
- The script filters nodes that have **at least one** of the specified partitions

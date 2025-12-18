#!/bin/bash
#
# json_to_node_csv.sh - Convert Slurm node JSON to CSV for Django fixtures
#
# This script reads Slurm node JSON data (from `scontrol show nodes --json`),
# filters nodes by partition membership, classifies them as GPU or CPU nodes,
# and outputs a CSV file compatible with the csv_to_fixtures converter.
#
# Usage:
#   ./json_to_node_csv.sh <input.json> <partition1,partition2,...> [output.csv]
#
# Arguments:
#   input.json    - Path to JSON file containing Slurm node data
#   partitions    - Comma-separated list of partitions to filter by
#   output.csv    - Optional output file path (default: nodes.csv)
#
# Examples:
#   ./json_to_node_csv.sh nodes.json "sched_bu_orcd_h200,sched_bu_orcd_l40s"
#   ./json_to_node_csv.sh nodes.json "sched_bu_orcd_h200" gpu_nodes.csv
#

set -euo pipefail

# Check for required tools
command -v jq >/dev/null 2>&1 || { echo "Error: jq is required but not installed." >&2; exit 1; }

# Parse arguments
if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <input.json> <partition1,partition2,...> [output.csv]" >&2
    echo "" >&2
    echo "Arguments:" >&2
    echo "  input.json    - Path to JSON file containing Slurm node data" >&2
    echo "  partitions    - Comma-separated list of partitions to filter by" >&2
    echo "  output.csv    - Optional output file path (default: nodes.csv)" >&2
    exit 1
fi

INPUT_FILE="$1"
PARTITIONS="$2"
OUTPUT_FILE="${3:-nodes.csv}"

# Validate input file exists
if [[ ! -f "$INPUT_FILE" ]]; then
    echo "Error: Input file '$INPUT_FILE' not found." >&2
    exit 1
fi

# Convert comma-separated partitions to JSON array for jq
# e.g., "part1,part2" -> ["part1","part2"]
PARTITION_ARRAY=$(echo "$PARTITIONS" | awk -F',' '{
    printf "["
    for (i=1; i<=NF; i++) {
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", $i)  # trim whitespace
        printf "\"%s\"", $i
        if (i < NF) printf ","
    }
    printf "]"
}')

# Write CSV header
echo "type,resource_address,status,rentable" > "$OUTPUT_FILE"

# Process nodes with jq and classify them
# - Filter nodes that have at least one partition in the specified list
# - Classify as GPU or CPU based on gres field
# - For GPU: extract type (h200/l40s) and count from gres field
# - For CPU: classify based on real_memory (>= 1000000 MB = CPU_1500G, else CPU_384G)
jq -r --argjson partitions "$PARTITION_ARRAY" '
    # Function to check if node has any of the specified partitions
    def has_partition:
        . as $node |
        ($node.partitions // []) | any(. as $p | $partitions | any(. == $p));
    
    # Function to classify node type
    def get_node_type:
        . as $node |
        if ($node.gres // "") | test("gpu:") then
            # GPU node - extract type and count from gres field
            # Patterns: "gpu:h200:8(S:0-1)", "gpu:l40s:4", "gpu:1"
            ($node.gres | capture("gpu:(?<type>[a-zA-Z0-9]+):(?<count>[0-9]+)") // null) as $match |
            if $match != null then
                # Check if type is h200 or l40s
                if ($match.type | ascii_downcase) == "h200" then
                    "H200x" + $match.count
                elif ($match.type | ascii_downcase) == "l40s" then
                    "L40Sx" + $match.count
                else
                    # Unknown GPU type - skip or use generic
                    null
                end
            else
                # Pattern like "gpu:1" without type - skip
                null
            end
        else
            # CPU node - classify based on real_memory
            if ($node.real_memory // 0) >= 1000000 then
                "CPU_1500G"
            else
                "CPU_384G"
            end
        end;
    
    # Process all nodes
    .nodes[] |
    select(has_partition) |
    get_node_type as $type |
    select($type != null) |
    [$type, .name, "AVAILABLE", "true"] |
    @csv
' "$INPUT_FILE" | tr -d '"' >> "$OUTPUT_FILE"

# Count results
TOTAL_LINES=$(($(wc -l < "$OUTPUT_FILE") - 1))
GPU_COUNT=$(grep -c -E "^(H200|L40S)" "$OUTPUT_FILE" 2>/dev/null || echo 0)
CPU_COUNT=$(grep -c -E "^CPU_" "$OUTPUT_FILE" 2>/dev/null || echo 0)

echo "Wrote $TOTAL_LINES nodes to $OUTPUT_FILE"
echo "  GPU nodes: $GPU_COUNT"
echo "  CPU nodes: $CPU_COUNT"

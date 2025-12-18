#!/usr/bin/env python3
"""
Convert CSV node instance data to Django fixture JSON files.

This script reads a CSV file containing node instance definitions and generates
separate JSON fixture files for GPU and CPU node instances that can be loaded
into ColdFront Django using the loaddata command.

Usage:
    python csv_to_node_fixtures.py input.csv [--output-dir OUTPUT_DIR]

CSV Format:
    type,resource_address,status,rentable
    H200x8,gpu-h200x8-001,AVAILABLE,true
    CPU_384M,cpu-384m-001,AVAILABLE,true
"""

import argparse
import csv
import json
import sys
from pathlib import Path


# Known GPU and CPU node types (based on node_types fixture)
GPU_TYPES = {"H200x8", "H200x4", "H200x2", "H200x1", "L40Sx4", "L40Sx2", "L40Sx1"}
CPU_TYPES = {"CPU_384M", "CPU_1500T"}


def parse_bool(value: str) -> bool:
    """Parse a string value to boolean."""
    return value.lower() in ("true", "yes", "1", "t", "y")


def parse_status(value: str) -> str:
    """Parse and validate status value."""
    normalized = value.upper().strip()
    valid_statuses = {"AVAILABLE", "PLACEHOLDER"}
    if normalized not in valid_statuses:
        raise ValueError(f"Invalid status '{value}'. Must be one of: {valid_statuses}")
    return normalized


def get_node_category(node_type: str) -> str:
    """Determine if a node type is GPU or CPU."""
    if node_type in GPU_TYPES:
        return "GPU"
    elif node_type in CPU_TYPES:
        return "CPU"
    else:
        raise ValueError(
            f"Unknown node type '{node_type}'. "
            f"Valid GPU types: {GPU_TYPES}. Valid CPU types: {CPU_TYPES}"
        )


def create_fixture_entry(node_type: str, resource_address: str, status: str, is_rentable: bool, category: str) -> dict:
    """Create a single fixture entry for a node instance."""
    model_name = (
        "coldfront_orcd_direct_charge.gpunodeinstance"
        if category == "GPU"
        else "coldfront_orcd_direct_charge.cpunodeinstance"
    )
    
    return {
        "_comment": f"**{node_type} Node - {resource_address}**",
        "model": model_name,
        "fields": {
            "node_type": [node_type],  # Natural key format
            "is_rentable": is_rentable,
            "status": status,
            "associated_resource_address": resource_address
        }
    }


def read_csv_and_generate_fixtures(csv_path: Path) -> tuple[list[dict], list[dict]]:
    """Read CSV file and generate GPU and CPU fixture lists."""
    gpu_fixtures = []
    cpu_fixtures = []
    
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        # Try to detect the delimiter
        sample = csvfile.read(1024)
        csvfile.seek(0)
        
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=',\t')
        except csv.Error:
            dialect = csv.excel  # Default to comma-separated
        
        reader = csv.DictReader(csvfile, dialect=dialect)
        
        # Normalize header names (handle variations in spacing/case)
        if reader.fieldnames:
            normalized_fieldnames = []
            for field in reader.fieldnames:
                normalized = field.lower().strip().replace(' ', '_')
                normalized_fieldnames.append(normalized)
            reader.fieldnames = normalized_fieldnames
        
        required_fields = {'type', 'resource_address', 'status', 'rentable'}
        if not required_fields.issubset(set(reader.fieldnames or [])):
            # Also check for 'resource address' with space
            alt_fieldnames = {f.replace('_', ' ') for f in (reader.fieldnames or [])}
            if not required_fields.issubset(alt_fieldnames):
                raise ValueError(
                    f"CSV must contain columns: {required_fields}. "
                    f"Found: {reader.fieldnames}"
                )
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 to account for header
            try:
                node_type = row['type'].strip()
                resource_address = row['resource_address'].strip()
                status = parse_status(row['status'])
                is_rentable = parse_bool(row['rentable'])
                
                category = get_node_category(node_type)
                
                entry = create_fixture_entry(
                    node_type=node_type,
                    resource_address=resource_address,
                    status=status,
                    is_rentable=is_rentable,
                    category=category
                )
                
                if category == "GPU":
                    gpu_fixtures.append(entry)
                else:
                    cpu_fixtures.append(entry)
                    
            except (KeyError, ValueError) as e:
                print(f"Error on row {row_num}: {e}", file=sys.stderr)
                raise
    
    return gpu_fixtures, cpu_fixtures


def add_fixture_headers(fixtures: list[dict], fixture_type: str) -> list[dict]:
    """Add header comments to the first fixture entry."""
    if not fixtures:
        return fixtures
    
    type_upper = fixture_type.upper()
    type_lower = fixture_type.lower()
    
    # Add header comments to first entry
    first_entry = fixtures[0].copy()
    first_entry = {
        "_comment": f"**Django Fixture for ORCD Direct Charge plugin: {type_upper} Node Instance definitions**",
        "_comment_usage": f"**Load with: coldfront loaddata {type_lower}_node_instances**",
        "_comment_prereq": "**Requires node_types fixture to be loaded first**",
        **{k: v for k, v in first_entry.items() if not k.startswith('_comment')}
    }
    
    # Re-add the original comment as _comment_note
    original_comment = fixtures[0].get('_comment', '')
    if original_comment:
        first_entry['_comment_note'] = original_comment
    
    return [first_entry] + fixtures[1:]


def write_fixture_file(fixtures: list[dict], output_path: Path) -> None:
    """Write fixtures to a JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(fixtures, f, indent=2)
        f.write('\n')  # Add trailing newline
    print(f"Wrote {len(fixtures)} entries to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Convert CSV node instance data to Django fixture JSON files.',
        epilog='''
CSV Format:
  type,resource_address,status,rentable
  H200x8,gpu-h200x8-001,AVAILABLE,true
  CPU_384M,cpu-384m-001,PLACEHOLDER,false

Valid node types:
  GPU: H200x8, H200x4, H200x2, H200x1, L40Sx4, L40Sx2, L40Sx1
  CPU: CPU_384M, CPU_1500T

Valid status values: AVAILABLE, PLACEHOLDER
Valid rentable values: true, false, yes, no, 1, 0
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        'csv_file',
        type=Path,
        help='Path to the input CSV file'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        type=Path,
        default=None,
        help='Output directory for fixture files (default: same directory as CSV)'
    )
    
    parser.add_argument(
        '--gpu-output',
        type=str,
        default='gpu_node_instances.json',
        help='Filename for GPU fixtures (default: gpu_node_instances.json)'
    )
    
    parser.add_argument(
        '--cpu-output',
        type=str,
        default='cpu_node_instances.json',
        help='Filename for CPU fixtures (default: cpu_node_instances.json)'
    )
    
    args = parser.parse_args()
    
    if not args.csv_file.exists():
        print(f"Error: CSV file not found: {args.csv_file}", file=sys.stderr)
        sys.exit(1)
    
    output_dir = args.output_dir or args.csv_file.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        gpu_fixtures, cpu_fixtures = read_csv_and_generate_fixtures(args.csv_file)
        
        if gpu_fixtures:
            gpu_fixtures = add_fixture_headers(gpu_fixtures, "GPU")
            gpu_output_path = output_dir / args.gpu_output
            write_fixture_file(gpu_fixtures, gpu_output_path)
        else:
            print("No GPU node instances found in CSV")
        
        if cpu_fixtures:
            cpu_fixtures = add_fixture_headers(cpu_fixtures, "CPU")
            cpu_output_path = output_dir / args.cpu_output
            write_fixture_file(cpu_fixtures, cpu_output_path)
        else:
            print("No CPU node instances found in CSV")
        
        print(f"\nSummary: {len(gpu_fixtures)} GPU instances, {len(cpu_fixtures)} CPU instances")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

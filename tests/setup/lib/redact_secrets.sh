#!/usr/bin/env bash
#
# Redact sensitive token values from output files before publishing.
#
# Usage: redact_secrets.sh [output_dir]
#
# This script replaces actual API token values with "XXXX" in:
#   - JSON files containing "token" keys
#   - TSV files with token columns
#
# Run this before pushing artifacts to public branches to prevent
# secret detection tools (e.g., Git Guardian) from flagging tokens.
#
set -euo pipefail

OUTPUT_DIR="${1:-.}"

if [ ! -d "$OUTPUT_DIR" ]; then
    echo "Error: Directory not found: $OUTPUT_DIR"
    exit 1
fi

echo "Redacting secrets in: $OUTPUT_DIR"

# Redact tokens in JSON files
# Handles both flat objects and arrays of objects with "token" keys
json_files=$(find "$OUTPUT_DIR" -name "*.json" -type f 2>/dev/null || true)

if [ -n "$json_files" ]; then
    echo "$json_files" | while read -r json_file; do
        if [ -f "$json_file" ]; then
            python3 -c "
import json
import sys

path = sys.argv[1]
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    def redact(obj):
        if isinstance(obj, dict):
            return {k: 'XXXX' if k == 'token' else redact(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [redact(x) for x in obj]
        return obj

    redacted = redact(data)

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(redacted, f, indent=4)

    print(f'  Redacted: {path}')
except json.JSONDecodeError:
    print(f'  Skipped (not valid JSON): {path}')
except Exception as e:
    print(f'  Error processing {path}: {e}')
" "$json_file"
        fi
    done
fi

# Redact tokens in TSV files (format: username<tab>token)
# Matches hex tokens of 32+ characters
tsv_files=$(find "$OUTPUT_DIR" -name "*.tsv" -type f 2>/dev/null || true)

if [ -n "$tsv_files" ]; then
    echo "$tsv_files" | while read -r tsv_file; do
        if [ -f "$tsv_file" ]; then
            # Use a temp file for portability (BSD sed vs GNU sed)
            tmp_file="${tsv_file}.tmp"
            sed 's/\t[a-f0-9]\{32,\}$/\tXXXX/' "$tsv_file" > "$tmp_file"
            mv "$tmp_file" "$tsv_file"
            echo "  Redacted: $tsv_file"
        fi
    done
fi

echo "Redaction complete."

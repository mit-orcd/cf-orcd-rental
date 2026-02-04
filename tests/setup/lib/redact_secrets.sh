#!/usr/bin/env bash
#
# Redact sensitive token values from output files before publishing.
#
# Usage: redact_secrets.sh [output_dir]
#
# This script replaces actual API token values with "XXXX" in:
#   - JSON files containing "token" keys
#   - TSV files with token columns
#   - Log/text files with "API Token:" patterns (extensible)
#
# Run this before pushing artifacts to public branches to prevent
# secret detection tools (e.g., Git Guardian) from flagging tokens.
#
set -euo pipefail

OUTPUT_DIR="${1:-.}"

# =============================================================================
# Redaction Patterns for Text Files (log, txt, etc.)
# =============================================================================
# Each pattern is a sed substitution expression using extended regex (-E).
# Format: 's/PATTERN/REPLACEMENT/'
#
# To add new patterns, simply append to this array.
# Patterns are applied in order to all .log and .txt files.
# =============================================================================

TEXT_REDACT_PATTERNS=(
    # API Token: <40-char hex> -> API Token: XXXX
    's/(API Token: )[a-f0-9]{32,}/\1XXXX/g'
    
    # Generated token <40-char hex> -> Generated ... XXXX
    # Handles lines like: "Generated new API token for 'user'\nAPI Token: abc123..."
    's/(token[^a-f0-9]{0,20})[a-f0-9]{32,}/\1XXXX/gi'
)

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

# =============================================================================
# Redact patterns in text files (log, txt, etc.)
# =============================================================================
# Uses the extensible TEXT_REDACT_PATTERNS array defined above.
# Each pattern is applied using sed with extended regex (-E).
# =============================================================================

text_files=$(find "$OUTPUT_DIR" \( -name "*.log" -o -name "*.txt" \) -type f 2>/dev/null || true)

if [ -n "$text_files" ]; then
    echo "$text_files" | while read -r text_file; do
        if [ -f "$text_file" ]; then
            tmp_file="${text_file}.tmp"
            cp "$text_file" "$tmp_file"
            
            # Apply each pattern from the extensible array
            for pattern in "${TEXT_REDACT_PATTERNS[@]}"; do
                # Use sed -E for extended regex (portable across BSD and GNU sed)
                # Write to temp file, then rename for portability
                sed -E "$pattern" "$tmp_file" > "${tmp_file}.sed"
                mv "${tmp_file}.sed" "$tmp_file"
            done
            
            mv "$tmp_file" "$text_file"
            echo "  Redacted: $text_file"
        fi
    done
fi

echo "Redaction complete."

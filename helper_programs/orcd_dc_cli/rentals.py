#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""CLI for querying ColdFront Rentals API."""

import argparse
import json
import os
import sys

try:
    import requests
except ImportError:
    print("Error: 'requests' library is required. Install with: pip install requests")
    sys.exit(1)


def format_table(reservations):
    """Format reservations as a text table."""
    if not reservations:
        print("No reservations found.")
        return

    # Define columns
    headers = ["ID", "Node", "Project", "User", "Start Date", "Hours", "Status"]
    
    # Calculate column widths
    widths = [len(h) for h in headers]
    rows = []
    for r in reservations:
        row = [
            str(r.get("id", "")),
            r.get("node", "")[:20],
            r.get("project", "")[:25],
            r.get("requesting_user", "")[:15],
            r.get("start_date", ""),
            str(r.get("billable_hours", "")),
            r.get("status", ""),
        ]
        rows.append(row)
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(val))

    # Print header
    header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(header_line)
    print("-" * len(header_line))

    # Print rows
    for row in rows:
        print(" | ".join(val.ljust(widths[i]) for i, val in enumerate(row)))


def main():
    parser = argparse.ArgumentParser(
        description="Query ColdFront Rentals API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python rentals.py                           # List all rentals
  python rentals.py --status PENDING          # List pending rentals
  python rentals.py --node holygpu8a19101     # Filter by node
  python rentals.py --format table            # Output as table
  python rentals.py | jq '.[].status'         # Pipe to jq
        """,
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("COLDFRONT_URL", "http://localhost:8000"),
        help="ColdFront base URL (default: $COLDFRONT_URL or http://localhost:8000)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("COLDFRONT_API_TOKEN"),
        help="API token (default: $COLDFRONT_API_TOKEN)",
    )
    parser.add_argument(
        "--status",
        choices=["ANY", "PENDING", "APPROVED", "DECLINED", "CANCELLED"],
        default="ANY",
        help="Filter by status (default: ANY = show all)",
    )
    parser.add_argument(
        "--node",
        help="Filter by node address",
    )
    parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="json",
        help="Output format (default: json)",
    )

    args = parser.parse_args()

    # Validate token
    if not args.token:
        print("Error: API token required. Set COLDFRONT_API_TOKEN or use --token", file=sys.stderr)
        sys.exit(1)

    # Build query params
    params = {}
    if args.status != "ANY":
        params["status"] = args.status
    if args.node:
        params["node"] = args.node

    # Build URL
    api_url = f"{args.url.rstrip('/')}/nodes/api/rentals/"

    # Make API request
    headers = {"Authorization": f"Token {args.token}"}

    try:
        response = requests.get(api_url, headers=headers, params=params, timeout=30)
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to {args.url}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("Error: Request timed out", file=sys.stderr)
        sys.exit(1)

    # Handle response
    if response.status_code == 401:
        print("Error: Authentication failed. Check your API token.", file=sys.stderr)
        sys.exit(1)
    elif response.status_code == 403:
        print("Error: Permission denied. User needs 'can_manage_rentals' permission.", file=sys.stderr)
        sys.exit(1)
    elif response.status_code != 200:
        print(f"Error: API returned status {response.status_code}", file=sys.stderr)
        try:
            print(response.json(), file=sys.stderr)
        except Exception:
            print(response.text, file=sys.stderr)
        sys.exit(1)

    # Parse response
    try:
        data = response.json()
    except json.JSONDecodeError:
        print("Error: Invalid JSON response from API", file=sys.stderr)
        sys.exit(1)

    # Output
    if args.format == "json":
        print(json.dumps(data, indent=2))
    else:
        format_table(data)


if __name__ == "__main__":
    main()

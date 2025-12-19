# ORCD Direct Charge CLI

Command-line tools for interacting with the ColdFront ORCD Direct Charge plugin API.

## Prerequisites

1. The ColdFront API plugin must be enabled:
   ```bash
   export PLUGIN_API=True
   ```

2. Generate an API token for your user:
   ```bash
   export PLUGIN_API=True; DEBUG=True python manage.py drf_create_token <username>
   ```

3. Set the token as an environment variable:
   ```bash
   export COLDFRONT_API_TOKEN="your_token_here"
   ```

4. Install the `requests` library (if not already installed):
   ```bash
   pip install requests
   ```

## rentals.py - Query Rental Reservations

Query and filter reservation data from the ColdFront Rentals API.

### Usage

```bash
python rentals.py [OPTIONS]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--url` | ColdFront base URL | `http://localhost:8000` or `$COLDFRONT_URL` |
| `--token` | API token | `$COLDFRONT_API_TOKEN` |
| `--status` | Filter by status: `ANY`, `PENDING`, `APPROVED`, `DECLINED`, `CANCELLED` | `ANY` |
| `--node` | Filter by node address | None |
| `--format` | Output format: `json` or `table` | `json` |

### Examples

```bash
# List ALL rentals (default)
python rentals.py

# List only pending rentals
python rentals.py --status PENDING

# List approved rentals for a specific node
python rentals.py --status APPROVED --node holygpu8a19101

# Output as formatted table
python rentals.py --format table

# Use a different server
python rentals.py --url https://coldfront.example.com

# Pipe to jq for custom processing
python rentals.py | jq '.[] | select(.billable_hours > 24)'
```

### Output

JSON output includes the following fields for each reservation:

```json
{
  "id": 1,
  "node": "holygpu8a19101",
  "node_type": "H200x8",
  "project": "Research Project A",
  "requesting_user": "jsmith",
  "start_date": "2025-01-15",
  "start_datetime": "2025-01-15T16:00:00",
  "end_datetime": "2025-01-16T04:00:00",
  "num_blocks": 1,
  "billable_hours": 12,
  "status": "PENDING",
  "manager_notes": "",
  "created": "2025-01-10T14:30:00Z",
  "modified": "2025-01-10T14:30:00Z"
}
```

## API Endpoint

The CLI queries the rentals API at:
```
GET /nodes/api/rentals/
```

This endpoint requires:
- Valid API token authentication
- `can_manage_rentals` permission

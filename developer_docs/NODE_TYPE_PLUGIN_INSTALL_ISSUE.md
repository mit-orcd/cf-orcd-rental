# NodeType to RentalSKU Synchronization

## Overview

The `coldfront-orcd-direct-charge` plugin automatically synchronizes `NodeType` records with `RentalSKU` records. This ensures that the Rates tab correctly displays all available node types.

## How It Works

### Automatic Synchronization (Signal Handler)

When a `NodeType` record is created or updated (including via `loaddata` fixtures), a Django signal handler automatically:

1. **Creates a new RentalSKU** if one doesn't exist for the NodeType
2. **Updates the existing RentalSKU** if the NodeType changes (name, description, is_active)
3. **Creates an initial placeholder rate** of $0.01/hour for new SKUs with `effective_date = 1999-01-01` (the sentinel date -- see [Placeholder Rates and the Sentinel Date](RATE_MANAGER.md#placeholder-rates-and-the-sentinel-date))

The signal handler is defined in `signals.py`:
- `sync_nodetype_to_sku()` - Handles NodeType post_save signals
- `connect_nodetype_sku_signals()` - Connects the signal in `apps.py`

### SKU Code Stability

The `sku_code` (e.g., `NODE_H200x8`) is based on the NodeType name at creation time and is **not changed** if the NodeType is renamed. This preserves billing history references. However, the display name and linked_model are updated to reflect the current NodeType name.

### Metadata Sync

The signal handler copies metadata from NodeType to RentalSKU:
- `category` - GPU or CPU
- `node_type_name` - Current name of the NodeType

## Manual Synchronization

For existing deployments or to verify synchronization, use the management command:

```bash
# Sync all active NodeTypes (creates missing SKUs, updates existing)
coldfront sync_node_skus

# Include inactive NodeTypes
coldfront sync_node_skus --all

# Preview what would be done without making changes
coldfront sync_node_skus --dry-run
```

## Installation Order (No Longer Critical)

With automatic synchronization, the installation order is no longer critical:

1. Run all migrations: `coldfront migrate`
2. Load fixtures: `coldfront loaddata node_types.json` (triggers automatic SKU creation)
3. Verify: `coldfront sync_node_skus --dry-run` (should show all SKUs as "already synced")

The Rates tab will automatically display all NodeTypes that have been loaded.

## Troubleshooting

### Rates Tab Shows "No node SKUs configured"

If you see this after loading NodeType fixtures:

1. **Verify NodeTypes exist:**
   ```python
   from coldfront_orcd_direct_charge.models import NodeType
   print(NodeType.objects.filter(is_active=True).count())
   ```

2. **Run manual sync:**
   ```bash
   coldfront sync_node_skus
   ```

3. **Check RentalSKU records:**
   ```python
   from coldfront_orcd_direct_charge.models import RentalSKU
   print(RentalSKU.objects.filter(sku_type='NODE').count())
   ```

### SKUs Have Placeholder Rates

New SKUs are created with $0.01/hour placeholder rates and an `effective_date` of `1999-01-01` (the sentinel date). This sentinel date ensures that any real rate you set -- even with a retroactive effective date -- will always take precedence over the placeholder.

To set actual rates:
1. Log in as a Rate Manager
2. Go to Project → Manage Rates
3. Select each SKU and add the correct rate
4. Or use the `set_sku_rate` management command (see [RATE_MANAGER.md](RATE_MANAGER.md#management-commands))

## Historical Context

Prior to this fix, `RentalSKU` records were only created during migration 0022. If `NodeType` fixtures were loaded after the migration ran, no SKUs would be created, causing the Rates tab to appear empty.

The automatic synchronization via signals resolves this issue permanently.

## Related Files

- `coldfront_orcd_direct_charge/signals.py` - Signal handler for sync
- `coldfront_orcd_direct_charge/apps.py` - Signal connection
- `coldfront_orcd_direct_charge/management/commands/sync_node_skus.py` - Manual sync command
- `coldfront_orcd_direct_charge/models.py` - NodeType and RentalSKU models
- `coldfront_orcd_direct_charge/migrations/0022_rentalsku_rentalrate.py` - Original migration (still runs but sync ensures completeness)

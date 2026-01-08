# Node SKUs Missing After Plugin Installation

## Problem Summary

When deploying the `coldfront-orcd-direct-charge` plugin to a new environment, the **Node Rentals** section on the Rate Management page may show "No node SKUs configured" even though NodeType records exist in the database.

## Root Cause

The migration `0022_rentalsku_rentalrate.py` creates `RentalSKU` records for nodes by iterating over existing `NodeType` records **at the time the migration runs**:

```python
# From migration 0022
for node_type in NodeType.objects.filter(is_active=True):
    sku = RentalSKU.objects.create(
        sku_code=f"NODE_{node_type.name}",
        ...
    )
```

If the NodeType fixtures are loaded **after** the migration has already completed, no node SKUs will be created. The migration only runs once.

**Typical problematic sequence:**
1. Run `python manage.py migrate` → Migration 0022 runs, finds no NodeTypes, creates only maintenance fee SKUs
2. Run `python manage.py loaddata node_types.json` → NodeTypes now exist
3. Node SKUs were never created because the migration already completed

## Diagnosis

Check the database to verify the issue:

```bash
python -c "
import sqlite3
conn = sqlite3.connect('coldfront.db')
cursor = conn.cursor()

print('=== NodeType records ===')
cursor.execute('SELECT name, is_active FROM coldfront_orcd_direct_charge_nodetype')
rows = cursor.fetchall()
for row in rows:
    print(f'  {row[0]}: is_active={row[1]}')

print()
print('=== RentalSKU records ===')
cursor.execute('SELECT sku_code, name, sku_type FROM coldfront_orcd_direct_charge_rentalsku')
rows = cursor.fetchall()
for row in rows:
    print(f'  {row[0]}: {row[1]} (type={row[2]}')

conn.close()
"
```

**If you see NodeType records but no NODE-type RentalSKU records, this confirms the issue.**

## Solution

### Option 1: Manual Database Fix (for existing deployments)

Run this Python script to create the missing node SKUs:

```python
import sqlite3
from datetime import date

conn = sqlite3.connect('coldfront.db')
cursor = conn.cursor()

today = date.today().isoformat()
placeholder_rate = '0.01'

# Get all active NodeTypes
cursor.execute('SELECT name, description FROM coldfront_orcd_direct_charge_nodetype WHERE is_active = 1')
node_types = cursor.fetchall()

print('Creating node SKUs...')
for name, description in node_types:
    sku_code = f'NODE_{name}'
    sku_name = f'{name} Node'
    
    # Check if already exists
    cursor.execute('SELECT id FROM coldfront_orcd_direct_charge_rentalsku WHERE sku_code = ?', (sku_code,))
    if cursor.fetchone():
        print(f'  {sku_code} already exists, skipping')
        continue
    
    # Insert the SKU
    cursor.execute('''
        INSERT INTO coldfront_orcd_direct_charge_rentalsku 
        (created, modified, sku_code, name, description, sku_type, billing_unit, is_active, linked_model, is_public, metadata)
        VALUES (datetime('now'), datetime('now'), ?, ?, ?, 'NODE', 'HOURLY', 1, ?, 1, '{}')
    ''', (sku_code, sku_name, description or '', f'NodeType:{name}'))
    
    sku_id = cursor.lastrowid
    
    # Insert the initial rate
    cursor.execute('''
        INSERT INTO coldfront_orcd_direct_charge_rentalrate
        (created, modified, rate, effective_date, notes, set_by_id, sku_id)
        VALUES (datetime('now'), datetime('now'), ?, ?, 'Initial placeholder rate', NULL, ?)
    ''', (placeholder_rate, today, sku_id))
    
    print(f'  Created {sku_code} with $0.01 placeholder rate')

conn.commit()
conn.close()
print('Done!')
```

### Option 2: Correct Installation Order (for new deployments)

When setting up a new environment, ensure fixtures are loaded **before** running migrations:

```bash
# 1. Run migrations up to (but not including) 0022
python manage.py migrate coldfront_orcd_direct_charge 0021

# 2. Load NodeType fixtures
python manage.py loaddata coldfront_orcd_direct_charge/fixtures/node_types.json

# 3. Run remaining migrations (including 0022 which creates SKUs)
python manage.py migrate coldfront_orcd_direct_charge
```

### Option 3: Use Django Admin

If you have access to Django Admin:
1. Navigate to Admin → Rental SKUs
2. Manually create RentalSKU records for each NodeType
3. Create corresponding RentalRate records

## Prevention

For future deployments, consider:
1. Documenting the correct installation order in the README
2. Creating a management command that syncs NodeTypes to RentalSKUs
3. Adding a post-fixture-load hook that creates missing SKUs

## Related Files

- Migration: `coldfront_orcd_direct_charge/migrations/0022_rentalsku_rentalrate.py`
- Models: `coldfront_orcd_direct_charge/models.py` (RentalSKU, RentalRate, NodeType)
- Fixtures: `coldfront_orcd_direct_charge/fixtures/node_types.json`

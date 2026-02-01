# Maintenance Windows

## Purpose

Maintenance windows allow rental managers to define scheduled maintenance periods 
during which **node rentals are not billed**. This feature ensures researchers 
are not charged for time when nodes are unavailable due to planned maintenance.

## How It Works

- Rentals can extend through maintenance windows without interruption
- Billable hours are automatically reduced to exclude any overlap with maintenance periods
- The adjustment appears on invoices showing original hours and maintenance deductions

## When to Use

Create a maintenance window when:
- Scheduled system maintenance will make nodes unavailable
- Emergency maintenance requires taking nodes offline
- Planned upgrades or infrastructure work affects node availability

## Billing Impact

**Example:** A rental spans Feb 14-16 (41 hours total). A maintenance window 
covers Feb 15 8AM-8PM (12 hours). The invoice will show:
- Original hours: 41
- Maintenance deduction: 12  
- Billable hours: 29

## Important Notes

- Maintenance windows apply system-wide to all nodes
- Only future maintenance windows can be edited or deleted via this page
- Past and in-progress windows are locked to preserve billing accuracy
- For corrections to past windows, contact a system administrator

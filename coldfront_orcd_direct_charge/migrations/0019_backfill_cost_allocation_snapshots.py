# Generated manually for data migration
# Backfills CostAllocationSnapshot for all currently-approved ProjectCostAllocation records

from django.db import migrations


def backfill_snapshots(apps, schema_editor):
    """Create snapshots for all existing approved cost allocations."""
    ProjectCostAllocation = apps.get_model('coldfront_orcd_direct_charge', 'ProjectCostAllocation')
    CostAllocationSnapshot = apps.get_model('coldfront_orcd_direct_charge', 'CostAllocationSnapshot')
    CostObjectSnapshot = apps.get_model('coldfront_orcd_direct_charge', 'CostObjectSnapshot')

    # Get all approved allocations
    approved_allocations = ProjectCostAllocation.objects.filter(status='APPROVED')

    for allocation in approved_allocations:
        # Create snapshot using the reviewed_at timestamp (or modified if not set)
        approved_at = allocation.reviewed_at or allocation.modified

        snapshot = CostAllocationSnapshot.objects.create(
            allocation=allocation,
            approved_at=approved_at,
            approved_by=allocation.reviewed_by,
            superseded_at=None,  # Current snapshot
        )

        # Copy all cost objects to the snapshot
        for cost_object in allocation.cost_objects.all():
            CostObjectSnapshot.objects.create(
                snapshot=snapshot,
                cost_object=cost_object.cost_object,
                percentage=cost_object.percentage,
            )


def reverse_backfill(apps, schema_editor):
    """Remove all backfilled snapshots."""
    CostAllocationSnapshot = apps.get_model('coldfront_orcd_direct_charge', 'CostAllocationSnapshot')
    # Delete all snapshots - this will cascade to CostObjectSnapshot
    CostAllocationSnapshot.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('coldfront_orcd_direct_charge', '0018_costallocationsnapshot_invoiceperiod_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_snapshots, reverse_backfill),
    ]

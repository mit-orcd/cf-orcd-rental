# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Management command to synchronize RentalSKUs with NodeTypes.

This command creates missing RentalSKU records for NodeTypes that don't
have corresponding SKUs. This is useful for:
- Initial setup after loading NodeType fixtures
- Recovering from migration issues where SKUs weren't created
- Verifying SKU/NodeType consistency

Usage:
    coldfront sync_node_skus           # Sync all active NodeTypes
    coldfront sync_node_skus --all     # Include inactive NodeTypes
    coldfront sync_node_skus --dry-run # Show what would be done
"""

from decimal import Decimal

from django.core.management.base import BaseCommand

from coldfront_orcd_direct_charge.models import (
    NodeType,
    PLACEHOLDER_RATE_AMOUNT,
    PLACEHOLDER_RATE_DATE,
    RentalRate,
    RentalSKU,
)


class Command(BaseCommand):
    help = "Synchronize RentalSKUs with NodeTypes (creates missing SKUs)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Include inactive NodeTypes (default: only active)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )

    def handle(self, *args, **options):
        include_inactive = options["all"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made\n"))

        # Get NodeTypes to sync
        if include_inactive:
            node_types = NodeType.objects.all()
            self.stdout.write(f"Checking all {node_types.count()} NodeTypes...")
        else:
            node_types = NodeType.objects.filter(is_active=True)
            self.stdout.write(f"Checking {node_types.count()} active NodeTypes...")

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for node_type in node_types:
            sku_code = f"NODE_{node_type.name}"
            linked_model = f"NodeType:{node_type.name}"

            # Check if SKU already exists
            existing_sku = RentalSKU.objects.filter(sku_code=sku_code).first()

            # Build metadata
            metadata = {
                "category": node_type.category,
                "node_type_name": node_type.name,
            }

            if existing_sku:
                # Check if update is needed
                needs_update = (
                    existing_sku.name != f"{node_type.name} Node"
                    or existing_sku.description != (node_type.description or "")
                    or existing_sku.is_active != node_type.is_active
                    or existing_sku.linked_model != linked_model
                )

                if needs_update:
                    if not dry_run:
                        existing_sku.name = f"{node_type.name} Node"
                        existing_sku.description = node_type.description or ""
                        existing_sku.is_active = node_type.is_active
                        existing_sku.linked_model = linked_model
                        if existing_sku.metadata:
                            existing_sku.metadata.update(metadata)
                        else:
                            existing_sku.metadata = metadata
                        existing_sku.save()
                    self.stdout.write(
                        f"  Updated: {sku_code} (NodeType: {node_type.name})"
                    )
                    updated_count += 1
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f"  OK: {sku_code} (already synced)")
                    )
                    skipped_count += 1
            else:
                # Create new SKU
                if not dry_run:
                    sku = RentalSKU.objects.create(
                        sku_code=sku_code,
                        name=f"{node_type.name} Node",
                        description=node_type.description or "",
                        sku_type=RentalSKU.SKUType.NODE,
                        billing_unit=RentalSKU.BillingUnit.HOURLY,
                        is_active=node_type.is_active,
                        linked_model=linked_model,
                        is_public=True,
                        metadata=metadata,
                    )

                    # Create initial placeholder rate with sentinel date
                    # (1999-01-01) so any real rate always takes precedence
                    RentalRate.objects.create(
                        sku=sku,
                        rate=PLACEHOLDER_RATE_AMOUNT,
                        effective_date=PLACEHOLDER_RATE_DATE,
                        notes="Initial placeholder rate (created by sync_node_skus)",
                    )

                self.stdout.write(
                    self.style.SUCCESS(f"  Created: {sku_code} (NodeType: {node_type.name})")
                )
                created_count += 1

        # Summary
        self.stdout.write("")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN SUMMARY:"))
            self.stdout.write(f"  Would create: {created_count}")
            self.stdout.write(f"  Would update: {updated_count}")
            self.stdout.write(f"  Already synced: {skipped_count}")
        else:
            self.stdout.write(self.style.SUCCESS("SYNC COMPLETE:"))
            self.stdout.write(f"  Created: {created_count}")
            self.stdout.write(f"  Updated: {updated_count}")
            self.stdout.write(f"  Already synced: {skipped_count}")

        if created_count > 0 and not dry_run:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "Note: New SKUs have placeholder rates of $0.01. "
                    "Use Rate Management to set actual rates."
                )
            )

# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Django management command to set a rate on a RentalSKU.

Sets the rate amount and optionally the visibility (is_public) for a
RentalSKU identified by its sku_code.  The effective_date can be any
date (past or future) -- there is no restriction.

Examples:
    # Set an hourly rate effective today
    coldfront set_sku_rate NODE_H200x8 8.00

    # Set a rate with a specific effective date (including past dates)
    coldfront set_sku_rate NODE_H200x8 8.00 --effective-date 2025-01-01

    # Set rate and make the SKU visible on the public rates page
    coldfront set_sku_rate NODE_H200x8 8.00 --visibility public

    # Set rate and hide the SKU from the public rates page
    coldfront set_sku_rate NODE_H200x8 8.00 --visibility private

    # Record who set the rate
    coldfront set_sku_rate NODE_H200x8 8.00 --set-by rate_manager

    # Replace an existing rate on the same date
    coldfront set_sku_rate NODE_H200x8 8.00 --effective-date 2025-01-01 --force

    # Preview changes without applying
    coldfront set_sku_rate NODE_H200x8 8.00 --dry-run
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from coldfront_orcd_direct_charge.models import (
    RentalRate,
    RentalSKU,
)


class Command(BaseCommand):
    help = "Set a rate on a RentalSKU"

    def add_arguments(self, parser):
        # Required positional arguments
        parser.add_argument(
            "sku_code",
            type=str,
            help="SKU code (e.g., 'NODE_H200x8', 'MAINT_BASIC')",
        )
        parser.add_argument(
            "rate",
            type=str,
            help="Rate amount as a decimal (e.g., '8.00')",
        )

        # Optional arguments
        parser.add_argument(
            "--effective-date",
            type=str,
            dest="effective_date",
            default=None,
            help=(
                "Date when this rate becomes effective (YYYY-MM-DD). "
                "Defaults to today. Accepts any date including past dates."
            ),
        )
        parser.add_argument(
            "--notes",
            type=str,
            default="",
            help="Optional notes about this rate change",
        )
        parser.add_argument(
            "--set-by",
            type=str,
            dest="set_by",
            default=None,
            help="Username of the rate manager who set this rate",
        )
        parser.add_argument(
            "--visibility",
            type=str,
            choices=["public", "private"],
            default=None,
            help=(
                "Set SKU visibility on the Current Rates page. "
                "'public' makes it visible, 'private' hides it. "
                "If omitted, visibility is left unchanged."
            ),
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Replace existing rate on the same effective date",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show the Django ORM commands that would be executed without making changes",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress non-essential output",
        )

    def handle(self, *args, **options):
        sku_code = options["sku_code"]
        rate_str = options["rate"]
        effective_date_str = options["effective_date"]
        notes = options["notes"]
        set_by_username = options["set_by"]
        visibility = options["visibility"]
        force = options["force"]
        dry_run = options["dry_run"]
        quiet = options["quiet"]

        # -----------------------------------------------------------------
        # Validate rate amount
        # -----------------------------------------------------------------
        try:
            rate_amount = Decimal(rate_str)
        except InvalidOperation:
            self.stdout.write(self.style.ERROR(
                f"Invalid rate amount '{rate_str}'. Must be a decimal number."
            ))
            return

        if rate_amount < 0:
            self.stdout.write(self.style.ERROR(
                f"Rate amount must be non-negative, got {rate_amount}"
            ))
            return

        # -----------------------------------------------------------------
        # Parse effective date
        # -----------------------------------------------------------------
        if effective_date_str:
            try:
                effective_date = datetime.strptime(effective_date_str, "%Y-%m-%d").date()
            except ValueError:
                self.stdout.write(self.style.ERROR(
                    f"Invalid date format '{effective_date_str}'. Expected YYYY-MM-DD."
                ))
                return
        else:
            effective_date = date.today()

        # -----------------------------------------------------------------
        # Look up SKU
        # -----------------------------------------------------------------
        sku = self._find_sku(sku_code)
        if not sku:
            return

        # -----------------------------------------------------------------
        # Look up set_by user if provided
        # -----------------------------------------------------------------
        set_by_user = None
        if set_by_username:
            set_by_user = self._find_user(set_by_username)
            if not set_by_user:
                return

        # -----------------------------------------------------------------
        # Check for existing rate on the same date
        # -----------------------------------------------------------------
        existing_rate = RentalRate.objects.filter(
            sku=sku,
            effective_date=effective_date,
        ).first()

        if existing_rate and not force:
            self.stdout.write(self.style.ERROR(
                f"A rate already exists for SKU '{sku_code}' on {effective_date} "
                f"(${existing_rate.rate}). Use --force to replace."
            ))
            return

        # -----------------------------------------------------------------
        # Dry-run mode
        # -----------------------------------------------------------------
        if dry_run:
            self._print_dry_run(
                sku=sku,
                rate_amount=rate_amount,
                effective_date=effective_date,
                notes=notes,
                set_by_user=set_by_user,
                visibility=visibility,
                existing_rate=existing_rate,
            )
            return

        # -----------------------------------------------------------------
        # Create or replace rate
        # -----------------------------------------------------------------
        if existing_rate:
            existing_rate.rate = rate_amount
            existing_rate.notes = notes
            existing_rate.set_by = set_by_user
            existing_rate.save()
            if not quiet:
                self.stdout.write(self.style.SUCCESS(
                    f"Updated existing rate on {effective_date}: "
                    f"${existing_rate.rate} -> ${rate_amount}"
                ))
        else:
            RentalRate.objects.create(
                sku=sku,
                rate=rate_amount,
                effective_date=effective_date,
                notes=notes,
                set_by=set_by_user,
            )
            if not quiet:
                self.stdout.write(self.style.SUCCESS(
                    f"Created rate ${rate_amount} effective {effective_date}"
                ))

        # -----------------------------------------------------------------
        # Update visibility if requested
        # -----------------------------------------------------------------
        if visibility is not None:
            new_is_public = visibility == "public"
            old_is_public = sku.is_public
            if old_is_public != new_is_public:
                sku.is_public = new_is_public
                sku.save(update_fields=["is_public", "modified"])
                if not quiet:
                    label = "public" if new_is_public else "private"
                    self.stdout.write(self.style.SUCCESS(
                        f"Set SKU visibility to {label}"
                    ))
            elif not quiet:
                label = "public" if new_is_public else "private"
                self.stdout.write(f"SKU visibility already {label} (no change)")

        # -----------------------------------------------------------------
        # Summary
        # -----------------------------------------------------------------
        if not quiet:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Rate set successfully."))
            self.stdout.write(f"  SKU: {sku.sku_code} ({sku.name})")
            self.stdout.write(f"  Rate: ${rate_amount}")
            self.stdout.write(f"  Effective date: {effective_date}")
            self.stdout.write(f"  Billing unit: {sku.billing_unit}")
            if set_by_user:
                self.stdout.write(f"  Set by: {set_by_user.username}")
            if notes:
                self.stdout.write(f"  Notes: {notes}")
            if visibility is not None:
                self.stdout.write(f"  Visibility: {visibility}")

    def _find_sku(self, sku_code):
        """Find a RentalSKU by sku_code.

        Returns:
            RentalSKU instance or None if not found.
        """
        try:
            return RentalSKU.objects.get(sku_code=sku_code)
        except RentalSKU.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"SKU '{sku_code}' not found. "
                "Run 'coldfront sync_node_skus' to create missing SKUs."
            ))
            return None

    def _find_user(self, username):
        """Find a user by username.

        Returns:
            User instance or None if not found.
        """
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"User '{username}' not found"
            ))
            return None

    def _print_dry_run(self, sku, rate_amount, effective_date, notes,
                       set_by_user, visibility, existing_rate):
        """Print the Django ORM commands that would be executed."""
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(
            "[DRY-RUN] Would execute the following commands:"
        ))
        self.stdout.write("")

        set_by_repr = f"<User: {set_by_user.username}>" if set_by_user else "None"

        if existing_rate:
            self.stdout.write("# Update existing rate")
            self.stdout.write(
                f"rate = RentalRate.objects.get(sku=<SKU: {sku.sku_code}>, "
                f"effective_date={effective_date})"
            )
            self.stdout.write(f"rate.rate = Decimal('{rate_amount}')")
            self.stdout.write(f"rate.notes = '{notes}'")
            self.stdout.write(f"rate.set_by = {set_by_repr}")
            self.stdout.write("rate.save()")
        else:
            self.stdout.write("# Create new rate")
            self.stdout.write("RentalRate.objects.create(")
            self.stdout.write(f"    sku=<SKU: {sku.sku_code}>,")
            self.stdout.write(f"    rate=Decimal('{rate_amount}'),")
            self.stdout.write(f"    effective_date={effective_date},")
            self.stdout.write(f"    notes='{notes}',")
            self.stdout.write(f"    set_by={set_by_repr},")
            self.stdout.write(")")

        if visibility is not None:
            new_is_public = visibility == "public"
            self.stdout.write("")
            self.stdout.write("# Update SKU visibility")
            self.stdout.write(
                f"sku = RentalSKU.objects.get(sku_code='{sku.sku_code}')"
            )
            self.stdout.write(f"sku.is_public = {new_is_public}")
            self.stdout.write("sku.save()")

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("[DRY-RUN] No changes made."))

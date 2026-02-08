# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Data migration to backfill placeholder rate dates to the sentinel date.

Existing deployments created placeholder rates with effective_date set to
date.today() (the date the migration or sync command ran). This causes
problems when a real rate is later set with a retroactive effective_date
that is earlier than the placeholder's date -- the placeholder wins the
rate lookup in get_rate_for_date().

This migration updates all placeholder rates to use the fixed sentinel
date of 1999-01-01, which predates any possible real rate and ensures
real rates always take precedence.

Placeholder rates are identified by:
  - rate = $0.01
  - notes containing "placeholder" (case-insensitive)
  - effective_date != 1999-01-01 (already backfilled)
"""

from datetime import date
from decimal import Decimal

from django.db import migrations


def backfill_placeholder_dates(apps, schema_editor):
    """Update all placeholder rates to use the sentinel date 1999-01-01."""
    RentalRate = apps.get_model("coldfront_orcd_direct_charge", "RentalRate")

    sentinel = date(1999, 1, 1)
    updated = RentalRate.objects.filter(
        notes__icontains="placeholder",
        rate=Decimal("0.01"),
    ).exclude(
        effective_date=sentinel,
    ).update(
        effective_date=sentinel,
    )

    if updated:
        print(f"\n  Updated {updated} placeholder rate(s) to sentinel date {sentinel}")


def reverse_noop(apps, schema_editor):
    """No reverse operation -- cannot restore original dates."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("coldfront_orcd_direct_charge", "0027_maintenancewindow"),
    ]

    operations = [
        migrations.RunPython(backfill_placeholder_dates, reverse_noop),
    ]

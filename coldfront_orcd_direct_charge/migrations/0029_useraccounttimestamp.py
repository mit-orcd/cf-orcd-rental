# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Add UserAccountTimestamp model.

Tracks a ``last_modified`` datetime for every user account.  The companion
creation timestamp is the built-in ``User.date_joined`` field.
"""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("coldfront_orcd_direct_charge", "0028_backfill_placeholder_rate_dates"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserAccountTimestamp",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "last_modified",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        help_text="When the user account was last modified",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        help_text="The user this timestamp record belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="account_timestamp",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "User Account Timestamp",
                "verbose_name_plural": "User Account Timestamps",
            },
        ),
    ]

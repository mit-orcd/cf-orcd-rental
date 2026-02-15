# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Add end_date field to UserMaintenanceStatus.

Allows AMF subscriptions to have an explicit end date after which billing
stops.  Defaults to 2100-01-01 (effectively indefinite) so existing rows
retain their current billing behaviour.
"""

import datetime

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("coldfront_orcd_direct_charge", "0029_useraccounttimestamp"),
    ]

    operations = [
        migrations.AddField(
            model_name="usermaintenancestatus",
            name="end_date",
            field=models.DateField(
                default=datetime.date(2100, 1, 1),
                help_text=(
                    "Date after which AMF billing stops. "
                    "Defaults to 2100-01-01 (effectively indefinite)."
                ),
            ),
        ),
    ]

# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("coldfront_orcd_direct_charge", "0022_rentalsku_rentalrate"),
    ]

    operations = [
        migrations.AlterField(
            model_name="rentalrate",
            name="rate",
            field=models.DecimalField(
                decimal_places=6,
                help_text="Rate per billing unit (hourly or monthly)",
                max_digits=12,
            ),
        ),
    ]


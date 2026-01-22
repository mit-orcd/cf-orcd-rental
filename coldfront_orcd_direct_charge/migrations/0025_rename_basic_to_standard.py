# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from django.db import migrations


def rename_basic_to_standard(apps, schema_editor):
    """Rename Basic Account Maintenance Fee to Standard Account Maintenance Fee.
    
    Updates the SKU code, name, and description for the basic maintenance SKU
    to use "Standard" terminology instead of "Basic".
    """
    RentalSKU = apps.get_model("coldfront_orcd_direct_charge", "RentalSKU")
    
    RentalSKU.objects.filter(sku_code="MAINT_BASIC").update(
        sku_code="MAINT_STANDARD",
        name="Standard Account Maintenance Fee",
        description="Standard account maintenance subscription for rental services",
    )


def reverse_standard_to_basic(apps, schema_editor):
    """Revert Standard Account Maintenance Fee back to Basic."""
    RentalSKU = apps.get_model("coldfront_orcd_direct_charge", "RentalSKU")
    
    RentalSKU.objects.filter(sku_code="MAINT_STANDARD").update(
        sku_code="MAINT_BASIC",
        name="Basic Account Maintenance Fee",
        description="Basic account maintenance subscription for rental services",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("coldfront_orcd_direct_charge", "0024_rentalsku_metadata_visibility"),
    ]

    operations = [
        migrations.RunPython(
            rename_basic_to_standard,
            reverse_standard_to_basic,
        ),
    ]

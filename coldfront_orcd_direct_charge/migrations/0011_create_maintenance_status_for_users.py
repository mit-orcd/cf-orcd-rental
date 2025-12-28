# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Data migration to create UserMaintenanceStatus for all existing users.

Creates a maintenance status record with 'inactive' default for every user
that doesn't already have one.
"""

from django.db import migrations


def create_maintenance_status_for_users(apps, schema_editor):
    """Create UserMaintenanceStatus for all existing users."""
    User = apps.get_model("auth", "User")
    UserMaintenanceStatus = apps.get_model(
        "coldfront_orcd_direct_charge", "UserMaintenanceStatus"
    )

    created_count = 0
    for user in User.objects.all():
        _, created = UserMaintenanceStatus.objects.get_or_create(
            user=user,
            defaults={"status": "inactive"},
        )
        if created:
            created_count += 1

    if created_count:
        print(f"  Created {created_count} maintenance status record(s)")


def delete_maintenance_status_for_users(apps, schema_editor):
    """Delete all UserMaintenanceStatus records (reverse migration)."""
    UserMaintenanceStatus = apps.get_model(
        "coldfront_orcd_direct_charge", "UserMaintenanceStatus"
    )
    deleted_count, _ = UserMaintenanceStatus.objects.all().delete()
    if deleted_count:
        print(f"  Deleted {deleted_count} maintenance status record(s)")


class Migration(migrations.Migration):

    dependencies = [
        ("coldfront_orcd_direct_charge", "0010_usermaintenancestatus"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(
            create_maintenance_status_for_users,
            delete_maintenance_status_for_users,
        ),
    ]


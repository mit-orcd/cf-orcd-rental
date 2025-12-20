# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Data migration to delete old _default_project projects.

After migrating to _personal naming, this removes any remaining
USERNAME_default_project projects.
"""

from django.db import migrations


def delete_old_default_projects(apps, schema_editor):
    """Delete all _default_project projects."""
    Project = apps.get_model("project", "Project")
    deleted_count, _ = Project.objects.filter(title__endswith="_default_project").delete()
    if deleted_count:
        print(f"  Deleted {deleted_count} old _default_project project(s)")


def noop(apps, schema_editor):
    """No-op reverse migration - deleted projects cannot be restored."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("coldfront_orcd_direct_charge", "0007_rename_default_projects"),
    ]

    operations = [
        migrations.RunPython(delete_old_default_projects, noop),
    ]

# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Data migration to rename existing default projects.

Renames USERNAME_default_project to USERNAME_personal and updates descriptions.
"""

from django.db import migrations


def rename_default_projects(apps, schema_editor):
    """Rename all _default_project projects to _personal."""
    Project = apps.get_model("project", "Project")
    for project in Project.objects.filter(title__endswith="_default_project"):
        new_title = project.title.replace("_default_project", "_personal")
        # Skip if the new title already exists for this PI (avoid unique constraint violation)
        if Project.objects.filter(title=new_title, pi=project.pi).exists():
            continue
        project.title = new_title
        if project.description.startswith("Default project for"):
            project.description = project.description.replace(
                "Default project for", "Personal project for"
            )
        project.save()


def revert_rename(apps, schema_editor):
    """Revert _personal projects back to _default_project."""
    Project = apps.get_model("project", "Project")
    for project in Project.objects.filter(title__endswith="_personal"):
        new_title = project.title.replace("_personal", "_default_project")
        # Skip if the old title already exists for this PI (avoid unique constraint violation)
        if Project.objects.filter(title=new_title, pi=project.pi).exists():
            continue
        project.title = new_title
        if project.description.startswith("Personal project for"):
            project.description = project.description.replace(
                "Personal project for", "Default project for"
            )
        project.save()


class Migration(migrations.Migration):

    dependencies = [
        ("coldfront_orcd_direct_charge", "0006_migrate_metadata_to_entries"),
        ("project", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(rename_default_projects, revert_rename),
    ]


# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from django.db import migrations, models


def update_maintenance_sku_names(apps, schema_editor):
    """Update maintenance SKU names to use 'Account Maintenance Fee' terminology."""
    RentalSKU = apps.get_model("coldfront_orcd_direct_charge", "RentalSKU")
    
    # Update Basic Maintenance Fee
    RentalSKU.objects.filter(sku_code="MAINT_BASIC").update(
        name="Basic Account Maintenance Fee",
        description="Basic account maintenance subscription for rental services",
    )
    
    # Update Advanced Maintenance Fee
    RentalSKU.objects.filter(sku_code="MAINT_ADVANCED").update(
        name="Advanced Account Maintenance Fee",
        description="Advanced account maintenance subscription with priority support",
    )


def reverse_maintenance_sku_names(apps, schema_editor):
    """Revert maintenance SKU names."""
    RentalSKU = apps.get_model("coldfront_orcd_direct_charge", "RentalSKU")
    
    RentalSKU.objects.filter(sku_code="MAINT_BASIC").update(
        name="Basic Maintenance Fee",
        description="Basic account maintenance subscription",
    )
    
    RentalSKU.objects.filter(sku_code="MAINT_ADVANCED").update(
        name="Advanced Maintenance Fee",
        description="Advanced account maintenance subscription",
    )


def populate_node_metadata(apps, schema_editor):
    """Populate metadata for existing NODE SKUs based on their names."""
    RentalSKU = apps.get_model("coldfront_orcd_direct_charge", "RentalSKU")
    
    # Metadata templates for different node types
    node_metadata = {
        # H200 GPU nodes
        "NODE_H200x8": {
            "gpu_type": "NVIDIA H200",
            "gpu_count": 8,
            "gpu_memory_gb": 80,
            "system_memory_gb": 1500,
            "category": "GPU",
        },
        "NODE_H200x4": {
            "gpu_type": "NVIDIA H200",
            "gpu_count": 4,
            "gpu_memory_gb": 80,
            "system_memory_gb": 1500,
            "category": "GPU",
        },
        "NODE_H200x2": {
            "gpu_type": "NVIDIA H200",
            "gpu_count": 2,
            "gpu_memory_gb": 80,
            "system_memory_gb": 1500,
            "category": "GPU",
        },
        "NODE_H200x1": {
            "gpu_type": "NVIDIA H200",
            "gpu_count": 1,
            "gpu_memory_gb": 80,
            "system_memory_gb": 1500,
            "category": "GPU",
        },
        # L40S GPU nodes
        "NODE_L40Sx4": {
            "gpu_type": "NVIDIA L40S",
            "gpu_count": 4,
            "gpu_memory_gb": 48,
            "system_memory_gb": 384,
            "category": "GPU",
        },
        "NODE_L40Sx2": {
            "gpu_type": "NVIDIA L40S",
            "gpu_count": 2,
            "gpu_memory_gb": 48,
            "system_memory_gb": 384,
            "category": "GPU",
        },
        "NODE_L40Sx1": {
            "gpu_type": "NVIDIA L40S",
            "gpu_count": 1,
            "gpu_memory_gb": 48,
            "system_memory_gb": 384,
            "category": "GPU",
        },
        # CPU nodes
        "NODE_CPU_384G": {
            "system_memory_gb": 384,
            "category": "CPU",
        },
        "NODE_CPU_1500G": {
            "system_memory_gb": 1500,
            "category": "CPU",
        },
    }
    
    for sku_code, metadata in node_metadata.items():
        RentalSKU.objects.filter(sku_code=sku_code).update(metadata=metadata)


def clear_node_metadata(apps, schema_editor):
    """Clear metadata for NODE SKUs."""
    RentalSKU = apps.get_model("coldfront_orcd_direct_charge", "RentalSKU")
    RentalSKU.objects.filter(sku_type="NODE").update(metadata={})


class Migration(migrations.Migration):

    dependencies = [
        ("coldfront_orcd_direct_charge", "0023_alter_rentalrate_rate"),
    ]

    operations = [
        migrations.AddField(
            model_name="rentalsku",
            name="is_public",
            field=models.BooleanField(
                default=True,
                help_text="Whether this SKU is visible on the public Current Rates page",
            ),
        ),
        migrations.AddField(
            model_name="rentalsku",
            name="metadata",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Flexible metadata attributes (GPU type, memory, cores, etc.)",
            ),
        ),
        # Update maintenance SKU names to use proper terminology
        migrations.RunPython(
            update_maintenance_sku_names,
            reverse_maintenance_sku_names,
        ),
        # Populate metadata for existing NODE SKUs
        migrations.RunPython(
            populate_node_metadata,
            clear_node_metadata,
        ),
    ]


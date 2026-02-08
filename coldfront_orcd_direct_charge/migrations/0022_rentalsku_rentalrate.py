# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def create_initial_skus_and_rates(apps, schema_editor):
    """Create initial SKUs from NodeTypes and maintenance fees with $0.01 placeholder rates."""
    RentalSKU = apps.get_model("coldfront_orcd_direct_charge", "RentalSKU")
    RentalRate = apps.get_model("coldfront_orcd_direct_charge", "RentalRate")
    NodeType = apps.get_model("coldfront_orcd_direct_charge", "NodeType")

    # Use a fixed sentinel date so that any subsequently set rate
    # (even a retroactive one) will always take precedence.
    sentinel_date = date(1999, 1, 1)
    placeholder_rate = Decimal("0.01")

    # Create Node SKUs from all active NodeTypes
    for node_type in NodeType.objects.filter(is_active=True):
        sku = RentalSKU.objects.create(
            sku_code=f"NODE_{node_type.name}",
            name=f"{node_type.name} Node",
            description=node_type.description,
            sku_type="NODE",
            billing_unit="HOURLY",
            is_active=True,
            linked_model=f"NodeType:{node_type.name}",
        )
        # Create initial rate
        RentalRate.objects.create(
            sku=sku,
            rate=placeholder_rate,
            effective_date=sentinel_date,
            notes="Initial placeholder rate",
        )

    # Create Maintenance SKUs
    maint_basic = RentalSKU.objects.create(
        sku_code="MAINT_BASIC",
        name="Basic Maintenance Fee",
        description="Basic account maintenance subscription",
        sku_type="MAINTENANCE",
        billing_unit="MONTHLY",
        is_active=True,
    )
    RentalRate.objects.create(
        sku=maint_basic,
        rate=placeholder_rate,
        effective_date=sentinel_date,
        notes="Initial placeholder rate",
    )

    maint_advanced = RentalSKU.objects.create(
        sku_code="MAINT_ADVANCED",
        name="Advanced Maintenance Fee",
        description="Advanced account maintenance subscription",
        sku_type="MAINTENANCE",
        billing_unit="MONTHLY",
        is_active=True,
    )
    RentalRate.objects.create(
        sku=maint_advanced,
        rate=placeholder_rate,
        effective_date=sentinel_date,
        notes="Initial placeholder rate",
    )


def reverse_initial_skus(apps, schema_editor):
    """Remove all initial SKUs and rates."""
    RentalSKU = apps.get_model("coldfront_orcd_direct_charge", "RentalSKU")
    # Cascade will delete associated rates
    RentalSKU.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("coldfront_orcd_direct_charge", "0021_reservation_processed_by"),
    ]

    operations = [
        migrations.CreateModel(
            name="RentalSKU",
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
                ("created", models.DateTimeField(auto_now_add=True)),
                ("modified", models.DateTimeField(auto_now=True)),
                (
                    "sku_code",
                    models.CharField(
                        help_text="Unique identifier for this SKU (e.g., NODE_H200x8)",
                        max_length=50,
                        unique=True,
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Display name for this SKU",
                        max_length=100,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="Optional description of this SKU",
                    ),
                ),
                (
                    "sku_type",
                    models.CharField(
                        choices=[
                            ("NODE", "Node Rental"),
                            ("MAINTENANCE", "Maintenance Fee"),
                            ("QOS", "Rentable QoS"),
                        ],
                        help_text="Type of rentable item",
                        max_length=20,
                    ),
                ),
                (
                    "billing_unit",
                    models.CharField(
                        choices=[
                            ("HOURLY", "Per Hour"),
                            ("MONTHLY", "Per Month"),
                        ],
                        help_text="How this SKU is billed",
                        max_length=20,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Whether this SKU is currently active and available",
                    ),
                ),
                (
                    "linked_model",
                    models.CharField(
                        blank=True,
                        help_text="Optional link to source model (e.g., 'NodeType:H200x8')",
                        max_length=100,
                    ),
                ),
            ],
            options={
                "verbose_name": "Rental SKU",
                "verbose_name_plural": "Rental SKUs",
                "ordering": ["sku_type", "name"],
                "permissions": [("can_manage_rates", "Can manage rental rates")],
            },
        ),
        migrations.CreateModel(
            name="RentalRate",
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
                ("created", models.DateTimeField(auto_now_add=True)),
                ("modified", models.DateTimeField(auto_now=True)),
                (
                    "rate",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Rate per billing unit (hourly or monthly)",
                        max_digits=10,
                    ),
                ),
                (
                    "effective_date",
                    models.DateField(
                        help_text="Date when this rate becomes effective",
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        help_text="Optional notes about this rate change",
                    ),
                ),
                (
                    "set_by",
                    models.ForeignKey(
                        help_text="The Rate Manager who set this rate",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="rates_set",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "sku",
                    models.ForeignKey(
                        help_text="The SKU this rate applies to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rates",
                        to="coldfront_orcd_direct_charge.rentalsku",
                    ),
                ),
            ],
            options={
                "verbose_name": "Rental Rate",
                "verbose_name_plural": "Rental Rates",
                "ordering": ["-effective_date"],
                "unique_together": {("sku", "effective_date")},
            },
        ),
        # Data migration to create initial SKUs and rates
        migrations.RunPython(create_initial_skus_and_rates, reverse_initial_skus),
    ]


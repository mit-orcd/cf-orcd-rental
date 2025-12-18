# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from django.db import models
from model_utils.models import TimeStampedModel


class NodeType(TimeStampedModel):
    """Defines available node types for GPU and CPU instances.

    This model provides a constrained set of valid node types that can be
    assigned to GpuNodeInstance and CpuNodeInstance records. Types are
    categorized as either GPU or CPU, and can be managed via admin or fixtures.

    Attributes:
        name (str): Unique name of the node type (e.g., "H200x8", "CPU_384G")
        category (str): Category of the node type ("GPU" or "CPU")
        description (str): Optional description of the node type
        is_active (bool): Whether this type is currently active/available
    """

    class CategoryChoices(models.TextChoices):
        GPU = "GPU", "GPU Node"
        CPU = "CPU", "CPU Node"

    class NodeTypeManager(models.Manager):
        def get_by_natural_key(self, name):
            """Get node type by natural key (name)."""
            return self.get(name=name)

    name = models.CharField(
        max_length=64,
        unique=True,
        help_text="Unique name of the node type (e.g., H200x8, CPU_384G)",
    )
    category = models.CharField(
        max_length=16,
        choices=CategoryChoices.choices,
        help_text="Category of node type: GPU or CPU",
    )
    description = models.TextField(
        blank=True,
        help_text="Optional description of the node type",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this node type is currently active and available for use",
    )

    objects = NodeTypeManager()

    class Meta:
        ordering = ["category", "name"]
        verbose_name = "Node Type"
        verbose_name_plural = "Node Types"

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

    def natural_key(self):
        """Return natural key for serialization/deserialization."""
        return (self.name,)


class GpuNodeInstance(TimeStampedModel):
    """A GPU node instance represents a specific GPU node configuration.

    This model defines the schema for GPU node instances used in booking management.
    The actual instances are loaded via fixtures and can be updated dynamically.

    Attributes:
        node_type (NodeType): The type of GPU node (e.g., H200x8, L40Sx4)
        is_rentable (bool): Flag indicating if this node can be rented
        status (str): Current status of the node instance (AVAILABLE, PLACEHOLDER)
        associated_resource_address (str): External HPC/AI cluster resource identifier
    """

    class StatusChoices(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        PLACEHOLDER = "PLACEHOLDER", "Placeholder"

    node_type = models.ForeignKey(
        NodeType,
        on_delete=models.PROTECT,
        limit_choices_to={"category": "GPU"},
        related_name="gpu_instances",
        help_text="The type of GPU node",
    )
    is_rentable = models.BooleanField(
        default=False,
        help_text="Whether this node can be rented for booking management",
    )
    status = models.CharField(
        max_length=32,
        choices=StatusChoices.choices,
        default=StatusChoices.AVAILABLE,
        help_text="Current status of the node instance",
    )
    associated_resource_address = models.CharField(
        max_length=128,
        unique=True,
        help_text="Unique identifier for the external HPC/AI cluster resource (e.g., gpu-h200x8-001, node3401). Required for natural key support.",
    )

    class Meta:
        ordering = ["node_type__name", "associated_resource_address"]
        verbose_name = "GPU Node Instance"
        verbose_name_plural = "GPU Node Instances"

    class GpuNodeInstanceManager(models.Manager):
        def get_by_natural_key(self, associated_resource_address):
            """Get instance by natural key (associated_resource_address)."""
            return self.get(associated_resource_address=associated_resource_address)

    objects = GpuNodeInstanceManager()

    def __str__(self):
        return f"{self.node_type.name} ({self.status})"

    def natural_key(self):
        """Return natural key for serialization/deserialization.

        Uses associated_resource_address as the natural key, which allows
        loaddata to update existing records instead of creating duplicates.

        Returns:
            tuple: Natural key tuple containing associated_resource_address
        """
        return (self.associated_resource_address,)

    natural_key.dependencies = ["coldfront_orcd_direct_charge.nodetype"]


class CpuNodeInstance(TimeStampedModel):
    """A CPU node instance represents a specific CPU node configuration.

    This model defines the schema for CPU node instances used in booking management.
    The actual instances are loaded via fixtures and can be updated dynamically.

    Attributes:
        node_type (NodeType): The type of CPU node (e.g., CPU_384G, CPU_1500G)
        is_rentable (bool): Flag indicating if this node can be rented
        status (str): Current status of the node instance (AVAILABLE, PLACEHOLDER)
        associated_resource_address (str): External HPC/AI cluster resource identifier
    """

    class StatusChoices(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        PLACEHOLDER = "PLACEHOLDER", "Placeholder"

    node_type = models.ForeignKey(
        NodeType,
        on_delete=models.PROTECT,
        limit_choices_to={"category": "CPU"},
        related_name="cpu_instances",
        help_text="The type of CPU node",
    )
    is_rentable = models.BooleanField(
        default=False,
        help_text="Whether this node can be rented for booking management",
    )
    status = models.CharField(
        max_length=32,
        choices=StatusChoices.choices,
        default=StatusChoices.AVAILABLE,
        help_text="Current status of the node instance",
    )
    associated_resource_address = models.CharField(
        max_length=128,
        unique=True,
        help_text="Unique identifier for the external HPC/AI cluster resource (e.g., cpu-384g-001, node5001). Required for natural key support.",
    )

    class Meta:
        ordering = ["node_type__name", "associated_resource_address"]
        verbose_name = "CPU Node Instance"
        verbose_name_plural = "CPU Node Instances"

    class CpuNodeInstanceManager(models.Manager):
        def get_by_natural_key(self, associated_resource_address):
            """Get instance by natural key (associated_resource_address)."""
            return self.get(associated_resource_address=associated_resource_address)

    objects = CpuNodeInstanceManager()

    def __str__(self):
        return f"{self.node_type.name} ({self.status})"

    def natural_key(self):
        """Return natural key for serialization/deserialization.

        Uses associated_resource_address as the natural key, which allows
        loaddata to update existing records instead of creating duplicates.

        Returns:
            tuple: Natural key tuple containing associated_resource_address
        """
        return (self.associated_resource_address,)

    natural_key.dependencies = ["coldfront_orcd_direct_charge.nodetype"]

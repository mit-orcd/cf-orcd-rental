# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from django.core.exceptions import ValidationError
from django.db import models
from model_utils.models import TimeStampedModel


class GpuNodeInstance(TimeStampedModel):
    """A GPU node instance represents a specific GPU node type configuration.

    This model defines the schema for GPU node instances used in booking management.
    The actual instances are loaded via fixtures and can be updated dynamically.

    Attributes:
        name (str): Name of the GPU node type (e.g., "H200x8", "L40Sx4")
        is_rentable (bool): Flag indicating if this node type can be rented
        status (str): Current status of the node instance (AVAILABLE, PLACEHOLDER)
        associated_resource_address (str): Name of the associated ColdFront resource
    """

    class StatusChoices(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        PLACEHOLDER = "PLACEHOLDER", "Placeholder"

    name = models.CharField(
        max_length=64,
        help_text="GPU node type name (e.g., H200x8, L40Sx4). Multiple instances of the same type are allowed.",
    )
    is_rentable = models.BooleanField(
        default=False,
        help_text="Whether this node type can be rented for booking management",
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
        blank=True,
        null=True,
        help_text="Name of the associated resource (e.g., node3401). Must be unique when provided.",
    )

    class Meta:
        ordering = ["name", "associated_resource_address"]
        verbose_name = "GPU Node Instance"
        verbose_name_plural = "GPU Node Instances"

    class GpuNodeInstanceManager(models.Manager):
        def get_by_natural_key(self, associated_resource_address):
            """Get instance by natural key (associated_resource_address)."""
            return self.get(associated_resource_address=associated_resource_address)

    objects = GpuNodeInstanceManager()

    def __str__(self):
        return f"{self.name} ({self.status})"

    def natural_key(self):
        """Return natural key for serialization/deserialization.
        
        Uses associated_resource_address as the natural key, which allows
        loaddata to update existing records instead of creating duplicates.
        
        Returns:
            tuple: Natural key tuple containing associated_resource_address, or None if address is blank
        """
        if self.associated_resource_address:
            return (self.associated_resource_address,)
        # If no address, return None to indicate this record can't use natural key
        # This means records without addresses will be created fresh each time
        return None

    def clean(self):
        """Validate the model instance."""
        if self.associated_resource_address and not self.associated_resource_address.strip():
            raise ValidationError("associated_resource_address cannot be empty if provided")


class CpuNodeInstance(TimeStampedModel):
    """A CPU node instance represents a specific CPU node type configuration.

    This model defines the schema for CPU node instances used in booking management.
    The actual instances are loaded via fixtures and can be updated dynamically.
    Associated with the "CPU Node" resource type.

    Attributes:
        name (str): Name of the CPU node type (e.g., "CPU_384M", "CPU_1500T")
        is_rentable (bool): Flag indicating if this node type can be rented
        status (str): Current status of the node instance (AVAILABLE, PLACEHOLDER)
        associated_resource_address (str): External HPC/AI cluster resource identifier
    """

    class StatusChoices(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        PLACEHOLDER = "PLACEHOLDER", "Placeholder"

    name = models.CharField(
        max_length=64,
        help_text="CPU node type name (e.g., CPU_384M, CPU_1500T). Multiple instances of the same type are allowed.",
    )
    is_rentable = models.BooleanField(
        default=False,
        help_text="Whether this node type can be rented for booking management",
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
        blank=True,
        null=True,
        help_text="Name of the associated resource (e.g., node3401). Must be unique when provided.",
    )

    class Meta:
        ordering = ["name", "associated_resource_address"]
        verbose_name = "CPU Node Instance"
        verbose_name_plural = "CPU Node Instances"

    class CpuNodeInstanceManager(models.Manager):
        def get_by_natural_key(self, associated_resource_address):
            """Get instance by natural key (associated_resource_address)."""
            return self.get(associated_resource_address=associated_resource_address)

    objects = CpuNodeInstanceManager()

    def __str__(self):
        return f"{self.name} ({self.status})"

    def natural_key(self):
        """Return natural key for serialization/deserialization.
        
        Uses associated_resource_address as the natural key, which allows
        loaddata to update existing records instead of creating duplicates.
        
        Returns:
            tuple: Natural key tuple containing associated_resource_address, or None if address is blank
        """
        if self.associated_resource_address:
            return (self.associated_resource_address,)
        # If no address, return None to indicate this record can't use natural key
        # This means records without addresses will be created fresh each time
        return None

    def clean(self):
        """Validate the model instance."""
        if self.associated_resource_address and not self.associated_resource_address.strip():
            raise ValidationError("associated_resource_address cannot be empty if provided")


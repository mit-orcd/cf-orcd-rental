# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from datetime import datetime, time, timedelta

from django.contrib.auth.models import User
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


class Reservation(TimeStampedModel):
    """A reservation request for a GPU node instance.

    Time rules:
    - Reservations always start at 4:00 PM on start_date
    - Duration is stored in 12-hour blocks (1 block = 12 hours)
    - End time is calculated: start_datetime + (num_blocks * 12 hours)
    - End time must be no later than 9:00 AM on the final calendar day

    Attributes:
        node_instance (GpuNodeInstance): The GPU node being reserved
        project (Project): The Coldfront project associated with this reservation
        requesting_user (User): The user who submitted the reservation request
        start_date (date): The date when reservation starts (always at 4:00 PM)
        num_blocks (int): Number of 12-hour blocks (1 block = 12 hours)
        status (str): Current status of the reservation
        manager_notes (str): Notes from the rental manager
    """

    class StatusChoices(models.TextChoices):
        PENDING = "PENDING", "Pending Approval"
        APPROVED = "APPROVED", "Approved"
        DECLINED = "DECLINED", "Declined"
        CANCELLED = "CANCELLED", "Cancelled"

    node_instance = models.ForeignKey(
        GpuNodeInstance,
        on_delete=models.PROTECT,
        related_name="reservations",
        help_text="The GPU node instance being reserved",
    )
    project = models.ForeignKey(
        "project.Project",
        on_delete=models.PROTECT,
        related_name="node_reservations",
        help_text="The project this reservation is associated with",
    )
    requesting_user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="node_reservation_requests",
        help_text="The user who submitted this reservation request",
    )
    start_date = models.DateField(
        help_text="Reservation starts at 4:00 PM on this date"
    )
    num_blocks = models.PositiveIntegerField(
        default=1,
        help_text="Number of 12-hour blocks (1 block = 12 hours, minimum 1, maximum 14)",
    )
    status = models.CharField(
        max_length=16,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
        help_text="Current status of the reservation",
    )
    manager_notes = models.TextField(
        blank=True,
        help_text="Notes from the rental manager (visible to requester)",
    )
    rental_notes = models.TextField(
        blank=True,
        help_text="Optional notes from the requester about this reservation",
    )
    rental_management_metadata = models.TextField(
        blank=True,
        help_text="Internal metadata for rental management (managers only)",
    )

    class Meta:
        ordering = ["-created"]
        verbose_name = "Reservation"
        verbose_name_plural = "Reservations"
        permissions = (
            ("can_manage_rentals", "Can manage rental requests"),
        )

    def __str__(self):
        return f"{self.node_instance.associated_resource_address} - {self.start_date} ({self.get_status_display()})"

    # Reservation timing constants
    START_HOUR = 16  # 4:00 PM
    MAX_END_HOUR = 9  # 9:00 AM - reservations must end no later than this

    @property
    def start_datetime(self):
        """Returns the start datetime (4:00 PM on start_date)."""
        return datetime.combine(self.start_date, time(self.START_HOUR, 0))  # 4:00 PM

    @staticmethod
    def calculate_end_datetime(start_dt, num_blocks):
        """Calculate end datetime with 9 AM cap on final day.

        Reservations are specified in 12-hour blocks, but the final block
        is automatically truncated if it would extend past 9:00 AM.

        Args:
            start_dt: The start datetime
            num_blocks: Number of 12-hour blocks

        Returns:
            datetime: The end datetime, capped at 9:00 AM if necessary
        """
        calculated_end = start_dt + timedelta(hours=12 * num_blocks)
        max_end_time = time(Reservation.MAX_END_HOUR, 0)

        # If end time is after 9 AM, cap it at 9 AM on that day
        if calculated_end.time() > max_end_time:
            return datetime.combine(calculated_end.date(), max_end_time)

        return calculated_end

    @property
    def end_datetime(self):
        """Returns the end datetime based on num_blocks, capped at 9:00 AM."""
        return self.calculate_end_datetime(self.start_datetime, self.num_blocks)

    @property
    def billable_hours(self):
        """Returns total billable hours (actual duration after any truncation)."""
        delta = self.end_datetime - self.start_datetime
        return int(delta.total_seconds() / 3600)

    @property
    def end_date(self):
        """Returns the calendar date when reservation ends."""
        return self.end_datetime.date()

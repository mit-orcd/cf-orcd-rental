# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

import logging
from datetime import datetime, time, timedelta

from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models
from model_utils.models import TimeStampedModel

logger = logging.getLogger(__name__)


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
        APPROVED = "APPROVED", "Confirmed"
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
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_reservations",
        help_text="The rental manager who approved/declined this reservation",
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


class ReservationMetadataEntry(TimeStampedModel):
    """Individual metadata entry for a reservation (managers only).

    This model allows multiple metadata notes to be attached to a reservation,
    each with its own timestamp. Entries are ordered chronologically.

    Attributes:
        reservation (Reservation): The reservation this entry belongs to
        content (str): The metadata note content
    """

    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="metadata_entries",
        help_text="The reservation this metadata entry belongs to",
    )
    content = models.TextField(
        help_text="Metadata note content",
    )

    class Meta:
        ordering = ["created"]
        verbose_name = "Reservation Metadata Entry"
        verbose_name_plural = "Reservation Metadata Entries"

    def __str__(self):
        return f"Metadata for {self.reservation} ({self.created.strftime('%Y-%m-%d %H:%M')})"


class UserMaintenanceStatus(TimeStampedModel):
    """Tracks the account maintenance status for each user.

    Each user has an associated maintenance status that can be one of:
    - inactive: Default status for new accounts (no billing project required)
    - basic: Basic maintenance level (requires billing project)
    - advanced: Advanced maintenance level (requires billing project)

    Attributes:
        user (User): The Django user this status belongs to
        status (str): The current maintenance status
        billing_project (Project): Project to charge maintenance fees to (required for basic/advanced)
    """

    class StatusChoices(models.TextChoices):
        INACTIVE = "inactive", "Inactive"
        BASIC = "basic", "Basic"
        ADVANCED = "advanced", "Advanced"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="maintenance_status",
        help_text="The user this maintenance status belongs to",
    )
    status = models.CharField(
        max_length=16,
        choices=StatusChoices.choices,
        default=StatusChoices.INACTIVE,
        help_text="Current account maintenance status",
    )
    billing_project = models.ForeignKey(
        "project.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_fee_users",
        help_text="Project to which maintenance fees are charged (required for basic/advanced)",
    )

    class Meta:
        verbose_name = "User Maintenance Status"
        verbose_name_plural = "User Maintenance Statuses"

    def __str__(self):
        return f"{self.user.username}: {self.get_status_display()}"


class ProjectCostAllocation(TimeStampedModel):
    """Stores the overall cost allocation settings for a project.

    Each project can have one cost allocation configuration, which includes
    notes about the allocation and links to one or more cost objects.

    Cost allocations require approval from a Billing Manager before the project
    can be used for reservations. When created or modified, allocations are set
    to PENDING status and must be approved.

    Attributes:
        project (Project): The project this cost allocation belongs to
        notes (str): Notes about the cost allocation for this project
        status (str): Approval status (PENDING, APPROVED, REJECTED)
        reviewed_by (User): The Billing Manager who reviewed this allocation
        reviewed_at (datetime): When the allocation was reviewed
        review_notes (str): Notes from the reviewer
    """

    class StatusChoices(models.TextChoices):
        PENDING = "PENDING", "Pending Approval"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    project = models.OneToOneField(
        "project.Project",
        on_delete=models.CASCADE,
        related_name="cost_allocation",
        help_text="The project this cost allocation belongs to",
    )
    notes = models.TextField(
        blank=True,
        help_text="Notes about the cost allocation for this project",
    )
    status = models.CharField(
        max_length=16,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
        help_text="Approval status of this cost allocation",
    )
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_cost_allocations",
        help_text="The Billing Manager who reviewed this allocation",
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the allocation was reviewed",
    )
    review_notes = models.TextField(
        blank=True,
        help_text="Notes from the Billing Manager about the review decision",
    )

    class Meta:
        verbose_name = "Project Cost Allocation"
        verbose_name_plural = "Project Cost Allocations"
        permissions = [
            ("can_manage_billing", "Can approve/reject cost allocations"),
        ]

    def __str__(self):
        return f"Cost Allocation for {self.project.title}"

    def total_percentage(self):
        """Calculate the total percentage across all cost objects."""
        return sum(co.percentage for co in self.cost_objects.all())

    def is_approved(self):
        """Check if this allocation is approved."""
        return self.status == self.StatusChoices.APPROVED


class ProjectCostObject(TimeStampedModel):
    """Stores individual cost objects with their percentage allocation.

    Each cost object has a unique identifier and a percentage of the total
    billing that should be allocated to it. All percentages for a project
    should sum to 100%.

    Attributes:
        allocation (ProjectCostAllocation): The parent cost allocation
        cost_object (str): Cost object identifier (alphanumeric and hyphens)
        percentage (Decimal): Percentage of billing allocated to this cost object
    """

    allocation = models.ForeignKey(
        ProjectCostAllocation,
        on_delete=models.CASCADE,
        related_name="cost_objects",
        help_text="The cost allocation this cost object belongs to",
    )
    cost_object = models.CharField(
        max_length=64,
        help_text="Cost object identifier (alphanumeric characters and hyphens only)",
        validators=[
            RegexValidator(
                regex=r'^[A-Za-z0-9-]+$',
                message="Cost object must contain only letters, numbers, and hyphens",
            )
        ],
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Percentage of billing allocated to this cost object (0.00 - 100.00)",
    )

    class Meta:
        verbose_name = "Project Cost Object"
        verbose_name_plural = "Project Cost Objects"
        ordering = ["-percentage", "cost_object"]

    def __str__(self):
        return f"{self.cost_object}: {self.percentage}%"


class ProjectMemberRole(TimeStampedModel):
    """ORCD-specific role for project members.

    This model tracks the role of each user within a project for the ORCD
    Direct Charge plugin. The Owner role is implicit (determined by project.pi)
    and is not stored in this table.

    Role hierarchy (highest to lowest):
    - Owner: Implicit via project.pi. Has all permissions.
    - Financial Admin: Can edit cost allocations, manage all roles, create reservations.
                       NOT included in reservations or maintenance fee billing.
    - Technical Admin: Can manage members and technical admins, create reservations.
                       Included in reservations and maintenance fee billing.
    - Member: Can create reservations only.
              Included in reservations and maintenance fee billing.

    Attributes:
        project (Project): The project this role assignment belongs to
        user (User): The user who has this role
        role (str): The role assigned to the user
    """

    class RoleChoices(models.TextChoices):
        FINANCIAL_ADMIN = "financial_admin", "Financial Admin"
        TECHNICAL_ADMIN = "technical_admin", "Technical Admin"
        MEMBER = "member", "Member"

    project = models.ForeignKey(
        "project.Project",
        on_delete=models.CASCADE,
        related_name="member_roles",
        help_text="The project this role assignment belongs to",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="project_member_roles",
        help_text="The user who has this role",
    )
    role = models.CharField(
        max_length=32,
        choices=RoleChoices.choices,
        help_text="The role assigned to the user in this project",
    )

    class Meta:
        unique_together = ("project", "user", "role")  # Allow multiple roles per user
        verbose_name = "Project Member Role"
        verbose_name_plural = "Project Member Roles"
        ordering = ["project", "role", "user__username"]

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()} ({self.project.title})"


# =============================================================================
# Invoice Preparation Models
# =============================================================================


class CostAllocationSnapshot(TimeStampedModel):
    """Captures the cost object split at approval time for historical billing accuracy.

    When a ProjectCostAllocation is approved, a snapshot is created to preserve
    the exact cost object percentages that were in effect. This allows accurate
    billing even if the allocation is later modified.

    Attributes:
        allocation (ProjectCostAllocation): The cost allocation this is a snapshot of
        approved_at (datetime): When this split was approved
        approved_by (User): The Billing Manager who approved this allocation
        superseded_at (datetime): When this snapshot was replaced by a new approval
    """

    allocation = models.ForeignKey(
        ProjectCostAllocation,
        on_delete=models.CASCADE,
        related_name="snapshots",
        help_text="The cost allocation this is a snapshot of",
    )
    approved_at = models.DateTimeField(
        help_text="When this cost allocation split was approved",
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="approved_cost_snapshots",
        help_text="The Billing Manager who approved this allocation",
    )
    superseded_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this snapshot was replaced by a new approval (null if current)",
    )

    class Meta:
        ordering = ["-approved_at"]
        verbose_name = "Cost Allocation Snapshot"
        verbose_name_plural = "Cost Allocation Snapshots"

    def __str__(self):
        status = "current" if self.superseded_at is None else "superseded"
        return f"Snapshot for {self.allocation.project.title} ({status})"

    @classmethod
    def get_active_snapshot_for_date(cls, project, target_date):
        """Get the cost allocation snapshot that was active on a specific date.

        Args:
            project: The ColdFront Project object
            target_date: The date to find the active snapshot for

        Returns:
            CostAllocationSnapshot or None if no snapshot was active
        """
        from django.utils import timezone

        # Convert date to datetime for comparison
        if hasattr(target_date, 'date'):
            target_datetime = target_date
        else:
            target_datetime = timezone.make_aware(
                datetime.combine(target_date, time(0, 0))
            )

        try:
            allocation = project.cost_allocation
        except ProjectCostAllocation.DoesNotExist:
            return None

        # Find snapshot that was approved before target date and not superseded before it
        return cls.objects.filter(
            allocation=allocation,
            approved_at__lte=target_datetime,
        ).filter(
            models.Q(superseded_at__isnull=True) |
            models.Q(superseded_at__gt=target_datetime)
        ).order_by('-approved_at').first()


class CostObjectSnapshot(TimeStampedModel):
    """Individual cost objects within a snapshot.

    Stores the cost object identifier and percentage at the time of approval.

    Attributes:
        snapshot (CostAllocationSnapshot): The parent snapshot
        cost_object (str): Cost object identifier
        percentage (Decimal): Percentage of billing allocated to this cost object
    """

    snapshot = models.ForeignKey(
        CostAllocationSnapshot,
        on_delete=models.CASCADE,
        related_name="cost_objects",
        help_text="The snapshot this cost object belongs to",
    )
    cost_object = models.CharField(
        max_length=64,
        help_text="Cost object identifier",
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Percentage of billing allocated to this cost object",
    )

    class Meta:
        ordering = ["-percentage", "cost_object"]
        verbose_name = "Cost Object Snapshot"
        verbose_name_plural = "Cost Object Snapshots"

    def __str__(self):
        return f"{self.cost_object}: {self.percentage}%"


class InvoicePeriod(TimeStampedModel):
    """Tracks the status and metadata for a billing month.

    Each invoice period represents a calendar month and tracks whether
    the invoice has been finalized (locked from further edits).

    Attributes:
        year (int): The year of the invoice period
        month (int): The month of the invoice period (1-12)
        status (str): DRAFT or FINALIZED
        finalized_by (User): Who finalized the invoice
        finalized_at (datetime): When the invoice was finalized
        notes (str): Optional notes about the invoice period
    """

    class StatusChoices(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        FINALIZED = "FINALIZED", "Finalized"

    year = models.IntegerField(
        help_text="The year of the invoice period",
    )
    month = models.IntegerField(
        help_text="The month of the invoice period (1-12)",
    )
    status = models.CharField(
        max_length=16,
        choices=StatusChoices.choices,
        default=StatusChoices.DRAFT,
        help_text="Status of the invoice period",
    )
    finalized_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finalized_invoices",
        help_text="The user who finalized this invoice",
    )
    finalized_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the invoice was finalized",
    )
    notes = models.TextField(
        blank=True,
        help_text="Optional notes about the invoice period",
    )

    class Meta:
        unique_together = ("year", "month")
        ordering = ["-year", "-month"]
        verbose_name = "Invoice Period"
        verbose_name_plural = "Invoice Periods"
        permissions = [
            ("can_manage_invoices", "Can manage invoice preparation"),
        ]

    def __str__(self):
        import calendar
        return f"{calendar.month_name[self.month]} {self.year} ({self.get_status_display()})"

    @property
    def is_finalized(self):
        """Check if this invoice period is finalized."""
        return self.status == self.StatusChoices.FINALIZED


class InvoiceLineOverride(TimeStampedModel):
    """Stores manual overrides for invoice line items with audit trail.

    When a Billing Manager needs to adjust a calculated value, the override
    is stored here along with the original value and a required explanation.

    Attributes:
        invoice_period (InvoicePeriod): The invoice period this override belongs to
        reservation (Reservation): The reservation being overridden
        override_type (str): Type of override (HOURS, COST_SPLIT, EXCLUDE)
        original_value (dict): The original calculated values
        override_value (dict): The overridden values
        notes (str): Required explanation for the override
        created_by (User): Who created the override
    """

    class OverrideTypeChoices(models.TextChoices):
        HOURS = "HOURS", "Hours Override"
        COST_SPLIT = "COST_SPLIT", "Cost Split Override"
        EXCLUDE = "EXCLUDE", "Exclude from Invoice"

    invoice_period = models.ForeignKey(
        InvoicePeriod,
        on_delete=models.CASCADE,
        related_name="overrides",
        help_text="The invoice period this override belongs to",
    )
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="invoice_overrides",
        help_text="The reservation being overridden",
    )
    override_type = models.CharField(
        max_length=16,
        choices=OverrideTypeChoices.choices,
        help_text="Type of override being applied",
    )
    original_value = models.JSONField(
        help_text="The original calculated values before override",
    )
    override_value = models.JSONField(
        help_text="The overridden values",
    )
    notes = models.TextField(
        help_text="Required explanation for why this override was made",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="invoice_overrides_created",
        help_text="The user who created this override",
    )

    class Meta:
        ordering = ["-created"]
        verbose_name = "Invoice Line Override"
        verbose_name_plural = "Invoice Line Overrides"
        # Only one override per reservation per invoice period
        unique_together = ("invoice_period", "reservation")

    def __str__(self):
        return f"Override for Res #{self.reservation.pk} ({self.get_override_type_display()})"


# =============================================================================
# Role Permission Helper Functions
# =============================================================================


def get_user_project_roles(user, project):
    """Return all of the user's roles in the project.

    A user can have multiple roles (e.g., Financial Admin AND Technical Admin).
    Owner is implicit via project.pi and is always listed first if applicable.

    Args:
        user: The Django User object
        project: The ColdFront Project object

    Returns:
        list: List of role strings, e.g. ["owner", "financial_admin", "technical_admin"]
              Returns empty list if user has no roles in the project.
    """
    roles = []

    # Owner is implicit via project.pi
    if project.pi == user:
        roles.append("owner")

    # Get explicit roles from ProjectMemberRole
    explicit_roles = ProjectMemberRole.objects.filter(
        project=project, user=user
    ).values_list("role", flat=True)

    roles.extend(explicit_roles)

    return roles


# Keep the old function for backward compatibility but mark as deprecated
def get_user_project_role(user, project):
    """DEPRECATED: Use get_user_project_roles() instead.

    Returns the user's highest-priority role in the project.
    For multi-role support, use get_user_project_roles() which returns all roles.
    """
    roles = get_user_project_roles(user, project)
    if not roles:
        return None
    # Return highest priority role
    priority = ["owner", "financial_admin", "technical_admin", "member"]
    for role in priority:
        if role in roles:
            return role
    return roles[0] if roles else None


def can_edit_cost_allocation(user, project):
    """Check if user can edit cost allocation for a project.

    Only owners and financial admins (plus superusers) can edit cost allocations.
    With multi-role support, user only needs ONE of these roles.

    Args:
        user: The Django User object
        project: The ColdFront Project object

    Returns:
        bool: True if user can edit cost allocations
    """
    if user.is_superuser:
        return True
    roles = set(get_user_project_roles(user, project))
    return bool(roles & {"owner", "financial_admin"})


def can_manage_members(user, project):
    """Check if user can add/remove members and technical admins.

    Owners, financial admins, and technical admins can manage members.
    With multi-role support, user only needs ONE of these roles.

    Args:
        user: The Django User object
        project: The ColdFront Project object

    Returns:
        bool: True if user can manage members
    """
    if user.is_superuser:
        return True
    roles = set(get_user_project_roles(user, project))
    return bool(roles & {"owner", "financial_admin", "technical_admin"})


def can_manage_financial_admins(user, project):
    """Check if user can add/remove financial admins.

    Only owners and financial admins can manage financial admin assignments.
    With multi-role support, user only needs ONE of these roles.

    Args:
        user: The Django User object
        project: The ColdFront Project object

    Returns:
        bool: True if user can manage financial admins
    """
    if user.is_superuser:
        return True
    roles = set(get_user_project_roles(user, project))
    return bool(roles & {"owner", "financial_admin"})


def is_included_in_reservations(user, project):
    """Check if user should be included in reservations for a project.

    Owners, technical admins, and members are included in reservations.
    Financial admins are NOT included UNLESS they also have another role
    that includes them (technical_admin or member).

    Args:
        user: The Django User object
        project: The ColdFront Project object

    Returns:
        bool: True if user should be included in reservations
    """
    roles = set(get_user_project_roles(user, project))
    return bool(roles & {"owner", "technical_admin", "member"})


def can_use_for_maintenance_fee(user, project):
    """Check if user can use this project for maintenance fee billing.

    Owners, technical admins, and members can use the project for maintenance fees.
    Financial admins cannot UNLESS they also have another eligible role.

    Args:
        user: The Django User object
        project: The ColdFront Project object

    Returns:
        bool: True if user can use project for maintenance fee billing
    """
    roles = set(get_user_project_roles(user, project))
    return bool(roles & {"owner", "technical_admin", "member"})


def get_project_members_for_reservation(project):
    """Get all users who should be included in reservations for a project.

    Returns the project owner plus all users with technical_admin or member roles.
    Users with only financial_admin role are excluded.

    Args:
        project: The ColdFront Project object

    Returns:
        list: List of User objects to include in reservations
    """
    users = set()
    users.add(project.pi)  # Owner is always included

    # Add technical admins and members
    member_roles = ProjectMemberRole.objects.filter(
        project=project,
        role__in=[
            ProjectMemberRole.RoleChoices.TECHNICAL_ADMIN,
            ProjectMemberRole.RoleChoices.MEMBER,
        ],
    ).select_related("user")

    for member_role in member_roles:
        users.add(member_role.user)

    return list(users)


def has_approved_cost_allocation(project):
    """Check if a project has an approved cost allocation.

    Reservations and billing require an approved cost allocation.
    Projects without a cost allocation or with pending/rejected allocations
    cannot be used for reservations.

    Args:
        project: The ColdFront Project object

    Returns:
        bool: True if project has an approved cost allocation
    """
    try:
        return project.cost_allocation.status == ProjectCostAllocation.StatusChoices.APPROVED
    except ProjectCostAllocation.DoesNotExist:
        return False


# =============================================================================
# Activity Log Model and Helpers
# =============================================================================


class ActivityLog(models.Model):
    """Audit log for all user activity on the site."""

    class ActionCategory(models.TextChoices):
        AUTH = "auth", "Authentication"
        RESERVATION = "reservation", "Reservation"
        PROJECT = "project", "Project"
        MEMBER = "member", "Member Management"
        COST_ALLOCATION = "cost_allocation", "Cost Allocation"
        BILLING = "billing", "Billing"
        INVOICE = "invoice", "Invoice"
        MAINTENANCE = "maintenance", "Maintenance Status"
        API = "api", "API Access"
        VIEW = "view", "Page View"

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
        help_text="The user who performed this action",
    )
    action = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Machine-readable action identifier (e.g., reservation.approved)",
    )
    category = models.CharField(
        max_length=30,
        choices=ActionCategory.choices,
        db_index=True,
        help_text="Category of the action for filtering",
    )
    description = models.TextField(
        help_text="Human-readable description of the action",
    )

    # Target object (generic foreign key pattern)
    target_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Class name of the target object (e.g., Reservation, Project)",
    )
    target_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Primary key of the target object",
    )
    target_repr = models.CharField(
        max_length=255,
        blank=True,
        help_text="String representation of the target object",
    )

    # Request context
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the request",
    )
    user_agent = models.TextField(
        blank=True,
        help_text="Browser/client user agent string",
    )

    # Additional data (JSON)
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional structured data about the action",
    )

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Activity Log"
        verbose_name_plural = "Activity Logs"
        indexes = [
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["category", "-timestamp"]),
            models.Index(fields=["action", "-timestamp"]),
        ]

    def __str__(self):
        user_str = self.user.username if self.user else "Anonymous"
        return f"{self.timestamp:%Y-%m-%d %H:%M} - {user_str} - {self.action}"


def get_client_ip(request):
    """Extract client IP address from request, handling proxies."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def log_activity(
    action,
    category,
    description,
    user=None,
    request=None,
    target=None,
    extra_data=None,
):
    """Log an activity to the ActivityLog.

    Args:
        action: Machine-readable action identifier (e.g., "reservation.approved")
        category: ActionCategory choice value
        description: Human-readable description
        user: User who performed the action (optional, extracted from request if available)
        request: HTTP request object (optional, used for IP/user-agent)
        target: Target model instance (optional)
        extra_data: Additional JSON data (optional)

    Returns:
        ActivityLog instance
    """
    ip_address = None
    user_agent = ""

    if request:
        user = user or getattr(request, "user", None)
        ip_address = get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]

    if user and not user.is_authenticated:
        user = None

    target_type = ""
    target_id = None
    target_repr = ""
    if target:
        target_type = target.__class__.__name__
        target_id = getattr(target, "pk", None)
        target_repr = str(target)[:255]

    try:
        return ActivityLog.objects.create(
            user=user,
            action=action,
            category=category,
            description=description,
            target_type=target_type,
            target_id=target_id,
            target_repr=target_repr,
            ip_address=ip_address,
            user_agent=user_agent,
            extra_data=extra_data or {},
        )
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")
        return None


def can_view_activity_log(user):
    """Check if user can view activity logs.

    Access is restricted to:
    - Superusers
    - Users with can_manage_billing permission (Billing Managers)
    - Users with can_manage_rentals permission (Rental Managers)

    Args:
        user: Django User object

    Returns:
        bool: True if user can view activity logs
    """
    if not user or not user.is_authenticated:
        return False
    return (
        user.is_superuser
        or user.has_perm("coldfront_orcd_direct_charge.can_manage_billing")
        or user.has_perm("coldfront_orcd_direct_charge.can_manage_rentals")
    )

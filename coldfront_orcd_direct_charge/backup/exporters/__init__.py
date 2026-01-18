# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Model-specific exporters.

Each module in this package provides exporters for a group of related models.
Exporters are automatically registered with their respective registries when imported.

Components:
    - coldfront_core: ColdFront core models (registered with CoreExporterRegistry)
    - plugin (default): ORCD plugin models (registered with PluginExporterRegistry)

Plugin Modules (ORCD):
    nodes: NodeType, GpuNodeInstance, CpuNodeInstance
    reservations: Reservation, ReservationMetadataEntry
    billing: ProjectCostAllocation, CostObjectSnapshot, InvoicePeriod, etc.
    users: UserMaintenanceStatus, ProjectMemberRole
    rates: RentalSKU, RentalRate

Core Modules (ColdFront):
    coldfront_core.auth: User, Group, Permission
    coldfront_core.project: Project, ProjectUser, FieldOfScience
    coldfront_core.resource: Resource, ResourceType, ResourceAttribute
    coldfront_core.allocation: Allocation, AllocationUser, AllocationAttribute
    coldfront_core.publication: Publication, Grant
"""

# Import plugin exporters to trigger registration with PluginExporterRegistry
from . import nodes
from . import reservations
from . import billing
from . import users
from . import rates

# Import core exporters to trigger registration with CoreExporterRegistry
from . import coldfront_core

__all__ = [
    # Plugin modules
    "nodes",
    "reservations",
    "billing",
    "users",
    "rates",
    # Core modules
    "coldfront_core",
]

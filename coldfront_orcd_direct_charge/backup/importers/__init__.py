# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Model-specific importers.

Each module in this package provides importers for a group of related models.
Importers are automatically registered with their respective registries when imported.

Components:
    - coldfront_core: ColdFront core models (registered with CoreImporterRegistry)
    - plugin (default): ORCD plugin models (registered with PluginImporterRegistry)

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

# Import plugin importers to trigger registration with PluginImporterRegistry
from . import nodes
from . import reservations
from . import billing
from . import users
from . import rates

# Import core importers to trigger registration with CoreImporterRegistry
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

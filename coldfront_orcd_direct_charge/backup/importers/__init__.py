# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Model-specific importers.

Each module in this package provides importers for a group of related models.
Importers are automatically registered with the ImporterRegistry when imported.

Modules:
    nodes: NodeType, GpuNodeInstance, CpuNodeInstance
    reservations: Reservation, ReservationMetadataEntry
    billing: ProjectCostAllocation, CostObjectSnapshot, InvoicePeriod, etc.
    users: UserMaintenanceStatus, ProjectMemberRole
    rates: RentalSKU, RentalRate
"""

# Import all importers to trigger registration
from . import nodes
from . import reservations
from . import billing
from . import users
from . import rates

__all__ = [
    "nodes",
    "reservations",
    "billing",
    "users",
    "rates",
]

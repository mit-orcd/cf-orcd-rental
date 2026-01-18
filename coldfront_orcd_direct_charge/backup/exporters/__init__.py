# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Model-specific exporters.

Each module in this package provides exporters for a group of related models.
Exporters are automatically registered with the ExporterRegistry when imported.

Modules:
    nodes: NodeType, GpuNodeInstance, CpuNodeInstance
    reservations: Reservation, ReservationMetadataEntry
    billing: ProjectCostAllocation, CostObjectSnapshot, InvoicePeriod, etc.
    users: UserMaintenanceStatus, ProjectMemberRole
    rates: RentalSKU, RentalRate
"""

# Import all exporters to trigger registration
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

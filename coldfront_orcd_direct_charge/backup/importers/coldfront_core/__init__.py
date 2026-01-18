# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""ColdFront core model importers.

Imports Django auth models and ColdFront core models:
    - auth: User, Group, Permission
    - project: Project, ProjectUser, FieldOfScience
    - resource: Resource, ResourceType, ResourceAttribute
    - allocation: Allocation, AllocationUser, AllocationAttribute
    - publication: Publication, Grant
"""

# Import all importers to trigger registration
from . import auth
from . import project
from . import resource
from . import allocation
from . import publication

__all__ = [
    "auth",
    "project",
    "resource",
    "allocation",
    "publication",
]

# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from django import template

register = template.Library()


@register.filter
def get_availability(availability_dict, node_id):
    """Get availability dictionary for a specific node.
    
    Args:
        availability_dict: The full availability dictionary {node_id: {day: info}}
        node_id: The node ID to look up
        
    Returns:
        Dictionary of {day: info} for the specified node, or empty dict if not found
    """
    return availability_dict.get(node_id, {})


@register.filter
def get_day_info(day_dict, day):
    """Get availability info for a specific day.
    
    Args:
        day_dict: Dictionary of {day: info}
        day: The day number to look up
        
    Returns:
        Dictionary with rental_type, am_is_mine, pm_is_mine, is_bookable, has_pending
    """
    default = {
        'rental_type': 'available',
        'am_is_mine': False,
        'pm_is_mine': False,
        'is_bookable': True,
        'has_pending': False,
    }
    return day_dict.get(day, default)

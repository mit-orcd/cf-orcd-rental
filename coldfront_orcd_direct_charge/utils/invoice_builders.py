# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Shared invoice billing builders.

These functions build the line-item dicts for each billing type
(reservations, AMF, QoS) and the project-grouped combined response.

Both the REST API views (``api/views.py``) and the web-portal views
(``views/billing.py``) call into this module so that both code paths
return identical data.
"""

import calendar
from datetime import date, datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone

from coldfront_orcd_direct_charge.models import (
    CostAllocationSnapshot,
    InvoiceLineOverride,
    InvoicePeriod,
    RentalSKU,
    Reservation,
    UserMaintenanceStatus,
    UserQoSSubscription,
    compute_effective_billing_end,
    get_sku_for_reservation,
)

# Map maintenance status to SKU code
STATUS_TO_SKU = {
    "basic": "MAINT_STANDARD",
    "advanced": "MAINT_ADVANCED",
}


# =========================================================================
# Cost breakdown helper
# =========================================================================


def get_project_cost_breakdown(project, reference_date):
    """Get cost object percentage breakdown for a project.

    Uses the active ``CostAllocationSnapshot`` for the given date.
    Returns a list of ``{"cost_object": ..., "percentage": ...}`` dicts.
    """
    snapshot = CostAllocationSnapshot.get_active_snapshot_for_date(
        project, reference_date
    )
    if not snapshot:
        return [{"cost_object": "UNKNOWN", "percentage": 100.0}]

    return [
        {
            "cost_object": co_snap.cost_object,
            "percentage": float(co_snap.percentage),
        }
        for co_snap in snapshot.cost_objects.all()
    ]


# =========================================================================
# Reservation line-item builder
# =========================================================================


def build_reservation_lines(year, month, invoice_period):
    """Build reservation billing line items for the given month.

    Returns a list of dicts, each representing one reservation's billing
    data for the month.
    """
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)

    all_reservations = Reservation.objects.filter(
        status=Reservation.StatusChoices.APPROVED,
    ).select_related("project", "project__pi", "node_instance")

    reservations = [
        res for res in all_reservations
        if res.start_date <= month_end and res.end_date >= month_start
    ]

    overrides = {
        o.reservation_id: o
        for o in invoice_period.overrides.select_related("created_by")
    }

    lines = []
    for res in reservations:
        override = overrides.get(res.pk)
        sku = get_sku_for_reservation(res)

        if override and override.override_type == InvoiceLineOverride.OverrideTypeChoices.EXCLUDE:
            lines.append({
                "reservation": res,
                "excluded": True,
                "override": override,
                "hours_in_month": 0,
                "cost_breakdown": [],
                "sku": sku,
            })
            continue

        hours_data = _calculate_hours_for_month(res, year, month)

        if override and override.override_type == InvoiceLineOverride.OverrideTypeChoices.HOURS:
            hours_in_month = override.override_value.get("hours", hours_data["hours"])
        else:
            hours_in_month = hours_data["hours"]

        if override and override.override_type == InvoiceLineOverride.OverrideTypeChoices.COST_SPLIT:
            cost_breakdown = override.override_value.get("cost_breakdown", [])
        else:
            cost_breakdown = _calculate_cost_breakdown(res, year, month, hours_in_month)

        lines.append({
            "reservation": res,
            "excluded": False,
            "override": override,
            "hours_in_month": hours_in_month,
            "cost_breakdown": cost_breakdown,
            "sku": sku,
        })

    return lines


# =========================================================================
# AMF line-item builder
# =========================================================================


def build_amf_lines(year, month):
    """Build AMF billing line items for the given month.

    Returns a list of dicts, each representing one user's maintenance
    fee for the month.

    AMF billing is always rounded up to whole subscription months
    anchored to the activation date.  The ``effective_billing_end``
    is the last day of the subscription-month period that contains
    ``end_date``.  Billing for a calendar month uses the fraction of
    that month that falls within ``[activated_at, effective_billing_end]``.
    """
    month_start = date(year, month, 1)
    if month == 12:
        next_month_start = date(year + 1, 1, 1)
    else:
        next_month_start = date(year, month + 1, 1)
    month_end = next_month_start - timedelta(days=1)
    days_in_month = (next_month_start - month_start).days

    active_amf = UserMaintenanceStatus.objects.filter(
        status__in=[
            UserMaintenanceStatus.StatusChoices.BASIC,
            UserMaintenanceStatus.StatusChoices.ADVANCED,
        ],
        billing_project__isnull=False,
    ).select_related("user", "billing_project", "billing_project__pi")

    sku_cache = {
        sku.sku_code: sku
        for sku in RentalSKU.objects.filter(
            sku_code__in=list(STATUS_TO_SKU.values())
        )
    }

    lines = []
    for amf in active_amf:
        activated_date = amf.created.date() if amf.created else month_start

        if activated_date > month_end:
            continue

        eff_billing_end = compute_effective_billing_end(activated_date, amf.end_date)

        if eff_billing_end < month_start:
            continue

        effective_end = min(next_month_start, eff_billing_end + timedelta(days=1))
        effective_start = max(activated_date, month_start)
        billable_days = (effective_end - effective_start).days
        fraction = round(billable_days / days_in_month, 6)

        sku_code = STATUS_TO_SKU.get(amf.status)
        sku = sku_cache.get(sku_code)
        rate_obj = sku.get_rate_for_date(month_start) if sku else None

        cost_breakdown = get_project_cost_breakdown(amf.billing_project, month_start)

        lines.append({
            "project": amf.billing_project,
            "username": amf.user.username,
            "status": amf.status,
            "sku_code": sku_code,
            "sku_name": sku.name if sku else None,
            "rate": str(rate_obj.rate) if rate_obj else None,
            "billing_unit": "MONTHLY",
            "activated_at": amf.created.isoformat() if amf.created else None,
            "end_date": amf.end_date.isoformat(),
            "effective_billing_end": eff_billing_end.isoformat(),
            "days_in_month": days_in_month,
            "billable_days": billable_days,
            "fraction": fraction,
            "cost_breakdown": cost_breakdown,
        })

    return lines


# =========================================================================
# QoS line-item builder
# =========================================================================


def build_qos_lines(year, month):
    """Build QoS subscription billing line items for the given month.

    Returns a list of dicts, each representing one user's QoS
    subscription for the month.
    """
    month_start = date(year, month, 1)
    if month == 12:
        next_month_start = date(year + 1, 1, 1)
    else:
        next_month_start = date(year, month + 1, 1)
    month_end = next_month_start - timedelta(days=1)
    days_in_month = (next_month_start - month_start).days

    active_qos = UserQoSSubscription.objects.filter(
        is_active=True,
        billing_project__isnull=False,
        start_date__lte=month_end,
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=month_start)
    ).select_related("user", "sku", "billing_project", "billing_project__pi")

    lines = []
    for qos in active_qos:
        effective_start = max(qos.start_date, month_start)
        effective_end = min(qos.end_date, month_end) if qos.end_date else month_end
        billable_days = (effective_end - effective_start).days + 1
        fraction = round(billable_days / days_in_month, 6)

        rate_obj = qos.sku.get_rate_for_date(month_start) if qos.sku else None

        cost_breakdown = get_project_cost_breakdown(qos.billing_project, month_start)

        lines.append({
            "project": qos.billing_project,
            "username": qos.user.username,
            "sku_code": qos.sku.sku_code if qos.sku else None,
            "sku_name": qos.sku.name if qos.sku else None,
            "rate": str(rate_obj.rate) if rate_obj else None,
            "billing_unit": "MONTHLY",
            "start_date": qos.start_date.isoformat(),
            "end_date": qos.end_date.isoformat() if qos.end_date else None,
            "days_in_month": days_in_month,
            "billable_days": billable_days,
            "fraction": fraction,
            "cost_breakdown": cost_breakdown,
        })

    return lines


# =========================================================================
# Combined response builder
# =========================================================================


def build_combined_response(request, year, month, invoice_period,
                            reservation_lines, amf_lines, qos_lines):
    """Merge reservation, AMF, and QoS lines into a project-grouped response.

    Returns a dict ready for JSON serialization.
    """
    total_reservations = len(reservation_lines)
    excluded_count = sum(1 for line in reservation_lines if line["excluded"])

    projects = {}

    def _ensure_project(proj):
        if proj.pk not in projects:
            projects[proj.pk] = {
                "project": proj,
                "reservation_lines": [],
                "amf_lines": [],
                "qos_lines": [],
                "total_hours": 0,
                "cost_totals": {},
            }

    for line in reservation_lines:
        proj = line["reservation"].project
        _ensure_project(proj)
        projects[proj.pk]["reservation_lines"].append(line)
        if not line["excluded"]:
            projects[proj.pk]["total_hours"] += line["hours_in_month"]
            for co in line["cost_breakdown"]:
                if co["cost_object"] not in projects[proj.pk]["cost_totals"]:
                    projects[proj.pk]["cost_totals"][co["cost_object"]] = 0
                projects[proj.pk]["cost_totals"][co["cost_object"]] += co["hours"]

    for line in amf_lines:
        proj = line["project"]
        _ensure_project(proj)
        projects[proj.pk]["amf_lines"].append(line)

    for line in qos_lines:
        proj = line["project"]
        _ensure_project(proj)
        projects[proj.pk]["qos_lines"].append(line)

    export_data = {
        "metadata": {
            "year": year,
            "month": month,
            "month_name": calendar.month_name[month],
            "generated_at": timezone.now().isoformat(),
            "generated_by": request.user.username,
            "invoice_status": invoice_period.get_status_display(),
            "total_reservations": total_reservations,
            "excluded_count": excluded_count,
            "total_amf_entries": len(amf_lines),
            "total_qos_entries": len(qos_lines),
        },
        "projects": [],
    }

    for proj_data in projects.values():
        project_export = {
            "project_id": proj_data["project"].pk,
            "project_title": proj_data["project"].title,
            "project_owner": proj_data["project"].pi.username,
            "total_hours": proj_data["total_hours"],
            "cost_totals": proj_data["cost_totals"],
            "reservations": [],
            "amf_entries": [],
            "qos_entries": [],
        }

        for line in proj_data["reservation_lines"]:
            res = line["reservation"]
            override = line["override"]
            sku = line.get("sku")

            res_export = {
                "reservation_id": res.pk,
                "node": res.node_instance.associated_resource_address,
                "sku_code": sku.sku_code if sku else None,
                "sku_name": sku.name if sku else None,
                "start_date": res.start_date.isoformat(),
                "start_datetime": res.start_datetime.isoformat(),
                "end_date": res.end_date.isoformat(),
                "end_datetime": res.end_datetime.isoformat(),
                "billable_hours": res.billable_hours,
                "hours_in_month": line["hours_in_month"],
                "excluded": line["excluded"],
                "cost_breakdown": line["cost_breakdown"],
            }

            if override:
                res_export["override"] = {
                    "type": override.get_override_type_display(),
                    "notes": override.notes,
                    "created_by": override.created_by.username if override.created_by else None,
                    "created_at": override.created.isoformat(),
                    "original_value": override.original_value,
                    "override_value": override.override_value,
                }

            project_export["reservations"].append(res_export)

        for line in proj_data["amf_lines"]:
            project_export["amf_entries"].append({
                k: v for k, v in line.items() if k != "project"
            })

        for line in proj_data["qos_lines"]:
            project_export["qos_entries"].append({
                k: v for k, v in line.items() if k != "project"
            })

        export_data["projects"].append(project_export)

    return export_data


# =========================================================================
# Reservation hour/cost helpers (used by both reservation builders above
# and the web-portal InvoiceDetailView which needs daily breakdowns)
# =========================================================================


def _calculate_hours_for_month(reservation, year, month):
    """Calculate how many hours of a reservation fall within a specific month."""
    month_start = datetime.combine(date(year, month, 1), time(0, 0))
    if month == 12:
        month_end = datetime.combine(date(year + 1, 1, 1), time(0, 0))
    else:
        month_end = datetime.combine(date(year, month + 1, 1), time(0, 0))

    effective_start = max(reservation.start_datetime, month_start)
    effective_end = min(reservation.end_datetime, month_end)

    if effective_end <= effective_start:
        return {"hours": 0}

    delta = effective_end - effective_start
    hours = delta.total_seconds() / 3600

    return {"hours": round(hours, 2)}


def _calculate_cost_breakdown(reservation, year, month, total_hours):
    """Calculate cost object breakdown using historical snapshots."""
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)

    cost_hours = {}
    current_date = max(reservation.start_date, month_start)
    end_date = min(reservation.end_date, month_end)

    while current_date <= end_date:
        day_hours = _get_hours_for_day(reservation, current_date)

        if day_hours > 0:
            snapshot = CostAllocationSnapshot.get_active_snapshot_for_date(
                reservation.project, current_date
            )

            if snapshot:
                for co_snap in snapshot.cost_objects.all():
                    co_id = co_snap.cost_object
                    pct = float(co_snap.percentage) / 100.0
                    hours_for_co = day_hours * pct

                    if co_id not in cost_hours:
                        cost_hours[co_id] = 0
                    cost_hours[co_id] += hours_for_co
            else:
                if "UNKNOWN" not in cost_hours:
                    cost_hours["UNKNOWN"] = 0
                cost_hours["UNKNOWN"] += day_hours

        current_date += timedelta(days=1)

    return [
        {"cost_object": co, "hours": round(hours, 2)}
        for co, hours in sorted(cost_hours.items())
    ]


def _get_hours_for_day(reservation, target_date):
    """Calculate hours for a specific day of a reservation."""
    day_start = datetime.combine(target_date, time(0, 0))
    day_end = datetime.combine(target_date + timedelta(days=1), time(0, 0))

    effective_start = max(reservation.start_datetime, day_start)
    effective_end = min(reservation.end_datetime, day_end)

    if effective_end <= effective_start:
        return 0

    delta = effective_end - effective_start
    return delta.total_seconds() / 3600

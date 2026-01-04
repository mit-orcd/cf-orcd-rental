# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Rate management views.

Includes rate/SKU management for Rate Managers to maintain
charging rates for rentable items.
"""

import logging
from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView

from coldfront_orcd_direct_charge.forms import (
    RateForm,
    SKUForm,
)
from coldfront_orcd_direct_charge.models import (
    RentalSKU,
    RentalRate,
    ActivityLog,
    log_activity,
)

logger = logging.getLogger(__name__)


class RateManagementView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Rate management dashboard showing all SKUs grouped by type.

    Only accessible to users with can_manage_rates permission (Rate Managers).
    """

    template_name = "coldfront_orcd_direct_charge/rate_management.html"
    permission_required = "coldfront_orcd_direct_charge.can_manage_rates"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all SKUs grouped by type
        all_skus = RentalSKU.objects.prefetch_related("rates").order_by("name")

        # Group by SKU type
        node_skus = []
        maintenance_skus = []
        qos_skus = []

        for sku in all_skus:
            current_rate = sku.current_rate
            sku_data = {
                "sku": sku,
                "current_rate": current_rate,
                "rate_count": sku.rates.count(),
            }

            if sku.sku_type == RentalSKU.SKUType.NODE:
                node_skus.append(sku_data)
            elif sku.sku_type == RentalSKU.SKUType.MAINTENANCE:
                maintenance_skus.append(sku_data)
            else:  # QOS
                qos_skus.append(sku_data)

        context["node_skus"] = node_skus
        context["maintenance_skus"] = maintenance_skus
        context["qos_skus"] = qos_skus

        return context


class SKURateDetailView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Detail view for a single SKU with rate history.

    Only accessible to users with can_manage_rates permission (Rate Managers).
    """

    template_name = "coldfront_orcd_direct_charge/sku_rate_detail.html"
    permission_required = "coldfront_orcd_direct_charge.can_manage_rates"

    def dispatch(self, request, *args, **kwargs):
        self.sku = get_object_or_404(RentalSKU, pk=kwargs.get("pk"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sku"] = self.sku
        context["current_rate"] = self.sku.current_rate
        context["rates"] = self.sku.rates.select_related("set_by").order_by("-effective_date")
        return context


class AddRateView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Add a new rate to an existing SKU.

    Only accessible to users with can_manage_rates permission (Rate Managers).
    """

    template_name = "coldfront_orcd_direct_charge/add_rate_form.html"
    permission_required = "coldfront_orcd_direct_charge.can_manage_rates"

    def dispatch(self, request, *args, **kwargs):
        self.sku = get_object_or_404(RentalSKU, pk=kwargs.get("pk"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sku"] = self.sku
        context["current_rate"] = self.sku.current_rate
        context["form"] = RateForm(sku=self.sku)
        return context

    def post(self, request, *args, **kwargs):
        form = RateForm(request.POST, sku=self.sku)

        if form.is_valid():
            # Create the new rate
            rate = RentalRate.objects.create(
                sku=self.sku,
                rate=form.cleaned_data["rate"],
                effective_date=form.cleaned_data["effective_date"],
                notes=form.cleaned_data.get("notes", ""),
                set_by=request.user,
            )

            messages.success(
                request,
                f"Rate of ${rate.rate}/{self.sku.get_billing_unit_display()} "
                f"added for {self.sku.name}, effective {rate.effective_date}."
            )

            logger.info(
                f"Rate added: sku={self.sku.sku_code}, rate={rate.rate}, "
                f"effective={rate.effective_date}, user={request.user.username}"
            )

            return redirect("coldfront_orcd_direct_charge:sku-rate-detail", pk=self.sku.pk)

        # Form invalid - re-render with errors
        context = self.get_context_data(**kwargs)
        context["form"] = form
        return self.render_to_response(context)


class CreateSKUView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Create a new custom SKU (primarily for QoS).

    Only accessible to users with can_manage_rates permission (Rate Managers).
    """

    template_name = "coldfront_orcd_direct_charge/create_sku_form.html"
    permission_required = "coldfront_orcd_direct_charge.can_manage_rates"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = SKUForm()
        return context

    def post(self, request, *args, **kwargs):
        form = SKUForm(request.POST)

        if form.is_valid():
            # Create the SKU
            sku = RentalSKU.objects.create(
                sku_code=form.cleaned_data["sku_code"],
                name=form.cleaned_data["name"],
                description=form.cleaned_data.get("description", ""),
                sku_type=form.cleaned_data["sku_type"],
                billing_unit=RentalSKU.BillingUnit.MONTHLY,  # QoS and Maintenance are always monthly
                is_active=True,
            )

            # Create initial rate
            rate = RentalRate.objects.create(
                sku=sku,
                rate=form.cleaned_data["initial_rate"],
                effective_date=date.today(),
                notes="Initial rate",
                set_by=request.user,
            )

            messages.success(
                request,
                f"SKU '{sku.name}' created with initial rate of "
                f"${rate.rate}/{sku.get_billing_unit_display()}."
            )

            logger.info(
                f"SKU created: code={sku.sku_code}, name={sku.name}, "
                f"type={sku.sku_type}, rate={rate.rate}, user={request.user.username}"
            )

            # Log activity
            log_activity(
                action="sku.created",
                category=ActivityLog.ActionCategory.RATE,
                description=f"SKU '{sku.name}' ({sku.sku_code}) created",
                user=request.user,
                request=request,
                target=sku,
                extra_data={
                    "sku_code": sku.sku_code,
                    "sku_type": sku.sku_type,
                    "initial_rate": str(rate.rate),
                },
            )

            return redirect("coldfront_orcd_direct_charge:sku-rate-detail", pk=sku.pk)

        # Form invalid - re-render with errors
        context = self.get_context_data(**kwargs)
        context["form"] = form
        return self.render_to_response(context)


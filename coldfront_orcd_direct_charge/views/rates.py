# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Rate management views.

Includes rate/SKU management for Rate Managers to maintain
charging rates for rentable items, and public current rates page.
"""

import json
import logging
from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
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


# =============================================================================
# Public Rates Pages (accessible to all logged-in users)
# =============================================================================


class CurrentRatesView(LoginRequiredMixin, TemplateView):
    """Public current rates page showing all visible SKUs with rates.

    Accessible to all logged-in users. Shows SKUs grouped by type with
    current rates, metadata, and upcoming rate changes.
    """

    template_name = "coldfront_orcd_direct_charge/current_rates.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all public, active SKUs
        public_skus = RentalSKU.objects.filter(
            is_active=True,
            is_public=True,
        ).prefetch_related("rates").order_by("sku_type", "name")

        # Organize SKUs by type with rate info
        node_skus = []
        maintenance_skus = []
        qos_skus = []

        # Collect all metadata keys for dynamic filter generation
        all_metadata_keys = set()

        for sku in public_skus:
            current_rate = sku.current_rate
            next_rate = sku.next_rate_change
            metadata = sku.metadata or {}

            sku_data = {
                "sku": sku,
                "current_rate": current_rate,
                "next_rate_change": next_rate,
                "metadata": metadata,
                "metadata_json": json.dumps(metadata),  # JSON-serialized for data attribute
            }

            # Collect metadata keys
            if sku.metadata:
                all_metadata_keys.update(sku.metadata.keys())

            if sku.sku_type == RentalSKU.SKUType.NODE:
                node_skus.append(sku_data)
            elif sku.sku_type == RentalSKU.SKUType.MAINTENANCE:
                maintenance_skus.append(sku_data)
            else:  # QOS
                qos_skus.append(sku_data)

        # Build filter options from metadata
        filter_options = self._build_filter_options(public_skus, all_metadata_keys)

        context["node_skus"] = node_skus
        context["maintenance_skus"] = maintenance_skus
        context["qos_skus"] = qos_skus
        context["filter_options"] = filter_options
        context["filter_options_json"] = json.dumps(filter_options)

        return context

    def _build_filter_options(self, skus, metadata_keys):
        """Build filter dropdown options from SKU metadata.

        Args:
            skus: QuerySet of RentalSKU objects
            metadata_keys: Set of metadata keys found across all SKUs

        Returns:
            dict mapping metadata key to list of unique values
        """
        # Exclude internal/complex fields from filters
        exclude_keys = {"features", "category"}
        filterable_keys = metadata_keys - exclude_keys

        filter_options = {}
        for key in sorted(filterable_keys):
            values = set()
            for sku in skus:
                if sku.metadata and key in sku.metadata:
                    value = sku.metadata[key]
                    # Only include simple values (not lists/dicts)
                    if isinstance(value, (str, int, float)):
                        values.add(value)

            if values:
                # Sort values (handle mixed types)
                sorted_values = sorted(values, key=lambda x: (isinstance(x, str), str(x)))
                filter_options[key] = sorted_values

        return filter_options


class SKUPublicDetailView(LoginRequiredMixin, TemplateView):
    """Public detail view for a single SKU.

    Shows full description, metadata, current rate, and rate history
    for a public SKU. Accessible to all logged-in users.
    """

    template_name = "coldfront_orcd_direct_charge/sku_public_detail.html"

    def dispatch(self, request, *args, **kwargs):
        # Only allow viewing public, active SKUs
        self.sku = get_object_or_404(
            RentalSKU,
            pk=kwargs.get("pk"),
            is_active=True,
            is_public=True,
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sku"] = self.sku
        context["current_rate"] = self.sku.current_rate
        context["next_rate_change"] = self.sku.next_rate_change
        context["upcoming_rates"] = list(self.sku.upcoming_rates[:5])
        context["metadata"] = self.sku.metadata or {}

        # Format metadata for display (human-readable keys)
        formatted_metadata = []
        if self.sku.metadata:
            key_labels = {
                "gpu_type": "GPU Type",
                "gpu_count": "Number of GPUs",
                "gpu_memory_gb": "GPU Memory (GB)",
                "cpu_cores": "CPU Cores",
                "cpu_sockets": "CPU Sockets",
                "system_memory_gb": "System Memory (GB)",
                "local_storage_tb": "Local Storage (TB)",
                "features": "Features",
                "category": "Category",
            }
            for key, value in self.sku.metadata.items():
                label = key_labels.get(key, key.replace("_", " ").title())
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                formatted_metadata.append({"key": key, "label": label, "value": value})

        context["formatted_metadata"] = formatted_metadata

        return context


class ToggleSKUVisibilityView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """AJAX endpoint to toggle SKU visibility on Current Rates page.

    Only accessible to Rate Managers.
    """

    permission_required = "coldfront_orcd_direct_charge.can_manage_rates"

    def post(self, request, pk):
        sku = get_object_or_404(RentalSKU, pk=pk)

        # Toggle visibility
        sku.is_public = not sku.is_public
        sku.save(update_fields=["is_public"])

        # Log the change
        action = "sku.made_public" if sku.is_public else "sku.made_private"
        log_activity(
            action=action,
            category=ActivityLog.ActionCategory.RATE,
            description=f"SKU '{sku.name}' visibility changed to {'public' if sku.is_public else 'private'}",
            user=request.user,
            request=request,
            target=sku,
            extra_data={
                "sku_code": sku.sku_code,
                "is_public": sku.is_public,
            },
        )

        logger.info(
            f"SKU visibility toggled: sku={sku.sku_code}, "
            f"is_public={sku.is_public}, user={request.user.username}"
        )

        return JsonResponse({
            "success": True,
            "is_public": sku.is_public,
            "message": f"SKU is now {'visible' if sku.is_public else 'hidden'} on Current Rates page",
        })


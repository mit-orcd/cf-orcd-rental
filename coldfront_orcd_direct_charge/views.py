# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, DetailView
from coldfront_orcd_direct_charge.models import GpuNodeInstance, CpuNodeInstance


class NodeInstanceListView(LoginRequiredMixin, TemplateView):
    """List view showing all GPU and CPU node instances."""

    template_name = "coldfront_orcd_direct_charge/node_instance_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["gpu_nodes"] = GpuNodeInstance.objects.all()
        context["cpu_nodes"] = CpuNodeInstance.objects.all()
        context["gpu_count"] = GpuNodeInstance.objects.count()
        context["cpu_count"] = CpuNodeInstance.objects.count()
        return context


class GpuNodeInstanceDetailView(LoginRequiredMixin, DetailView):
    """Detail view for a single GPU node instance."""

    model = GpuNodeInstance
    template_name = "coldfront_orcd_direct_charge/gpu_node_detail.html"
    context_object_name = "node"


class CpuNodeInstanceDetailView(LoginRequiredMixin, DetailView):
    """Detail view for a single CPU node instance."""

    model = CpuNodeInstance
    template_name = "coldfront_orcd_direct_charge/cpu_node_detail.html"
    context_object_name = "node"



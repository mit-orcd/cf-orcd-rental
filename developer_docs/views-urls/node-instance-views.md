# Node Instance Views

This document describes views for displaying GPU and CPU node instances.

---

## NodeInstanceListView

**URL**: `/nodes/`  
**Name**: `coldfront_orcd_direct_charge:node-instance-list`  
**Template**: `coldfront_orcd_direct_charge/node_instance_list.html`

Lists all GPU and CPU node instances with counts.

```python
class NodeInstanceListView(LoginRequiredMixin, TemplateView):
    template_name = "coldfront_orcd_direct_charge/node_instance_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["gpu_nodes"] = GpuNodeInstance.objects.all()
        context["cpu_nodes"] = CpuNodeInstance.objects.all()
        context["gpu_count"] = GpuNodeInstance.objects.count()
        context["cpu_count"] = CpuNodeInstance.objects.count()
        return context
```

**Context Variables**:
- `gpu_nodes` - QuerySet of all GPU nodes
- `cpu_nodes` - QuerySet of all CPU nodes
- `gpu_count` - Total GPU node count
- `cpu_count` - Total CPU node count

---

## GpuNodeInstanceDetailView

**URL**: `/nodes/gpu/<pk>/`  
**Name**: `coldfront_orcd_direct_charge:gpu-node-detail`  
**Template**: `coldfront_orcd_direct_charge/gpu_node_detail.html`

```python
class GpuNodeInstanceDetailView(LoginRequiredMixin, DetailView):
    model = GpuNodeInstance
    template_name = "coldfront_orcd_direct_charge/gpu_node_detail.html"
    context_object_name = "node"
```

---

## CpuNodeInstanceDetailView

**URL**: `/nodes/cpu/<pk>/`  
**Name**: `coldfront_orcd_direct_charge:cpu-node-detail`  
**Template**: `coldfront_orcd_direct_charge/cpu_node_detail.html`

```python
class CpuNodeInstanceDetailView(LoginRequiredMixin, DetailView):
    model = CpuNodeInstance
    template_name = "coldfront_orcd_direct_charge/cpu_node_detail.html"
    context_object_name = "node"
```

---

[← Back to Views and URL Routing](README.md)

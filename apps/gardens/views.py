from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    UpdateView,
)

from .forms import GardenForm, RollLinkForm, TroughForm, WitherBatchForm
from .models import Garden, RollLink, Trough, WitherBatch


def _wants_htmx(request):
    return request.headers.get("HX-Request") == "true"


@login_required
def home(request):
    open_roll_link_count = RollLink.objects.filter(closedAt__isnull=True).count()
    context = {
        "garden_count": Garden.objects.count(),
        "trough_count": Trough.objects.count(),
        "batch_count": WitherBatch.objects.count(),
        "ready_count": Trough.objects.filter(status=Trough.STATUS_READY).count(),
        "withering_count": Trough.objects.filter(
            status=Trough.STATUS_WITHERING
        ).count(),
        "loading_count": Trough.objects.filter(
            status=Trough.STATUS_LOADING
        ).count(),
        # 与揉捻衔接列表中「未关闭」各行使用同一口径计数。
        "open_roll_link_count": open_roll_link_count,
    }
    return render(request, "home.html", context)


# ---- Garden ----


class GardenListView(LoginRequiredMixin, ListView):
    model = Garden
    template_name = "gardens/list.html"
    context_object_name = "gardens"

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        if _wants_htmx(request):
            html = render_to_string(
                "gardens/_table.html",
                {"gardens": self.object_list},
                request=request,
            )
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)


class GardenCreateView(LoginRequiredMixin, CreateView):
    model = Garden
    form_class = GardenForm
    template_name = "gardens/form.html"
    success_url = reverse_lazy("garden_list")

    def form_valid(self, form):
        messages.success(self.request, "茶园已创建")
        response = super().form_valid(form)
        if _wants_htmx(self.request):
            return redirect("garden_list")
        return response


class GardenUpdateView(LoginRequiredMixin, UpdateView):
    model = Garden
    form_class = GardenForm
    template_name = "gardens/form.html"
    success_url = reverse_lazy("garden_list")

    def form_valid(self, form):
        messages.success(self.request, "茶园已更新")
        return super().form_valid(form)


class GardenDeleteView(LoginRequiredMixin, DeleteView):
    model = Garden
    template_name = "gardens/confirm_delete.html"
    success_url = reverse_lazy("garden_list")

    def form_valid(self, form):
        messages.success(self.request, "茶园已删除")
        return super().form_valid(form)


# ---- Trough ----


class TroughListView(LoginRequiredMixin, ListView):
    model = Trough
    template_name = "troughs/list.html"
    context_object_name = "troughs"

    def get_queryset(self):
        return Trough.objects.select_related("garden").all()

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        if _wants_htmx(request):
            html = render_to_string(
                "troughs/_table.html",
                {"troughs": self.object_list},
                request=request,
            )
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)


class TroughCreateView(LoginRequiredMixin, CreateView):
    model = Trough
    form_class = TroughForm
    template_name = "troughs/form.html"
    success_url = reverse_lazy("trough_list")

    def form_valid(self, form):
        messages.success(self.request, "萎凋槽已创建")
        return super().form_valid(form)


class TroughUpdateView(LoginRequiredMixin, UpdateView):
    model = Trough
    form_class = TroughForm
    template_name = "troughs/form.html"
    success_url = reverse_lazy("trough_list")

    def form_valid(self, form):
        messages.success(self.request, "萎凋槽已更新")
        return super().form_valid(form)


class TroughDeleteView(LoginRequiredMixin, DeleteView):
    model = Trough
    template_name = "troughs/confirm_delete.html"
    success_url = reverse_lazy("trough_list")

    def form_valid(self, form):
        messages.success(self.request, "萎凋槽已删除")
        return super().form_valid(form)


# ---- WitherBatch ----


class BatchListView(LoginRequiredMixin, ListView):
    model = WitherBatch
    template_name = "batches/list.html"
    context_object_name = "batches"

    def get_queryset(self):
        return WitherBatch.objects.select_related(
            "trough", "trough__garden"
        ).all()

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        locked_ids = set(
            RollLink.objects.filter(closedAt__isnull=True).values_list(
                "batch_id", flat=True
            )
        )
        if _wants_htmx(request):
            html = render_to_string(
                "batches/_table.html",
                {"batches": self.object_list, "locked_batch_ids": locked_ids},
                request=request,
            )
            return HttpResponse(html)
        self.locked_batch_ids = locked_ids
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["locked_batch_ids"] = getattr(self, "locked_batch_ids", set())
        return context


class BatchCreateView(LoginRequiredMixin, CreateView):
    model = WitherBatch
    form_class = WitherBatchForm
    template_name = "batches/form.html"
    success_url = reverse_lazy("batch_list")

    def form_valid(self, form):
        messages.success(self.request, "萎凋批次已创建")
        return super().form_valid(form)


class BatchUpdateView(LoginRequiredMixin, UpdateView):
    model = WitherBatch
    form_class = WitherBatchForm
    template_name = "batches/form.html"
    success_url = reverse_lazy("batch_list")

    def form_valid(self, form):
        messages.success(self.request, "萎凋批次已更新")
        return super().form_valid(form)


class BatchDeleteView(LoginRequiredMixin, DeleteView):
    model = WitherBatch
    template_name = "batches/confirm_delete.html"
    success_url = reverse_lazy("batch_list")

    def form_valid(self, form):
        messages.success(self.request, "萎凋批次已删除")
        return super().form_valid(form)


# ---- RollLink（揉捻衔接单） ----


class RollLinkListView(LoginRequiredMixin, ListView):
    model = RollLink
    template_name = "rolllinks/list.html"
    context_object_name = "roll_links"

    def get_queryset(self):
        return RollLink.objects.select_related(
            "batch",
            "batch__trough",
            "batch__trough__garden",
            "openedBy",
        ).all()

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        # 首页「未关闭衔接单数」与此处计数同源同口径。
        self.open_count = self.object_list.filter(closedAt__isnull=True).count()
        context = {
            "roll_links": self.object_list,
            "open_count": self.open_count,
        }
        if _wants_htmx(request):
            html = render_to_string(
                "rolllinks/_table.html", context, request=request
            )
            return HttpResponse(html)
        return render(request, self.template_name, context)


class RollLinkCreateView(LoginRequiredMixin, CreateView):
    model = RollLink
    form_class = RollLinkForm
    template_name = "rolllinks/form.html"
    success_url = reverse_lazy("rolllink_list")

    def get_initial(self):
        initial = super().get_initial()
        batch_id = self.request.GET.get("batch")
        if batch_id:
            initial["batch"] = batch_id
        return initial

    def form_valid(self, form):
        form.instance.openedBy = self.request.user
        messages.success(
            self.request,
            "揉捻衔接单已开单：该批次的实测含水率与揉捻等级已锁定，关闭后恢复可改。",
        )
        return super().form_valid(form)


class RollLinkUpdateView(LoginRequiredMixin, UpdateView):
    model = RollLink
    form_class = RollLinkForm
    template_name = "rolllinks/form.html"
    success_url = reverse_lazy("rolllink_list")

    def form_valid(self, form):
        messages.success(self.request, "揉捻衔接单已更新")
        return super().form_valid(form)


@login_required
def rolllink_close(request, pk):
    """关闭衔接单，仅主管（超级用户）可操作。"""
    link = get_object_or_404(
        RollLink.objects.select_related("batch", "batch__trough"), pk=pk
    )
    if not request.user.is_superuser:
        return render(request, "403.html", status=403)
    if link.closedAt is not None:
        messages.warning(request, "该揉捻衔接单已关闭，无需重复操作。")
        return redirect("rolllink_list")
    if request.method == "POST":
        link.closedAt = timezone.now()
        try:
            link.save()
        except ValidationError as exc:
            # 关闭前计划揉次须为正整数（模型层兜底）。
            texts = []
            if hasattr(exc, "message_dict"):
                for msgs in exc.message_dict.values():
                    texts.extend(msgs)
            else:
                texts = exc.messages
            for text in texts:
                messages.error(request, text)
            return redirect("rolllink_edit", link.pk)
        messages.success(request, "揉捻衔接单已关闭，批次锁定字段恢复可改。")
        return redirect("rolllink_list")
    return render(request, "rolllinks/confirm_close.html", {"object": link})

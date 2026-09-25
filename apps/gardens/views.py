from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
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
        # 必须与衔接列表中 closedAt 为空的各行计数一致（同一查询口径）。
        "open_rolllink_count": RollLink.objects.filter(
            closedAt__isnull=True
        ).count(),
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
        open_link = RollLink.objects.filter(
            batch=OuterRef("pk"), closedAt__isnull=True
        )
        return (
            WitherBatch.objects.select_related("trough", "trough__garden")
            .annotate(roll_locked=Exists(open_link))
            .all()
        )

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        if _wants_htmx(request):
            html = render_to_string(
                "batches/_table.html",
                {"batches": self.object_list},
                request=request,
            )
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)


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
        # 锁定字段在表单层（WitherBatchForm.clean 比对原始 POST）与
        # 模型层（WitherBatch.clean 比对库内旧值）双重拒绝，
        # 绕过禁用控件直接提交同样无法保存。
        messages.success(self.request, "萎凋批次已更新")
        return super().form_valid(form)


class BatchDeleteView(LoginRequiredMixin, DeleteView):
    model = WitherBatch
    template_name = "batches/confirm_delete.html"
    success_url = reverse_lazy("batch_list")

    def form_valid(self, form):
        if self.object.rolllinks.exists():
            messages.error(
                self.request,
                "该批次已有揉捻衔接单记录，不能删除（含未关闭单据时先由主管关闭）。",
            )
            return redirect("batch_list")
        messages.success(self.request, "萎凋批次已删除")
        return super().form_valid(form)


# ---- RollLink（揉捻衔接单） ----


class RollLinkListView(LoginRequiredMixin, ListView):
    model = RollLink
    template_name = "rolllinks/list.html"
    context_object_name = "rolllinks"

    def get_queryset(self):
        return RollLink.objects.select_related(
            "batch",
            "batch__trough",
            "batch__trough__garden",
            "openedBy",
            "closedBy",
        ).all()

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        if _wants_htmx(request):
            html = render_to_string(
                "rolllinks/_table.html",
                {"rolllinks": self.object_list},
                request=request,
            )
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 首页统计与列表使用同一口径：closedAt 为空即未关闭。
        context["open_count"] = self.object_list.filter(
            closedAt__isnull=True
        ).count()
        return context


class RollLinkCreateView(LoginRequiredMixin, CreateView):
    model = RollLink
    form_class = RollLinkForm
    template_name = "rolllinks/form.html"
    success_url = reverse_lazy("rolllink_list")

    def form_valid(self, form):
        form.instance.openedBy = self.request.user
        try:
            with transaction.atomic():
                response = super().form_valid(form)
        except ValidationError as exc:
            for field, msgs in exc.message_dict.items():
                form.add_error(field if field in form.fields else None, msgs)
            return self.form_invalid(form)
        except IntegrityError:
            form.add_error(
                "batch", "该批次已存在未关闭的揉捻衔接单，不可重复开单。"
            )
            return self.form_invalid(form)
        messages.success(self.request, "揉捻衔接单已开单，批次锁定字段已冻结")
        return response


class RollLinkCloseView(LoginRequiredMixin, UserPassesTestMixin, View):
    """关闭衔接单：仅主管（is_staff）。关闭前计划揉次须为正整数。"""

    template_name = "rolllinks/confirm_close.html"

    def test_func(self):
        return self.request.user.is_staff

    def get_object(self):
        return get_object_or_404(
            RollLink.objects.select_related(
                "batch", "batch__trough", "batch__trough__garden"
            ),
            pk=self.kwargs["pk"],
        )

    def get(self, request, *args, **kwargs):
        link = self.get_object()
        return render(request, self.template_name, {"object": link})

    def post(self, request, *args, **kwargs):
        link = self.get_object()
        if link.closedAt is not None:
            messages.error(self.request, "该衔接单已经关闭，无需重复关闭。")
            return redirect("rolllink_list")
        if not link.plannedRolls or link.plannedRolls <= 0:
            messages.error(self.request, "关闭被拒：计划揉次须为正整数。")
            return redirect("rolllink_close", pk=link.pk)
        link.closedAt = timezone.now()
        link.closedBy = request.user
        try:
            link.save()
        except ValidationError as exc:
            messages.error(self.request, "；".join(exc.messages))
            return redirect("rolllink_close", pk=link.pk)
        messages.success(request, "揉捻衔接单已关闭，批次实测含水与揉捻等级恢复可改")
        return redirect("rolllink_list")

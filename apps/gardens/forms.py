from django import forms

from .models import Garden, RollLink, Trough, WitherBatch


class GardenForm(forms.ModelForm):
    class Meta:
        model = Garden
        fields = ["name", "altitudeBand", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input"}),
            "altitudeBand": forms.TextInput(attrs={"class": "input"}),
            "notes": forms.Textarea(attrs={"class": "input", "rows": 3}),
        }


class TroughForm(forms.ModelForm):
    class Meta:
        model = Trough
        fields = ["garden", "troughCode", "cultivar", "loadKg", "status"]
        widgets = {
            "garden": forms.Select(attrs={"class": "input"}),
            "troughCode": forms.TextInput(attrs={"class": "input"}),
            "cultivar": forms.TextInput(attrs={"class": "input"}),
            "loadKg": forms.NumberInput(attrs={"class": "input", "step": "0.01"}),
            "status": forms.Select(attrs={"class": "input"}),
        }


class WitherBatchForm(forms.ModelForm):
    class Meta:
        model = WitherBatch
        fields = [
            "trough",
            "startedAt",
            "targetMoisture",
            "actualMoisture",
            "rollGrade",
        ]
        widgets = {
            "trough": forms.Select(attrs={"class": "input"}),
            "startedAt": forms.DateTimeInput(
                attrs={"class": "input", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "targetMoisture": forms.NumberInput(
                attrs={"class": "input", "step": "0.01"}
            ),
            "actualMoisture": forms.NumberInput(
                attrs={"class": "input", "step": "0.01"}
            ),
            "rollGrade": forms.TextInput(attrs={"class": "input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["startedAt"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]
        if self.instance and self.instance.pk and self.instance.startedAt:
            from django.utils import timezone

            local = timezone.localtime(self.instance.startedAt)
            self.initial["startedAt"] = local.strftime("%Y-%m-%dT%H:%M")
        # 存在未关闭揉捻衔接单时，前端同步禁用锁定字段；
        # 真正的拦截在模型 clean()/save()，篡改 POST 仍然无法保存。
        if self.instance and self.instance.pk and self.instance.is_locked_for_rolling():
            for name in ("actualMoisture", "rollGrade"):
                self.fields[name].disabled = True
                self.fields[name].widget.attrs["title"] = (
                    "未关闭揉捻衔接单期间锁定，关闭后恢复可改"
                )
            self.fields["actualMoisture"].help_text = (
                "该批次有未关闭的揉捻衔接单，字段已锁定。"
            )
            self.fields["rollGrade"].help_text = (
                "该批次有未关闭的揉捻衔接单，字段已锁定。"
            )


class RollLinkForm(forms.ModelForm):
    class Meta:
        model = RollLink
        fields = ["batch", "rollerNo", "plannedRolls"]
        widgets = {
            "batch": forms.Select(attrs={"class": "input"}),
            "rollerNo": forms.TextInput(attrs={"class": "input"}),
            "plannedRolls": forms.NumberInput(
                attrs={"class": "input", "min": "1", "step": "1"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 开单下拉只给可选批次：所属槽可下槽、已填实测含水且 ≤40%、
        # 且当前没有未关闭衔接单。最终判定仍在模型层，防止绕过。
        # 用子查询排除，不能用 exclude(roll_links__closedAt__isnull=True)：
        # 该 LEFT JOIN 会把从未开过单的批次一并误排。
        open_link_batch_ids = RollLink.objects.filter(
            closedAt__isnull=True
        ).values("batch_id")
        eligible = (
            WitherBatch.objects.select_related("trough", "trough__garden")
            .filter(
                trough__status=Trough.STATUS_READY,
                actualMoisture__isnull=False,
                actualMoisture__lte=40,
            )
            .exclude(pk__in=open_link_batch_ids)
            .order_by("-startedAt", "-id")
        )
        # 编辑已有单据时，本单批次必须留在选项里（该批正因本单被过滤），
        # 且关联批次不允许再改。
        if self.instance.pk:
            eligible = WitherBatch.objects.filter(
                pk__in=list(eligible.values_list("pk", flat=True))
                + [self.instance.batch_id]
            )
            self.fields["batch"].disabled = True
        self.fields["batch"].queryset = eligible
        self.fields["batch"].label_from_instance = (
            lambda b: f"{b.trough.garden.name} / {b.trough.troughCode} / "
            f"{b.startedAt:%Y-%m-%d %H:%M}（实测 {b.actualMoisture}%）"
        )

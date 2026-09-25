from decimal import Decimal, InvalidOperation

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

        # 前端锁定：存在未关闭揉捻衔接单时，实测含水率与揉捻等级不可编辑。
        # 注意：真正的强制在后端模型层（WitherBatch.clean），
        # 绕过页面直接提交同样会被拒绝。
        if self.instance and self.instance.pk and self.instance.is_roll_locked():
            for fname in ("actualMoisture", "rollGrade"):
                field = self.fields[fname]
                field.disabled = True
                field.required = False
                field.help_text = (
                    "已被未关闭的揉捻衔接单锁定，关闭衔接单后恢复可改。"
                )
            self.roll_locked = True
        else:
            self.roll_locked = False

    def clean(self):
        cleaned_data = super().clean()
        if not self.roll_locked:
            return cleaned_data
        # 后端表单层强制：浏览器对 disabled 控件默认不提交该字段，
        # 但凡有人手工构造 POST 带上锁定字段，值与库内旧值不一致即拒绝。
        # （模型 WitherBatch.clean 另有一层兜底。）
        self._reject_locked_change(
            "actualMoisture",
            self.instance.actualMoisture,
            "该批次存在未关闭的揉捻衔接单，关闭前禁止修改实测含水率。",
            numeric=True,
        )
        self._reject_locked_change(
            "rollGrade",
            self.instance.rollGrade,
            "该批次存在未关闭的揉捻衔接单，关闭前禁止修改揉捻等级。",
            numeric=False,
        )
        return cleaned_data

    def _reject_locked_change(self, fname, old_value, message, numeric):
        if fname not in self.data:
            # disabled 控件正常不提交，允许保存其余字段
            return
        raw = self.data.get(fname)
        if numeric:
            try:
                new_value = None if raw == "" else Decimal(str(raw))
            except (InvalidOperation, ValueError):
                self.add_error(fname, message)
                return
            changed = (new_value is None) != (old_value is None) or (
                new_value is not None
                and old_value is not None
                and new_value != Decimal(old_value)
            )
        else:
            changed = (raw or "") != (old_value or "")
        if changed:
            self.add_error(fname, message)


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
        # 仅为前端引导：下拉只列当前可开单的批次；
        # 真正的开单校验在模型层，手工提交其他批次仍会被拒绝。
        eligible = (
            WitherBatch.objects.select_related("trough", "trough__garden")
            .filter(
                trough__status=Trough.STATUS_READY,
                actualMoisture__isnull=False,
                actualMoisture__lte=40,
            )
            .exclude(rolllinks__closedAt__isnull=True)
            .distinct()
            .order_by("-startedAt", "-id")
        )
        if self.instance and self.instance.pk:
            # 编辑已开单据时保留其原批次选项
            self.fields["batch"].queryset = WitherBatch.objects.select_related(
                "trough", "trough__garden"
            ).filter(pk=self.instance.batch_id)
            self.fields["batch"].disabled = True
        else:
            self.fields["batch"].queryset = eligible
        self.fields["plannedRolls"].min_value = 1

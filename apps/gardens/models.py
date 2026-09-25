from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Garden(models.Model):
    name = models.CharField("茶园名称", max_length=120)
    altitudeBand = models.CharField("海拔带", max_length=60)
    notes = models.TextField("备注", blank=True, default="")

    class Meta:
        ordering = ["name"]
        verbose_name = "茶园"
        verbose_name_plural = "茶园"

    def __str__(self):
        return self.name


class Trough(models.Model):
    STATUS_LOADING = "loading"
    STATUS_WITHERING = "withering"
    STATUS_READY = "ready"
    STATUS_CHOICES = [
        (STATUS_LOADING, "装叶中"),
        (STATUS_WITHERING, "萎凋中"),
        (STATUS_READY, "可下槽"),
    ]

    garden = models.ForeignKey(
        Garden,
        on_delete=models.CASCADE,
        related_name="troughs",
        verbose_name="茶园",
    )
    troughCode = models.CharField("槽位编号", max_length=40)
    cultivar = models.CharField("茶树品种", max_length=80)
    loadKg = models.DecimalField("装叶量(kg)", max_digits=10, decimal_places=2)
    status = models.CharField(
        "状态",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_LOADING,
    )

    class Meta:
        ordering = ["garden__name", "troughCode"]
        verbose_name = "萎凋槽"
        verbose_name_plural = "萎凋槽"
        constraints = [
            models.UniqueConstraint(
                fields=["garden", "troughCode"],
                name="uniq_trough_code_per_garden",
            ),
        ]

    def __str__(self):
        return f"{self.garden.name}-{self.troughCode}"

    def latest_batch(self):
        return self.batches.order_by("-startedAt", "-id").first()

    def clean(self):
        super().clean()
        if self.status != self.STATUS_READY:
            return
        latest = None
        if self.pk:
            latest = (
                WitherBatch.objects.filter(trough_id=self.pk)
                .order_by("-startedAt", "-id")
                .first()
            )
        if latest is None or latest.actualMoisture is None or latest.actualMoisture > 40:
            raise ValidationError(
                {
                    "status": "无法设为可下槽：最新萎凋批次的实测含水率为空或高于 40%。"
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class WitherBatch(models.Model):
    trough = models.ForeignKey(
        Trough,
        on_delete=models.CASCADE,
        related_name="batches",
        verbose_name="萎凋槽",
    )
    startedAt = models.DateTimeField("开始时间")
    targetMoisture = models.DecimalField(
        "目标含水率(%)", max_digits=5, decimal_places=2
    )
    actualMoisture = models.DecimalField(
        "实测含水率(%)",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    rollGrade = models.CharField("揉捻等级", max_length=40)

    class Meta:
        ordering = ["-startedAt", "-id"]
        verbose_name = "萎凋批次"
        verbose_name_plural = "萎凋批次"

    def __str__(self):
        return f"{self.trough} @ {self.startedAt:%Y-%m-%d %H:%M}"

    def open_roll_link(self):
        """该批次当前未关闭的揉捻衔接单（无则 None）。"""
        return self.rolllinks.filter(closedAt__isnull=True).first()

    def is_roll_locked(self):
        return self.rolllinks.filter(closedAt__isnull=True).exists()

    def clean(self):
        super().clean()
        # 已有未关闭揉捻衔接单时，实测含水率与揉捻等级在后端禁止修改。
        # 规则不依赖任何页面：后台、shell、API 保存同样会被拒绝。
        if not self.pk:
            return
        previous = WitherBatch.objects.filter(pk=self.pk).values(
            "actualMoisture", "rollGrade"
        ).first()
        if previous is None:
            return
        locked = self.rolllinks.filter(closedAt__isnull=True).exists()
        if not locked:
            return
        errors = {}
        old_moisture = previous["actualMoisture"]
        old_grade = previous["rollGrade"]
        new_moisture = self.actualMoisture
        if (old_moisture is None) != (new_moisture is None) or (
            old_moisture is not None
            and new_moisture is not None
            and Decimal(old_moisture) != Decimal(new_moisture)
        ):
            errors["actualMoisture"] = (
                "该批次存在未关闭的揉捻衔接单，关闭前禁止修改实测含水率。"
            )
        if str(old_grade) != (self.rollGrade or ""):
            errors["rollGrade"] = (
                "该批次存在未关闭的揉捻衔接单，关闭前禁止修改揉捻等级。"
            )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class RollLink(models.Model):
    """揉捻衔接单：可下槽批次衔接揉捻工序的开单/关单记录。"""

    batch = models.ForeignKey(
        WitherBatch,
        on_delete=models.PROTECT,
        related_name="rolllinks",
        verbose_name="关联批次",
    )
    rollerNo = models.CharField("揉捻机号", max_length=40)
    plannedRolls = models.PositiveIntegerField("计划揉次")
    openedAt = models.DateTimeField("开单时刻", default=timezone.now)
    closedAt = models.DateTimeField("关闭时刻", null=True, blank=True)
    openedBy = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="opened_rolllinks",
        verbose_name="开单人",
    )
    closedBy = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="closed_rolllinks",
        verbose_name="关闭人",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-openedAt", "-id"]
        verbose_name = "揉捻衔接单"
        verbose_name_plural = "揉捻衔接单"
        constraints = [
            # 同一批次至多存在一张未关闭衔接单（数据库层兜底）。
            models.UniqueConstraint(
                fields=["batch"],
                condition=models.Q(closedAt__isnull=True),
                name="uniq_open_rolllink_per_batch",
            ),
        ]

    def __str__(self):
        state = "未关闭" if self.closedAt is None else "已关闭"
        return f"揉捻衔接单 #{self.pk} {self.batch}（{state}）"

    @property
    def is_open(self):
        return self.closedAt is None

    def clean(self):
        super().clean()
        if not self.batch_id:
            return
        try:
            batch = self.batch
        except WitherBatch.DoesNotExist:
            return

        if self.closedAt is not None:
            # 关闭时：计划揉次须为正整数，且只能由主管关闭。
            if self.plannedRolls is None or self.plannedRolls <= 0:
                raise ValidationError(
                    {"plannedRolls": "关闭前计划揉次须为正整数。"}
                )
        else:
            # 开单时：计划揉次必须为正整数；所属槽必须可下槽；
            # 批次须已写实测含水且不超过 40。
            if self.plannedRolls is None or self.plannedRolls <= 0:
                raise ValidationError(
                    {"plannedRolls": "计划揉次须为正整数。"}
                )
            if batch.trough.status != Trough.STATUS_READY:
                raise ValidationError(
                    {"batch": "开单被拒：该批次所属槽位当前不是「可下槽」状态。"}
                )
            if batch.actualMoisture is None:
                raise ValidationError(
                    {"batch": "开单被拒：该批次尚未填写实测含水率。"}
                )
            if batch.actualMoisture > 40:
                raise ValidationError(
                    {"batch": "开单被拒：该批次实测含水率高于 40%。"}
                )
            # 同一批次未关闭时不可再开。
            qs = RollLink.objects.filter(batch=batch, closedAt__isnull=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    {"batch": "该批次已存在未关闭的揉捻衔接单，不可重复开单。"}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

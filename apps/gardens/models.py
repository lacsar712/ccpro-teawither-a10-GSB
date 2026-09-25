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

    # ---- 揉捻衔接单锁定 ----
    # 存在未关闭衔接单时，实测含水率与揉捻等级被后端锁定，
    # 任何写入路径（表单 / admin / ORM）都会在 clean()/save() 被拒绝。
    LOCK_MESSAGE = "该批次存在未关闭的揉捻衔接单，锁定期间禁止修改实测含水率与揉捻等级。"

    def open_roll_link(self):
        return self.roll_links.filter(closedAt__isnull=True).first()

    def is_locked_for_rolling(self):
        return self.roll_links.filter(closedAt__isnull=True).exists()

    def clean(self):
        super().clean()
        if not self.pk:
            return
        locked_field = None
        old = WitherBatch.objects.filter(pk=self.pk).values(
            "actualMoisture", "rollGrade"
        ).first()
        if old is None:
            return
        if old["actualMoisture"] != self.actualMoisture:
            locked_field = "actualMoisture"
        elif old["rollGrade"] != self.rollGrade:
            locked_field = "rollGrade"
        if locked_field is not None and self.is_locked_for_rolling():
            raise ValidationError({locked_field: self.LOCK_MESSAGE})

    def save(self, *args, **kwargs):
        # full_clean 覆盖表单/admin；直接 .save() 绕过表单时这里再拦一道，
        # 避免“只锁前端字段却后端仍能改”。
        if self.pk:
            old = WitherBatch.objects.filter(pk=self.pk).values(
                "actualMoisture", "rollGrade"
            ).first()
            if old is not None:
                changed = (
                    old["actualMoisture"] != self.actualMoisture
                    or old["rollGrade"] != self.rollGrade
                )
                if changed and self.is_locked_for_rolling():
                    raise ValidationError(self.LOCK_MESSAGE)
        self.full_clean()
        return super().save(*args, **kwargs)


class RollLink(models.Model):
    """揉捻衔接单：可下槽批次开单进入揉捻，未关闭前锁定批次实测含水与揉捻等级。"""

    batch = models.ForeignKey(
        WitherBatch,
        on_delete=models.CASCADE,
        related_name="roll_links",
        verbose_name="关联批次",
    )
    rollerNo = models.CharField("揉捻机号", max_length=40)
    plannedRolls = models.PositiveIntegerField("计划揉次", null=True, blank=True)
    openedAt = models.DateTimeField("开单时刻", default=timezone.now)
    closedAt = models.DateTimeField("关闭时刻", null=True, blank=True)
    openedBy = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="opened_roll_links",
        verbose_name="开单人",
    )

    class Meta:
        ordering = ["-openedAt", "-id"]
        verbose_name = "揉捻衔接单"
        verbose_name_plural = "揉捻衔接单"
        constraints = [
            # 同一批次同时只允许一张未关闭衔接单（数据库层兜底）。
            models.UniqueConstraint(
                fields=["batch"],
                condition=models.Q(closedAt__isnull=True),
                name="uniq_open_roll_link_per_batch",
            ),
        ]

    def __str__(self):
        state = "未关闭" if self.closedAt is None else "已关闭"
        return f"揉捻衔接单#{self.pk} {self.batch}（{state}）"

    @property
    def is_open(self):
        return self.closedAt is None

    def clean(self):
        super().clean()
        # 仅新建开单时校验可下槽与含水率；已有关联单只做关闭/机号维护。
        if not self.pk and self.batch_id:
            trough = self.batch.trough
            if trough.status != Trough.STATUS_READY:
                raise ValidationError(
                    {"batch": "开单失败：该批次所属槽位当前不是「可下槽」状态。"}
                )
            if self.batch.actualMoisture is None:
                raise ValidationError(
                    {"batch": "开单失败：该批次尚未填写实测含水率。"}
                )
            if self.batch.actualMoisture > Decimal("40"):
                raise ValidationError(
                    {"batch": "开单失败：该批次实测含水率高于 40%，不能开单。"}
                )
            if RollLink.objects.filter(
                batch_id=self.batch_id, closedAt__isnull=True
            ).exists():
                raise ValidationError(
                    {"batch": "开单失败：该批次已有未关闭的揉捻衔接单。"}
                )
        # 关闭（填入关闭时刻）前，计划揉次必须是正整数。
        if self.closedAt is not None:
            if self.plannedRolls is None or self.plannedRolls <= 0:
                raise ValidationError(
                    {"plannedRolls": "关闭前必须填写正整数的计划揉次。"}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

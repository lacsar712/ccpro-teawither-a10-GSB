from django.contrib import admin

from .models import Garden, RollLink, Trough, WitherBatch


@admin.register(Garden)
class GardenAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "altitudeBand")
    search_fields = ("name", "altitudeBand")


@admin.register(Trough)
class TroughAdmin(admin.ModelAdmin):
    list_display = ("id", "garden", "troughCode", "cultivar", "loadKg", "status")
    list_filter = ("status", "garden")
    search_fields = ("troughCode", "cultivar")


@admin.register(WitherBatch)
class WitherBatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "trough",
        "startedAt",
        "targetMoisture",
        "actualMoisture",
        "rollGrade",
        "rolling_lock",
    )
    list_filter = ("rollGrade",)
    readonly_fields = ("rolling_lock",)

    @admin.display(description="揉捻衔接锁定", boolean=True)
    def rolling_lock(self, obj):
        return obj.pk is not None and obj.is_locked_for_rolling()


@admin.register(RollLink)
class RollLinkAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "batch",
        "rollerNo",
        "plannedRolls",
        "openedAt",
        "closedAt",
        "openedBy",
    )
    list_filter = ("closedAt",)
    search_fields = ("rollerNo",)

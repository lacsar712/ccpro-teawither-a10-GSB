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
    )
    list_filter = ("rollGrade",)


@admin.register(RollLink)
class RollLinkAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "batch",
        "rollerNo",
        "plannedRolls",
        "openedAt",
        "openedBy",
        "closedAt",
        "closedBy",
    )
    list_filter = ("closedAt",)
    raw_id_fields = ("batch", "openedBy", "closedBy")

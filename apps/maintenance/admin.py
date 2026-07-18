from django.contrib import admin

from .models import Complaint, Remark, WorkOrder


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "equipment",
        "reporter",
        "status",
        "close_reason",
        "created_at",
    )
    list_filter = ("status", "close_reason")
    readonly_fields = [f.name for f in Complaint._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "equipment",
        "status",
        "outcome",
        "fault_category",
        "opened_at",
    )
    list_filter = ("status", "fault_category")
    readonly_fields = [f.name for f in WorkOrder._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Remark)
class RemarkAdmin(admin.ModelAdmin):
    list_display = ("created_at", "work_order", "author", "kind")
    readonly_fields = [f.name for f in Remark._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

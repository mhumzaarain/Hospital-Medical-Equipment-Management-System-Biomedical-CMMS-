from django.contrib import admin

from .models import RiskScoringConfig, ServiceManual


@admin.register(RiskScoringConfig)
class RiskScoringConfigAdmin(admin.ModelAdmin):
    list_display = ("points_per_repair", "high_risk_threshold")
    actions = ["recompute_now"]

    def has_add_permission(self, request):
        return not RiskScoringConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Recompute risk scores now")
    def recompute_now(self, request, queryset):
        from .tasks import compute_risk_scores

        compute_risk_scores.defer()
        self.message_user(request, "Risk recomputation queued.")


@admin.register(ServiceManual)
class ServiceManualAdmin(admin.ModelAdmin):
    list_display = ("title", "manufacturer", "model_number", "status")

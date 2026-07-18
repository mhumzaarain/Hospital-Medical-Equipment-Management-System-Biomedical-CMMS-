from django.conf import settings
from django.db import models


class ReportStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    GENERATING = "generating", "Generating"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"


class MonthlyReport(models.Model):
    month = models.DateField(unique=True, help_text="First day of the month.")
    status = models.CharField(
        max_length=20, choices=ReportStatus.choices, default=ReportStatus.PENDING
    )
    metrics = models.JSONField(default=dict, blank=True)
    narrative = models.TextField(null=True, blank=True)
    pdf = models.FileField(upload_to="reports/", blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reports_requested",
    )

    class Meta:
        ordering = ["-month"]

    def __str__(self):
        return f"Monthly report {self.month:%Y-%m} ({self.status})"

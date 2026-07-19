from datetime import date

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from apps.reports.models import MonthlyReport, ReportStatus


@pytest.fixture(autouse=True)
def isolated_media_root(settings, tmp_path):
    # ready_report saves a real file via FileField/FileSystemStorage; point
    # MEDIA_ROOT at a throwaway tmp_path so test runs don't leak files into
    # the real project media/ directory.
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def ready_report(db):
    report = MonthlyReport.objects.create(
        month=date(2026, 6, 1), status=ReportStatus.READY
    )
    report.pdf.save("monthly-2026-06.pdf", ContentFile(b"%PDF-fake"))
    return report


def test_staff_blocked(client, staff_user):
    client.force_login(staff_user)
    assert client.get(reverse("report_list")).status_code == 403


def test_list_shows_reports(client, engineer, ready_report):
    client.force_login(engineer)
    response = client.get(reverse("report_list"))
    assert b"2026-06" in response.content


def test_generate_defers_task(client, engineer, monkeypatch, db):
    deferred = {}

    from apps.ai import tasks

    monkeypatch.setattr(
        tasks.generate_monthly_report, "defer", lambda **kw: deferred.update(kw)
    )
    client.force_login(engineer)
    response = client.post(reverse("report_generate"), {"month": "2026-06"})
    assert response.status_code == 302
    assert deferred == {"month_iso": "2026-06", "requested_by_id": engineer.id}


def test_download_streams_pdf(client, engineer, ready_report):
    client.force_login(engineer)
    response = client.get(reverse("report_download", args=[ready_report.pk]))
    assert response["Content-Type"] == "application/pdf"
    assert b"".join(response.streaming_content) == b"%PDF-fake"

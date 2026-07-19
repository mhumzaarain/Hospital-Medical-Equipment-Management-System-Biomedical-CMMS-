from datetime import date

import pytest

from apps.ai import client, tasks
from apps.reports.models import MonthlyReport, ReportStatus


@pytest.fixture(autouse=True)
def isolated_media_root(settings, tmp_path):
    # Each test in this module saves a real PDF via FileField/FileSystemStorage
    # (only render_monthly_pdf is faked). Point MEDIA_ROOT at a throwaway
    # tmp_path so runs don't leak files into the real project media/ dir and
    # so same-named months across tests/runs can't collide on disk.
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def fake_pdf(monkeypatch):
    from apps.reports import pdf

    monkeypatch.setattr(pdf, "render_monthly_pdf", lambda report: b"%PDF-fake")


@pytest.fixture
def fake_llm(monkeypatch):
    monkeypatch.setattr(client, "chat", lambda messages, **kw: "Executive summary.")


def test_generate_creates_ready_report(db, fake_pdf, fake_llm):
    tasks.generate_monthly_report.func("2026-06")
    report = MonthlyReport.objects.get(month=date(2026, 6, 1))
    assert report.status == ReportStatus.READY
    assert report.narrative == "Executive summary."
    assert report.metrics["month"] == "2026-06"
    assert report.pdf.read() == b"%PDF-fake"


def test_generate_without_llm_still_ready(db, fake_pdf, monkeypatch):
    def _boom(messages, **kw):
        raise client.LLMUnavailable("down")

    monkeypatch.setattr(client, "chat", _boom)
    tasks.generate_monthly_report.func("2026-06")
    report = MonthlyReport.objects.get(month=date(2026, 6, 1))
    assert report.status == ReportStatus.READY and report.narrative is None


def test_generate_is_rerunnable(db, fake_pdf, fake_llm):
    tasks.generate_monthly_report.func("2026-06")
    tasks.generate_monthly_report.func("2026-06")
    assert MonthlyReport.objects.filter(month=date(2026, 6, 1)).count() == 1
    report = MonthlyReport.objects.get(month=date(2026, 6, 1))
    assert report.pdf.name == "reports/monthly-2026-06.pdf"

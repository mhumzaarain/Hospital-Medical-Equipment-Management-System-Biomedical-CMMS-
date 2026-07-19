import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.ai.models import ManualStatus, ServiceManual


@pytest.fixture(autouse=True)
def isolated_media_root(settings, tmp_path):
    # Manual uploads save a real file via FileField/FileSystemStorage; point
    # MEDIA_ROOT at a throwaway tmp_path so test runs don't leak files into
    # the real project media/ directory.
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def engineer_client(client, engineer):
    client.force_login(engineer)
    return client


def _upload(client, **overrides):
    data = {
        "manufacturer": "Hamilton",
        "model_number": "C2",
        "title": "C2 Service Manual",
        "file": SimpleUploadedFile("manual.pdf", b"%PDF-1.4 fake"),
    }
    data.update(overrides)
    return client.post(reverse("manual_list"), data)


def test_staff_blocked(client, staff_user):
    client.force_login(staff_user)
    assert client.get(reverse("manual_list")).status_code == 403


def test_upload_creates_processing_manual_and_defers(
    engineer_client, monkeypatch, db
):
    deferred = []
    from apps.ai import tasks

    monkeypatch.setattr(
        tasks.process_manual, "defer", lambda **kw: deferred.append(kw)
    )
    response = _upload(engineer_client)
    assert response.status_code == 302
    manual = ServiceManual.objects.get()
    assert manual.status == ManualStatus.PROCESSING
    assert deferred == [{"manual_id": manual.id}]


def test_reupload_replaces_same_model(engineer_client, monkeypatch, db):
    from apps.ai import tasks

    monkeypatch.setattr(tasks.process_manual, "defer", lambda **kw: None)
    _upload(engineer_client)
    _upload(engineer_client, title="C2 Manual rev B")
    assert ServiceManual.objects.count() == 1
    assert ServiceManual.objects.get().title == "C2 Manual rev B"


def test_equipment_detail_links_ready_manual(
    engineer_client, equipment, engineer, db
):
    ServiceManual.objects.create(
        manufacturer="Hamilton", model_number="C2", title="C2 Manual",
        uploaded_by=engineer, status=ManualStatus.READY,
    )
    response = engineer_client.get(reverse("equipment_detail", args=[equipment.pk]))
    assert b"C2 Manual" in response.content

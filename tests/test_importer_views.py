import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.equipment.models import Equipment

CSV = "name,serial_number,department,ward_notes\nVentilator,SN-77,ICU,3rd floor\n"


@pytest.fixture
def engineer_client(client, engineer):
    client.force_login(engineer)
    return client


def _upload(client, text=CSV, filename="equip.csv"):
    return client.post(
        reverse("equipment_import"),
        {"file": SimpleUploadedFile(filename, text.encode())},
    )


def test_staff_gets_403(client, staff_user):
    client.force_login(staff_user)
    assert client.get(reverse("equipment_import")).status_code == 403


def test_get_shows_form(engineer_client):
    response = engineer_client.get(reverse("equipment_import"))
    assert response.status_code == 200
    assert b"sample" in response.content.lower()


def test_preview_lists_rows_without_importing(engineer_client, department):
    response = _upload(engineer_client)
    assert response.status_code == 200
    assert b"SN-77" in response.content
    assert Equipment.objects.count() == 0


def test_confirm_imports_valid_rows(engineer_client, department):
    _upload(engineer_client)
    response = engineer_client.post(reverse("equipment_import_confirm"), follow=True)
    assert b"1 imported" in response.content
    assert Equipment.objects.get(serial_number="SN-77").extra == {
        "ward_notes": "3rd floor"
    }


def test_confirm_without_preview_redirects(engineer_client):
    response = engineer_client.post(reverse("equipment_import_confirm"))
    assert response.status_code == 302


def test_bad_file_shows_error(engineer_client):
    response = _upload(engineer_client, text="only-header")
    assert response.status_code == 200
    assert b"header row" in response.content

import io

import pytest
from django.core.exceptions import PermissionDenied
from openpyxl import Workbook

from apps.core.models import AuditLog
from apps.equipment.importer import (
    ImportFormatError,
    import_rows,
    parse_upload,
    validate_rows,
)
from apps.equipment.models import Equipment


def _csv(text: str) -> io.BytesIO:
    return io.BytesIO(text.encode("utf-8"))


def test_parse_csv_maps_headers_to_rows():
    f = _csv("Name,Serial_Number,department\nVentilator, SN-1 ,ICU\n")
    rows = parse_upload(f, "equip.csv")
    expected = [{"name": "Ventilator", "serial_number": "SN-1", "department": "ICU"}]
    assert rows == expected


def test_parse_csv_empty_cells_become_empty_strings():
    f = _csv("name,serial_number,department,vendor\nX,SN-2,ICU,\n")
    assert parse_upload(f, "e.csv")[0]["vendor"] == ""


def test_parse_xlsx():
    wb = Workbook()
    ws = wb.active
    ws.append(["name", "serial_number", "department"])
    ws.append(["Pump", "SN-3", "ICU"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    rows = parse_upload(buf, "equip.xlsx")
    expected = [{"name": "Pump", "serial_number": "SN-3", "department": "ICU"}]
    assert rows == expected


def test_parse_rejects_unknown_extension():
    with pytest.raises(ImportFormatError):
        parse_upload(_csv("x"), "equip.pdf")


def test_parse_rejects_file_without_rows():
    with pytest.raises(ImportFormatError):
        parse_upload(_csv(""), "equip.csv")


def test_parse_row_with_more_cells_than_headers_keeps_extras():
    f = _csv("name,serial_number,department\nPump,SN-1,ICU,stray\n")
    rows = parse_upload(f, "e.csv")
    assert rows[0]["column_4"] == "stray"


def _row(**overrides):
    row = {"name": "Ventilator", "serial_number": "SN-10", "department": "ICU"}
    row.update(overrides)
    return row


def test_validate_ok_row(department):
    results = validate_rows([_row()])
    assert results[0].ok and results[0].line == 2
    assert results[0].data["name"] == "Ventilator"
    assert results[0].department_name == "ICU"


def test_validate_missing_required(department):
    results = validate_rows([_row(serial_number="")])
    assert not results[0].ok
    assert any("serial_number" in e for e in results[0].errors)


def test_validate_duplicate_serial_within_file(department):
    results = validate_rows([_row(), _row(name="Copy")])
    assert results[0].ok and not results[1].ok


def test_validate_duplicate_serial_in_db(equipment):
    results = validate_rows([_row(serial_number=equipment.serial_number)])
    assert any("already exists" in e for e in results[0].errors)


def test_validate_unknown_department_errors_unless_flag(db):
    assert not validate_rows([_row(department="Ghost")])[0].ok
    result = validate_rows(
        [_row(department="Ghost")], create_missing_departments=True
    )
    assert result[0].ok


def test_validate_bad_date(department):
    results = validate_rows([_row(purchase_date="31/12/2020")])
    assert any("purchase_date" in e for e in results[0].errors)


def test_validate_good_optionals_and_extra(department):
    row = _row(
        purchase_date="2020-12-31",
        is_critical_asset="Yes",
        ward_notes="3rd floor",
    )
    r = validate_rows([row])[0]
    assert r.ok
    assert str(r.data["purchase_date"]) == "2020-12-31"
    assert r.data["is_critical_asset"] is True
    assert r.extra == {"ward_notes": "3rd floor"}


def test_import_creates_valid_rows_and_skips_errors(engineer, department):
    results = validate_rows([_row(), _row(serial_number="")])
    summary = import_rows(engineer, results)
    assert summary.created == 1
    assert len(summary.skipped) == 1
    assert Equipment.objects.filter(serial_number="SN-10").exists()


def test_import_writes_audit_log(engineer, department):
    import_rows(engineer, validate_rows([_row()]))
    assert AuditLog.objects.filter(verb="equipment.created").count() == 1


def test_import_creates_missing_departments_when_flagged(engineer, db):
    results = validate_rows([_row(department="Ghost")], create_missing_departments=True)
    summary = import_rows(engineer, results, create_missing_departments=True)
    assert summary.created == 1
    from apps.equipment.models import Department

    assert Department.objects.filter(name="Ghost").exists()


def test_import_extra_columns_land_in_jsonb(engineer, department):
    results = validate_rows([_row(ward_notes="3rd floor")])
    import_rows(engineer, results)
    assert Equipment.objects.get(serial_number="SN-10").extra == {
        "ward_notes": "3rd floor"
    }


def test_import_rejects_staff(staff_user, department):
    with pytest.raises(PermissionDenied):
        import_rows(staff_user, validate_rows([_row()]))

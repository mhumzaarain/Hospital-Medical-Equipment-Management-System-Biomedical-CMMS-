import io

import pytest
from openpyxl import Workbook

from apps.equipment.importer import ImportFormatError, parse_upload


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

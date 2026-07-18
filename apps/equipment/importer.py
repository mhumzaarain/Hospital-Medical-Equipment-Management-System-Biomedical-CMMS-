"""Equipment bulk import: parse → validate (dry run) → import.

Pure functions; no HTTP concerns. Views feed files in and render the results.
"""

import csv
import io


class ImportFormatError(Exception):
    pass


def parse_upload(file_obj, filename) -> list[dict]:
    """Return one {header: cell} dict per data row. Headers lower-cased and
    stripped; values stringified and stripped ("" for empty cells)."""
    name = filename.lower()
    if name.endswith(".csv"):
        raw = file_obj.read().decode("utf-8-sig")
        table = list(csv.reader(io.StringIO(raw)))
    elif name.endswith(".xlsx"):
        from openpyxl import load_workbook

        ws = load_workbook(file_obj, read_only=True, data_only=True).active
        table = [list(row) for row in ws.iter_rows(values_only=True)]
    else:
        raise ImportFormatError("Only .csv and .xlsx files are supported.")

    table = [row for row in table if any(c not in (None, "") for c in row)]
    if len(table) < 2:
        raise ImportFormatError("File needs a header row and at least one data row.")

    headers = [str(h or "").strip().lower() for h in table[0]]
    rows = []
    for raw_row in table[1:]:
        cells = ["" if c is None else str(c).strip() for c in raw_row]
        row_dict = dict(zip(headers, cells[:len(headers)]))
        # Add extra cells beyond header count with synthetic keys (column_N)
        for i, cell in enumerate(cells[len(headers):], start=len(headers) + 1):
            if cell:  # Only add non-empty extra cells
                row_dict[f"column_{i}"] = cell
        rows.append(row_dict)
    return rows

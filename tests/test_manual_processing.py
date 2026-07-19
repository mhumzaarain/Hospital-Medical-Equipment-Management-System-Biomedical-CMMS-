import pytest

from apps.ai import manuals
from apps.ai.models import ManualStatus, ServiceManual


@pytest.fixture(autouse=True)
def isolated_media_root(settings, tmp_path):
    # process() operates on manual.file; keep any incidental file I/O out of
    # the real project media/ directory.
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def manual(db, engineer):
    return ServiceManual.objects.create(
        manufacturer="Hamilton", model_number="C2",
        title="C2 Manual", uploaded_by=engineer,
    )


def test_chunk_pages_windows_and_page_ranges():
    # 3 pages x 1000 chars; windows of 1500 stepping 1300 → 3 chunks at
    # offsets 0, 1300, 2600 covering pages (1,2), (2,3), (3,3).
    pages = ["A" * 1000, "B" * 1000, "C" * 1000]
    chunks = manuals.chunk_pages(pages, size=1500, overlap=200)
    assert [(start, end) for _, start, end in chunks] == [(1, 2), (2, 3), (3, 3)]
    assert len(chunks[0][0]) == 1500
    assert len(chunks[2][0]) == 400  # tail window


def test_chunk_pages_short_doc_single_chunk():
    chunks = manuals.chunk_pages(["short text"], size=1500, overlap=200)
    assert chunks == [("short text", 1, 1)]


def test_process_marks_scanned_pdf_failed(manual, monkeypatch):
    monkeypatch.setattr(manuals, "extract_pages", lambda f: ["", " ", ""])
    manuals.process(manual)
    manual.refresh_from_db()
    assert manual.status == ManualStatus.FAILED
    assert "scanned" in manual.status_note


def test_process_creates_searchable_chunks(manual, monkeypatch):
    page = "The NO OXYGEN alarm indicates a blocked O2 supply line. " * 40
    monkeypatch.setattr(manuals, "extract_pages", lambda f: [page, page])
    manuals.process(manual)
    manual.refresh_from_db()
    assert manual.status == ManualStatus.READY and manual.page_count == 2
    assert manual.chunks.count() >= 1
    assert manual.chunks.filter(search__isnull=False).count() == manual.chunks.count()


def test_process_replaces_old_chunks(manual, monkeypatch):
    monkeypatch.setattr(manuals, "extract_pages", lambda f: ["some text " * 50])
    manuals.process(manual)
    first_ids = set(manual.chunks.values_list("id", flat=True))
    manuals.process(manual)
    assert set(manual.chunks.values_list("id", flat=True)).isdisjoint(first_ids)

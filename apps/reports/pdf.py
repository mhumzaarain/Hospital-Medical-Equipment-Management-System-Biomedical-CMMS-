"""PDF rendering. WeasyPrint imports stay inside the function: Windows dev
machines without GTK can still run everything else; tests monkeypatch this."""

from django.template.loader import render_to_string


def render_monthly_pdf(report) -> bytes:
    from weasyprint import HTML

    html = render_to_string(
        "reports/pdf/monthly.html", {"report": report, "m": report.metrics}
    )
    return HTML(string=html).write_pdf()

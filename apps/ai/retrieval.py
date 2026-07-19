"""Postgres FTS retrieval for the assistant (spec §5-§6). The manual is
always pre-filtered to the device's model — FTS only finds sections within
one known manual, never the device itself."""

import re

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import F, Q

from apps.maintenance.models import WorkOrder, WorkOrderStatus


def _queries(query_text):
    yield SearchQuery(query_text, search_type="websearch")
    words = re.findall(r"\w+", query_text)
    if len(words) > 1:
        yield SearchQuery(" OR ".join(words), search_type="websearch")


def manual_sections(manual, query_text, k=5):
    for query in _queries(query_text):
        rows = list(
            manual.chunks.filter(search=query)
            .annotate(rank=SearchRank(F("search"), query))
            .order_by("-rank")[:k]
        )
        if rows:
            return rows
    return []


def similar_repairs(equipment, query_text, k=3):
    for query in _queries(query_text):
        work_orders = (
            WorkOrder.objects.filter(
                status=WorkOrderStatus.COMPLETED,
                equipment__manufacturer__iexact=equipment.manufacturer,
                equipment__model_number__iexact=equipment.model_number,
            )
            .filter(
                Q(complaints__description__search=query)
                | Q(remarks__text__search=query)
            )
            .distinct()
            .order_by("-repair_completed_at")
            .prefetch_related("complaints", "remarks")[:k]
        )
        rows = [
            {
                "wo_id": wo.id,
                "completed_at": wo.repair_completed_at,
                "fault_category": wo.get_fault_category_display()
                if wo.fault_category
                else "",
                "remarks": [r.text for r in wo.remarks.all()],
                "complaints": [c.description for c in wo.complaints.all()],
            }
            for wo in work_orders
        ]
        if rows:
            return rows
    return []

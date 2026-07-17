"""Dashboard/report numbers. Numbers come from SQL/ORM — never from an LLM.
No MTTR and no SLA metrics anywhere (spec sections 7 and 9)."""

from collections import defaultdict

from django.db.models import Count, Q

from apps.accounts.models import Roles, User
from apps.equipment.models import Equipment
from apps.maintenance.models import (
    CloseReason,
    Complaint,
    FaultCategory,
    Remark,
    RemarkKind,
    WorkOrder,
    WorkOrderStatus,
)


def _downtime_start(wo):
    first = min((c.created_at for c in wo.complaints.all()), default=None)
    return first or wo.opened_at


def _overlap_hours(start, end, window_start, window_end):
    lo, hi = max(start, window_start), min(end, window_end)
    return max((hi - lo).total_seconds() / 3600.0, 0.0)


def critical_downtime_by_department(window_start, window_end):
    totals = defaultdict(float)
    work_orders = (
        WorkOrder.objects.filter(equipment__is_critical_asset=True)
        .exclude(status=WorkOrderStatus.CANCELLED)
        .select_related("equipment__department")
        .prefetch_related("complaints")
    )
    for wo in work_orders:
        down_from = _downtime_start(wo)
        down_to = wo.repair_completed_at or window_end
        hours = _overlap_hours(down_from, down_to, window_start, window_end)
        if hours > 0:
            totals[wo.equipment.department.name] += hours
    return dict(totals)


def complaints_per_department(window_start, window_end):
    rows = (
        Complaint.objects.filter(created_at__range=(window_start, window_end))
        .values("equipment__department__name")
        .annotate(n=Count("id"))
        .order_by("-n")
    )
    return {r["equipment__department__name"]: r["n"] for r in rows}


def most_complained_devices(window_start, window_end, limit=10):
    rows = (
        Equipment.objects.annotate(
            n=Count(
                "complaints",
                filter=Q(complaints__created_at__range=(window_start, window_end)),
            )
        )
        .filter(n__gt=0)
        .order_by("-n")[:limit]
    )
    return [(f"{eq.name} ({eq.serial_number})", eq.n) for eq in rows]


def fault_category_counts(window_start, window_end):
    labels = dict(FaultCategory.choices)
    rows = (
        WorkOrder.objects.filter(
            status=WorkOrderStatus.COMPLETED,
            repair_completed_at__range=(window_start, window_end),
            fault_category__isnull=False,
        )
        .values("fault_category")
        .annotate(n=Count("id"))
        .order_by("-n")
    )
    return {labels[r["fault_category"]]: r["n"] for r in rows}


def repairs_completed_count(window_start, window_end):
    return WorkOrder.objects.filter(
        status=WorkOrderStatus.COMPLETED,
        repair_completed_at__range=(window_start, window_end),
    ).count()


def open_workorders_count():
    return WorkOrder.objects.filter(
        status__in=[WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS]
    ).count()


def delayed_repairs(window_start, window_end):
    delay_remarks = (
        Remark.objects.filter(
            kind=RemarkKind.DELAY,
            created_at__range=(window_start, window_end),
        )
        .select_related("work_order__equipment")
        .order_by("created_at")
    )
    latest = {}
    for remark in delay_remarks:
        latest[remark.work_order_id] = remark
    return [
        {
            "wo_id": wo_id,
            "equipment": str(r.work_order.equipment),
            "latest_delay_note": r.text,
        }
        for wo_id, r in latest.items()
    ]


def per_engineer_activity(window_start, window_end):
    users = (
        User.objects.filter(role__in=[Roles.ENGINEER, Roles.ADMIN], is_active=True)
        .annotate(
            repairs=Count(
                "workorders_participated",
                filter=Q(
                    workorders_participated__status=WorkOrderStatus.COMPLETED,
                    workorders_participated__repair_completed_at__range=(
                        window_start,
                        window_end,
                    ),
                ),
                distinct=True,
            ),
            # annotation must NOT be named "complaints_closed" — that name is
            # taken by the reverse accessor of Complaint.closed_by and Django
            # raises a conflict error for it
            closed_count=Count(
                "complaints_closed",
                filter=Q(
                    complaints_closed__closed_at__range=(window_start, window_end),
                    complaints_closed__close_reason__in=[
                        CloseReason.DUPLICATE,
                        CloseReason.NO_FAULT,
                    ],
                ),
                distinct=True,
            ),
        )
        .order_by("-repairs")
    )
    return [
        {
            "name": u.get_full_name() or u.username,
            "employee_id": u.employee_id,
            "repairs": u.repairs,
            "complaints_closed": u.closed_count,
        }
        for u in users
        if u.repairs or u.closed_count
    ]

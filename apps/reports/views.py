import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from . import metrics


@login_required
def dashboard(request):
    if not request.user.is_engineer_or_admin:
        raise PermissionDenied
    window_end = timezone.now()
    window_start = window_end - timedelta(days=30)
    downtime = metrics.critical_downtime_by_department(window_start, window_end)
    complaints = metrics.complaints_per_department(window_start, window_end)
    devices = metrics.most_complained_devices(window_start, window_end)
    faults = metrics.fault_category_counts(window_start, window_end)
    context = {
        "repairs_completed": metrics.repairs_completed_count(window_start, window_end),
        "open_workorders": metrics.open_workorders_count(),
        "delayed": metrics.delayed_repairs(window_start, window_end),
        "resolved": metrics.per_engineer_resolved(window_start, window_end),
        "confirmations": metrics.recent_confirmations(window_start, window_end),
        "downtime_json": json.dumps(
            {
                "labels": list(downtime.keys()),
                "values": [round(v, 1) for v in downtime.values()],
            }
        ),
        "complaints_json": json.dumps(
            {"labels": list(complaints.keys()), "values": list(complaints.values())}
        ),
        "devices_json": json.dumps(
            {"labels": [d[0] for d in devices], "values": [d[1] for d in devices]}
        ),
        "faults_json": json.dumps(
            {"labels": list(faults.keys()), "values": list(faults.values())}
        ),
    }
    return render(request, "reports/dashboard.html", context)


@login_required
def engineer_resolved(request, user_id):
    if not request.user.is_engineer_or_admin:
        raise PermissionDenied
    from django.contrib.auth import get_user_model

    window_end = timezone.now()
    window_start = window_end - timedelta(days=30)
    engineer = get_object_or_404(get_user_model(), pk=user_id)
    rows = metrics.resolved_complaints_for_engineer(engineer, window_start, window_end)
    return render(
        request,
        "reports/engineer_resolved.html",
        {
            "engineer": engineer,
            "rows": rows,
            "total": len(rows),
        },
    )

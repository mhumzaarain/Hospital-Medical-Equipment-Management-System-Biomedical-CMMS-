from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.generic import View

from apps.accounts.mixins import RoleRequiredMixin
from apps.accounts.models import Roles

from .models import ManualStatus, ServiceManual

ENGINEER_ROLES = (Roles.ENGINEER, Roles.ADMIN)


class ManualListView(RoleRequiredMixin, View):
    allowed_roles = ENGINEER_ROLES

    def get(self, request):
        return render(
            request,
            "ai/manuals.html",
            {"manuals": ServiceManual.objects.order_by("manufacturer", "model_number")},
        )

    def post(self, request):
        from . import tasks

        manufacturer = request.POST.get("manufacturer", "").strip()
        model_number = request.POST.get("model_number", "").strip()
        title = request.POST.get("title", "").strip()
        upload = request.FILES.get("file")
        if not all([manufacturer, model_number, title, upload]):
            messages.error(request, "All fields including the PDF are required.")
            return redirect("manual_list")
        manual, _ = ServiceManual.objects.update_or_create(
            manufacturer__iexact=manufacturer,
            model_number__iexact=model_number,
            defaults={
                "manufacturer": manufacturer,
                "model_number": model_number,
                "title": title,
                "file": upload,
                "uploaded_by": request.user,
                "status": ManualStatus.PROCESSING,
                "status_note": "",
            },
        )
        tasks.process_manual.defer(manual_id=manual.id)
        messages.success(request, f"{title} uploaded — processing in background.")
        return redirect("manual_list")

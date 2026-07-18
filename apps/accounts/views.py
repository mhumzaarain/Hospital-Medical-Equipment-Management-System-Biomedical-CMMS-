from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


@login_required
def home(request):
    if request.user.is_engineer_or_admin:
        return redirect("complaint_queue")
    return redirect("my_complaints")

from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path(
        "engineer/<int:user_id>/resolved/",
        views.engineer_resolved,
        name="engineer_resolved",
    ),
    path("reports/", views.report_list, name="report_list"),
    path("reports/generate/", views.report_generate, name="report_generate"),
    path("reports/<int:pk>/download/", views.report_download, name="report_download"),
]

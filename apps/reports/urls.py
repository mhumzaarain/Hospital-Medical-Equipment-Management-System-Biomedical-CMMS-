from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("engineer/<int:user_id>/resolved/", views.engineer_resolved,
         name="engineer_resolved"),
]

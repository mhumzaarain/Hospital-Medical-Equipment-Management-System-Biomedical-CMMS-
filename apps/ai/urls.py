from django.urls import path

from . import views

urlpatterns = [
    path("manuals/", views.ManualListView.as_view(), name="manual_list"),
]

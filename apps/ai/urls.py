from django.urls import path

from . import views

urlpatterns = [
    path("manuals/", views.ManualListView.as_view(), name="manual_list"),
    path(
        "assistant/<int:equipment_id>/",
        views.AssistantMessagesView.as_view(),
        name="assistant_messages",
    ),
    path(
        "assistant/<int:equipment_id>/send/",
        views.AssistantSendView.as_view(),
        name="assistant_send",
    ),
]

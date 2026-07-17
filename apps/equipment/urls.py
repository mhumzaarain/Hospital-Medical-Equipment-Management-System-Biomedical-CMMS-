from django.urls import path

from . import views

urlpatterns = [
    path("", views.EquipmentListView.as_view(), name="equipment_list"),
    path("search/", views.EquipmentSearchView.as_view(), name="equipment_search"),
    path("new/", views.EquipmentCreateView.as_view(), name="equipment_create"),
    path("<int:pk>/", views.EquipmentDetailView.as_view(), name="equipment_detail"),
    path("<int:pk>/edit/", views.EquipmentEditView.as_view(), name="equipment_edit"),
    path("<int:pk>/condemn/", views.EquipmentCondemnView.as_view(),
         name="equipment_condemn"),
]

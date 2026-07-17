from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("equipment/", include("apps.equipment.urls")),
    path("maintenance/", include("apps.maintenance.urls")),
]

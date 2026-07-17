from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "employee_id", "role", "first_name", "last_name")
    fieldsets = UserAdmin.fieldsets + (("CMMS", {"fields": ("employee_id", "role")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("CMMS", {"fields": ("employee_id", "role")}),
    )

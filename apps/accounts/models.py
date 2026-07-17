from django.contrib.auth.models import AbstractUser
from django.db import models


class Roles(models.TextChoices):
    STAFF = "staff", "Staff"
    ENGINEER = "engineer", "Biomedical Engineer"
    ADMIN = "admin", "Admin"


class User(AbstractUser):
    employee_id = models.CharField(max_length=30, unique=True)
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.STAFF)
    department = models.ForeignKey(
        "equipment.Department",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="users",
    )

    REQUIRED_FIELDS = ["employee_id"]

    @property
    def is_engineer_or_admin(self) -> bool:
        return self.role in (Roles.ENGINEER, Roles.ADMIN)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.employee_id})"

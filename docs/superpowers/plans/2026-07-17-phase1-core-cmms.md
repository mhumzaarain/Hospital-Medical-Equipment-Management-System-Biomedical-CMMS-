# Biomedical CMMS — Phase 1 (Core CMMS) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete Phase 1 CMMS: accounts/roles, equipment registry with immutable status events and condemnation cascade, complaint → work-order workflow with manual duplicate rules, audit log, HTMX complaint queue, dashboard, demo seed data, and Docker Compose deployment. Zero AI dependencies.

**Architecture:** Server-rendered Django with all state changes flowing through per-app `services.py` functions (views stay thin). Append-only event tables (`StatusEvent`, `Remark`, `AuditLog`) provide the audit trail; `Equipment.status` is a denormalized cache always written in the same transaction as its `StatusEvent`. Spec: `docs/superpowers/specs/2026-07-17-biomedical-cmms-design.md`.

**Tech Stack:** Python 3.12, Django ~5.2, PostgreSQL (psycopg 3), pytest-django, HTMX + Alpine.js + Chart.js (vendored static files), Tailwind CSS standalone CLI (no Node), Procrastinate (wiring only in Phase 1), Gunicorn + Nginx via Docker Compose.

## Global Constraints

- **Equipment can NEVER be deleted** — no delete views, admin delete disabled, `delete()` and bulk queryset delete raise.
- **Append-only tables:** `StatusEvent`, `Remark`, `AuditLog` — updates and deletes raise; insert only.
- **All state changes go through `services.py`** — views and admin never write `Equipment.status`, close complaints, or mutate work orders directly.
- **Role checks live in services too** (not just view mixins): mutating services raise `django.core.exceptions.PermissionDenied` unless actor role is `engineer` or `admin`.
- **Status machine:** `working → in_repair`, `in_repair → working`, `working|in_repair → condemned`. `condemned` is terminal.
- **At most one non-closed WorkOrder per device** (partial unique constraint, name `one_active_workorder_per_equipment`).
- **Complaints blocked** when equipment is `in_repair` or `condemned`; auto-attach when an `open` work order exists.
- **Completing a WorkOrder requires `fault_category`.**
- **No SLA, no MTTR, no triage, no embeddings, no QR codes** — excluded by spec §9. Do not add them.
- **Timestamps stored UTC** (`USE_TZ=True`); display timezone from `TIME_ZONE` env var.
- All timestamps come from `django.utils.timezone.now()` — never `datetime.now()`.
- Settings module for all commands/tests: `config.settings.dev` (pytest.ini sets it).
- Python deps pinned in `requirements.txt`; commit after every green test cycle.
- Local dev/test database: Postgres via `docker compose up -d db` (localhost:5432, db/user/password `cmms`). Tests will not run on SQLite (JSONField + partial constraints must match prod).

---

### Task 1: Project scaffold

**Files:**
- Create: `requirements.txt`, `pytest.ini`, `.gitignore`, `.env.example`, `manage.py`, `docker-compose.yml` (db only for now), `config/__init__.py`, `config/settings/__init__.py`, `config/settings/base.py`, `config/settings/dev.py`, `config/settings/prod.py`, `config/urls.py`, `config/wsgi.py`, `apps/__init__.py`, and empty app packages `apps/accounts`, `apps/core`, `apps/equipment`, `apps/maintenance`, `apps/reports` (each with `__init__.py`, `apps.py`, `models.py`, `migrations/__init__.py`), `templates/.gitkeep`, `static/.gitkeep`, `tests/__init__.py`, `tests/test_smoke.py`, `conftest.py`

**Interfaces:**
- Produces: importable settings `config.settings.dev`; app labels `accounts`, `core`, `equipment`, `maintenance`, `reports` under the `apps.` package; a running Postgres at localhost:5432.

- [ ] **Step 1: Create the dependency and config files**

`requirements.txt`:
```
Django~=5.2
psycopg[binary]~=3.2
procrastinate[django]~=3.5
gunicorn~=23.0
pytest~=8.3
pytest-django~=4.9
```

`pytest.ini`:
```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings.dev
python_files = test_*.py
testpaths = tests
```

`.gitignore`:
```
__pycache__/
*.pyc
.env
staticfiles/
bin/
.pytest_cache/
```

`.env.example`:
```
SECRET_KEY=change-me
DEBUG=1
ALLOWED_HOSTS=localhost,127.0.0.1
POSTGRES_DB=cmms
POSTGRES_USER=cmms
POSTGRES_PASSWORD=cmms
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
TIME_ZONE=Asia/Karachi
HOSPITAL_NAME=Demo General Hospital
```

`docker-compose.yml` (extended in Task 15):
```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: cmms
      POSTGRES_USER: cmms
      POSTGRES_PASSWORD: cmms
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U cmms"]
      interval: 5s
      timeout: 3s
      retries: 10
volumes:
  pgdata:
```

- [ ] **Step 2: Create the Django project files**

`manage.py`:
```python
#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
```

`config/wsgi.py`:
```python
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
application = get_wsgi_application()
```

`config/settings/base.py`:
```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-key")
DEBUG = os.environ.get("DEBUG", "0") == "1"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts",
    "apps.core",
    "apps.equipment",
    "apps.maintenance",
    "apps.reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.hospital",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "cmms"),
        "USER": os.environ.get("POSTGRES_USER", "cmms"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "cmms"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

HOSPITAL_NAME = os.environ.get("HOSPITAL_NAME", "Demo General Hospital")
```

`config/settings/dev.py`:
```python
from .base import *  # noqa: F401,F403

DEBUG = True
```

`config/settings/prod.py`:
```python
from .base import *  # noqa: F401,F403

DEBUG = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o
]
```

`config/urls.py` (app includes are added by later tasks):
```python
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
```

For each of the five apps create `apps/<name>/__init__.py` (empty), `apps/<name>/models.py` (empty), `apps/<name>/migrations/__init__.py` (empty), and `apps/<name>/apps.py`. Example for accounts — repeat for `core`, `equipment`, `maintenance`, `reports` changing the two names:
```python
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
```

`apps/core/context_processors.py`:
```python
from django.conf import settings


def hospital(request):
    return {"HOSPITAL_NAME": settings.HOSPITAL_NAME}
```

`conftest.py` (root — fixtures grow in later tasks):
```python
import pytest  # noqa: F401
```

- [ ] **Step 3: Write the smoke test**

`tests/test_smoke.py`:
```python
import pytest


@pytest.mark.django_db
def test_database_roundtrip():
    from django.contrib.contenttypes.models import ContentType
    assert ContentType.objects.count() >= 0


def test_settings_load():
    from django.conf import settings
    assert settings.AUTH_USER_MODEL == "accounts.User"
    assert settings.USE_TZ is True
```

- [ ] **Step 4: Install, start db, verify**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
docker compose up -d db
python manage.py check
```
Expected: `System check identified no issues (0 silenced).`

Run: `pytest -v`
Expected: **FAILS** at this point with `Manager isn't available; 'accounts.User' has not been installed` or a migration error — that is fine and expected; `AUTH_USER_MODEL` points at a model that Task 2 creates. If instead you see a Postgres connection error, the db container isn't up.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: project scaffold - settings, apps, pytest, dev db"
```

---

### Task 2: Custom User model, roles, auth URLs

**Files:**
- Create: `apps/accounts/models.py` (replace empty), `apps/accounts/mixins.py`, `apps/accounts/admin.py`, `apps/accounts/urls.py`, `apps/accounts/views.py`, `tests/test_accounts.py`
- Modify: `config/urls.py`, `conftest.py`

**Interfaces:**
- Produces: `apps.accounts.models.User` (`employee_id: str unique`, `role: str`), `apps.accounts.models.Roles` (TextChoices: `STAFF="staff"`, `ENGINEER="engineer"`, `ADMIN="admin"`), `User.is_engineer_or_admin -> bool` property, `apps.accounts.mixins.RoleRequiredMixin` (class attr `allowed_roles: tuple`), URL names `login`, `logout`, `home`. Fixtures `staff_user`, `engineer`, `admin_user` in `conftest.py`.

- [ ] **Step 1: Write the failing tests**

`tests/test_accounts.py`:
```python
import pytest
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.django_db


def test_user_has_employee_id_and_role(staff_user):
    assert staff_user.employee_id == "EMP-001"
    assert staff_user.role == "staff"
    assert staff_user.is_engineer_or_admin is False


def test_engineer_and_admin_helper(engineer, admin_user):
    assert engineer.is_engineer_or_admin is True
    assert admin_user.is_engineer_or_admin is True


def test_employee_id_unique(staff_user):
    with pytest.raises(Exception):
        get_user_model().objects.create_user(
            username="other", password="pw", employee_id="EMP-001"
        )


def test_login_page_renders(client):
    response = client.get("/accounts/login/")
    assert response.status_code == 200


def test_home_requires_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/accounts/login/" in response.url
```

Add fixtures to `conftest.py` (replace its content):
```python
import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def staff_user(db):
    return get_user_model().objects.create_user(
        username="nurse", password="pw", employee_id="EMP-001", role="staff",
        first_name="Nadia", last_name="Khan",
    )


@pytest.fixture
def engineer(db):
    return get_user_model().objects.create_user(
        username="engineer1", password="pw", employee_id="EMP-100", role="engineer",
        first_name="Bilal", last_name="Ahmed",
    )


@pytest.fixture
def engineer2(db):
    return get_user_model().objects.create_user(
        username="engineer2", password="pw", employee_id="EMP-101", role="engineer",
    )


@pytest.fixture
def admin_user(db):
    return get_user_model().objects.create_user(
        username="boss", password="pw", employee_id="EMP-900", role="admin",
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_accounts.py -v`
Expected: errors — `accounts.User` model does not exist yet.

- [ ] **Step 3: Implement**

`apps/accounts/models.py`:
```python
from django.contrib.auth.models import AbstractUser
from django.db import models


class Roles(models.TextChoices):
    STAFF = "staff", "Staff"
    ENGINEER = "engineer", "Biomedical Engineer"
    ADMIN = "admin", "Admin"


class User(AbstractUser):
    employee_id = models.CharField(max_length=30, unique=True)
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.STAFF)
    # department FK is added in Task 4 (after equipment.Department exists)

    REQUIRED_FIELDS = ["employee_id"]

    @property
    def is_engineer_or_admin(self) -> bool:
        return self.role in (Roles.ENGINEER, Roles.ADMIN)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.employee_id})"
```

`apps/accounts/mixins.py`:
```python
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class RoleRequiredMixin(LoginRequiredMixin):
    """Page access control. Services re-check roles independently."""

    allowed_roles: tuple = ()

    def dispatch(self, request, *args, **kwargs):
        if (
            request.user.is_authenticated
            and self.allowed_roles
            and request.user.role not in self.allowed_roles
        ):
            raise PermissionDenied("Your role does not allow this page.")
        return super().dispatch(request, *args, **kwargs)
```

`apps/accounts/views.py`:
```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


@login_required
def home(request):
    if request.user.is_engineer_or_admin:
        return redirect("complaint_queue")
    return redirect("my_complaints")
```
(`complaint_queue` / `my_complaints` URLs arrive in Task 12; until then `/` redirects will 500 for logged-in users — tests only assert the login redirect, which works.)

`apps/accounts/urls.py`:
```python
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
]
```

`config/urls.py` — replace with:
```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
]
```

`apps/accounts/admin.py`:
```python
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
```

Minimal login template so `login` renders before Task 10 styles it — `templates/registration/login.html`:
```html
<form method="post">{% csrf_token %}{{ form.as_p }}<button type="submit">Log in</button></form>
```

- [ ] **Step 4: Migrate and run tests**

```powershell
python manage.py makemigrations accounts
python manage.py migrate
pytest tests/test_accounts.py tests/test_smoke.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: custom User with employee_id and roles, auth urls, role mixin"
```

---

### Task 3: Core — append-only bases, AuditLog, audit recorder

**Files:**
- Create: `apps/core/models.py` (replace empty), `apps/core/audit.py`, `apps/core/exceptions.py`, `apps/core/admin.py`, `tests/test_core.py`

**Interfaces:**
- Produces:
  - `apps.core.models.AppendOnlyModel` (abstract; update/delete raise `TypeError`), `apps.core.models.NoDeleteModel` (abstract; delete raises), `apps.core.models.ProtectedQuerySet` (bulk `delete()` and `update()` allowed? — bulk `delete()` raises; `update()` allowed for seed backdating).
  - `apps.core.models.AuditLog` (fields: `actor`, `verb: str`, `content_type`, `object_id: str`, `changes: dict`, `created_at`).
  - `apps.core.audit.record(actor, verb, obj, changes=None) -> AuditLog`.
  - `apps.core.exceptions`: `DomainError(Exception)`, `InvalidTransition(DomainError)`, `ComplaintNotAllowed(DomainError)`, `WorkOrderStateError(DomainError)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_core.py`:
```python
import pytest

from apps.core import audit
from apps.core.models import AuditLog

pytestmark = pytest.mark.django_db


def test_record_creates_audit_row(staff_user):
    entry = audit.record(staff_user, "user.tested", staff_user, {"a": 1})
    assert entry.pk is not None
    assert entry.verb == "user.tested"
    assert entry.actor == staff_user
    assert entry.changes == {"a": 1}
    assert entry.object_id == str(staff_user.pk)


def test_audit_log_is_append_only(staff_user):
    entry = audit.record(staff_user, "user.tested", staff_user)
    entry.verb = "user.edited"
    with pytest.raises(TypeError):
        entry.save()
    with pytest.raises(TypeError):
        entry.delete()
    with pytest.raises(TypeError):
        AuditLog.objects.all().delete()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_core.py -v`
Expected: FAIL — `ImportError` (no `audit` module / `AuditLog`).

- [ ] **Step 3: Implement**

`apps/core/models.py`:
```python
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models


class ProtectedQuerySet(models.QuerySet):
    """Bulk delete disabled. Bulk update() stays available (used by seed_demo
    to backdate auto_now_add timestamps)."""

    def delete(self):
        raise TypeError(f"Bulk delete is disabled for {self.model.__name__}")


class NoDeleteModel(models.Model):
    objects = ProtectedQuerySet.as_manager()

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        raise TypeError(f"{self.__class__.__name__} can never be deleted")


class AppendOnlyModel(NoDeleteModel):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise TypeError(f"{self.__class__.__name__} is append-only")
        super().save(*args, **kwargs)


class AuditLog(AppendOnlyModel):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT,
        related_name="audit_entries",
    )
    verb = models.CharField(max_length=100)
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.CharField(max_length=64)
    changes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.actor} {self.verb}"
```

`apps/core/audit.py`:
```python
from django.contrib.contenttypes.models import ContentType

from .models import AuditLog


def record(actor, verb, obj, changes=None) -> AuditLog:
    return AuditLog.objects.create(
        actor=actor,
        verb=verb,
        content_type=ContentType.objects.get_for_model(obj),
        object_id=str(obj.pk),
        changes=changes or {},
    )
```

`apps/core/exceptions.py`:
```python
class DomainError(Exception):
    """Base for business-rule violations; views show str(exc) to the user."""


class InvalidTransition(DomainError):
    pass


class ComplaintNotAllowed(DomainError):
    pass


class WorkOrderStateError(DomainError):
    pass
```

`apps/core/admin.py`:
```python
from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "verb", "content_type", "object_id")
    list_filter = ("verb",)
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
```

- [ ] **Step 4: Migrate and run tests**

```powershell
python manage.py makemigrations core
python manage.py migrate
pytest tests/test_core.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: append-only bases, AuditLog, audit.record, domain exceptions"
```

---

### Task 4: Equipment models (Department, Equipment, StatusEvent) + User.department

**Files:**
- Create: `apps/equipment/models.py` (replace empty), `apps/equipment/admin.py`, `tests/test_equipment_models.py`
- Modify: `apps/accounts/models.py` (add `department` FK), `conftest.py` (add fixtures)

**Interfaces:**
- Produces:
  - `apps.equipment.models.EquipmentStatus` (TextChoices: `WORKING="working"`, `IN_REPAIR="in_repair"`, `CONDEMNED="condemned"`).
  - `Department(name unique, location)`; `Equipment(name, manufacturer, vendor, model_number, serial_number unique, department FK PROTECT related_name="equipment", is_critical_asset: bool, purchase_date, installation_date, status, condemned_at, condemned_location, extra: JSON)` — no-delete.
  - `StatusEvent(equipment FK related_name="status_events", old_status, new_status, actor FK, remark, created_at)` — append-only. (`work_order` FK added in Task 6.)
  - `User.department` nullable FK (informational only).
  - Fixtures: `department`, `department2`, `equipment` (working ventilator, `serial_number="SN-0001"`), `make_equipment(**overrides)` factory fixture.

- [ ] **Step 1: Write the failing tests**

`tests/test_equipment_models.py`:
```python
import pytest
from django.db import IntegrityError

from apps.equipment.models import Equipment, EquipmentStatus, StatusEvent

pytestmark = pytest.mark.django_db


def test_equipment_defaults(equipment):
    assert equipment.status == EquipmentStatus.WORKING
    assert equipment.is_critical_asset is False
    assert equipment.extra == {}


def test_serial_number_unique(equipment, make_equipment):
    with pytest.raises(IntegrityError):
        make_equipment(serial_number="SN-0001")


def test_equipment_can_never_be_deleted(equipment):
    with pytest.raises(TypeError):
        equipment.delete()
    with pytest.raises(TypeError):
        Equipment.objects.all().delete()


def test_status_event_is_append_only(equipment, engineer):
    event = StatusEvent.objects.create(
        equipment=equipment,
        old_status=EquipmentStatus.WORKING,
        new_status=EquipmentStatus.IN_REPAIR,
        actor=engineer,
        remark="test",
    )
    event.remark = "edited"
    with pytest.raises(TypeError):
        event.save()
    with pytest.raises(TypeError):
        event.delete()


def test_user_department_is_optional(staff_user, department):
    staff_user.department = department
    staff_user.save()
    staff_user.refresh_from_db()
    assert staff_user.department == department
```

Add to `conftest.py` (below the user fixtures):
```python
from apps.equipment.models import Department, Equipment


@pytest.fixture
def department(db):
    return Department.objects.create(name="ICU", location="Block A")


@pytest.fixture
def department2(db):
    return Department.objects.create(name="Radiology", location="Block B")


@pytest.fixture
def make_equipment(department):
    def _make(**overrides):
        fields = dict(
            name="Ventilator", manufacturer="Hamilton", vendor="MedServe Ltd",
            model_number="C2", serial_number="SN-0001", department=department,
        )
        fields.update(overrides)
        return Equipment.objects.create(**fields)
    return _make


@pytest.fixture
def equipment(make_equipment):
    return make_equipment()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_equipment_models.py -v`
Expected: FAIL — models don't exist.

- [ ] **Step 3: Implement**

`apps/equipment/models.py`:
```python
from django.conf import settings
from django.db import models

from apps.core.models import AppendOnlyModel, NoDeleteModel


class EquipmentStatus(models.TextChoices):
    WORKING = "working", "Working"
    IN_REPAIR = "in_repair", "In Repair"
    CONDEMNED = "condemned", "Condemned"


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    location = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Equipment(NoDeleteModel):
    name = models.CharField(max_length=200)
    manufacturer = models.CharField(max_length=200)
    vendor = models.CharField(max_length=200, blank=True)
    model_number = models.CharField(max_length=100)
    serial_number = models.CharField(max_length=100, unique=True)
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="equipment"
    )
    is_critical_asset = models.BooleanField(
        default=False,
        help_text="Downtime is tracked only for critical assets (MRI, CT, ...)",
    )
    purchase_date = models.DateField(null=True, blank=True)
    installation_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=EquipmentStatus.choices, default=EquipmentStatus.WORKING
    )
    condemned_at = models.DateTimeField(null=True, blank=True)
    condemned_location = models.CharField(max_length=200, blank=True)
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name", "serial_number"]
        verbose_name_plural = "equipment"

    def __str__(self):
        return f"{self.name} {self.model_number} ({self.serial_number})"


class StatusEvent(AppendOnlyModel):
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name="status_events"
    )
    old_status = models.CharField(max_length=20, choices=EquipmentStatus.choices)
    new_status = models.CharField(max_length=20, choices=EquipmentStatus.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="status_events"
    )
    remark = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # work_order FK is added in Task 6 (maintenance app must exist first)

    class Meta:
        ordering = ["-created_at"]
```

Add to `apps/accounts/models.py` inside `class User` (below `role`):
```python
    department = models.ForeignKey(
        "equipment.Department", null=True, blank=True,
        on_delete=models.PROTECT, related_name="users",
    )
```

`apps/equipment/admin.py`:
```python
from django.contrib import admin

from .models import Department, Equipment, StatusEvent


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "location")


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ("name", "model_number", "serial_number", "department",
                    "status", "is_critical_asset")
    list_filter = ("status", "department", "is_critical_asset")
    search_fields = ("name", "serial_number", "model_number", "manufacturer")
    readonly_fields = ("status", "condemned_at", "condemned_location")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StatusEvent)
class StatusEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "equipment", "old_status", "new_status", "actor")
    readonly_fields = [f.name for f in StatusEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
```

- [ ] **Step 4: Migrate and run tests**

```powershell
python manage.py makemigrations equipment accounts
python manage.py migrate
pytest tests/test_equipment_models.py -v
```
Expected: all PASS. (`accounts.0002` depends on `equipment.0001` — one-way, no circular migration.)

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: Department, Equipment (no-delete), append-only StatusEvent, User.department"
```

---

### Task 5: Status machine service (`transition_status`)

**Files:**
- Create: `apps/equipment/services.py`, `tests/test_status_machine.py`

**Interfaces:**
- Consumes: `EquipmentStatus`, `StatusEvent`, `apps.core.audit.record`, `apps.core.exceptions.InvalidTransition`.
- Produces: `apps.equipment.services.transition_status(equipment, new_status, actor, remark="", work_order=None) -> StatusEvent` — raises `PermissionDenied` for staff actors, `InvalidTransition` for illegal moves; atomically updates cached `Equipment.status`, inserts `StatusEvent`, writes AuditLog verb `"equipment.status_changed"`. Also `ALLOWED_TRANSITIONS` dict and `_require_engineer_or_admin(actor)` helper (reused by Tasks 8–9).

- [ ] **Step 1: Write the failing tests**

`tests/test_status_machine.py`:
```python
import pytest
from django.core.exceptions import PermissionDenied

from apps.core.exceptions import InvalidTransition
from apps.core.models import AuditLog
from apps.equipment.models import EquipmentStatus, StatusEvent
from apps.equipment.services import transition_status

pytestmark = pytest.mark.django_db


def test_working_to_in_repair(equipment, engineer):
    event = transition_status(
        equipment, EquipmentStatus.IN_REPAIR, engineer, remark="starting"
    )
    equipment.refresh_from_db()
    assert equipment.status == EquipmentStatus.IN_REPAIR
    assert event.old_status == EquipmentStatus.WORKING
    assert event.new_status == EquipmentStatus.IN_REPAIR
    assert event.actor == engineer
    assert AuditLog.objects.filter(verb="equipment.status_changed").count() == 1


def test_in_repair_back_to_working(equipment, engineer):
    transition_status(equipment, EquipmentStatus.IN_REPAIR, engineer)
    equipment.refresh_from_db()
    transition_status(equipment, EquipmentStatus.WORKING, engineer)
    equipment.refresh_from_db()
    assert equipment.status == EquipmentStatus.WORKING
    assert StatusEvent.objects.filter(equipment=equipment).count() == 2


def test_working_to_working_is_illegal(equipment, engineer):
    with pytest.raises(InvalidTransition):
        transition_status(equipment, EquipmentStatus.WORKING, engineer)


def test_condemned_is_terminal(equipment, engineer):
    transition_status(equipment, EquipmentStatus.CONDEMNED, engineer)
    equipment.refresh_from_db()
    for target in (EquipmentStatus.WORKING, EquipmentStatus.IN_REPAIR):
        with pytest.raises(InvalidTransition):
            transition_status(equipment, target, engineer)


def test_staff_cannot_transition(equipment, staff_user):
    with pytest.raises(PermissionDenied):
        transition_status(equipment, EquipmentStatus.IN_REPAIR, staff_user)
    equipment.refresh_from_db()
    assert equipment.status == EquipmentStatus.WORKING
    assert StatusEvent.objects.count() == 0


def test_admin_can_transition(equipment, admin_user):
    transition_status(equipment, EquipmentStatus.IN_REPAIR, admin_user)
    equipment.refresh_from_db()
    assert equipment.status == EquipmentStatus.IN_REPAIR
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_status_machine.py -v`
Expected: FAIL — `apps.equipment.services` does not exist.

- [ ] **Step 3: Implement**

`apps/equipment/services.py`:
```python
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.core import audit
from apps.core.exceptions import InvalidTransition

from .models import Equipment, EquipmentStatus, StatusEvent

ALLOWED_TRANSITIONS = {
    EquipmentStatus.WORKING: {EquipmentStatus.IN_REPAIR, EquipmentStatus.CONDEMNED},
    EquipmentStatus.IN_REPAIR: {EquipmentStatus.WORKING, EquipmentStatus.CONDEMNED},
    EquipmentStatus.CONDEMNED: set(),
}


def _require_engineer_or_admin(actor):
    if not actor.is_engineer_or_admin:
        raise PermissionDenied("Only engineers or admins may do this.")


@transaction.atomic
def transition_status(equipment, new_status, actor, remark="", work_order=None):
    """The single choke point for equipment status. Nothing else writes
    Equipment.status. `work_order` is accepted now but only persisted from
    Task 6 onward (the StatusEvent.work_order column arrives there)."""
    _require_engineer_or_admin(actor)
    equipment = Equipment.objects.select_for_update().get(pk=equipment.pk)
    old_status = equipment.status
    if new_status not in ALLOWED_TRANSITIONS[old_status]:
        raise InvalidTransition(f"Cannot go from {old_status} to {new_status}.")
    equipment.status = new_status
    equipment.save(update_fields=["status"])
    event = StatusEvent.objects.create(
        equipment=equipment, old_status=old_status, new_status=new_status,
        actor=actor, remark=remark,
    )
    audit.record(actor, "equipment.status_changed", equipment,
                 {"old": old_status, "new": new_status, "remark": remark})
    return event
```
(Task 6 changes the `StatusEvent.objects.create(...)` call to also pass `work_order=work_order`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_status_machine.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: transition_status service with role checks and audit trail"
```

---

### Task 6: Maintenance models (Complaint, WorkOrder, Remark) + StatusEvent.work_order

**Files:**
- Create: `apps/maintenance/models.py` (replace empty), `apps/maintenance/admin.py`, `tests/test_maintenance_models.py`
- Modify: `apps/equipment/models.py` (add `StatusEvent.work_order`), `apps/equipment/services.py` (pass `work_order` through), `conftest.py` (add `work_order` factory fixture)

**Interfaces:**
- Consumes: `Equipment`, `EquipmentStatus`, `AppendOnlyModel`, `NoDeleteModel`, `User`.
- Produces (all in `apps.maintenance.models`):
  - `ComplaintStatus` (TextChoices: `OPEN="open"`, `ATTACHED="attached"`, `CLOSED="closed"`)
  - `CloseReason` (TextChoices: `RESOLVED="resolved"`, `DUPLICATE="duplicate"`, `NO_FAULT="no_fault"`)
  - `WorkOrderStatus` (TextChoices: `OPEN="open"`, `IN_PROGRESS="in_progress"`, `COMPLETED="completed"`, `CANCELLED="cancelled"`)
  - `WorkOrderOutcome` (TextChoices: `REPAIRED="repaired"`, `CONDEMNED="condemned"`)
  - `FaultCategory` (TextChoices: `ELECTRICAL="electrical"`, `BATTERY_POWER="battery_power"`, `DISPLAY_MONITOR="display_monitor"`, `MECHANICAL="mechanical"`, `CALIBRATION="calibration"`, `SOFTWARE="software"`, `ACCESSORY_PROBE="accessory_probe"`, `OTHER="other"`)
  - `RemarkKind` (TextChoices: `NOTE="note"`, `DELAY="delay"`, `SYSTEM="system"`)
  - `Complaint(equipment FK related_name="complaints", reporter FK related_name="complaints_reported", description, created_at, status, work_order FK null related_name="complaints", close_reason null, duplicate_of self-FK null related_name="duplicates", close_note, closed_by FK null related_name="complaints_closed", closed_at null)` — no-delete
  - `WorkOrder(equipment FK related_name="work_orders", status, opened_by FK related_name="workorders_opened", opened_at auto, repair_started_at null, repair_completed_at null, closed_by FK null related_name="workorders_closed", closed_at null, outcome null, fault_category null, participants M2M related_name="workorders_participated")` — no-delete; partial unique constraint `one_active_workorder_per_equipment` on `equipment` where status not in (completed, cancelled). Property `is_active -> bool`.
  - `Remark(work_order FK related_name="remarks", author FK, text, kind, created_at)` — append-only
  - `StatusEvent.work_order` nullable FK → `maintenance.WorkOrder`, related_name `"status_events"`
  - Fixture `make_work_order(equipment=None, **overrides)` in conftest.

- [ ] **Step 1: Write the failing tests**

`tests/test_maintenance_models.py`:
```python
import pytest
from django.db import IntegrityError, transaction

from apps.maintenance.models import (
    Remark, RemarkKind, WorkOrder, WorkOrderStatus,
)

pytestmark = pytest.mark.django_db


def test_only_one_active_workorder_per_equipment(equipment, engineer, make_work_order):
    make_work_order(status=WorkOrderStatus.OPEN)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            make_work_order(status=WorkOrderStatus.IN_PROGRESS)


def test_closed_workorders_do_not_block_new_ones(equipment, make_work_order):
    make_work_order(status=WorkOrderStatus.COMPLETED)
    make_work_order(status=WorkOrderStatus.CANCELLED)
    wo = make_work_order(status=WorkOrderStatus.OPEN)
    assert wo.is_active is True


def test_remark_is_append_only(engineer, make_work_order):
    wo = make_work_order()
    remark = Remark.objects.create(
        work_order=wo, author=engineer, text="checking", kind=RemarkKind.NOTE
    )
    remark.text = "edited"
    with pytest.raises(TypeError):
        remark.save()
    with pytest.raises(TypeError):
        remark.delete()


def test_workorder_cannot_be_deleted(make_work_order):
    wo = make_work_order()
    with pytest.raises(TypeError):
        wo.delete()
    with pytest.raises(TypeError):
        WorkOrder.objects.all().delete()
```

Add to `conftest.py`:
```python
from apps.maintenance.models import WorkOrder, WorkOrderStatus


@pytest.fixture
def make_work_order(equipment, engineer):
    def _make(eq=None, **overrides):
        fields = dict(
            equipment=eq or equipment,
            status=WorkOrderStatus.OPEN,
            opened_by=engineer,
        )
        fields.update(overrides)
        return WorkOrder.objects.create(**fields)
    return _make
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_maintenance_models.py -v`
Expected: FAIL — models don't exist.

- [ ] **Step 3: Implement**

`apps/maintenance/models.py`:
```python
from django.conf import settings
from django.db import models

from apps.core.models import AppendOnlyModel, NoDeleteModel
from apps.equipment.models import Equipment


class ComplaintStatus(models.TextChoices):
    OPEN = "open", "Open"
    ATTACHED = "attached", "Attached to Work Order"
    CLOSED = "closed", "Closed"


class CloseReason(models.TextChoices):
    RESOLVED = "resolved", "Resolved"
    DUPLICATE = "duplicate", "Duplicate"
    NO_FAULT = "no_fault", "No Fault Found"


class WorkOrderStatus(models.TextChoices):
    OPEN = "open", "Open"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class WorkOrderOutcome(models.TextChoices):
    REPAIRED = "repaired", "Repaired"
    CONDEMNED = "condemned", "Condemned"


class FaultCategory(models.TextChoices):
    ELECTRICAL = "electrical", "Electrical"
    BATTERY_POWER = "battery_power", "Battery / Power"
    DISPLAY_MONITOR = "display_monitor", "Display / Monitor"
    MECHANICAL = "mechanical", "Mechanical"
    CALIBRATION = "calibration", "Calibration"
    SOFTWARE = "software", "Software"
    ACCESSORY_PROBE = "accessory_probe", "Accessory / Probe"
    OTHER = "other", "Other"


class RemarkKind(models.TextChoices):
    NOTE = "note", "Note"
    DELAY = "delay", "Delay"
    SYSTEM = "system", "System"


ACTIVE_WORKORDER_STATUSES = (WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS)


class WorkOrder(NoDeleteModel):
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name="work_orders"
    )
    status = models.CharField(
        max_length=20, choices=WorkOrderStatus.choices, default=WorkOrderStatus.OPEN
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="workorders_opened",
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    repair_started_at = models.DateTimeField(null=True, blank=True)
    repair_completed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="workorders_closed",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    outcome = models.CharField(
        max_length=20, choices=WorkOrderOutcome.choices, null=True, blank=True
    )
    fault_category = models.CharField(
        max_length=30, choices=FaultCategory.choices, null=True, blank=True,
        help_text="Required when completing a repair.",
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="workorders_participated",
        help_text="Engineers who worked on this repair.",
    )

    class Meta:
        ordering = ["-opened_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["equipment"],
                condition=~models.Q(
                    status__in=[WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED]
                ),
                name="one_active_workorder_per_equipment",
            )
        ]

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_WORKORDER_STATUSES

    def __str__(self):
        return f"WO #{self.pk} — {self.equipment}"


class Complaint(NoDeleteModel):
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name="complaints"
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="complaints_reported",
    )
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, choices=ComplaintStatus.choices, default=ComplaintStatus.OPEN
    )
    work_order = models.ForeignKey(
        WorkOrder, null=True, blank=True, on_delete=models.PROTECT,
        related_name="complaints",
    )
    close_reason = models.CharField(
        max_length=20, choices=CloseReason.choices, null=True, blank=True
    )
    duplicate_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT,
        related_name="duplicates",
    )
    close_note = models.TextField(blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="complaints_closed",
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Complaint #{self.pk} — {self.equipment}"


class Remark(AppendOnlyModel):
    work_order = models.ForeignKey(
        WorkOrder, on_delete=models.PROTECT, related_name="remarks"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="remarks"
    )
    text = models.TextField()
    kind = models.CharField(
        max_length=10, choices=RemarkKind.choices, default=RemarkKind.NOTE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
```

Add to `apps/equipment/models.py`, inside `class StatusEvent` (replacing the `# work_order FK is added in Task 6` comment):
```python
    work_order = models.ForeignKey(
        "maintenance.WorkOrder", null=True, blank=True, on_delete=models.PROTECT,
        related_name="status_events",
    )
```

In `apps/equipment/services.py`, change the `StatusEvent.objects.create(...)` call inside `transition_status` to pass the work order through:
```python
    event = StatusEvent.objects.create(
        equipment=equipment, old_status=old_status, new_status=new_status,
        actor=actor, remark=remark, work_order=work_order,
    )
```

`apps/maintenance/admin.py` (read-mostly; all mutations happen in the app UI via services):
```python
from django.contrib import admin

from .models import Complaint, Remark, WorkOrder


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("id", "equipment", "reporter", "status", "close_reason", "created_at")
    list_filter = ("status", "close_reason")
    readonly_fields = [f.name for f in Complaint._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "equipment", "status", "outcome", "fault_category", "opened_at")
    list_filter = ("status", "fault_category")
    readonly_fields = [f.name for f in WorkOrder._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Remark)
class RemarkAdmin(admin.ModelAdmin):
    list_display = ("created_at", "work_order", "author", "kind")
    readonly_fields = [f.name for f in Remark._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
```

- [ ] **Step 4: Migrate and run tests**

```powershell
python manage.py makemigrations maintenance equipment
python manage.py migrate
pytest -v
```
Expected: all tests PASS (including earlier suites — the `transition_status` change is backward compatible).

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: Complaint, WorkOrder with active-uniqueness and participants, Remark"
```

---

### Task 7: Complaint services (`lodge_complaint`, `close_complaint`)

**Files:**
- Create: `apps/maintenance/services.py`, `tests/test_complaint_services.py`

**Interfaces:**
- Consumes: models from Task 6, `apps.core.audit`, `apps.core.exceptions.ComplaintNotAllowed`, `apps.equipment.services._require_engineer_or_admin`.
- Produces (in `apps.maintenance.services`):
  - `lodge_complaint(reporter, equipment, description) -> Complaint` — any authenticated user; raises `ComplaintNotAllowed` if equipment condemned or in repair; auto-attaches to an `open` work order when one exists; audit verb `"complaint.lodged"`.
  - `close_complaint(complaint, actor, close_reason, duplicate_of=None, close_note="") -> Complaint` — engineer/admin only; raises `WorkOrderStateError` if already closed; `ValueError` if reason is duplicate without `duplicate_of` and without `close_note`; audit verb `"complaint.closed"`.

- [ ] **Step 1: Write the failing tests**

`tests/test_complaint_services.py`:
```python
import pytest
from django.core.exceptions import PermissionDenied

from apps.core.exceptions import ComplaintNotAllowed, WorkOrderStateError
from apps.core.models import AuditLog
from apps.equipment.models import EquipmentStatus
from apps.equipment.services import transition_status
from apps.maintenance.models import CloseReason, ComplaintStatus, WorkOrderStatus
from apps.maintenance.services import close_complaint, lodge_complaint

pytestmark = pytest.mark.django_db


def test_staff_can_lodge_complaint(equipment, staff_user):
    complaint = lodge_complaint(staff_user, equipment, "Screen goes black")
    assert complaint.status == ComplaintStatus.OPEN
    assert complaint.reporter == staff_user
    assert complaint.work_order is None
    assert AuditLog.objects.filter(verb="complaint.lodged").count() == 1


def test_complaint_blocked_when_in_repair(equipment, staff_user, engineer, make_work_order):
    wo = make_work_order(status=WorkOrderStatus.IN_PROGRESS)
    transition_status(equipment, EquipmentStatus.IN_REPAIR, engineer, work_order=wo)
    with pytest.raises(ComplaintNotAllowed) as exc:
        lodge_complaint(staff_user, equipment, "still broken")
    assert f"Work Order #{wo.pk}" in str(exc.value)


def test_complaint_blocked_when_condemned(equipment, staff_user, engineer):
    transition_status(equipment, EquipmentStatus.CONDEMNED, engineer)
    with pytest.raises(ComplaintNotAllowed):
        lodge_complaint(staff_user, equipment, "it is broken")


def test_complaint_auto_attaches_to_open_workorder(equipment, staff_user, make_work_order):
    wo = make_work_order(status=WorkOrderStatus.OPEN)
    complaint = lodge_complaint(staff_user, equipment, "second report")
    assert complaint.status == ComplaintStatus.ATTACHED
    assert complaint.work_order == wo


def test_engineer_closes_duplicate_with_link(equipment, staff_user, engineer):
    first = lodge_complaint(staff_user, equipment, "display broken")
    second = lodge_complaint(staff_user, equipment, "screen not working")
    closed = close_complaint(
        second, engineer, CloseReason.DUPLICATE,
        duplicate_of=first, close_note="already reported",
    )
    assert closed.status == ComplaintStatus.CLOSED
    assert closed.close_reason == CloseReason.DUPLICATE
    assert closed.duplicate_of == first
    assert closed.closed_by == engineer
    assert closed.closed_at is not None


def test_duplicate_close_requires_link_or_note(equipment, staff_user, engineer):
    complaint = lodge_complaint(staff_user, equipment, "broken")
    with pytest.raises(ValueError):
        close_complaint(complaint, engineer, CloseReason.DUPLICATE)


def test_staff_cannot_close_complaints(equipment, staff_user):
    complaint = lodge_complaint(staff_user, equipment, "broken")
    with pytest.raises(PermissionDenied):
        close_complaint(complaint, staff_user, CloseReason.NO_FAULT)


def test_cannot_close_twice(equipment, staff_user, engineer):
    complaint = lodge_complaint(staff_user, equipment, "broken")
    close_complaint(complaint, engineer, CloseReason.NO_FAULT, close_note="tested ok")
    with pytest.raises(WorkOrderStateError):
        close_complaint(complaint, engineer, CloseReason.NO_FAULT)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_complaint_services.py -v`
Expected: FAIL — `apps.maintenance.services` does not exist.

- [ ] **Step 3: Implement**

`apps/maintenance/services.py`:
```python
from django.db import transaction
from django.utils import timezone

from apps.core import audit
from apps.core.exceptions import ComplaintNotAllowed, WorkOrderStateError
from apps.equipment.models import EquipmentStatus
from apps.equipment.services import _require_engineer_or_admin

from .models import (
    ACTIVE_WORKORDER_STATUSES, CloseReason, Complaint, ComplaintStatus,
    WorkOrderStatus,
)


@transaction.atomic
def lodge_complaint(reporter, equipment, description) -> Complaint:
    if equipment.status == EquipmentStatus.CONDEMNED:
        raise ComplaintNotAllowed("This equipment is condemned; complaints are closed.")
    if equipment.status == EquipmentStatus.IN_REPAIR:
        active = equipment.work_orders.filter(
            status__in=ACTIVE_WORKORDER_STATUSES
        ).first()
        wo_ref = f"Work Order #{active.pk}" if active else "a work order"
        raise ComplaintNotAllowed(
            f"This equipment is already under repair ({wo_ref})."
        )
    open_wo = equipment.work_orders.filter(status=WorkOrderStatus.OPEN).first()
    complaint = Complaint.objects.create(
        equipment=equipment,
        reporter=reporter,
        description=description,
        status=ComplaintStatus.ATTACHED if open_wo else ComplaintStatus.OPEN,
        work_order=open_wo,
    )
    audit.record(reporter, "complaint.lodged", complaint,
                 {"equipment": equipment.serial_number,
                  "attached_to": open_wo.pk if open_wo else None})
    return complaint


@transaction.atomic
def close_complaint(complaint, actor, close_reason,
                    duplicate_of=None, close_note="") -> Complaint:
    _require_engineer_or_admin(actor)
    if complaint.status == ComplaintStatus.CLOSED:
        raise WorkOrderStateError("This complaint is already closed.")
    if close_reason == CloseReason.DUPLICATE and not (duplicate_of or close_note):
        raise ValueError(
            "Closing as duplicate requires the original complaint or a note."
        )
    complaint.status = ComplaintStatus.CLOSED
    complaint.close_reason = close_reason
    complaint.duplicate_of = duplicate_of
    complaint.close_note = close_note
    complaint.closed_by = actor
    complaint.closed_at = timezone.now()
    complaint.save(update_fields=[
        "status", "close_reason", "duplicate_of", "close_note",
        "closed_by", "closed_at",
    ])
    audit.record(actor, "complaint.closed", complaint,
                 {"reason": close_reason, "duplicate_of":
                  duplicate_of.pk if duplicate_of else None, "note": close_note})
    return complaint
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_complaint_services.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: lodge_complaint with blocking/auto-attach rules, close_complaint with duplicate rules"
```

---

### Task 8: Work-order services (open, start, complete, cancel, remarks, participants)

**Files:**
- Create: `tests/test_workorder_services.py`
- Modify: `apps/maintenance/services.py`

**Interfaces:**
- Consumes: Task 7's module, `transition_status`, `Remark`, `RemarkKind`, `WorkOrderOutcome`, `FaultCategory`.
- Produces (appended to `apps.maintenance.services`; all engineer/admin-only, all atomic, all audited):
  - `open_work_order(equipment, actor) -> WorkOrder` — raises `WorkOrderStateError` if equipment condemned or an active WO exists; attaches ALL open complaints of the device.
  - `start_repair(work_order, actor) -> WorkOrder` — WO must be `open`; sets `repair_started_at`, adds actor to participants, transitions equipment → `in_repair`.
  - `complete_work_order(work_order, actor, fault_category, participants=(), remark="") -> WorkOrder` — WO must be `in_progress`; `fault_category` required (ValueError); sets completion/closed fields, `outcome=repaired`; adds actor + given engineers to participants; optional closing remark; transitions equipment → `working`; closes attached complaints as `resolved`.
  - `cancel_work_order(work_order, actor, note="") -> WorkOrder` — WO must be active; transitions equipment back to `working` if it was `in_repair`; closes attached complaints as `no_fault`; system remark records the cancellation.
  - `add_remark(work_order, author, text, kind=RemarkKind.NOTE) -> Remark` — engineer/admin; WO may be in any status (remarks on closed WOs allowed, e.g. post-repair notes).
  - `add_participant(work_order, actor, user) -> None` — both actor and user must be engineer/admin; audit verb `"workorder.participant_added"`.

- [ ] **Step 1: Write the failing tests**

`tests/test_workorder_services.py`:
```python
import pytest
from django.core.exceptions import PermissionDenied

from apps.core.exceptions import WorkOrderStateError
from apps.equipment.models import EquipmentStatus
from apps.maintenance.models import (
    CloseReason, ComplaintStatus, FaultCategory, RemarkKind,
    WorkOrderOutcome, WorkOrderStatus,
)
from apps.maintenance.services import (
    add_participant, add_remark, cancel_work_order, complete_work_order,
    lodge_complaint, open_work_order, start_repair,
)

pytestmark = pytest.mark.django_db


def test_open_work_order_attaches_all_open_complaints(equipment, staff_user, engineer):
    c1 = lodge_complaint(staff_user, equipment, "broken")
    c2 = lodge_complaint(staff_user, equipment, "also broken")
    wo = open_work_order(equipment, engineer)
    c1.refresh_from_db(); c2.refresh_from_db()
    assert c1.status == ComplaintStatus.ATTACHED and c1.work_order == wo
    assert c2.status == ComplaintStatus.ATTACHED and c2.work_order == wo


def test_cannot_open_second_active_work_order(equipment, engineer):
    open_work_order(equipment, engineer)
    with pytest.raises(WorkOrderStateError):
        open_work_order(equipment, engineer)


def test_start_repair_flow(equipment, engineer):
    wo = open_work_order(equipment, engineer)
    wo = start_repair(wo, engineer)
    equipment.refresh_from_db()
    assert wo.status == WorkOrderStatus.IN_PROGRESS
    assert wo.repair_started_at is not None
    assert engineer in wo.participants.all()
    assert equipment.status == EquipmentStatus.IN_REPAIR
    event = equipment.status_events.first()
    assert event.work_order == wo


def test_cannot_start_twice(equipment, engineer):
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    with pytest.raises(WorkOrderStateError):
        start_repair(wo, engineer)


def test_complete_requires_fault_category(equipment, engineer):
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    with pytest.raises(ValueError):
        complete_work_order(wo, engineer, fault_category="")
    with pytest.raises(ValueError):
        complete_work_order(wo, engineer, fault_category="bogus")


def test_complete_work_order_full_cascade(equipment, staff_user, engineer, engineer2):
    complaint = lodge_complaint(staff_user, equipment, "no power")
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    wo = complete_work_order(
        wo, engineer2, fault_category=FaultCategory.BATTERY_POWER,
        participants=[engineer], remark="replaced battery pack",
    )
    equipment.refresh_from_db(); complaint.refresh_from_db()
    assert wo.status == WorkOrderStatus.COMPLETED
    assert wo.outcome == WorkOrderOutcome.REPAIRED
    assert wo.fault_category == FaultCategory.BATTERY_POWER
    assert wo.repair_completed_at is not None
    assert wo.closed_by == engineer2
    assert set(wo.participants.all()) == {engineer, engineer2}
    assert equipment.status == EquipmentStatus.WORKING
    assert complaint.status == ComplaintStatus.CLOSED
    assert complaint.close_reason == CloseReason.RESOLVED
    assert wo.remarks.filter(text="replaced battery pack").exists()


def test_cannot_complete_unstarted_work_order(equipment, engineer):
    wo = open_work_order(equipment, engineer)
    with pytest.raises(WorkOrderStateError):
        complete_work_order(wo, engineer, fault_category=FaultCategory.OTHER)


def test_cancel_from_in_progress_restores_working(equipment, staff_user, engineer):
    complaint = lodge_complaint(staff_user, equipment, "weird noise")
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    wo = cancel_work_order(wo, engineer, note="no fault found on inspection")
    equipment.refresh_from_db(); complaint.refresh_from_db()
    assert wo.status == WorkOrderStatus.CANCELLED
    assert equipment.status == EquipmentStatus.WORKING
    assert complaint.close_reason == CloseReason.NO_FAULT
    assert wo.remarks.filter(kind=RemarkKind.SYSTEM).exists()


def test_staff_cannot_touch_work_orders(equipment, staff_user, engineer):
    wo = open_work_order(equipment, engineer)
    for call in (
        lambda: start_repair(wo, staff_user),
        lambda: add_remark(wo, staff_user, "hello"),
        lambda: add_participant(wo, engineer, staff_user),
    ):
        with pytest.raises(PermissionDenied):
            call()


def test_add_remark_and_participant(equipment, engineer, engineer2):
    wo = open_work_order(equipment, engineer)
    remark = add_remark(wo, engineer, "waiting for vendor part", kind=RemarkKind.DELAY)
    assert remark.kind == RemarkKind.DELAY
    add_participant(wo, engineer, engineer2)
    assert engineer2 in wo.participants.all()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_workorder_services.py -v`
Expected: FAIL — `ImportError` on the new service names.

- [ ] **Step 3: Implement — append to `apps/maintenance/services.py`**

Extend the imports at the top of the file to:
```python
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.core import audit
from apps.core.exceptions import ComplaintNotAllowed, WorkOrderStateError
from apps.equipment.models import EquipmentStatus
from apps.equipment.services import _require_engineer_or_admin, transition_status

from .models import (
    ACTIVE_WORKORDER_STATUSES, CloseReason, Complaint, ComplaintStatus,
    FaultCategory, Remark, RemarkKind, WorkOrder, WorkOrderOutcome,
    WorkOrderStatus,
)
```

Then append these functions:
```python
@transaction.atomic
def open_work_order(equipment, actor) -> WorkOrder:
    _require_engineer_or_admin(actor)
    if equipment.status == EquipmentStatus.CONDEMNED:
        raise WorkOrderStateError("Cannot open a work order for condemned equipment.")
    if equipment.work_orders.filter(status__in=ACTIVE_WORKORDER_STATUSES).exists():
        raise WorkOrderStateError("This equipment already has an active work order.")
    wo = WorkOrder.objects.create(equipment=equipment, opened_by=actor)
    for complaint in equipment.complaints.filter(status=ComplaintStatus.OPEN):
        complaint.status = ComplaintStatus.ATTACHED
        complaint.work_order = wo
        complaint.save(update_fields=["status", "work_order"])
    audit.record(actor, "workorder.opened", wo,
                 {"equipment": equipment.serial_number})
    return wo


@transaction.atomic
def start_repair(work_order, actor) -> WorkOrder:
    _require_engineer_or_admin(actor)
    if work_order.status != WorkOrderStatus.OPEN:
        raise WorkOrderStateError("Only an open work order can be started.")
    work_order.status = WorkOrderStatus.IN_PROGRESS
    work_order.repair_started_at = timezone.now()
    work_order.save(update_fields=["status", "repair_started_at"])
    work_order.participants.add(actor)
    transition_status(
        work_order.equipment, EquipmentStatus.IN_REPAIR, actor,
        remark=f"Repair started (WO #{work_order.pk})", work_order=work_order,
    )
    audit.record(actor, "workorder.started", work_order, {})
    return work_order


@transaction.atomic
def complete_work_order(work_order, actor, fault_category,
                        participants=(), remark="") -> WorkOrder:
    _require_engineer_or_admin(actor)
    if work_order.status != WorkOrderStatus.IN_PROGRESS:
        raise WorkOrderStateError("Only an in-progress work order can be completed.")
    if fault_category not in FaultCategory.values:
        raise ValueError("A valid fault_category is required to complete a repair.")
    now = timezone.now()
    work_order.status = WorkOrderStatus.COMPLETED
    work_order.outcome = WorkOrderOutcome.REPAIRED
    work_order.fault_category = fault_category
    work_order.repair_completed_at = now
    work_order.closed_by = actor
    work_order.closed_at = now
    work_order.save(update_fields=[
        "status", "outcome", "fault_category", "repair_completed_at",
        "closed_by", "closed_at",
    ])
    work_order.participants.add(actor, *participants)
    if remark:
        Remark.objects.create(work_order=work_order, author=actor, text=remark)
    transition_status(
        work_order.equipment, EquipmentStatus.WORKING, actor,
        remark=f"Repair completed (WO #{work_order.pk})", work_order=work_order,
    )
    for complaint in work_order.complaints.exclude(status=ComplaintStatus.CLOSED):
        close_complaint(complaint, actor, CloseReason.RESOLVED,
                        close_note=f"Resolved by Work Order #{work_order.pk}")
    audit.record(actor, "workorder.completed", work_order,
                 {"fault_category": fault_category})
    return work_order


@transaction.atomic
def cancel_work_order(work_order, actor, note="") -> WorkOrder:
    _require_engineer_or_admin(actor)
    if not work_order.is_active:
        raise WorkOrderStateError("Only an active work order can be cancelled.")
    was_in_progress = work_order.status == WorkOrderStatus.IN_PROGRESS
    now = timezone.now()
    work_order.status = WorkOrderStatus.CANCELLED
    work_order.closed_by = actor
    work_order.closed_at = now
    work_order.save(update_fields=["status", "closed_by", "closed_at"])
    Remark.objects.create(
        work_order=work_order, author=actor, kind=RemarkKind.SYSTEM,
        text=f"Work order cancelled. {note}".strip(),
    )
    if was_in_progress:
        transition_status(
            work_order.equipment, EquipmentStatus.WORKING, actor,
            remark=f"Repair cancelled (WO #{work_order.pk})", work_order=work_order,
        )
    for complaint in work_order.complaints.exclude(status=ComplaintStatus.CLOSED):
        close_complaint(complaint, actor, CloseReason.NO_FAULT,
                        close_note=note or "No fault found.")
    audit.record(actor, "workorder.cancelled", work_order, {"note": note})
    return work_order


def add_remark(work_order, author, text, kind=RemarkKind.NOTE) -> Remark:
    _require_engineer_or_admin(author)
    remark = Remark.objects.create(
        work_order=work_order, author=author, text=text, kind=kind
    )
    audit.record(author, "workorder.remark_added", work_order,
                 {"kind": kind, "text": text})
    return remark


def add_participant(work_order, actor, user) -> None:
    _require_engineer_or_admin(actor)
    _require_engineer_or_admin(user)
    work_order.participants.add(user)
    audit.record(actor, "workorder.participant_added", work_order,
                 {"user": user.employee_id})
```

- [ ] **Step 4: Run the whole suite**

Run: `pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: work order lifecycle services with cascades, remarks, participants"
```

---

### Task 9: Condemnation cascade (`condemn_equipment`)

**Files:**
- Create: `tests/test_condemnation.py`
- Modify: `apps/equipment/services.py`

**Interfaces:**
- Consumes: `transition_status`, maintenance models/services (imported inside the function to avoid an import cycle).
- Produces: `apps.equipment.services.condemn_equipment(equipment, actor, remark, condemned_location) -> Equipment` — engineer/admin; one transaction: transition to `condemned` (validates from-state via the machine), set `condemned_at`/`condemned_location`, auto-complete any active WorkOrder with `outcome=condemned` (system remark "Device condemned", no fault_category requirement), close every non-closed complaint of the device as `resolved` with note "Device condemned", audit verb `"equipment.condemned"`.

- [ ] **Step 1: Write the failing tests**

`tests/test_condemnation.py`:
```python
import pytest

from apps.core.exceptions import InvalidTransition
from apps.core.models import AuditLog
from apps.equipment.models import EquipmentStatus
from apps.equipment.services import condemn_equipment
from apps.maintenance.models import (
    CloseReason, ComplaintStatus, RemarkKind, WorkOrderOutcome, WorkOrderStatus,
)
from apps.maintenance.services import lodge_complaint, open_work_order, start_repair

pytestmark = pytest.mark.django_db


def test_condemn_working_equipment(equipment, engineer):
    condemn_equipment(equipment, engineer, remark="beyond repair",
                      condemned_location="Store Room B")
    equipment.refresh_from_db()
    assert equipment.status == EquipmentStatus.CONDEMNED
    assert equipment.condemned_at is not None
    assert equipment.condemned_location == "Store Room B"
    assert AuditLog.objects.filter(verb="equipment.condemned").exists()


def test_condemn_cascades_to_workorder_and_complaints(equipment, staff_user, engineer):
    complaint = lodge_complaint(staff_user, equipment, "sparks and smoke")
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    condemn_equipment(equipment, engineer, remark="unsafe",
                      condemned_location="Disposal yard")
    equipment.refresh_from_db(); wo.refresh_from_db(); complaint.refresh_from_db()
    assert equipment.status == EquipmentStatus.CONDEMNED
    assert wo.status == WorkOrderStatus.COMPLETED
    assert wo.outcome == WorkOrderOutcome.CONDEMNED
    assert wo.closed_by == engineer
    assert wo.remarks.filter(kind=RemarkKind.SYSTEM, text__icontains="condemned").exists()
    assert complaint.status == ComplaintStatus.CLOSED
    assert complaint.close_reason == CloseReason.RESOLVED
    assert "condemned" in complaint.close_note.lower()


def test_cannot_condemn_twice(equipment, engineer):
    condemn_equipment(equipment, engineer, remark="done", condemned_location="Store")
    equipment.refresh_from_db()
    with pytest.raises(InvalidTransition):
        condemn_equipment(equipment, engineer, remark="again", condemned_location="Store")


def test_no_complaints_after_condemnation(equipment, staff_user, engineer):
    from apps.core.exceptions import ComplaintNotAllowed
    condemn_equipment(equipment, engineer, remark="done", condemned_location="Store")
    equipment.refresh_from_db()
    with pytest.raises(ComplaintNotAllowed):
        lodge_complaint(staff_user, equipment, "still want to report")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_condemnation.py -v`
Expected: FAIL — `condemn_equipment` does not exist.

- [ ] **Step 3: Implement — append to `apps/equipment/services.py`**

```python
@transaction.atomic
def condemn_equipment(equipment, actor, remark, condemned_location):
    """Terminal lifecycle step. Cascades in one transaction (spec section 6)."""
    from django.utils import timezone

    from apps.maintenance.models import (
        ACTIVE_WORKORDER_STATUSES, CloseReason, ComplaintStatus, Remark,
        RemarkKind, WorkOrderOutcome, WorkOrderStatus,
    )
    from apps.maintenance.services import close_complaint

    transition_status(equipment, EquipmentStatus.CONDEMNED, actor, remark=remark)
    equipment.refresh_from_db()
    equipment.condemned_at = timezone.now()
    equipment.condemned_location = condemned_location
    equipment.save(update_fields=["condemned_at", "condemned_location"])

    active_wo = equipment.work_orders.filter(
        status__in=ACTIVE_WORKORDER_STATUSES
    ).first()
    if active_wo:
        now = timezone.now()
        active_wo.status = WorkOrderStatus.COMPLETED
        active_wo.outcome = WorkOrderOutcome.CONDEMNED
        active_wo.repair_completed_at = active_wo.repair_completed_at or now
        active_wo.closed_by = actor
        active_wo.closed_at = now
        active_wo.save(update_fields=[
            "status", "outcome", "repair_completed_at", "closed_by", "closed_at",
        ])
        Remark.objects.create(
            work_order=active_wo, author=actor, kind=RemarkKind.SYSTEM,
            text="Device condemned; work order closed automatically.",
        )

    for complaint in equipment.complaints.exclude(status=ComplaintStatus.CLOSED):
        close_complaint(complaint, actor, CloseReason.RESOLVED,
                        close_note="Device condemned.")

    audit.record(actor, "equipment.condemned", equipment,
                 {"remark": remark, "location": condemned_location})
    return equipment
```
(The maintenance imports live inside the function because `maintenance.services` imports from `equipment.services` at module level — importing the other direction at module level would create a cycle.)

- [ ] **Step 4: Run the whole suite**

Run: `pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: condemn_equipment with work-order and complaint cascade"
```

---

### Task 10: Tailwind + base template + styled login

**Files:**
- Create: `static/css/input.css`, `static/css/app.css` (built artifact, committed), `static/js/` vendored libs, `templates/base.html`, `templates/partials/_messages.html`, `scripts/README.md`
- Modify: `templates/registration/login.html`, `tests/test_accounts.py` (one added test)

**Interfaces:**
- Produces: `templates/base.html` with blocks `title`, `content`, `extra_js`; nav that links Registry (all), Queue/Dashboard (engineer/admin), New Complaint / My Complaints (all); logout form. Vendored `static/js/htmx.min.js`, `static/js/alpine.min.js`, `static/js/chart.umd.js`.

- [ ] **Step 1: Vendor the JS libraries and Tailwind binary**

```powershell
New-Item -ItemType Directory -Force static\js, bin
Invoke-WebRequest https://unpkg.com/htmx.org@2/dist/htmx.min.js -OutFile static\js\htmx.min.js
Invoke-WebRequest https://unpkg.com/alpinejs@3/dist/cdn.min.js -OutFile static\js\alpine.min.js
Invoke-WebRequest https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.js -OutFile static\js\chart.umd.js
Invoke-WebRequest https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-windows-x64.exe -OutFile bin\tailwindcss.exe
```
(`bin/` is gitignored; the three JS files are committed. `scripts/README.md` documents these commands for other machines — copy them into it verbatim, plus the Linux binary name `tailwindcss-linux-x64` for CI/Docker rebuilds.)

- [ ] **Step 2: Create the CSS input and build**

`static/css/input.css` (Tailwind v4 syntax — no config file needed):
```css
@import "tailwindcss";
@source "../../templates";
```

Build (rerun after every template change that uses new utility classes):
```powershell
bin\tailwindcss.exe -i static\css\input.css -o static\css\app.css --minify
```
Expected: `app.css` generated without errors. **Commit `app.css`** so Docker builds don't need the binary.

- [ ] **Step 3: Create the base templates**

`templates/base.html`:
```html
{% load static %}
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}{{ HOSPITAL_NAME }} CMMS{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'css/app.css' %}">
  <script src="{% static 'js/htmx.min.js' %}" defer></script>
  <script src="{% static 'js/alpine.min.js' %}" defer></script>
</head>
<body class="min-h-screen bg-slate-100 text-slate-900">
<nav class="bg-sky-900 text-white">
  <div class="mx-auto max-w-6xl px-4 py-3 flex items-center gap-6">
    <a href="{% url 'home' %}" class="font-bold">{{ HOSPITAL_NAME }} · CMMS</a>
    {% if user.is_authenticated %}
      <a href="{% url 'equipment_list' %}" class="hover:underline">Equipment</a>
      <a href="{% url 'complaint_new' %}" class="hover:underline">New Complaint</a>
      <a href="{% url 'my_complaints' %}" class="hover:underline">My Complaints</a>
      {% if user.is_engineer_or_admin %}
        <a href="{% url 'complaint_queue' %}" class="hover:underline">Queue</a>
        <a href="{% url 'dashboard' %}" class="hover:underline">Dashboard</a>
      {% endif %}
      <form method="post" action="{% url 'logout' %}" class="ml-auto">
        {% csrf_token %}
        <button class="text-sky-200 hover:underline">
          Log out ({{ user.employee_id }})
        </button>
      </form>
    {% endif %}
  </div>
</nav>
<main class="mx-auto max-w-6xl px-4 py-6">
  {% include "partials/_messages.html" %}
  {% block content %}{% endblock %}
</main>
{% block extra_js %}{% endblock %}
</body>
</html>
```
Until Task 11/12 exist, `{% url 'equipment_list' %}` etc. would raise — so for THIS task, create the base.html with those four nav anchors wrapped in `{% if False %}…{% endif %}`; Task 11 unhides the Equipment link, Task 12 the rest, Task 13 Dashboard. (Alternative used by the tests: this task only asserts the login page renders, which doesn't extend nav URLs.) Concretely, in this task write the nav links block as:
```html
    {% if user.is_authenticated %}{# nav links enabled by Tasks 11-13 #}{% endif %}
```
and Task 11/12/13 each replace it with the final version above once their URLs exist.

`templates/partials/_messages.html`:
```html
{% if messages %}
  {% for message in messages %}
    <div class="mb-4 rounded border px-4 py-2
                {% if message.tags == 'error' %}border-red-300 bg-red-50 text-red-800
                {% else %}border-emerald-300 bg-emerald-50 text-emerald-800{% endif %}">
      {{ message }}
    </div>
  {% endfor %}
{% endif %}
```

`templates/registration/login.html` (replace stub):
```html
{% extends "base.html" %}
{% block title %}Log in{% endblock %}
{% block content %}
<div class="mx-auto max-w-sm mt-16 rounded-lg bg-white p-8 shadow">
  <h1 class="mb-6 text-xl font-bold">Log in</h1>
  {% if form.errors %}
    <p class="mb-4 text-sm text-red-700">Invalid username or password.</p>
  {% endif %}
  <form method="post" class="space-y-4">
    {% csrf_token %}
    <div>
      <label class="block text-sm mb-1" for="id_username">Username</label>
      {{ form.username }}
    </div>
    <div>
      <label class="block text-sm mb-1" for="id_password">Password</label>
      {{ form.password }}
    </div>
    <button class="w-full rounded bg-sky-800 py-2 text-white hover:bg-sky-700">
      Log in
    </button>
  </form>
</div>
{% endblock %}
```

Add to `tests/test_accounts.py`:
```python
def test_login_page_uses_base_template(client):
    response = client.get("/accounts/login/")
    assert b"CMMS" in response.content
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_accounts.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: tailwind base template, vendored htmx/alpine/chart, styled login"
```

---

### Task 11: Equipment views (list, search partial, detail, create/edit, condemn)

**Files:**
- Create: `apps/equipment/forms.py`, `apps/equipment/views.py`, `apps/equipment/urls.py`, `templates/equipment/list.html`, `templates/equipment/_search_results.html`, `templates/equipment/detail.html`, `templates/equipment/form.html`, `templates/equipment/condemn.html`, `tests/test_equipment_views.py`
- Modify: `config/urls.py`, `templates/base.html` (unhide Equipment nav link)

**Interfaces:**
- Consumes: services from Tasks 5/9, `RoleRequiredMixin`, `Roles`.
- Produces URL names: `equipment_list` (`/equipment/`), `equipment_search` (`/equipment/search/` — HTMX partial, `?q=` matches serial/name/model/manufacturer, `?exclude_unavailable=1` hides in-repair+condemned), `equipment_detail` (`/equipment/<pk>/`), `equipment_create`, `equipment_edit` (`/equipment/<pk>/edit/`), `equipment_condemn` (`/equipment/<pk>/condemn/`). Also `apps.equipment.services.create_equipment(actor, **fields)` and `update_equipment(equipment, actor, **fields)` (audited diffs).

- [ ] **Step 1: Write the failing tests**

`tests/test_equipment_views.py`:
```python
import pytest
from django.urls import reverse

from apps.equipment.models import Equipment, EquipmentStatus

pytestmark = pytest.mark.django_db


def test_staff_sees_registry_readonly(client, staff_user, equipment):
    client.force_login(staff_user)
    response = client.get(reverse("equipment_list"))
    assert response.status_code == 200
    assert b"SN-0001" in response.content


def test_staff_cannot_open_create_page(client, staff_user):
    client.force_login(staff_user)
    response = client.get(reverse("equipment_create"))
    assert response.status_code == 403


def test_engineer_creates_equipment(client, engineer, department):
    client.force_login(engineer)
    response = client.post(reverse("equipment_create"), {
        "name": "Infusion Pump", "manufacturer": "B.Braun", "vendor": "MedServe",
        "model_number": "P7", "serial_number": "SN-0100",
        "department": department.pk, "is_critical_asset": "",
    })
    assert response.status_code == 302
    assert Equipment.objects.filter(serial_number="SN-0100").exists()


def test_search_partial_matches_serial(client, staff_user, equipment):
    client.force_login(staff_user)
    response = client.get(reverse("equipment_search"), {"q": "SN-0001"})
    assert response.status_code == 200
    assert b"SN-0001" in response.content


def test_search_can_exclude_unavailable(client, staff_user, engineer,
                                        equipment, make_equipment):
    from apps.equipment.services import transition_status
    broken = make_equipment(serial_number="SN-0002")
    transition_status(broken, EquipmentStatus.IN_REPAIR, engineer)
    client.force_login(staff_user)
    response = client.get(reverse("equipment_search"),
                          {"q": "SN-000", "exclude_unavailable": "1"})
    assert b"SN-0001" in response.content
    assert b"SN-0002" not in response.content


def test_condemn_via_view(client, engineer, equipment):
    client.force_login(engineer)
    response = client.post(reverse("equipment_condemn", args=[equipment.pk]), {
        "remark": "beyond economical repair", "condemned_location": "Store Room B",
    })
    assert response.status_code == 302
    equipment.refresh_from_db()
    assert equipment.status == EquipmentStatus.CONDEMNED


def test_detail_shows_status_history(client, engineer, equipment):
    from apps.equipment.services import transition_status
    transition_status(equipment, EquipmentStatus.IN_REPAIR, engineer, remark="checking")
    client.force_login(engineer)
    response = client.get(reverse("equipment_detail", args=[equipment.pk]))
    assert response.status_code == 200
    assert b"checking" in response.content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_equipment_views.py -v`
Expected: FAIL — `NoReverseMatch`.

- [ ] **Step 3: Implement**

Append to `apps/equipment/services.py`:
```python
def create_equipment(actor, **fields):
    _require_engineer_or_admin(actor)
    equipment = Equipment.objects.create(**fields)
    audit.record(actor, "equipment.created", equipment,
                 {"serial_number": equipment.serial_number})
    return equipment


def update_equipment(equipment, actor, **fields):
    _require_engineer_or_admin(actor)
    changes = {}
    for name, value in fields.items():
        old = getattr(equipment, name)
        if old != value:
            changes[name] = {"old": str(old), "new": str(value)}
            setattr(equipment, name, value)
    if changes:
        equipment.save(update_fields=list(fields.keys()))
        audit.record(actor, "equipment.updated", equipment, changes)
    return equipment
```

`apps/equipment/forms.py`:
```python
from django import forms

from .models import Equipment

INPUT = ("w-full rounded border border-slate-300 px-3 py-2 "
         "focus:border-sky-500 focus:outline-none")


class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = ["name", "manufacturer", "vendor", "model_number",
                  "serial_number", "department", "is_critical_asset",
                  "purchase_date", "installation_date"]
        widgets = {
            "purchase_date": forms.DateInput(attrs={"type": "date"}),
            "installation_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != "is_critical_asset":
                field.widget.attrs.setdefault("class", INPUT)


class CondemnForm(forms.Form):
    remark = forms.CharField(widget=forms.Textarea(attrs={"rows": 3, "class": INPUT}))
    condemned_location = forms.CharField(
        widget=forms.TextInput(attrs={"class": INPUT}),
        help_text="Current physical location of the condemned unit.",
    )
```

`apps/equipment/views.py`:
```python
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView, View

from apps.accounts.mixins import RoleRequiredMixin
from apps.accounts.models import Roles
from apps.core.exceptions import DomainError

from . import services
from .forms import CondemnForm, EquipmentForm
from .models import Equipment, EquipmentStatus

ENGINEER_ROLES = (Roles.ENGINEER, Roles.ADMIN)


class EquipmentListView(LoginRequiredMixin, ListView):
    model = Equipment
    template_name = "equipment/list.html"
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset().select_related("department")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(serial_number__icontains=q) | Q(name__icontains=q)
                | Q(model_number__icontains=q) | Q(manufacturer__icontains=q)
            )
        status = self.request.GET.get("status", "")
        if status:
            qs = qs.filter(status=status)
        return qs


class EquipmentSearchView(LoginRequiredMixin, View):
    """HTMX partial used by list filtering and the complaint form picker."""

    def get(self, request):
        q = request.GET.get("q", "").strip()
        results = Equipment.objects.select_related("department")
        if request.GET.get("exclude_unavailable"):
            results = results.filter(status=EquipmentStatus.WORKING)
        if q:
            results = results.filter(
                Q(serial_number__icontains=q) | Q(name__icontains=q)
                | Q(model_number__icontains=q) | Q(manufacturer__icontains=q)
            )[:10]
        else:
            results = results.none()
        return render(request, "equipment/_search_results.html",
                      {"results": results})


class EquipmentDetailView(LoginRequiredMixin, DetailView):
    model = Equipment
    template_name = "equipment/detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        eq = self.object
        ctx["status_events"] = eq.status_events.select_related("actor")
        ctx["work_orders"] = eq.work_orders.prefetch_related("remarks", "participants")
        ctx["open_complaints"] = eq.complaints.exclude(status="closed")
        ctx["can_engineer"] = self.request.user.is_engineer_or_admin
        return ctx


class EquipmentCreateView(RoleRequiredMixin, View):
    allowed_roles = ENGINEER_ROLES

    def get(self, request):
        return render(request, "equipment/form.html", {"form": EquipmentForm()})

    def post(self, request):
        form = EquipmentForm(request.POST)
        if not form.is_valid():
            return render(request, "equipment/form.html", {"form": form})
        equipment = services.create_equipment(request.user, **form.cleaned_data)
        messages.success(request, f"Equipment {equipment.serial_number} registered.")
        return redirect("equipment_detail", pk=equipment.pk)


class EquipmentEditView(RoleRequiredMixin, View):
    allowed_roles = ENGINEER_ROLES

    def get(self, request, pk):
        equipment = get_object_or_404(Equipment, pk=pk)
        form = EquipmentForm(instance=equipment)
        return render(request, "equipment/form.html",
                      {"form": form, "equipment": equipment})

    def post(self, request, pk):
        equipment = get_object_or_404(Equipment, pk=pk)
        form = EquipmentForm(request.POST, instance=equipment)
        if not form.is_valid():
            return render(request, "equipment/form.html",
                          {"form": form, "equipment": equipment})
        services.update_equipment(equipment, request.user, **form.cleaned_data)
        messages.success(request, "Equipment updated.")
        return redirect("equipment_detail", pk=pk)


class EquipmentCondemnView(RoleRequiredMixin, View):
    allowed_roles = ENGINEER_ROLES

    def get(self, request, pk):
        equipment = get_object_or_404(Equipment, pk=pk)
        return render(request, "equipment/condemn.html",
                      {"equipment": equipment, "form": CondemnForm()})

    def post(self, request, pk):
        equipment = get_object_or_404(Equipment, pk=pk)
        form = CondemnForm(request.POST)
        if not form.is_valid():
            return render(request, "equipment/condemn.html",
                          {"equipment": equipment, "form": form})
        try:
            services.condemn_equipment(equipment, request.user, **form.cleaned_data)
        except DomainError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Equipment condemned. Its history is preserved.")
        return redirect("equipment_detail", pk=pk)
```
Note on `EquipmentForm(instance=equipment)` + `update_equipment`: the ModelForm mutates `instance` during validation, so `update_equipment`'s diff would see no changes. In `EquipmentEditView.post`, bind the form WITHOUT instance and pass data through: use `form = EquipmentForm(request.POST)` and add `self.instance_pk = pk` exclusion for the serial-unique check by instantiating as `EquipmentForm(request.POST, instance=Equipment.objects.get(pk=pk))` for validation but calling the service with a FRESH object: `services.update_equipment(Equipment.objects.get(pk=pk), request.user, **form.cleaned_data)`. Concretely, replace the two post lines with:
```python
        form = EquipmentForm(request.POST, instance=equipment)
        if not form.is_valid():
            return render(request, "equipment/form.html",
                          {"form": form, "equipment": equipment})
        fresh = Equipment.objects.get(pk=pk)
        services.update_equipment(fresh, request.user, **form.cleaned_data)
```

`apps/equipment/urls.py`:
```python
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
```

In `config/urls.py` add:
```python
    path("equipment/", include("apps.equipment.urls")),
```

In `templates/base.html`, replace the nav placeholder comment with the Equipment link only (Queue/Dashboard/complaints stay for Tasks 12–13):
```html
    {% if user.is_authenticated %}
      <a href="{% url 'equipment_list' %}" class="hover:underline">Equipment</a>
      <form method="post" action="{% url 'logout' %}" class="ml-auto">
        {% csrf_token %}
        <button class="text-sky-200 hover:underline">
          Log out ({{ user.employee_id }})
        </button>
      </form>
    {% endif %}
```

`templates/equipment/list.html`:
```html
{% extends "base.html" %}
{% block title %}Equipment Registry{% endblock %}
{% block content %}
<div class="mb-4 flex items-center justify-between">
  <h1 class="text-2xl font-bold">Equipment Registry</h1>
  {% if user.is_engineer_or_admin %}
    <a href="{% url 'equipment_create' %}"
       class="rounded bg-sky-800 px-4 py-2 text-white hover:bg-sky-700">
      + Add Equipment</a>
  {% endif %}
</div>
<form method="get" class="mb-4 flex gap-2">
  <input name="q" value="{{ request.GET.q }}" placeholder="Search serial, name, model…"
         class="w-72 rounded border border-slate-300 px-3 py-2">
  <select name="status" class="rounded border border-slate-300 px-2">
    <option value="">All statuses</option>
    <option value="working">Working</option>
    <option value="in_repair">In Repair</option>
    <option value="condemned">Condemned</option>
  </select>
  <button class="rounded bg-slate-700 px-4 py-2 text-white">Filter</button>
</form>
<table class="w-full rounded bg-white shadow text-sm">
  <thead><tr class="border-b text-left">
    <th class="p-3">Name</th><th class="p-3">Model</th><th class="p-3">Serial #</th>
    <th class="p-3">Department</th><th class="p-3">Status</th><th class="p-3">Critical</th>
  </tr></thead>
  <tbody>
    {% for eq in object_list %}
    <tr class="border-b hover:bg-slate-50">
      <td class="p-3"><a class="text-sky-700 hover:underline"
          href="{% url 'equipment_detail' eq.pk %}">{{ eq.name }}</a></td>
      <td class="p-3">{{ eq.model_number }}</td>
      <td class="p-3 font-mono">{{ eq.serial_number }}</td>
      <td class="p-3">{{ eq.department }}</td>
      <td class="p-3">{{ eq.get_status_display }}</td>
      <td class="p-3">{% if eq.is_critical_asset %}★{% endif %}</td>
    </tr>
    {% empty %}
    <tr><td class="p-6 text-center text-slate-500" colspan="6">No equipment found.</td></tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
```

`templates/equipment/_search_results.html`:
```html
{% for eq in results %}
<button type="button"
        class="block w-full border-b px-3 py-2 text-left hover:bg-sky-50"
        @click="select({{ eq.pk }}, '{{ eq.name|escapejs }}',
                '{{ eq.model_number|escapejs }}', '{{ eq.serial_number|escapejs }}',
                '{{ eq.department|escapejs }}')">
  <span class="font-medium">{{ eq.name }}</span>
  <span class="text-slate-500">{{ eq.model_number }} ·
    <span class="font-mono">{{ eq.serial_number }}</span> · {{ eq.department }}</span>
</button>
{% empty %}
<div class="px-3 py-2 text-slate-500">No matching equipment.</div>
{% endfor %}
```

`templates/equipment/detail.html`:
```html
{% extends "base.html" %}
{% block title %}{{ equipment.name }}{% endblock %}
{% block content %}
<div class="mb-4 flex items-start justify-between">
  <div>
    <h1 class="text-2xl font-bold">{{ equipment.name }} {{ equipment.model_number }}</h1>
    <p class="font-mono text-slate-600">{{ equipment.serial_number }}</p>
  </div>
  <span class="rounded px-3 py-1 text-sm
    {% if equipment.status == 'working' %}bg-emerald-100 text-emerald-800
    {% elif equipment.status == 'in_repair' %}bg-amber-100 text-amber-800
    {% else %}bg-red-100 text-red-800{% endif %}">
    {{ equipment.get_status_display }}</span>
</div>
<div class="grid gap-6 md:grid-cols-2">
  <div class="rounded bg-white p-4 shadow">
    <h2 class="mb-2 font-semibold">Details</h2>
    <dl class="text-sm space-y-1">
      <div><dt class="inline text-slate-500">Manufacturer:</dt> <dd class="inline">{{ equipment.manufacturer }}</dd></div>
      <div><dt class="inline text-slate-500">Vendor:</dt> <dd class="inline">{{ equipment.vendor|default:"—" }}</dd></div>
      <div><dt class="inline text-slate-500">Department:</dt> <dd class="inline">{{ equipment.department }}</dd></div>
      <div><dt class="inline text-slate-500">Critical asset:</dt> <dd class="inline">{{ equipment.is_critical_asset|yesno }}</dd></div>
      <div><dt class="inline text-slate-500">Purchased:</dt> <dd class="inline">{{ equipment.purchase_date|default:"—" }}</dd></div>
      <div><dt class="inline text-slate-500">Installed:</dt> <dd class="inline">{{ equipment.installation_date|default:"—" }}</dd></div>
      <div><dt class="inline text-slate-500">Repairs completed:</dt>
        <dd class="inline">{{ completed_repair_count }}</dd></div>
      {% if equipment.status == 'condemned' %}
      <div><dt class="inline text-slate-500">Condemned:</dt>
        <dd class="inline">{{ equipment.condemned_at }} — {{ equipment.condemned_location }}</dd></div>
      {% endif %}
    </dl>
    {% if can_engineer and equipment.status != 'condemned' %}
    <div class="mt-4 flex gap-2">
      <a href="{% url 'equipment_edit' equipment.pk %}"
         class="rounded bg-slate-700 px-3 py-1.5 text-sm text-white">Edit</a>
      <a href="{% url 'equipment_condemn' equipment.pk %}"
         class="rounded bg-red-700 px-3 py-1.5 text-sm text-white">Condemn…</a>
    </div>
    {% endif %}
  </div>
  <div class="rounded bg-white p-4 shadow">
    <h2 class="mb-2 font-semibold">Status History</h2>
    <ul class="space-y-2 text-sm">
      {% for event in status_events %}
      <li class="border-l-2 border-sky-300 pl-3">
        <span class="text-slate-500">{{ event.created_at }}</span> —
        {{ event.get_old_status_display }} → {{ event.get_new_status_display }}
        by {{ event.actor }}
        {% if event.remark %}<div class="text-slate-600">“{{ event.remark }}”</div>{% endif %}
      </li>
      {% empty %}<li class="text-slate-500">No status changes yet.</li>{% endfor %}
    </ul>
  </div>
</div>
<div class="mt-6 rounded bg-white p-4 shadow">
  <h2 class="mb-2 font-semibold">Work Orders</h2>
  {% for wo in work_orders %}
  <div class="mb-3 border-b pb-3 text-sm">
    <a class="font-medium text-sky-700 hover:underline"
       href="{% url 'workorder_detail' wo.pk %}">WO #{{ wo.pk }}</a>
    — {{ wo.get_status_display }}{% if wo.outcome %} ({{ wo.get_outcome_display }}){% endif %}
    {% if wo.fault_category %} · {{ wo.get_fault_category_display }}{% endif %}
    · opened {{ wo.opened_at|date }}
  </div>
  {% empty %}<p class="text-sm text-slate-500">No repairs recorded.</p>{% endfor %}
</div>
{% endblock %}
```
Add `completed_repair_count` to `EquipmentDetailView.get_context_data`:
```python
        ctx["completed_repair_count"] = eq.work_orders.filter(
            status="completed").count()
```
(The `workorder_detail` URL exists from Task 12 — until then, temporarily render `WO #{{ wo.pk }}` without the anchor; Task 12's steps say to add the link.) For THIS task use:
```html
    <span class="font-medium">WO #{{ wo.pk }}</span>
```

`templates/equipment/form.html`:
```html
{% extends "base.html" %}
{% block title %}{% if equipment %}Edit{% else %}Add{% endif %} Equipment{% endblock %}
{% block content %}
<div class="mx-auto max-w-xl rounded bg-white p-6 shadow">
  <h1 class="mb-4 text-xl font-bold">
    {% if equipment %}Edit {{ equipment.serial_number }}{% else %}Add Equipment{% endif %}
  </h1>
  <form method="post" class="space-y-4">
    {% csrf_token %}
    {% for field in form %}
    <div>
      <label class="mb-1 block text-sm font-medium">{{ field.label }}</label>
      {{ field }}
      {% if field.help_text %}<p class="text-xs text-slate-500">{{ field.help_text }}</p>{% endif %}
      {% for error in field.errors %}<p class="text-sm text-red-700">{{ error }}</p>{% endfor %}
    </div>
    {% endfor %}
    <button class="rounded bg-sky-800 px-4 py-2 text-white hover:bg-sky-700">Save</button>
  </form>
</div>
{% endblock %}
```

`templates/equipment/condemn.html`:
```html
{% extends "base.html" %}
{% block title %}Condemn {{ equipment.serial_number }}{% endblock %}
{% block content %}
<div class="mx-auto max-w-xl rounded bg-white p-6 shadow">
  <h1 class="mb-2 text-xl font-bold text-red-800">Condemn equipment</h1>
  <p class="mb-4 text-sm text-slate-600">
    {{ equipment }} will be permanently retired. Its record and full history
    are preserved forever. Any active work order and open complaints will be
    closed automatically. <strong>This cannot be undone.</strong>
  </p>
  <form method="post" class="space-y-4">
    {% csrf_token %}
    {% for field in form %}
    <div>
      <label class="mb-1 block text-sm font-medium">{{ field.label }}</label>
      {{ field }}
      {% if field.help_text %}<p class="text-xs text-slate-500">{{ field.help_text }}</p>{% endif %}
      {% for error in field.errors %}<p class="text-sm text-red-700">{{ error }}</p>{% endfor %}
    </div>
    {% endfor %}
    <button class="rounded bg-red-700 px-4 py-2 text-white hover:bg-red-600">
      Condemn permanently</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 4: Rebuild CSS, run tests**

```powershell
bin\tailwindcss.exe -i static\css\input.css -o static\css\app.css --minify
pytest -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: equipment registry views - list, search partial, detail, create/edit, condemn"
```

---

### Task 12: Complaint & work-order views (lodge form, my complaints, HTMX queue, WO actions)

**Files:**
- Create: `apps/maintenance/forms.py`, `apps/maintenance/views.py`, `apps/maintenance/urls.py`, `templates/maintenance/complaint_form.html`, `templates/maintenance/my_complaints.html`, `templates/maintenance/queue.html`, `templates/maintenance/_queue_rows.html`, `templates/maintenance/complaint_close.html`, `templates/maintenance/workorder_detail.html`, `templates/maintenance/workorder_complete.html`, `tests/test_maintenance_views.py`
- Modify: `config/urls.py`, `templates/base.html` (full nav), `templates/equipment/detail.html` (link WO numbers)

**Interfaces:**
- Consumes: all Task 7/8 services, `equipment_search` partial (with `exclude_unavailable=1`).
- Produces URL names (prefix `/maintenance/`): `complaint_new`, `my_complaints`, `complaint_queue`, `complaint_queue_rows` (HTMX partial, polled every 10s), `complaint_close` (`/complaints/<pk>/close/`), `workorder_open` (POST, `/workorders/open/<equipment_pk>/`), `workorder_detail` (`/workorders/<pk>/`), `workorder_start` (POST), `workorder_complete` (GET form + POST), `workorder_cancel` (POST), `workorder_remark` (POST), `workorder_join` (POST). After this task `home` works for both roles.

- [ ] **Step 1: Write the failing tests**

`tests/test_maintenance_views.py`:
```python
import pytest
from django.urls import reverse

from apps.maintenance.models import (
    CloseReason, Complaint, ComplaintStatus, FaultCategory, WorkOrderStatus,
)
from apps.maintenance.services import lodge_complaint, open_work_order, start_repair

pytestmark = pytest.mark.django_db


def test_staff_lodges_complaint_via_form(client, staff_user, equipment):
    client.force_login(staff_user)
    response = client.post(reverse("complaint_new"), {
        "equipment": equipment.pk, "description": "Screen flickers then dies",
    })
    assert response.status_code == 302
    complaint = Complaint.objects.get()
    assert complaint.reporter == staff_user
    assert complaint.equipment == equipment


def test_lodge_blocked_for_in_repair_shows_error(client, staff_user, equipment, engineer):
    start_repair(open_work_order(equipment, engineer), engineer)
    client.force_login(staff_user)
    response = client.post(reverse("complaint_new"), {
        "equipment": equipment.pk, "description": "still broken",
    }, follow=True)
    assert b"already under repair" in response.content
    assert Complaint.objects.count() == 0


def test_queue_requires_engineer(client, staff_user):
    client.force_login(staff_user)
    assert client.get(reverse("complaint_queue")).status_code == 403


def test_queue_rows_partial_lists_open_complaints(client, engineer, staff_user, equipment):
    lodge_complaint(staff_user, equipment, "no power at all")
    client.force_login(engineer)
    response = client.get(reverse("complaint_queue_rows"))
    assert b"no power at all" in response.content
    assert b"SN-0001" in response.content


def test_close_duplicate_via_view(client, engineer, staff_user, equipment):
    first = lodge_complaint(staff_user, equipment, "display broken")
    second = lodge_complaint(staff_user, equipment, "screen dead")
    client.force_login(engineer)
    response = client.post(reverse("complaint_close", args=[second.pk]), {
        "close_reason": CloseReason.DUPLICATE, "duplicate_of": first.pk,
        "close_note": "same fault, reported twice",
    })
    assert response.status_code == 302
    second.refresh_from_db()
    assert second.status == ComplaintStatus.CLOSED
    assert second.duplicate_of == first


def test_open_start_complete_workorder_via_views(client, engineer, staff_user, equipment):
    complaint = lodge_complaint(staff_user, equipment, "won't switch on")
    client.force_login(engineer)
    r = client.post(reverse("workorder_open", args=[equipment.pk]))
    assert r.status_code == 302
    wo = equipment.work_orders.get()
    client.post(reverse("workorder_start", args=[wo.pk]))
    wo.refresh_from_db()
    assert wo.status == WorkOrderStatus.IN_PROGRESS
    r = client.post(reverse("workorder_complete", args=[wo.pk]), {
        "fault_category": FaultCategory.ELECTRICAL,
        "participants": [], "remark": "fuse replaced",
    })
    assert r.status_code == 302
    wo.refresh_from_db(); complaint.refresh_from_db()
    assert wo.status == WorkOrderStatus.COMPLETED
    assert complaint.status == ComplaintStatus.CLOSED


def test_delay_remark_via_view(client, engineer, equipment):
    wo = open_work_order(equipment, engineer)
    client.force_login(engineer)
    client.post(reverse("workorder_remark", args=[wo.pk]), {
        "text": "waiting for vendor part", "kind": "delay",
    })
    assert wo.remarks.filter(kind="delay").exists()


def test_join_workorder(client, engineer, engineer2, equipment):
    wo = open_work_order(equipment, engineer)
    client.force_login(engineer2)
    client.post(reverse("workorder_join", args=[wo.pk]))
    assert engineer2 in wo.participants.all()


def test_home_redirects_by_role(client, staff_user, engineer):
    client.force_login(staff_user)
    assert client.get(reverse("home")).url == reverse("my_complaints")
    client.force_login(engineer)
    assert client.get(reverse("home")).url == reverse("complaint_queue")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_maintenance_views.py -v`
Expected: FAIL — `NoReverseMatch`.

- [ ] **Step 3: Implement**

`apps/maintenance/forms.py`:
```python
from django import forms
from django.contrib.auth import get_user_model

from apps.accounts.models import Roles
from apps.equipment.models import Equipment

from .models import CloseReason, Complaint, ComplaintStatus, FaultCategory, RemarkKind

INPUT = ("w-full rounded border border-slate-300 px-3 py-2 "
         "focus:border-sky-500 focus:outline-none")


class ComplaintForm(forms.Form):
    equipment = forms.ModelChoiceField(
        queryset=Equipment.objects.all(), widget=forms.HiddenInput
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 4, "class": INPUT,
            "placeholder": "Describe what is wrong with the equipment…",
        })
    )


class CloseComplaintForm(forms.Form):
    close_reason = forms.ChoiceField(choices=[
        (CloseReason.DUPLICATE, "Duplicate of another complaint"),
        (CloseReason.NO_FAULT, "No fault found"),
    ], widget=forms.RadioSelect)
    duplicate_of = forms.ModelChoiceField(
        queryset=Complaint.objects.none(), required=False,
        widget=forms.Select(attrs={"class": INPUT}),
    )
    close_note = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2, "class": INPUT}),
    )

    def __init__(self, *args, complaint=None, **kwargs):
        super().__init__(*args, **kwargs)
        if complaint is not None:
            self.fields["duplicate_of"].queryset = (
                Complaint.objects.filter(equipment=complaint.equipment)
                .exclude(pk=complaint.pk)
                .exclude(status=ComplaintStatus.CLOSED)
            )

    def clean(self):
        data = super().clean()
        if (data.get("close_reason") == CloseReason.DUPLICATE
                and not data.get("duplicate_of") and not data.get("close_note")):
            raise forms.ValidationError(
                "Closing as duplicate needs the original complaint or a note."
            )
        return data


class CompleteWorkOrderForm(forms.Form):
    fault_category = forms.ChoiceField(
        choices=FaultCategory.choices,
        widget=forms.Select(attrs={"class": INPUT}),
    )
    participants = forms.ModelMultipleChoiceField(
        queryset=get_user_model().objects.filter(
            role__in=[Roles.ENGINEER, Roles.ADMIN], is_active=True
        ),
        required=False, widget=forms.CheckboxSelectMultiple,
        help_text="Tick every engineer who worked on this repair.",
    )
    remark = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2, "class": INPUT}),
    )


class RemarkForm(forms.Form):
    text = forms.CharField(widget=forms.Textarea(attrs={"rows": 2, "class": INPUT}))
    kind = forms.ChoiceField(choices=[
        (RemarkKind.NOTE, "Note"),
        (RemarkKind.DELAY, "Delay (explain why the repair is taking long)"),
    ], initial=RemarkKind.NOTE)
```

`apps/maintenance/views.py`:
```python
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import Roles
from apps.core.exceptions import DomainError
from apps.equipment.models import Equipment

from . import services
from .forms import (
    CloseComplaintForm, ComplaintForm, CompleteWorkOrderForm, RemarkForm,
)
from .models import Complaint, ComplaintStatus, WorkOrder

ENGINEER_ROLES = (Roles.ENGINEER, Roles.ADMIN)


def _require_engineer(user):
    if user.role not in ENGINEER_ROLES:
        raise PermissionDenied


@login_required
def complaint_new(request):
    form = ComplaintForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            complaint = services.lodge_complaint(
                request.user, form.cleaned_data["equipment"],
                form.cleaned_data["description"],
            )
        except DomainError as exc:
            messages.error(request, str(exc))
            return redirect("complaint_new")
        messages.success(request,
                         f"Complaint #{complaint.pk} lodged. Thank you.")
        return redirect("my_complaints")
    return render(request, "maintenance/complaint_form.html", {"form": form})


@login_required
def my_complaints(request):
    complaints = (Complaint.objects.filter(reporter=request.user)
                  .select_related("equipment", "work_order"))
    return render(request, "maintenance/my_complaints.html",
                  {"complaints": complaints})


def _open_complaints_queryset():
    return (Complaint.objects
            .filter(status__in=[ComplaintStatus.OPEN, ComplaintStatus.ATTACHED])
            .select_related("equipment__department", "reporter", "work_order")
            .order_by("-created_at"))


@login_required
def complaint_queue(request):
    _require_engineer(request.user)
    return render(request, "maintenance/queue.html",
                  {"complaints": _open_complaints_queryset()})


@login_required
def complaint_queue_rows(request):
    _require_engineer(request.user)
    return render(request, "maintenance/_queue_rows.html",
                  {"complaints": _open_complaints_queryset()})


@login_required
def complaint_close(request, pk):
    _require_engineer(request.user)
    complaint = get_object_or_404(Complaint, pk=pk)
    form = CloseComplaintForm(request.POST or None, complaint=complaint)
    if request.method == "POST" and form.is_valid():
        try:
            services.close_complaint(
                complaint, request.user, form.cleaned_data["close_reason"],
                duplicate_of=form.cleaned_data["duplicate_of"],
                close_note=form.cleaned_data["close_note"],
            )
        except (DomainError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Complaint #{complaint.pk} closed.")
        return redirect("complaint_queue")
    return render(request, "maintenance/complaint_close.html",
                  {"complaint": complaint, "form": form})


@login_required
@require_POST
def workorder_open(request, equipment_pk):
    _require_engineer(request.user)
    equipment = get_object_or_404(Equipment, pk=equipment_pk)
    try:
        wo = services.open_work_order(equipment, request.user)
    except DomainError as exc:
        messages.error(request, str(exc))
        return redirect("equipment_detail", pk=equipment_pk)
    messages.success(request, f"Work Order #{wo.pk} opened.")
    return redirect("workorder_detail", pk=wo.pk)


@login_required
def workorder_detail(request, pk):
    wo = get_object_or_404(
        WorkOrder.objects.select_related("equipment__department", "opened_by")
        .prefetch_related("remarks__author", "participants", "complaints__reporter"),
        pk=pk,
    )
    return render(request, "maintenance/workorder_detail.html", {
        "wo": wo,
        "remark_form": RemarkForm(),
        "can_engineer": request.user.is_engineer_or_admin,
    })


@login_required
@require_POST
def workorder_start(request, pk):
    _require_engineer(request.user)
    wo = get_object_or_404(WorkOrder, pk=pk)
    try:
        services.start_repair(wo, request.user)
    except DomainError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Repair started on WO #{wo.pk}.")
    return redirect("workorder_detail", pk=pk)


@login_required
def workorder_complete(request, pk):
    _require_engineer(request.user)
    wo = get_object_or_404(WorkOrder, pk=pk)
    form = CompleteWorkOrderForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.complete_work_order(
                wo, request.user, form.cleaned_data["fault_category"],
                participants=form.cleaned_data["participants"],
                remark=form.cleaned_data["remark"],
            )
        except (DomainError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"WO #{wo.pk} completed. Equipment is Working.")
            return redirect("workorder_detail", pk=pk)
    form.fields["participants"].initial = wo.participants.all()
    return render(request, "maintenance/workorder_complete.html",
                  {"wo": wo, "form": form})


@login_required
@require_POST
def workorder_cancel(request, pk):
    _require_engineer(request.user)
    wo = get_object_or_404(WorkOrder, pk=pk)
    try:
        services.cancel_work_order(wo, request.user,
                                   note=request.POST.get("note", ""))
    except DomainError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"WO #{wo.pk} cancelled (no fault found).")
    return redirect("workorder_detail", pk=pk)


@login_required
@require_POST
def workorder_remark(request, pk):
    _require_engineer(request.user)
    wo = get_object_or_404(WorkOrder, pk=pk)
    form = RemarkForm(request.POST)
    if form.is_valid():
        services.add_remark(wo, request.user, form.cleaned_data["text"],
                            kind=form.cleaned_data["kind"])
        messages.success(request, "Remark added.")
    return redirect("workorder_detail", pk=pk)


@login_required
@require_POST
def workorder_join(request, pk):
    _require_engineer(request.user)
    wo = get_object_or_404(WorkOrder, pk=pk)
    services.add_participant(wo, request.user, request.user)
    messages.success(request, "You are now a participant on this work order.")
    return redirect("workorder_detail", pk=pk)
```

`apps/maintenance/urls.py`:
```python
from django.urls import path

from . import views

urlpatterns = [
    path("complaints/new/", views.complaint_new, name="complaint_new"),
    path("complaints/mine/", views.my_complaints, name="my_complaints"),
    path("queue/", views.complaint_queue, name="complaint_queue"),
    path("queue/rows/", views.complaint_queue_rows, name="complaint_queue_rows"),
    path("complaints/<int:pk>/close/", views.complaint_close, name="complaint_close"),
    path("workorders/open/<int:equipment_pk>/", views.workorder_open,
         name="workorder_open"),
    path("workorders/<int:pk>/", views.workorder_detail, name="workorder_detail"),
    path("workorders/<int:pk>/start/", views.workorder_start, name="workorder_start"),
    path("workorders/<int:pk>/complete/", views.workorder_complete,
         name="workorder_complete"),
    path("workorders/<int:pk>/cancel/", views.workorder_cancel,
         name="workorder_cancel"),
    path("workorders/<int:pk>/remark/", views.workorder_remark,
         name="workorder_remark"),
    path("workorders/<int:pk>/join/", views.workorder_join, name="workorder_join"),
]
```

In `config/urls.py` add:
```python
    path("maintenance/", include("apps.maintenance.urls")),
```

In `templates/base.html`, expand the nav to the full version (still without Dashboard — Task 13 adds it):
```html
    {% if user.is_authenticated %}
      <a href="{% url 'equipment_list' %}" class="hover:underline">Equipment</a>
      <a href="{% url 'complaint_new' %}" class="hover:underline">New Complaint</a>
      <a href="{% url 'my_complaints' %}" class="hover:underline">My Complaints</a>
      {% if user.is_engineer_or_admin %}
        <a href="{% url 'complaint_queue' %}" class="hover:underline">Queue</a>
      {% endif %}
      <form method="post" action="{% url 'logout' %}" class="ml-auto">
        {% csrf_token %}
        <button class="text-sky-200 hover:underline">
          Log out ({{ user.employee_id }})
        </button>
      </form>
    {% endif %}
```

In `templates/equipment/detail.html`, replace `<span class="font-medium">WO #{{ wo.pk }}</span>` with the link:
```html
    <a class="font-medium text-sky-700 hover:underline"
       href="{% url 'workorder_detail' wo.pk %}">WO #{{ wo.pk }}</a>
```
and, inside the `{% if can_engineer and equipment.status != 'condemned' %}` action row, add:
```html
      <form method="post" action="{% url 'workorder_open' equipment.pk %}">
        {% csrf_token %}
        <button class="rounded bg-amber-600 px-3 py-1.5 text-sm text-white">
          Open Work Order</button>
      </form>
```

`templates/maintenance/complaint_form.html` (search-and-select with Alpine + HTMX):
```html
{% extends "base.html" %}
{% block title %}New Complaint{% endblock %}
{% block content %}
<div class="mx-auto max-w-xl rounded bg-white p-6 shadow"
     x-data="{ picked: null, name: '', model: '', serial: '', dept: '',
               select(id, name, model, serial, dept) {
                 this.picked = id; this.name = name; this.model = model;
                 this.serial = serial; this.dept = dept;
                 document.getElementById('id_equipment').value = id;
                 document.getElementById('search-results').innerHTML = '';
               } }">
  <h1 class="mb-4 text-xl font-bold">Lodge a Complaint</h1>
  <p class="mb-4 text-sm text-slate-600">
    Reporting as <strong>{{ user.get_full_name|default:user.username }}</strong>
    (ID: {{ user.employee_id }}) — attached automatically.
  </p>
  <div class="mb-4">
    <label class="mb-1 block text-sm font-medium">Find the equipment</label>
    <input type="search" name="q" placeholder="Type serial number, name or model…"
           class="w-full rounded border border-slate-300 px-3 py-2"
           hx-get="{% url 'equipment_search' %}" hx-trigger="input changed delay:300ms"
           hx-target="#search-results" hx-vals='{"exclude_unavailable": "1"}'>
    <div id="search-results" class="mt-1 rounded border border-slate-200 bg-white
                                    empty:border-0 shadow-sm"></div>
  </div>
  <template x-if="picked">
    <div class="mb-4 rounded border border-sky-200 bg-sky-50 p-3 text-sm">
      <div><span class="text-slate-500">Equipment:</span> <span x-text="name"></span>
           <span x-text="model"></span></div>
      <div><span class="text-slate-500">Serial #:</span>
           <span class="font-mono" x-text="serial"></span></div>
      <div><span class="text-slate-500">Department:</span> <span x-text="dept"></span></div>
    </div>
  </template>
  <form method="post" class="space-y-4">
    {% csrf_token %}
    {{ form.equipment }}
    <div>
      <label class="mb-1 block text-sm font-medium">What is wrong?</label>
      {{ form.description }}
      {% for error in form.description.errors %}
        <p class="text-sm text-red-700">{{ error }}</p>{% endfor %}
      {% for error in form.equipment.errors %}
        <p class="text-sm text-red-700">Please pick the equipment above.</p>{% endfor %}
    </div>
    <button class="rounded bg-sky-800 px-4 py-2 text-white hover:bg-sky-700"
            :disabled="!picked" :class="{ 'opacity-50': !picked }">
      Submit Complaint</button>
  </form>
</div>
{% endblock %}
```

`templates/maintenance/my_complaints.html`:
```html
{% extends "base.html" %}
{% block title %}My Complaints{% endblock %}
{% block content %}
<h1 class="mb-4 text-2xl font-bold">My Complaints</h1>
<table class="w-full rounded bg-white shadow text-sm">
  <thead><tr class="border-b text-left">
    <th class="p-3">#</th><th class="p-3">Equipment</th><th class="p-3">Description</th>
    <th class="p-3">Lodged</th><th class="p-3">Status</th>
  </tr></thead>
  <tbody>
    {% for c in complaints %}
    <tr class="border-b">
      <td class="p-3">{{ c.pk }}</td>
      <td class="p-3">{{ c.equipment.name }}
        <span class="font-mono text-slate-500">{{ c.equipment.serial_number }}</span></td>
      <td class="p-3">{{ c.description|truncatechars:80 }}</td>
      <td class="p-3">{{ c.created_at }}</td>
      <td class="p-3">
        {{ c.get_status_display }}
        {% if c.close_reason %}<span class="text-slate-500">
          ({{ c.get_close_reason_display }})</span>{% endif %}
      </td>
    </tr>
    {% empty %}
    <tr><td colspan="5" class="p-6 text-center text-slate-500">
      You have not lodged any complaints.</td></tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
```

`templates/maintenance/queue.html`:
```html
{% extends "base.html" %}
{% block title %}Complaint Queue{% endblock %}
{% block content %}
<h1 class="mb-4 text-2xl font-bold">Complaint Queue</h1>
<p class="mb-2 text-sm text-slate-500">Auto-refreshes every 10 seconds.</p>
<table class="w-full rounded bg-white shadow text-sm">
  <thead><tr class="border-b text-left">
    <th class="p-3">#</th><th class="p-3">Equipment</th><th class="p-3">Department</th>
    <th class="p-3">Description</th><th class="p-3">Reporter</th>
    <th class="p-3">Received</th><th class="p-3">State</th><th class="p-3"></th>
  </tr></thead>
  <tbody hx-get="{% url 'complaint_queue_rows' %}" hx-trigger="every 10s"
         hx-swap="innerHTML">
    {% include "maintenance/_queue_rows.html" %}
  </tbody>
</table>
{% endblock %}
```

`templates/maintenance/_queue_rows.html`:
```html
{% for c in complaints %}
<tr class="border-b hover:bg-slate-50">
  <td class="p-3">{{ c.pk }}</td>
  <td class="p-3">
    <a class="text-sky-700 hover:underline"
       href="{% url 'equipment_detail' c.equipment.pk %}">{{ c.equipment.name }}</a>
    <span class="font-mono text-slate-500">{{ c.equipment.serial_number }}</span>
  </td>
  <td class="p-3">{{ c.equipment.department }}</td>
  <td class="p-3">{{ c.description|truncatechars:60 }}</td>
  <td class="p-3">{{ c.reporter.get_full_name|default:c.reporter.username }}
    <span class="text-slate-500">({{ c.reporter.employee_id }})</span></td>
  <td class="p-3">{{ c.created_at|timesince }} ago</td>
  <td class="p-3">
    {% if c.work_order %}
      <a class="text-amber-700 hover:underline"
         href="{% url 'workorder_detail' c.work_order.pk %}">WO #{{ c.work_order.pk }}</a>
    {% else %}<span class="text-slate-500">unassigned</span>{% endif %}
  </td>
  <td class="p-3 whitespace-nowrap">
    {% if not c.work_order %}
    <form method="post" action="{% url 'workorder_open' c.equipment.pk %}"
          class="inline">{% csrf_token %}
      <button class="rounded bg-amber-600 px-2 py-1 text-xs text-white">
        Open WO</button>
    </form>
    {% endif %}
    <a href="{% url 'complaint_close' c.pk %}"
       class="rounded bg-slate-600 px-2 py-1 text-xs text-white">Close…</a>
  </td>
</tr>
{% empty %}
<tr><td colspan="8" class="p-6 text-center text-slate-500">
  No open complaints. 🎉</td></tr>
{% endfor %}
```

`templates/maintenance/complaint_close.html`:
```html
{% extends "base.html" %}
{% block title %}Close Complaint #{{ complaint.pk }}{% endblock %}
{% block content %}
<div class="mx-auto max-w-xl rounded bg-white p-6 shadow">
  <h1 class="mb-2 text-xl font-bold">Close Complaint #{{ complaint.pk }}</h1>
  <p class="mb-4 text-sm text-slate-600">
    {{ complaint.equipment }} — “{{ complaint.description|truncatechars:120 }}”
    by {{ complaint.reporter }} ({{ complaint.created_at }})
  </p>
  <form method="post" class="space-y-4">
    {% csrf_token %}
    {% for error in form.non_field_errors %}
      <p class="text-sm text-red-700">{{ error }}</p>{% endfor %}
    <div>
      <label class="mb-1 block text-sm font-medium">Reason</label>
      {{ form.close_reason }}
    </div>
    <div>
      <label class="mb-1 block text-sm font-medium">Original complaint (if duplicate)</label>
      {{ form.duplicate_of }}
    </div>
    <div>
      <label class="mb-1 block text-sm font-medium">Note</label>
      {{ form.close_note }}
      <p class="text-xs text-slate-500">
        e.g. “Already reported by Nurse Khan, complaint #482.”</p>
    </div>
    <button class="rounded bg-slate-700 px-4 py-2 text-white">Close complaint</button>
  </form>
</div>
{% endblock %}
```

`templates/maintenance/workorder_detail.html`:
```html
{% extends "base.html" %}
{% block title %}WO #{{ wo.pk }}{% endblock %}
{% block content %}
<div class="mb-4 flex items-start justify-between">
  <div>
    <h1 class="text-2xl font-bold">Work Order #{{ wo.pk }}</h1>
    <p class="text-slate-600">
      <a class="text-sky-700 hover:underline"
         href="{% url 'equipment_detail' wo.equipment.pk %}">{{ wo.equipment }}</a>
      · {{ wo.equipment.department }}</p>
  </div>
  <span class="rounded px-3 py-1 text-sm
    {% if wo.status == 'completed' %}bg-emerald-100 text-emerald-800
    {% elif wo.status == 'cancelled' %}bg-slate-200 text-slate-700
    {% elif wo.status == 'in_progress' %}bg-amber-100 text-amber-800
    {% else %}bg-sky-100 text-sky-800{% endif %}">
    {{ wo.get_status_display }}</span>
</div>
<div class="grid gap-6 md:grid-cols-2">
  <div class="rounded bg-white p-4 shadow text-sm space-y-1">
    <h2 class="mb-2 font-semibold">Timeline</h2>
    <div><span class="text-slate-500">Opened:</span> {{ wo.opened_at }} by {{ wo.opened_by }}</div>
    <div><span class="text-slate-500">Repair started:</span> {{ wo.repair_started_at|default:"—" }}</div>
    <div><span class="text-slate-500">Repair completed:</span> {{ wo.repair_completed_at|default:"—" }}</div>
    {% if wo.closed_by %}<div><span class="text-slate-500">Closed by:</span> {{ wo.closed_by }}</div>{% endif %}
    {% if wo.outcome %}<div><span class="text-slate-500">Outcome:</span> {{ wo.get_outcome_display }}</div>{% endif %}
    {% if wo.fault_category %}<div><span class="text-slate-500">Fault:</span> {{ wo.get_fault_category_display }}</div>{% endif %}
    <div><span class="text-slate-500">Participants:</span>
      {% for p in wo.participants.all %}{{ p }}{% if not forloop.last %}, {% endif %}
      {% empty %}—{% endfor %}</div>
    {% if can_engineer and wo.is_active %}
    <div class="mt-3 flex flex-wrap gap-2">
      {% if wo.status == 'open' %}
      <form method="post" action="{% url 'workorder_start' wo.pk %}">{% csrf_token %}
        <button class="rounded bg-amber-600 px-3 py-1.5 text-white">Start repair</button>
      </form>
      {% endif %}
      {% if wo.status == 'in_progress' %}
      <a href="{% url 'workorder_complete' wo.pk %}"
         class="rounded bg-emerald-700 px-3 py-1.5 text-white">Complete…</a>
      {% endif %}
      <form method="post" action="{% url 'workorder_cancel' wo.pk %}">{% csrf_token %}
        <input type="hidden" name="note" value="No fault found.">
        <button class="rounded bg-slate-600 px-3 py-1.5 text-white">
          Cancel (no fault)</button>
      </form>
      <form method="post" action="{% url 'workorder_join' wo.pk %}">{% csrf_token %}
        <button class="rounded bg-sky-700 px-3 py-1.5 text-white">
          I'm working on this</button>
      </form>
    </div>
    {% endif %}
  </div>
  <div class="rounded bg-white p-4 shadow">
    <h2 class="mb-2 font-semibold">Attached Complaints ({{ wo.complaints.count }})</h2>
    <ul class="space-y-2 text-sm">
      {% for c in wo.complaints.all %}
      <li class="border-l-2 border-slate-300 pl-3">
        #{{ c.pk }} — “{{ c.description|truncatechars:100 }}”
        <div class="text-slate-500">{{ c.reporter }} · {{ c.created_at }}
          · {{ c.get_status_display }}</div>
      </li>
      {% empty %}<li class="text-slate-500">Engineer-initiated (no complaints).</li>
      {% endfor %}
    </ul>
  </div>
</div>
<div class="mt-6 rounded bg-white p-4 shadow">
  <h2 class="mb-2 font-semibold">Remarks</h2>
  <ul class="mb-4 space-y-2 text-sm">
    {% for remark in wo.remarks.all %}
    <li class="rounded p-2
        {% if remark.kind == 'delay' %}bg-amber-50 border border-amber-200
        {% elif remark.kind == 'system' %}bg-slate-50 text-slate-600
        {% else %}bg-sky-50{% endif %}">
      <span class="text-slate-500">{{ remark.created_at }} · {{ remark.author }}
        {% if remark.kind != 'note' %}· {{ remark.get_kind_display }}{% endif %}</span>
      <div>{{ remark.text }}</div>
    </li>
    {% empty %}<li class="text-slate-500">No remarks yet.</li>{% endfor %}
  </ul>
  {% if can_engineer %}
  <form method="post" action="{% url 'workorder_remark' wo.pk %}" class="space-y-2">
    {% csrf_token %}
    {{ remark_form.text }}
    <div class="flex items-center gap-3">
      {{ remark_form.kind }}
      <button class="rounded bg-sky-800 px-3 py-1.5 text-white">Add remark</button>
    </div>
  </form>
  {% endif %}
</div>
{% endblock %}
```

`templates/maintenance/workorder_complete.html`:
```html
{% extends "base.html" %}
{% block title %}Complete WO #{{ wo.pk }}{% endblock %}
{% block content %}
<div class="mx-auto max-w-xl rounded bg-white p-6 shadow">
  <h1 class="mb-4 text-xl font-bold">Complete Work Order #{{ wo.pk }}</h1>
  <form method="post" class="space-y-4">
    {% csrf_token %}
    <div>
      <label class="mb-1 block text-sm font-medium">Fault category (required)</label>
      {{ form.fault_category }}
      {% for error in form.fault_category.errors %}
        <p class="text-sm text-red-700">{{ error }}</p>{% endfor %}
    </div>
    <div>
      <label class="mb-1 block text-sm font-medium">Who worked on this repair?</label>
      {{ form.participants }}
      <p class="text-xs text-slate-500">{{ form.participants.help_text }}</p>
    </div>
    <div>
      <label class="mb-1 block text-sm font-medium">Closing remark (optional)</label>
      {{ form.remark }}
    </div>
    <button class="rounded bg-emerald-700 px-4 py-2 text-white hover:bg-emerald-600">
      Mark repaired &amp; return to service</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 4: Rebuild CSS, run the whole suite**

```powershell
bin\tailwindcss.exe -i static\css\input.css -o static\css\app.css --minify
pytest -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: complaint lodging with search-select, HTMX queue, work order action views"
```

---

### Task 13: Dashboard metrics + Chart.js view

**Files:**
- Create: `apps/reports/metrics.py`, `apps/reports/views.py`, `apps/reports/urls.py`, `templates/reports/dashboard.html`, `tests/test_metrics.py`, `tests/test_dashboard_view.py`
- Modify: `config/urls.py`, `templates/base.html` (add Dashboard nav link)

**Interfaces:**
- Consumes: all models; window boundaries are timezone-aware datetimes.
- Produces (in `apps.reports.metrics`, all pure query functions taking `(window_start, window_end)`):
  - `critical_downtime_by_department(ws, we) -> dict[str, float]` — hours, critical assets only; downtime runs from the earliest attached complaint's `created_at` (or `opened_at` if engineer-initiated) to `repair_completed_at` (or `we` if still active), clipped to the window; cancelled WOs excluded.
  - `complaints_per_department(ws, we) -> dict[str, int]`
  - `most_complained_devices(ws, we, limit=10) -> list[tuple[str, int]]` — label `"{name} ({serial})"`.
  - `fault_category_counts(ws, we) -> dict[str, int]` — display labels, completed WOs.
  - `repairs_completed_count(ws, we) -> int`, `open_workorders_count() -> int`
  - `delayed_repairs(ws, we) -> list[dict]` — WOs with ≥1 `delay` remark in window: `{"wo_id", "equipment", "latest_delay_note"}`.
  - `per_engineer_activity(ws, we) -> list[dict]` — `{"name", "employee_id", "repairs", "complaints_closed"}`; repairs counted by **participation** in completed WOs; complaints_closed counts duplicate/no-fault closures by that user.
  - URL name `dashboard` (`/dashboard/`), engineer/admin only, window = last 30 days.

- [ ] **Step 1: Write the failing tests**

`tests/test_metrics.py`:
```python
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.maintenance.models import (
    CloseReason, Complaint, FaultCategory, WorkOrder, WorkOrderStatus,
)
from apps.maintenance.services import (
    close_complaint, complete_work_order, lodge_complaint, open_work_order,
    add_remark, start_repair,
)
from apps.reports import metrics

pytestmark = pytest.mark.django_db

NOW = None  # set per-test via timezone.now()


def _backdate(obj, **fields):
    """Seed/test helper: bypass auto_now_add/append-only via queryset update."""
    type(obj).objects.filter(pk=obj.pk).update(**fields)
    obj.refresh_from_db()


def test_downtime_full_cycle_inside_window(make_equipment, staff_user, engineer):
    now = timezone.now()
    eq = make_equipment(serial_number="SN-MRI", name="MRI", is_critical_asset=True)
    complaint = lodge_complaint(staff_user, eq, "coil fault")
    _backdate(complaint, created_at=now - timedelta(days=10))
    wo = start_repair(open_work_order(eq, engineer), engineer)
    wo = complete_work_order(wo, engineer, FaultCategory.ELECTRICAL)
    _backdate(wo, repair_completed_at=now - timedelta(days=8))
    result = metrics.critical_downtime_by_department(now - timedelta(days=30), now)
    assert result == {"ICU": pytest.approx(48.0, abs=0.1)}


def test_downtime_clipped_to_window(make_equipment, staff_user, engineer):
    now = timezone.now()
    eq = make_equipment(serial_number="SN-CT", is_critical_asset=True)
    complaint = lodge_complaint(staff_user, eq, "tube fault")
    _backdate(complaint, created_at=now - timedelta(days=40))
    wo = start_repair(open_work_order(eq, engineer), engineer)
    wo = complete_work_order(wo, engineer, FaultCategory.OTHER)
    _backdate(wo, repair_completed_at=now - timedelta(days=29))
    result = metrics.critical_downtime_by_department(now - timedelta(days=30), now)
    assert result["ICU"] == pytest.approx(24.0, abs=0.1)


def test_non_critical_equipment_excluded(equipment, staff_user, engineer):
    now = timezone.now()
    lodge_complaint(staff_user, equipment, "broken")  # equipment fixture: not critical
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    complete_work_order(wo, engineer, FaultCategory.OTHER)
    assert metrics.critical_downtime_by_department(
        now - timedelta(days=30), timezone.now()) == {}


def test_per_engineer_activity_counts_participation(
        equipment, staff_user, engineer, engineer2):
    now = timezone.now()
    lodge_complaint(staff_user, equipment, "broken")
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    complete_work_order(wo, engineer2, FaultCategory.MECHANICAL,
                        participants=[engineer])
    extra = lodge_complaint(staff_user, equipment, "hmm")
    close_complaint(extra, engineer, CloseReason.NO_FAULT, close_note="fine")
    rows = {r["employee_id"]: r for r in
            metrics.per_engineer_activity(now - timedelta(days=1), timezone.now())}
    assert rows["EMP-100"]["repairs"] == 1       # participant
    assert rows["EMP-101"]["repairs"] == 1       # closer, auto-participant
    assert rows["EMP-100"]["complaints_closed"] == 1


def test_fault_categories_and_counts(equipment, engineer):
    now = timezone.now()
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    complete_work_order(wo, engineer, FaultCategory.BATTERY_POWER)
    counts = metrics.fault_category_counts(now - timedelta(days=1), timezone.now())
    assert counts == {"Battery / Power": 1}
    assert metrics.repairs_completed_count(now - timedelta(days=1), timezone.now()) == 1


def test_delayed_repairs_listed(equipment, engineer):
    now = timezone.now()
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    add_remark(wo, engineer, "waiting for vendor part", kind="delay")
    rows = metrics.delayed_repairs(now - timedelta(days=1), timezone.now())
    assert len(rows) == 1
    assert rows[0]["wo_id"] == wo.pk
    assert "vendor part" in rows[0]["latest_delay_note"]
```

`tests/test_dashboard_view.py`:
```python
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_dashboard_requires_engineer(client, staff_user):
    client.force_login(staff_user)
    assert client.get(reverse("dashboard")).status_code == 403


def test_dashboard_renders_for_engineer(client, engineer):
    client.force_login(engineer)
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    assert b"chart.umd.js" in response.content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_metrics.py tests/test_dashboard_view.py -v`
Expected: FAIL — `apps.reports.metrics` does not exist.

- [ ] **Step 3: Implement**

`apps/reports/metrics.py`:
```python
"""Dashboard/report numbers. Numbers come from SQL/ORM — never from an LLM.
No MTTR and no SLA metrics anywhere (spec sections 7 and 9)."""
from collections import defaultdict

from django.db.models import Count, Q

from apps.accounts.models import Roles, User
from apps.equipment.models import Equipment
from apps.maintenance.models import (
    CloseReason, Complaint, FaultCategory, Remark, RemarkKind, WorkOrder,
    WorkOrderStatus,
)


def _downtime_start(wo):
    first = min((c.created_at for c in wo.complaints.all()), default=None)
    return first or wo.opened_at


def _overlap_hours(start, end, window_start, window_end):
    lo, hi = max(start, window_start), min(end, window_end)
    return max((hi - lo).total_seconds() / 3600.0, 0.0)


def critical_downtime_by_department(window_start, window_end):
    totals = defaultdict(float)
    work_orders = (
        WorkOrder.objects.filter(equipment__is_critical_asset=True)
        .exclude(status=WorkOrderStatus.CANCELLED)
        .select_related("equipment__department")
        .prefetch_related("complaints")
    )
    for wo in work_orders:
        down_from = _downtime_start(wo)
        down_to = wo.repair_completed_at or window_end
        hours = _overlap_hours(down_from, down_to, window_start, window_end)
        if hours > 0:
            totals[wo.equipment.department.name] += hours
    return dict(totals)


def complaints_per_department(window_start, window_end):
    rows = (
        Complaint.objects.filter(created_at__range=(window_start, window_end))
        .values("equipment__department__name")
        .annotate(n=Count("id")).order_by("-n")
    )
    return {r["equipment__department__name"]: r["n"] for r in rows}


def most_complained_devices(window_start, window_end, limit=10):
    rows = (
        Equipment.objects.annotate(
            n=Count("complaints", filter=Q(
                complaints__created_at__range=(window_start, window_end)))
        ).filter(n__gt=0).order_by("-n")[:limit]
    )
    return [(f"{eq.name} ({eq.serial_number})", eq.n) for eq in rows]


def fault_category_counts(window_start, window_end):
    labels = dict(FaultCategory.choices)
    rows = (
        WorkOrder.objects.filter(
            status=WorkOrderStatus.COMPLETED,
            repair_completed_at__range=(window_start, window_end),
            fault_category__isnull=False,
        ).values("fault_category").annotate(n=Count("id")).order_by("-n")
    )
    return {labels[r["fault_category"]]: r["n"] for r in rows}


def repairs_completed_count(window_start, window_end):
    return WorkOrder.objects.filter(
        status=WorkOrderStatus.COMPLETED,
        repair_completed_at__range=(window_start, window_end),
    ).count()


def open_workorders_count():
    return WorkOrder.objects.filter(
        status__in=[WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS]
    ).count()


def delayed_repairs(window_start, window_end):
    delay_remarks = (
        Remark.objects.filter(
            kind=RemarkKind.DELAY,
            created_at__range=(window_start, window_end),
        ).select_related("work_order__equipment").order_by("created_at")
    )
    latest = {}
    for remark in delay_remarks:
        latest[remark.work_order_id] = remark
    return [
        {"wo_id": wo_id, "equipment": str(r.work_order.equipment),
         "latest_delay_note": r.text}
        for wo_id, r in latest.items()
    ]


def per_engineer_activity(window_start, window_end):
    users = (
        User.objects.filter(role__in=[Roles.ENGINEER, Roles.ADMIN], is_active=True)
        .annotate(
            repairs=Count(
                "workorders_participated",
                filter=Q(
                    workorders_participated__status=WorkOrderStatus.COMPLETED,
                    workorders_participated__repair_completed_at__range=(
                        window_start, window_end),
                ), distinct=True,
            ),
            # annotation must NOT be named "complaints_closed" — that name is
            # taken by the reverse accessor of Complaint.closed_by and Django
            # raises a conflict error for it
            closed_count=Count(
                "complaints_closed",
                filter=Q(
                    complaints_closed__closed_at__range=(window_start, window_end),
                    complaints_closed__close_reason__in=[
                        CloseReason.DUPLICATE, CloseReason.NO_FAULT],
                ), distinct=True,
            ),
        ).order_by("-repairs")
    )
    return [
        {"name": u.get_full_name() or u.username, "employee_id": u.employee_id,
         "repairs": u.repairs, "complaints_closed": u.closed_count}
        for u in users if u.repairs or u.closed_count
    ]
```

`apps/reports/views.py`:
```python
import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.utils import timezone

from . import metrics


@login_required
def dashboard(request):
    if not request.user.is_engineer_or_admin:
        raise PermissionDenied
    window_end = timezone.now()
    window_start = window_end - timedelta(days=30)
    downtime = metrics.critical_downtime_by_department(window_start, window_end)
    complaints = metrics.complaints_per_department(window_start, window_end)
    devices = metrics.most_complained_devices(window_start, window_end)
    faults = metrics.fault_category_counts(window_start, window_end)
    context = {
        "repairs_completed": metrics.repairs_completed_count(window_start, window_end),
        "open_workorders": metrics.open_workorders_count(),
        "delayed": metrics.delayed_repairs(window_start, window_end),
        "engineers": metrics.per_engineer_activity(window_start, window_end),
        "downtime_json": json.dumps({
            "labels": list(downtime.keys()),
            "values": [round(v, 1) for v in downtime.values()]}),
        "complaints_json": json.dumps({
            "labels": list(complaints.keys()), "values": list(complaints.values())}),
        "devices_json": json.dumps({
            "labels": [d[0] for d in devices], "values": [d[1] for d in devices]}),
        "faults_json": json.dumps({
            "labels": list(faults.keys()), "values": list(faults.values())}),
    }
    return render(request, "reports/dashboard.html", context)
```

`apps/reports/urls.py`:
```python
from django.urls import path

from . import views

urlpatterns = [path("", views.dashboard, name="dashboard")]
```

In `config/urls.py` add:
```python
    path("dashboard/", include("apps.reports.urls")),
```

In `templates/base.html`, inside the `{% if user.is_engineer_or_admin %}` block after Queue:
```html
        <a href="{% url 'dashboard' %}" class="hover:underline">Dashboard</a>
```

`templates/reports/dashboard.html`:
```html
{% extends "base.html" %}
{% load static %}
{% block title %}Dashboard{% endblock %}
{% block content %}
<h1 class="mb-4 text-2xl font-bold">Dashboard <span class="text-base font-normal
  text-slate-500">last 30 days</span></h1>
<div class="mb-6 grid gap-4 sm:grid-cols-2">
  <div class="rounded bg-white p-4 shadow">
    <div class="text-3xl font-bold">{{ repairs_completed }}</div>
    <div class="text-sm text-slate-500">Repairs completed</div>
  </div>
  <div class="rounded bg-white p-4 shadow">
    <div class="text-3xl font-bold">{{ open_workorders }}</div>
    <div class="text-sm text-slate-500">Work orders open right now</div>
  </div>
</div>
<div class="grid gap-6 md:grid-cols-2">
  <div class="rounded bg-white p-4 shadow">
    <h2 class="mb-2 font-semibold">Critical-asset downtime (hours, by department)</h2>
    <canvas id="chart-downtime"></canvas>
  </div>
  <div class="rounded bg-white p-4 shadow">
    <h2 class="mb-2 font-semibold">Complaints per department</h2>
    <canvas id="chart-complaints"></canvas>
  </div>
  <div class="rounded bg-white p-4 shadow">
    <h2 class="mb-2 font-semibold">Most-complained devices</h2>
    <canvas id="chart-devices"></canvas>
  </div>
  <div class="rounded bg-white p-4 shadow">
    <h2 class="mb-2 font-semibold">Fault categories (completed repairs)</h2>
    <canvas id="chart-faults"></canvas>
  </div>
</div>
<div class="mt-6 grid gap-6 md:grid-cols-2">
  <div class="rounded bg-white p-4 shadow">
    <h2 class="mb-2 font-semibold">Repairs with delay remarks</h2>
    <ul class="space-y-2 text-sm">
      {% for d in delayed %}
      <li><a class="text-sky-700 hover:underline"
             href="{% url 'workorder_detail' d.wo_id %}">WO #{{ d.wo_id }}</a>
        — {{ d.equipment }}<div class="text-slate-500">“{{ d.latest_delay_note }}”</div></li>
      {% empty %}<li class="text-slate-500">No delays recorded. 🎉</li>{% endfor %}
    </ul>
  </div>
  <div class="rounded bg-white p-4 shadow">
    <h2 class="mb-2 font-semibold">Engineer activity</h2>
    <table class="w-full text-sm">
      <thead><tr class="border-b text-left"><th class="py-1">Engineer</th>
        <th class="py-1">Repairs</th><th class="py-1">Complaints closed</th></tr></thead>
      <tbody>
        {% for e in engineers %}
        <tr class="border-b"><td class="py-1">{{ e.name }}
          <span class="text-slate-500">({{ e.employee_id }})</span></td>
          <td class="py-1">{{ e.repairs }}</td>
          <td class="py-1">{{ e.complaints_closed }}</td></tr>
        {% empty %}<tr><td colspan="3" class="py-2 text-slate-500">
          No activity in this window.</td></tr>{% endfor %}
      </tbody>
    </table>
  </div>
</div>
{{ downtime_json|json_script:"downtime-data" }}
{{ complaints_json|json_script:"complaints-data" }}
{{ devices_json|json_script:"devices-data" }}
{{ faults_json|json_script:"faults-data" }}
{% endblock %}
{% block extra_js %}
<script src="{% static 'js/chart.umd.js' %}"></script>
<script>
  function draw(canvasId, scriptId, type, color) {
    const data = JSON.parse(JSON.parse(
      document.getElementById(scriptId).textContent));
    new Chart(document.getElementById(canvasId), {
      type: type,
      data: { labels: data.labels,
              datasets: [{ data: data.values, backgroundColor: color }] },
      options: { plugins: { legend: { display: type === 'doughnut' } },
                 indexAxis: type === 'bar-h' ? 'y' : 'x' },
    });
  }
  draw('chart-downtime', 'downtime-data', 'bar', '#b91c1c');
  draw('chart-complaints', 'complaints-data', 'bar', '#0369a1');
  draw('chart-devices', 'devices-data', 'bar', '#b45309');
  draw('chart-faults', 'faults-data', 'doughnut',
       ['#0369a1', '#b45309', '#15803d', '#b91c1c', '#7c3aed', '#0f766e',
        '#be185d', '#64748b']);
</script>
{% endblock %}
```
(Note `indexAxis: 'bar-h'` is never triggered — all bars are vertical; the helper keeps the option for future use. `JSON.parse` twice because `json_script` wraps the already-JSON string.)

- [ ] **Step 4: Rebuild CSS, run the whole suite**

```powershell
bin\tailwindcss.exe -i static\css\input.css -o static\css\app.css --minify
pytest -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: dashboard metrics module and Chart.js dashboard"
```

---

### Task 14: `seed_demo` management command

**Files:**
- Create: `apps/core/management/__init__.py`, `apps/core/management/commands/__init__.py`, `apps/core/management/commands/seed_demo.py`, `tests/test_seed_demo.py`

**Interfaces:**
- Consumes: every service. Produces: `python manage.py seed_demo` — idempotent guard (refuses if any Equipment exists unless `--flush-first` is NOT offered; simply refuse), creates: 5 departments, ~14 users (1 admin `admin/demo1234`, 3 engineers `engineer1..3/demo1234`, 10 staff `staff1..10/demo1234`), ~60 devices (4 critical: MRI, CT, Angiography, Ventilator), ~90 days of complaint/repair history via the real services with backdated timestamps (queryset `.update()`), a few delay remarks, 2 condemned devices.

- [ ] **Step 1: Write the failing test**

`tests/test_seed_demo.py`:
```python
import pytest
from django.core.management import call_command

from apps.core.models import AuditLog
from apps.equipment.models import Equipment, EquipmentStatus, StatusEvent
from apps.maintenance.models import Complaint, WorkOrder

pytestmark = pytest.mark.django_db


def test_seed_demo_builds_world():
    call_command("seed_demo")
    assert Equipment.objects.count() >= 50
    assert Equipment.objects.filter(is_critical_asset=True).count() >= 4
    assert Equipment.objects.filter(status=EquipmentStatus.CONDEMNED).count() >= 2
    assert Complaint.objects.count() >= 40
    assert WorkOrder.objects.filter(status="completed").count() >= 20
    assert StatusEvent.objects.count() > 0
    assert AuditLog.objects.count() > 0
    # history is spread over time, not all "now"
    first = Complaint.objects.order_by("created_at").first()
    last = Complaint.objects.order_by("created_at").last()
    assert (last.created_at - first.created_at).days > 30


def test_seed_demo_refuses_to_run_twice():
    call_command("seed_demo")
    with pytest.raises(SystemExit):
        call_command("seed_demo")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_seed_demo.py -v`
Expected: FAIL — unknown command.

- [ ] **Step 3: Implement**

`apps/core/management/commands/seed_demo.py`:
```python
import random
import sys
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Roles
from apps.equipment.models import Department, Equipment, StatusEvent
from apps.equipment.services import condemn_equipment
from apps.maintenance.models import Complaint, FaultCategory, WorkOrder
from apps.maintenance.services import (
    add_remark, complete_work_order, lodge_complaint, open_work_order,
    start_repair,
)

DEVICES = [
    ("MRI Scanner", "Siemens", "Magnetom Aera", True),
    ("CT Scanner", "GE Healthcare", "Revolution ACT", True),
    ("Angiography System", "Philips", "Azurion 7", True),
    ("Ventilator", "Hamilton", "C2", True),
    ("Infusion Pump", "B.Braun", "Perfusor Space", False),
    ("Patient Monitor", "Mindray", "uMEC 12", False),
    ("Defibrillator", "Zoll", "R Series", False),
    ("ECG Machine", "Schiller", "Cardiovit AT-102", False),
    ("Suction Machine", "Yuwell", "7A-23D", False),
    ("Syringe Pump", "Medtronic", "SP-500", False),
    ("Ultrasound", "Mindray", "DC-70", False),
    ("Anesthesia Machine", "Draeger", "Fabius Plus", False),
]
COMPLAINT_TEXTS = [
    "Screen goes black after a few minutes of use.",
    "Machine will not power on at all.",
    "Loud clicking noise during operation.",
    "Battery drains within minutes when unplugged.",
    "Error code E-42 shown, alarm keeps beeping.",
    "Readings look wrong compared to the backup unit.",
    "Smells like something is burning inside.",
    "Touch panel not responding to input.",
]
DELAY_TEXTS = [
    "Waiting for spare part from vendor.",
    "Part shipment delayed due to holidays.",
    "Awaiting quotation approval from procurement.",
]


def backdate(model, pk, **fields):
    model.objects.filter(pk=pk).update(**fields)


class Command(BaseCommand):
    help = "Seed the database with realistic demo data. Refuses on non-empty DB."

    def handle(self, *args, **options):
        if Equipment.objects.exists():
            self.stderr.write("Database already has equipment; refusing to seed.")
            sys.exit(1)
        random.seed(42)
        User = get_user_model()
        now = timezone.now()

        departments = [Department.objects.create(name=n, location=l) for n, l in [
            ("ICU", "Block A, Floor 2"), ("Radiology", "Block B, Ground"),
            ("Emergency", "Block A, Ground"), ("Cardiology", "Block C, Floor 1"),
            ("Operation Theater", "Block A, Floor 3"),
        ]]
        admin = User.objects.create_user(
            username="admin", password="demo1234", employee_id="EMP-900",
            role=Roles.ADMIN, first_name="Ayesha", last_name="Malik",
            is_staff=True, is_superuser=True)
        engineers = [User.objects.create_user(
            username=f"engineer{i}", password="demo1234",
            employee_id=f"EMP-10{i}", role=Roles.ENGINEER,
            first_name=f"Engineer{i}", last_name="Demo") for i in range(1, 4)]
        staff = [User.objects.create_user(
            username=f"staff{i}", password="demo1234",
            employee_id=f"EMP-00{i}", role=Roles.STAFF,
            first_name=f"Staff{i}", last_name="Demo",
            department=random.choice(departments)) for i in range(1, 11)]

        devices = []
        serial = 1000
        for name, maker, model, critical in DEVICES:
            for _ in range(random.randint(3, 7)):
                serial += 1
                devices.append(Equipment.objects.create(
                    name=name, manufacturer=maker, vendor="MedServe Ltd",
                    model_number=model, serial_number=f"SN-{serial}",
                    department=random.choice(departments),
                    is_critical_asset=critical,
                    purchase_date=now.date() - timedelta(days=random.randint(400, 3000)),
                    installation_date=now.date() - timedelta(days=random.randint(100, 400)),
                ))

        # ~90 days of complaint -> repair history through the real services
        for day_offset in range(90, 0, -2):
            device = random.choice([d for d in devices
                                    if d.status == "working"])
            device.refresh_from_db()
            if device.status != "working":
                continue
            reporter = random.choice(staff)
            engineer = random.choice(engineers)
            t0 = now - timedelta(days=day_offset, hours=random.randint(0, 8))
            complaint = lodge_complaint(reporter, device,
                                        random.choice(COMPLAINT_TEXTS))
            backdate(Complaint, complaint.pk, created_at=t0)
            wo = open_work_order(device, engineer)
            backdate(WorkOrder, wo.pk, opened_at=t0 + timedelta(hours=1))
            wo.refresh_from_db()
            wo = start_repair(wo, engineer)
            started = t0 + timedelta(hours=random.randint(2, 24))
            backdate(WorkOrder, wo.pk, repair_started_at=started)
            repair_hours = random.choice([2, 4, 6, 12, 24, 48, 96])
            if repair_hours >= 48:
                add_remark(wo, engineer, random.choice(DELAY_TEXTS), kind="delay")
            wo.refresh_from_db()
            wo = complete_work_order(
                wo, engineer,
                fault_category=random.choice(FaultCategory.values),
                remark="Repaired and tested OK.")
            done = started + timedelta(hours=repair_hours)
            backdate(WorkOrder, wo.pk, repair_completed_at=done, closed_at=done)
            # backdate the two status events of this cycle
            for event in StatusEvent.objects.filter(work_order=wo):
                ts = started if event.new_status == "in_repair" else done
                backdate(StatusEvent, event.pk, created_at=ts)

        # a couple of currently-open complaints for the queue demo
        for _ in range(4):
            device = random.choice([d for d in devices if d.status == "working"])
            device.refresh_from_db()
            if device.status == "working":
                lodge_complaint(random.choice(staff), device,
                                random.choice(COMPLAINT_TEXTS))

        # two condemned devices
        for device in random.sample(
                [d for d in devices if not d.is_critical_asset], 2):
            device.refresh_from_db()
            if device.status == "working":
                condemn_equipment(device, admin,
                                  remark="Beyond economical repair.",
                                  condemned_location="Condemned store, basement")

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {Equipment.objects.count()} devices, "
            f"{Complaint.objects.count()} complaints, "
            f"{WorkOrder.objects.count()} work orders. "
            "Logins: admin/demo1234, engineer1/demo1234, staff1/demo1234"))
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_seed_demo.py -v` then the full suite `pytest -v`
Expected: all PASS. Then try it for real:
```powershell
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```
Log in as `engineer1/demo1234` — queue, registry, dashboard all show data.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: seed_demo command with 90 days of realistic history"
```

---

### Task 15: Docker Compose deployment + Procrastinate wiring

**Files:**
- Create: `Dockerfile`, `nginx.conf`, `config/procrastinate.py`
- Modify: `docker-compose.yml` (add web, worker, nginx), `config/settings/base.py` (add procrastinate app), `.env.example` (add OLLAMA_MODEL placeholder for Phase 2), `requirements.txt` (already has procrastinate)

**Interfaces:**
- Produces: `docker compose up` serves the app at `http://localhost:8080` (nginx → gunicorn), with migrations applied on start and a procrastinate worker running (empty task registry — tasks arrive in Phase 2).

- [ ] **Step 1: Write the deployment files**

`Dockerfile`:
```dockerfile
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV DJANGO_SETTINGS_MODULE=config.settings.prod
RUN SECRET_KEY=collectstatic-dummy python manage.py collectstatic --noinput
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
```

`nginx.conf`:
```nginx
server {
    listen 80;
    client_max_body_size 20m;
    location /static/ { alias /staticfiles/; }
    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

`config/procrastinate.py`:
```python
"""Procrastinate wiring. Phase 1 registers no tasks; Phase 2 adds them in
apps/ai/tasks.py. The worker runs fine with an empty registry."""
```

Add `"procrastinate.contrib.django",` to `INSTALLED_APPS` in `config/settings/base.py` (below the django.contrib entries).

Replace `docker-compose.yml` with:
```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-cmms}
      POSTGRES_USER: ${POSTGRES_USER:-cmms}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-cmms}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-cmms}"]
      interval: 5s
      timeout: 3s
      retries: 10

  web:
    build: .
    env_file: .env
    environment:
      POSTGRES_HOST: db
    command: >
      sh -c "python manage.py migrate --noinput &&
             gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3"
    volumes:
      - staticfiles:/app/staticfiles
    depends_on:
      db:
        condition: service_healthy

  worker:
    build: .
    env_file: .env
    environment:
      POSTGRES_HOST: db
    command: python manage.py procrastinate worker
    depends_on:
      db:
        condition: service_healthy

  nginx:
    image: nginx:alpine
    ports:
      - "8080:80"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - staticfiles:/staticfiles:ro
    depends_on:
      - web

volumes:
  pgdata:
  staticfiles:
```

Append to `.env.example`:
```
# Phase 2 (LLM) — unused in Phase 1
OLLAMA_MODEL=llama3.1:8b
```

- [ ] **Step 2: Verify compose config and migrations run**

```powershell
Copy-Item .env.example .env
docker compose config
docker compose up -d --build
docker compose exec web python manage.py seed_demo
```
Expected: `docker compose config` prints the resolved file with no errors; all four containers healthy; seeding succeeds.

- [ ] **Step 3: Smoke-test in a browser**

Open `http://localhost:8080/accounts/login/` — log in as `engineer1/demo1234`; check queue, equipment registry, a device detail page, dashboard charts render. Check the worker log shows a connected worker: `docker compose logs worker` → "Starting worker".

- [ ] **Step 4: Run the deploy checklist**

```powershell
docker compose exec web python manage.py check --deploy
```
Expected: warnings about SECRET_KEY/SSL settings are acceptable for a demo (documented in `.env.example`); no errors.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: docker compose deployment - nginx, gunicorn, worker, procrastinate wiring"
```

---

## Verification sweep (after all tasks)

- `pytest -v` — entire suite green.
- `docker compose up` + browser walkthrough: staff lodges complaint → engineer opens WO → starts → equipment shows In Repair → complaint blocked for that device → complete with fault category → equipment Working, complaint closed → dashboard reflects it → condemn a device → its history intact, complaints blocked.
- `git log --oneline` — one commit per task minimum.

## Out of scope for this plan (per spec)

Phase 2: Ollama client, risk scoring, monthly PDF report, CSV importer. Phase 3: device chat, nightly backup, SMTP notifications. Do not build any of it here.

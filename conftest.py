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

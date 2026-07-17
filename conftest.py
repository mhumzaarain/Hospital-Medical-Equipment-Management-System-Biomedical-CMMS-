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

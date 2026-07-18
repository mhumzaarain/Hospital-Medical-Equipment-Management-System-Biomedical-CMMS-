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


def test_login_page_shows_logo(client):
    # the logo renders via the base-template nav and the login card
    response = client.get("/accounts/login/")
    assert b"img/logo.png" in response.content

import pytest

from apps.maintenance.models import Complaint, FunctionalConfirmation

pytestmark = pytest.mark.django_db


def test_complaint_confirmation_fields_default_null(equipment, staff_user):
    c = Complaint.objects.create(
        equipment=equipment, reporter=staff_user, description="x"
    )
    assert c.functional_confirmation is None
    assert c.confirmed_at is None


def test_functional_confirmation_choices():
    assert FunctionalConfirmation.FUNCTIONAL == "functional"
    assert FunctionalConfirmation.NOT_FUNCTIONAL == "not_functional"

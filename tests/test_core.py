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

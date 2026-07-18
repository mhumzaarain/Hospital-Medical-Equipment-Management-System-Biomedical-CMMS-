import pytest


@pytest.mark.django_db
def test_database_roundtrip():
    from django.contrib.contenttypes.models import ContentType

    assert ContentType.objects.count() >= 0


def test_settings_load():
    from django.conf import settings

    assert settings.AUTH_USER_MODEL == "accounts.User"
    assert settings.USE_TZ is True

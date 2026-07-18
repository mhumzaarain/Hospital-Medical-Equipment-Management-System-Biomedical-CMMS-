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

import pytest
from django.db import IntegrityError, transaction

from apps.maintenance.models import (
    Remark,
    RemarkKind,
    WorkOrder,
    WorkOrderStatus,
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

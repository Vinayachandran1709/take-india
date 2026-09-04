import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BatchSchedule, Merchant, Service, ServiceCustomField, StaffMember
from scripts.seed import seed_data


@pytest.mark.asyncio
async def test_seed_is_idempotent(db: AsyncSession) -> None:
    await seed_data(db)
    await seed_data(db)
    assert await db.scalar(select(func.count(Merchant.id))) == 3
    assert await db.scalar(select(func.count(Service.id))) == 3
    assert await db.scalar(select(func.count(StaffMember.id))) == 2
    assert await db.scalar(select(func.count(BatchSchedule.id))) == 3
    assert await db.scalar(select(func.count(ServiceCustomField.id))) == 3

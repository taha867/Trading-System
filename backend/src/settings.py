from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.models import Setting

SETTING_ID = 1


class SettingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    shop_name: str | None = None
    shop_address: str | None = None


class SettingUpdate(BaseModel):
    shop_name: Annotated[str, Field(max_length=120)] | None = None
    shop_address: Annotated[str, Field(max_length=255)] | None = None


async def get_or_create_setting(db: AsyncSession) -> Setting:
    setting = await db.get(Setting, SETTING_ID)
    if setting is None:
        setting = Setting(id=SETTING_ID)
        db.add(setting)
        await db.commit()
        await db.refresh(setting)
    return setting


router = APIRouter(tags=["settings"])


@router.get("", response_model=SettingRead)
async def read_setting(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await get_or_create_setting(db)


@router.put("", response_model=SettingRead)
async def update_setting(
    payload: SettingUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    setting = await get_or_create_setting(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(setting, field, value)
    await db.commit()
    await db.refresh(setting)
    return setting

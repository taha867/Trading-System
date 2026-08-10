from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.parties import service
from src.parties.constants import PartyRole
from src.parties.models import Party


async def valid_party(party_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> Party:
    return await service.get_active_party(db, party_id)


async def valid_china_vendor(party: Annotated[Party, Depends(valid_party)]) -> Party:
    # Unused by any route in Phase 1 (purchasing/service.py calls service.get_active_party +
    # service.ensure_role directly, since its party_id comes from a JSON body field, not a path
    # param — see purchasing/service.py's create_purchase_order). Kept as the composable,
    # path-param form of the same rule for Phase 5's local-vendor purchase flow.
    return service.ensure_role(party, PartyRole.CHINA_VENDOR)

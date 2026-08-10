from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.cargo.exceptions import MissingBasisValue, PurchaseOrderNotOpen
from src.cargo.models import CargoAllocation, CargoCostBasis, CargoMode, CargoShipment
from src.cargo.schemas import CargoShipmentCreate, CargoShipmentRead
from src.cargo.utils import money
from src.exceptions import ConflictException, NotFoundException
from src.pagination import PaginatedResponse, PaginationParams
from src.parties import service as parties_service
from src.parties.constants import PartyRole
from src.purchasing.exceptions import PurchaseOrderNotFound
from src.purchasing.models import PurchaseOrderLine


async def create_shipment(db: AsyncSession, payload: CargoShipmentCreate) -> CargoShipment:
    agent = await parties_service.get_active_party(db, payload.cargo_agent_id)
    parties_service.ensure_role(agent, PartyRole.CARGO_AGENT)

    mode = await db.get(CargoMode, payload.cargo_mode_id)
    if not mode or not mode.is_active:
        raise NotFoundException("Cargo mode not found or inactive")

    basis = await db.get(CargoCostBasis, payload.cost_basis_id)
    if not basis or not basis.is_active:
        raise NotFoundException("Cost basis not found or inactive")

    # Attachment is whole-PO (PLAN.md: "attach one or more open POs"), so this single
    # query pulls every line under every requested PO — no separate per-line filter.
    result = await db.execute(
        select(PurchaseOrderLine)
        .where(PurchaseOrderLine.purchase_order_id.in_(payload.purchase_order_ids))
        .options(selectinload(PurchaseOrderLine.purchase_order))
        .order_by(PurchaseOrderLine.id)
    )
    lines = result.scalars().all()

    found_po_ids = {line.purchase_order_id for line in lines}
    if missing := set(payload.purchase_order_ids) - found_po_ids:
        raise PurchaseOrderNotFound(f"Purchase order id(s) not found: {sorted(missing)}")

    for line in lines:
        # source == "local" is checked explicitly (not just status != "draft") as a
        # belt-and-suspenders backstop: local orders are created straight into
        # "allocated" and normally never reach this check at all, but if some future
        # reopen/correction path ever resets a PO back to "draft", this still keeps a
        # local order from being attached to a shipment and having its landed_cost_pkr
        # silently overwritten with a wrong, freight-inflated value.
        if line.purchase_order.source == "local" or line.purchase_order.status != "draft":
            raise PurchaseOrderNotOpen(
                f"Purchase order {line.purchase_order_id} cannot be attached to a cargo shipment "
                "(local-sourced orders skip cargo entirely; china-sourced orders must be in 'draft' status)"
            )

    basis_values: dict[int, Decimal] = {}
    if basis.code == "piece":
        if payload.line_basis_values:
            raise MissingBasisValue("Piece-basis shipments derive the split from qty — do not supply basis values")
        for line in lines:
            basis_values[line.id] = line.qty
    else:
        provided = {v.purchase_order_line_id: v.basis_value for v in payload.line_basis_values}
        for line in lines:
            value = provided.get(line.id)
            if value is None or value <= 0:
                raise MissingBasisValue(f"Line {line.id} needs a positive {basis.code} figure")
            basis_values[line.id] = value

    total_basis = sum(basis_values.values())

    # Split total_cost_pkr proportionally, then correct the last line (by id) for
    # rounding drift so the allocations always sum to exactly total_cost_pkr.
    allocations: list[CargoAllocation] = []
    allocated_so_far = Decimal(0)
    for idx, line in enumerate(lines):
        if idx == len(lines) - 1:
            allocated_cost = money(payload.total_cost_pkr - allocated_so_far)
        else:
            allocated_cost = money(payload.total_cost_pkr * basis_values[line.id] / total_basis)
            allocated_so_far += allocated_cost

        allocations.append(
            CargoAllocation(
                purchase_order_line_id=line.id,
                basis_value=basis_values[line.id],
                allocated_cost_pkr=allocated_cost,
            )
        )
        line.landed_cost_pkr = money(line.rate_pkr + allocated_cost / line.qty)

    for po_id in found_po_ids:
        po = next(line.purchase_order for line in lines if line.purchase_order_id == po_id)
        po.status = "allocated"

    # allocations passed through the relationship (not inserted standalone) so
    # shipment.allocations stays loaded through flush()/commit() (expire_on_commit=False)
    # without tripping the lazy="raise" guard on a fresh query.
    shipment = CargoShipment(
        cargo_agent_id=agent.id,
        cargo_mode_id=mode.id,
        cost_basis_id=basis.id,
        shipment_date=payload.shipment_date,
        total_cost_pkr=payload.total_cost_pkr,
        allocations=allocations,
    )
    db.add(shipment)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException("Cargo shipment could not be saved") from exc

    return shipment


async def list_shipments(db: AsyncSession, pagination: PaginationParams) -> PaginatedResponse[CargoShipmentRead]:
    offset = (pagination.page - 1) * pagination.page_size

    total = await db.scalar(select(func.count()).select_from(CargoShipment))
    result = await db.execute(
        select(CargoShipment)
        .options(selectinload(CargoShipment.allocations))
        .order_by(CargoShipment.id)
        .offset(offset)
        .limit(pagination.page_size)
    )
    items = result.scalars().all()

    return PaginatedResponse[CargoShipmentRead](
        items=items,
        total=total or 0,
        page=pagination.page,
        page_size=pagination.page_size,
    )

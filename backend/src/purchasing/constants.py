from typing import Literal

# Phase 2 introduces the first status transition: a PO stays "draft" (open, attachable
# to a cargo shipment) until every one of its lines gets a landed cost, then flips to
# "allocated" (src.cargo.service.create_shipment). Phase 3 adds the terminal transition:
# once every line has been received into a StockLot, the PO flips to "received"
# (src.inventory.service.receive_purchase_order_line). There is no status after this.
PurchaseOrderStatus = Literal["draft", "allocated", "received"]

# "china" orders go through the RMB/exchange-rate lookup above and must pass through
# cargo.service.create_shipment to earn a landed cost before they can reach "allocated".
# "local" and "mohsin" orders are quoted directly in PKR and skip both — they're created
# straight into "allocated" with landed_cost_pkr already set
# (src.purchasing.service.create_purchase_order), which also means they can never be
# attached to a shipment (cargo.service.create_shipment rejects any PO that isn't "draft",
# and now source in ("local", "mohsin") explicitly, too).
# "mohsin" is not a commercial vendor relationship like "local" — it tags stock Shakeel
# received as his share when he and Mohsin split their formerly-joint business, so it
# needs to stay visually/reportably distinct from ongoing local-vendor purchasing even
# though it's priced/received identically.
PurchaseOrderSource = Literal["china", "local", "mohsin"]

MAX_INVOICE_NUMBER_LOOKUP_IDS = 500  # matches PaginationParams' page_size ceiling — one statement page can't exceed it
MAX_INVOICE_OPTIONS = 500  # how many invoice numbers the Purchase Orders dropdown lists at once (search narrows it)

# Why a PurchaseLogException exists instead of a PurchaseOrder: "no_model" — the day book gave a
# category (e.g. "TPU", "Borderless") but no phone model, so no specific Item/StockLot can be
# created. Only the money owed to the supplier is recorded (a plain str column, same convention
# as SalesLogExceptionKind — the Literal is enforced at the Pydantic layer).
PurchaseLogExceptionKind = Literal["no_model"]

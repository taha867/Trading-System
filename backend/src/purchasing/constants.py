from typing import Literal

# Phase 2 introduces the first status transition: a PO stays "draft" (open, attachable
# to a cargo shipment) until every one of its lines gets a landed cost, then flips to
# "allocated" (src.cargo.service.create_shipment). Phase 3 adds the terminal transition:
# once every line has been received into a StockLot, the PO flips to "received"
# (src.inventory.service.receive_purchase_order_line). There is no status after this.
PurchaseOrderStatus = Literal["draft", "allocated", "received"]

# "china" orders go through the RMB/exchange-rate lookup above and must pass through
# cargo.service.create_shipment to earn a landed cost before they can reach "allocated".
# "local" orders are quoted directly in PKR and skip both — they're created straight into
# "allocated" with landed_cost_pkr already set (src.purchasing.service.create_purchase_order),
# which also means they can never be attached to a shipment (cargo.service.create_shipment
# rejects any PO that isn't "draft", and now source == "local" explicitly, too).
PurchaseOrderSource = Literal["china", "local"]

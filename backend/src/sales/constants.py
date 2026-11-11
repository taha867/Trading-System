from typing import Literal

# Matches EVERY value scripts/import_daybook_sept2026_* write to SalesLogException.kind
# (a plain str column, same convention as PurchaseOrderStatus / StockMovementType — the
# Literal is enforced only at the Pydantic layer, so a kind missing here can't be filtered on).
# "insufficient_stock" is a sale line for a real item that had no stock recorded at the time: the
# money is posted to the customer, but no stock was taken out (the largest group by far).
SalesLogExceptionKind = Literal[
    "cancelled_invoice", "bulk_mixed_models", "blank_model", "correction", "discount", "insufficient_stock"
]

# The "Show" choice on the Invoices list. An invoice is a sale plus any day-book entries (no stock found, bulk,
# correction, discount, cancelled) that share its number.
InvoiceShow = Literal["all", "has_no_stock", "has_other_entries", "cancelled", "fully_booked"]

MAX_INVOICE_NUMBER_LOOKUP_IDS = 500  # matches PaginationParams' page_size ceiling — one statement page can't exceed it

MAX_INVOICE_OPTIONS = 500  # how many invoice numbers the Sales Orders dropdown lists at once (search narrows it)
MAX_CANCELLED_ENTRIES = 50  # cancelled invoices listed alongside the sales list (the true count is returned separately)

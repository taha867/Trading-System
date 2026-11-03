from typing import Literal

# Matches the values scripts/import_daybook_sept2026_* write to SalesLogException.kind
# (a plain str column, same convention as PurchaseOrderStatus / StockMovementType — the
# Literal is enforced only at the Pydantic layer).
SalesLogExceptionKind = Literal["cancelled_invoice", "bulk_mixed_models", "blank_model", "correction", "discount"]

MAX_INVOICE_NUMBER_LOOKUP_IDS = 500  # matches PaginationParams' page_size ceiling — one statement page can't exceed it

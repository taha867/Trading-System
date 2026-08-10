from typing import Literal

PaymentDirection = Literal["in", "out"]

# Loose, non-FK-validated link — mirrors LedgerEntry.reference_type/reference_id.
# "expense" doesn't exist as a domain until Phase 7; kept here so payments/ never
# needs to change again once it does.
PaymentReferenceType = Literal["sales_order", "purchase_order", "expense"]

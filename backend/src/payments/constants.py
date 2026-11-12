from typing import Literal

PaymentDirection = Literal["in", "out"]

# Loose, non-FK-validated link — mirrors LedgerEntry.reference_type/reference_id.
# "expense" doesn't exist as a domain until Phase 7; kept here so payments/ never
# needs to change again once it does.
PaymentReferenceType = Literal["sales_order", "purchase_order", "expense"]

# What a payment row IS, for the Payments list's filter and totals (derived, not stored):
#   customer_receipt = money in from a party; supplier_payment = money out to a party;
#   expense = money out recorded by an expense; other = anything else (no party, no expense).
PaymentKind = Literal["customer_receipt", "supplier_payment", "expense", "other"]
PAYMENT_KINDS: tuple[str, ...] = ("customer_receipt", "supplier_payment", "expense", "other")


def classify_payment(direction: str, party_id: int | None, reference_type: str | None) -> str:
    """The same rule as the SQL CASE in service.list_payment_transactions (kept here as plain code so it is tested)."""
    if reference_type == "expense":
        return "expense"
    if party_id is not None:
        return "customer_receipt" if direction == "in" else "supplier_payment"
    return "other"

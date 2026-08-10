from src.exceptions import AppException, NotFoundException


class PurchaseOrderNotFound(NotFoundException):
    detail = "Purchase order not found"


class ExchangeRateMissingForDate(AppException):
    status_code = 422
    detail = "No exchange rate is set for this order's date"


class InvalidPurchaseOrderItem(AppException):
    status_code = 422
    detail = "One or more items on this purchase order are unknown or inactive"

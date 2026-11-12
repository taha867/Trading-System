from src.exceptions import AppException, NotFoundException


class PaymentAccountNotFound(NotFoundException):
    detail = "Payment account not found"


class InvalidPaymentFilter(AppException):
    status_code = 422
    detail = "Invalid payment filter"

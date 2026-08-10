from src.exceptions import NotFoundException


class PaymentAccountNotFound(NotFoundException):
    detail = "Payment account not found"

from src.exceptions import AppException, NotFoundException


class SalesOrderNotFound(NotFoundException):
    detail = "Sales order not found"


class InvalidSalesOrderItem(AppException):
    status_code = 422
    detail = "One or more items on this sales order are unknown, inactive, or duplicated"

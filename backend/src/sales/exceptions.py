from src.exceptions import AppException, NotFoundException


class SalesOrderNotFound(NotFoundException):
    detail = "Sales order not found"


class InvalidSalesFilter(AppException):
    status_code = 422
    detail = "Invalid sales filter"


class InvalidSalesOrderItem(AppException):
    status_code = 422
    detail = "One or more items on this sales order are unknown, inactive, or duplicated"

from src.exceptions import AppException, NotFoundException


class ItemNotFound(NotFoundException):
    detail = "Item not found"


class InvalidCatalogName(AppException):
    status_code = 422
    detail = "Invalid catalog name or item code"

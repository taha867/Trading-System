from src.exceptions import AppException, NotFoundException


class CargoShipmentNotFound(NotFoundException):
    detail = "Cargo shipment not found"


class PurchaseOrderNotOpen(AppException):
    status_code = 422
    detail = "One or more attached purchase orders cannot be attached to a cargo shipment"


class MissingBasisValue(AppException):
    status_code = 422
    detail = "A positive basis figure is required for every attached line under this cost basis"

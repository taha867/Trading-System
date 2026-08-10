from src.exceptions import AppException, ConflictException, NotFoundException


class PurchaseOrderLineNotFound(NotFoundException):
    detail = "Purchase order line not found"


class LineNotAllocated(AppException):
    status_code = 422
    detail = "This line has no landed cost yet — attach it to a cargo shipment before receiving"


class LineAlreadyReceived(ConflictException):
    detail = "This purchase order line has already been received into a stock lot"


class StockLotNotFound(NotFoundException):
    detail = "Stock lot not found"


class InvalidAdjustment(AppException):
    status_code = 422
    detail = "Adjustment is invalid"


class InsufficientStock(AppException):
    status_code = 422
    detail = "Insufficient stock to fulfil this line"

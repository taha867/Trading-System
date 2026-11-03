from src.exceptions import AppException


class InvalidReportPeriod(AppException):
    status_code = 422
    detail = "Invalid report period"

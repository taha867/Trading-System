from src.exceptions import AppException, NotFoundException


class PartyNotFound(NotFoundException):
    detail = "Party not found"


class PartyRoleMismatch(AppException):
    status_code = 422
    detail = "Party does not have the required role"

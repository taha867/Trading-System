from src.exceptions import AppException


class InvalidCredentials(AppException):
    status_code = 401
    detail = "Invalid username or password"


class TokenExpired(AppException):
    status_code = 401
    detail = "Token has expired"


class TokenInvalid(AppException):
    status_code = 401
    detail = "Token is invalid"

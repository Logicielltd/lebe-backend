from fastapi import HTTPException


class AuthenticationError(HTTPException):
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(status_code=401, detail=detail)


class InvalidCredentialsError(AuthenticationError):
    def __init__(self):
        super().__init__(detail="Invalid email or password")


class AccountNotVerifiedError(AuthenticationError):
    def __init__(self):
        super().__init__(detail="Account not verified. Please verify your email.")


class AccountLockedError(AuthenticationError):
    def __init__(self, unlock_time: str = None):
        detail = "Account temporarily locked due to too many failed attempts"
        if unlock_time:
            detail += f". Try again after {unlock_time}"
        super().__init__(detail=detail)


class TokenExpiredError(AuthenticationError):
    def __init__(self):
        super().__init__(detail="Token has expired. Please log in again.")


class InvalidTokenError(AuthenticationError):
    def __init__(self):
        super().__init__(detail="Invalid token. Please log in again.")


class PermissionDeniedError(HTTPException):
    def __init__(self, detail: str = "Permission denied"):
        super().__init__(status_code=403, detail=detail)
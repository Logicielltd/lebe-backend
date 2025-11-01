from fastapi import HTTPException
from core.exceptions.FileException import AuthenticationError


class SessionExpiredError(AuthenticationError):
    def __init__(self):
        super().__init__(detail="Session has expired. Please log in again.")


class InvalidRefreshTokenError(AuthenticationError):
    def __init__(self):
        super().__init__(detail="Invalid refresh token")


class TokenCreationError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=500,
            detail="Failed to create authentication token"
        )
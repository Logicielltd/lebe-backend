from fastapi import HTTPException


class UserAlreadyExistsError(HTTPException):
    def __init__(self, field: str = "email"):
        super().__init__(
            status_code=400,
            detail=f"User with this {field} already exists"
        )

class UserNotFoundError(HTTPException):
    def __init__(self):
        super().__init__(status_code=404, detail="User not found")


class InvalidPasswordError(HTTPException):
    def __init__(self, detail: str = "Invalid password"):
        super().__init__(status_code=400, detail=detail)


class PasswordComplexityError(HTTPException):
    def __init__(self, requirements: str):
        super().__init__(
            status_code=400,
            detail=f"Password does not meet requirements: {requirements}"
        )


class EmailNotVerifiedError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=403,
            detail="Email address not verified. Please verify your email."
        )
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic.error_wrappers import ErrorWrapper
from starlette.requests import Request

from utilities.exceptions import DatabaseValidationError


async def database_validation_exception_handler(request: Request, exc: DatabaseValidationError) -> JSONResponse:
    return await request_validation_exception_handler(
        request,
        RequestValidationError([ErrorWrapper(ValueError(exc.message), exc.field or "__root__")]),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Custom handler for Pydantic validation errors to maintain consistent response format"""
    errors = exc.errors()
    
    # Extract the first error for consistent messaging
    if errors:
        error = errors[0]
        field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        message = error["msg"]
        
        # Create consistent error response format
        return JSONResponse(
            status_code=400,
            content={"detail": f"Validation error in {field}: {message}"}
        )
    
    # Fallback to default handler
    return await request_validation_exception_handler(request, exc)


class ObjectDoesNotExist(Exception):
    pass

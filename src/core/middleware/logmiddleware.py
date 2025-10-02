import json
import time
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from core.auditlogging.service.logservice import logging_service

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = None
        error = None
        
        try:
            response = await call_next(request)
            return response
        except HTTPException as http_exc:
            error = f"HTTPException: {http_exc.detail}"
            response = Response(
                content=json.dumps({"detail": http_exc.detail}),
                status_code=http_exc.status_code,
                media_type="application/json"
            )
            raise http_exc
        except Exception as exc:
            error = f"Unhandled exception: {str(exc)}"
            response = Response(
                content=json.dumps({"detail": "Internal server error"}),
                status_code=500,
                media_type="application/json"
            )
            raise exc
        finally:
            processing_time = time.time() - start_time
            await logging_service.log_request(
                request=request,
                response=response,
                processing_time=processing_time,
                error=error
            )
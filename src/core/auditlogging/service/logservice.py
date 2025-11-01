import time
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import json
from loguru import logger
from core.auditlogging.handlers.loghandler import MongoDBHandler
from config import settings

class APILoggingService:
    def __init__(self):
        self.mongo_handler = MongoDBHandler(
            connection_string=settings.MONGO_URI,
            database_name=settings.MONGO_DB_NAME,
            collection_name="api_logs"
        )
    
    async def log_request(
        self,
        request: Request,
        response: Optional[Response] = None,
        processing_time: Optional[float] = None,
        error: Optional[str] = None
    ):
        try:
            # Extract request details
            client_host = request.client.host if request.client else "unknown"
            method = request.method
            url = str(request.url)
            endpoint = request.url.path
            
            # Try to read body (for POST/PUT requests)
            body = None
            if method in ["POST", "PUT", "PATCH"]:
                try:
                    body = await request.body()
                    # Convert bytes to string and try to parse as JSON
                    body_str = body.decode()
                    if body_str:
                        body = json.loads(body_str)
                except:
                    body = "Non-JSON body or unable to parse"
            
            # Prepare log data
            log_data = {
                "timestamp": datetime.utcnow(),
                "level": "ERROR" if error else "INFO",
                "client_ip": client_host,
                "method": method,
                "endpoint": endpoint,
                "url": url,
                "query_params": dict(request.query_params),
                "request_body": body,
                "processing_time_ms": processing_time * 1000 if processing_time else None,
                "error": error,
                "user_agent": request.headers.get("user-agent"),
                "status_code": response.status_code if response else None
            }
            
            # Insert into MongoDB
            self.mongo_handler.insert_log(log_data)
            
            # Also log to console for development
            if error:
                logger.error(f"{method} {url} - Error: {error}")
            else:
                logger.info(f"{method} {url} - {response.status_code if response else 'No response'}")
                
        except Exception as e:
            logger.error(f"Failed to log request: {str(e)}")
    
    def log_custom_event(
        self,
        level: str,
        message: str,
        extra_data: Optional[Dict[str, Any]] = None,
        user_email: Optional[str] = None
    ):
        """Log custom events (user actions, system events, etc.)"""
        log_data = {
            "timestamp": datetime.utcnow(),
            "level": level.upper(),
            "message": message,
            "user_email": user_email,
            "type": "custom_event",
            "extra_data": extra_data or {}
        }
        
        self.mongo_handler.insert_log(log_data)
        logger.log(level.upper(), message)

# Global instance
logging_service = APILoggingService()
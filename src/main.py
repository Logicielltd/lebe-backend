from fastapi import FastAPI
from fastapi_jwt_auth import AuthJWT
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseSettings
from routes import base_routes
from core.auth.controller.authcontroller import auth_routes
from core.user.controller.usercontroller import user_routes
from core.cloudstorage.controller.storagecontoller import storage_routes
from core.profile.controller.profilecontroller import profile_routes
from core.notification.controller.notificationcontroller import notification_routes
from core.payments.controller.billcontroller import bill_routes
from core.payments.controller.invoicecontroller import invoice_routes
from core.payments.controller.paymentcontroller import payment_routes
from core.agent.controller.agentcontroller import agent_routes

from dotenv import load_dotenv
import os
from utilities.dbconfig import Base, engine
from config import settings
from utilities.exceptions import DatabaseValidationError
import exceptions
from core.middleware.logmiddleware import LoggingMiddleware
from core.auditlogging.service.logservice import logging_service
from config import settings
import logging
from loguru import logger

# Initialize FastAPI app
app = FastAPI( 
    title=settings.SERVICE_NAME,
    version="1.0",
    description="""**LambdarCore API** An ML focused app infrastructure deployed with python.
    
    Default Endpoints
    
    "Authentication",
    "File and Document Management",
    "Message and Task Queuing",
    "Notifications",
    """,
    contact={
        "name": "API Support",
        "url": "http://support@lambdarcorp.com",
        "email": "mail@lambdarcorp.com",
    },
    license_info={
        "name": "MIT",
    },
)

# print("Creating tables...")
# Base.metadata.create_all(bind=engine)
# print("Tables created successfully.")

# Add middleware for CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# # Add logging middleware
# app.add_middleware(LoggingMiddleware)

# # Configure loguru
# logger.add(
#     "logs/api.log",
#     rotation="500 MB",
#     retention="10 days",
#     level=settings.LOG_LEVEL,
#     format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
# )

app.add_exception_handler(DatabaseValidationError, exceptions.database_validation_exception_handler)

# Register the routes
app.include_router(base_routes, prefix="/api/v1", tags=["Base Routes"])
app.include_router(storage_routes, prefix="/api/v1/storage", tags=["Storage Routes"])
app.include_router(auth_routes, prefix="/api/v1/auth", tags=["Auth Routes"])
app.include_router(user_routes, prefix="/api/v1/user", tags=["User Routes"])
app.include_router(profile_routes, prefix="/api/v1/profile", tags=["Profile Routes"])
app.include_router(notification_routes, prefix="/api/v1/notification", tags=["Notification Routes"])
app.include_router(payment_routes, prefix="/api/v1/payment", tags=["Payment Routes"])
app.include_router(bill_routes, prefix="/api/v1/bill", tags=["Billing Routes"])
app.include_router(invoice_routes, prefix="/api/v1/invoice", tags=["Invoice Routes"])
app.include_router(agent_routes, prefix="/api/v1/agent", tags=["Agent Routes"])

# AuthJWT Configuration
class JWTSettings(BaseSettings):
    authjwt_secret_key: str = settings.SECRET_KEY
    authjwt_algorithm: str = settings.ALGORITHM
    authjwt_access_token_expires: int = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # in seconds
    authjwt_refresh_token_expires: int = settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60  # in seconds


@AuthJWT.load_config
def get_config():
    return JWTSettings()

# Run the app (if using `uvicorn`)
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=settings.DEBUG,
    )

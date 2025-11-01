from fastapi import FastAPI
from fastapi_jwt_auth import AuthJWT
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseSettings
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.routes import base_routes
from src.core.auth.controller.authcontroller import auth_routes
from src.core.user.controller.usercontroller import user_routes
from src.core.cloudstorage.controller.storagecontoller import storage_routes
from src.core.profile.controller.profilecontroller import profile_routes
from src.core.notification.controller.notificationcontroller import notification_routes
from src.core.payments.controller.billcontroller import bill_routes
from src.core.payments.controller.invoicecontroller import invoice_routes
from src.core.payments.controller.paymentcontroller import payment_routes
from src.core.otp.controller.otpcontroller import otp_routes
from src.core.subscription.controller.subscription_controller import subscription_routes
from src.core.webhooks.controller.webhookscontroller import webhooks_routes

from src.utilities.dbconfig import Base, engine
from src.config import settings
from src.utilities.exceptions import DatabaseValidationError
import src.exceptions
from fastapi.exceptions import RequestValidationError
# from src.core.middleware.logmiddleware import LoggingMiddleware
from src.core.auditlogging.service.logservice import logging_service
from src.config import settings
import logging
from loguru import logger
from sqlalchemy import inspect

# Initialize FastAPI app
app = FastAPI( 
    title=settings.SERVICE_NAME,
    version="1.0",
    description="""**Lebe Core API** An AI focused app infrastructure deployed with python.
    
    Default Endpoints
    
    "Authentication",
    "File and Document Management",
    "Message and Task Queuing",
    "Notifications",
    """,
    contact={
        "name": "API Support",
        "url": "http://support@lebe.com",
        "email": "mail@lebe.com",
    },
    license_info={
        "name": "MIT",
    },
)



def tables_exist():
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    return len(existing_tables) > 0

# Initialize database tables only if they don't exist
if not tables_exist():
    print("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables initialized successfully.")
else:
    print("Database tables already exist.")

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
app.add_exception_handler(RequestValidationError, exceptions.validation_exception_handler)

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
app.include_router(otp_routes, prefix="/api/v1/otp", tags=["OTP Routes"])
app.include_router(subscription_routes, prefix="/api/v1/subscription", tags=["Subscription Routes"])
app.include_router(webhooks_routes, prefix="/api/v1/webhooks", tags=["Webhooks Routes"])

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
        port=3090,
        reload=settings.DEBUG,
    )

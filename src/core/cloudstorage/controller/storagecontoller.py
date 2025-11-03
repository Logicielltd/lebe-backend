from fastapi import APIRouter, Depends, HTTPException, UploadFile, status, Query
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from core.auth.service.sessiondriver import SessionDriver, TokenData
from fastapi_jwt_auth import AuthJWT
from core.cloudstorage.dto.filedto import FileDTO
from core.exceptions import *
from core.notification.dto.request.notificationcreate import NotificationCreateRequest
from core.notification.dto.request.notificationupdate import NotificationUpdateRequest
from utilities.dbconfig import SessionLocal
from sqlalchemy.orm import Session
import logging
from core.notification.model.Notification import Notification, NotificationStatus, NotificationType
from core.user.model.User import User

# DTO Models
from core.notification.dto.response.notification_response import NotificationResponse
from core.notification.dto.response.paged_notifications import PagedNotificationResponse
from core.notification.dto.response.message_response import MessageResponse

from core.notification.service.notification_service import NotificationService
from fastapi_jwt_auth.exceptions import MissingTokenError
from core.cloudstorage.service.storageservice import StorageService
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Reuse your existing token validation and DB dependencies
from core.user.controller.usercontroller import validate_token, get_db


storage_routes = APIRouter()

storage_service = StorageService()

@storage_routes.post("/upload", response_model=FileDTO)
async def upload_file(file: UploadFile, authjwt: AuthJWT = Depends(validate_token)):
    url = storage_service.upload_file(
        file.file,
        file.filename,
        content_type=file.content_type
    )
    return FileDTO(file_name=file.filename, file_url=url)


from fastapi.responses import FileResponse
import os

@storage_routes.get("/download/{file_name}")
async def download_file(file_name: str, authjwt: AuthJWT = Depends(validate_token)):
    # Sanitize file name
    safe_name = os.path.basename(file_name)

    # Ensure downloads directory exists
    os.makedirs("./downloads", exist_ok=True)

    destination_path = f"./downloads/{safe_name}"
    try:
        storage_service.download_file(safe_name, destination_path)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found: {safe_name}")
    

    # Return file to client
    return FileResponse(destination_path, filename=safe_name)


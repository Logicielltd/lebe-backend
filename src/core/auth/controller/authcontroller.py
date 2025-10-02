from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import MissingTokenError
import jwt
from sqlalchemy.orm import Session
from core.auth.service.sessiondriver import SessionDriver, TokenData
from core.exceptions import *
from core.auth.dto.request.user_create import UserCreateRequest
from core.auth.dto.request.userlogin import UserLoginRequest
from core.auth.dto.request.resetpassword import ResetPasswordRequest
from core.auth.dto.request.resetpassnoauth import ResetPassNoAuth
from core.auth.service.authservice import AuthService
from core.exceptions.AuthException import InvalidCredentialsError
from core.exceptions.UserException import UserAlreadyExistsError
from utilities.dbconfig import SessionLocal
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def validate_token(authjwt: AuthJWT = Depends()):
    try:
        authjwt.jwt_required()
        return authjwt
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401, 
            detail="Token expired. Please log in again."
        )
    except MissingTokenError:
        raise HTTPException(
            status_code=401,
            detail="No token found. Please create an account and log in.",
        )
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {str(e)}"
        )
    
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
    
auth_routes = APIRouter()

@auth_routes.post("/signup")
def signup(request: UserCreateRequest, db: Session = Depends(get_db)):
    auth_service = AuthService(db)

    return auth_service.create_user(request)


@auth_routes.post("/signin")
def signin(user: UserLoginRequest, db: Session = Depends(get_db), authjwt: AuthJWT = Depends()):
    auth_service = AuthService(db)

    return auth_service.signin(user)

        
@auth_routes.post("/signout")
def signout(authjwt: AuthJWT = Depends(validate_token), db: Session = Depends(get_db)):
        token = authjwt._token
        auth_service = AuthService(db)
        
        return auth_service.signout(token)

@auth_routes.post("/verify-account")
async def verify_account(
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    auth_service = AuthService(db)
    return auth_service.verify_account(email)

@auth_routes.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    auth_service = AuthService(db)
    return auth_service.reset_password(request)

@auth_routes.post("/no-auth/reset-password")
async def reset_password_no_auth(
    request: ResetPassNoAuth,
    db: Session = Depends(get_db)
):
    auth_service = AuthService(db)
    return auth_service.reset_password_no_auth(request)

@auth_routes.post("/refresh")
async def refresh_token(
    refresh_token: str = Form(...),
    db: Session = Depends(get_db)
):
    auth_service = AuthService(db)
    return auth_service.refresh_tokens(refresh_token)

@auth_routes.get("/validate")
async def validate_session(
    authjwt: AuthJWT = Depends(validate_token)
):
    current_user_email = authjwt.get_jwt_subject()
    
    return {"email": current_user_email, "valid": True}

@auth_routes.post("/signout-all")
async def signout_all_sessions(
    authjwt: AuthJWT = Depends(validate_token),
    db: Session = Depends(get_db)
):
        token = authjwt._token
        
        auth_service = AuthService(db)
        
        auth_service.signout_all(token)
        return {"message": "Logged out from all devices"}

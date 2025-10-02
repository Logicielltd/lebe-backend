from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import MissingTokenError
import jwt
from sqlalchemy.orm import Session
from core.agent.agent import BusinessAssistant
from core.agent.dto.commandreqeust import CommandRequest
from core.exceptions import *
from core.auth.dto.request.user_create import UserCreateRequest
from core.auth.service.authservice import AuthService
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
    
agent_routes = APIRouter()

@agent_routes.post("/command")
def agent(query: CommandRequest, db: Session = Depends(get_db)):

    assistant = BusinessAssistant()
    
    return assistant.process_query(query.query)

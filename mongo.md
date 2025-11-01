from core.logging.logging_service import logging_service

@auth_routes.post("/signup")
def signup(request: UserCreateRequest, db: Session = Depends(get_db)):
    try:
        auth_service = AuthService(db)
        result = auth_service.create_user(request)
        
        # Log successful signup
        logging_service.log_custom_event(
            level="INFO",
            message=f"User registered successfully: {request.email}",
            user_email=request.email
        )
        
        return result
    except UserAlreadyExistsError as e:
        # Log failed signup attempt
        logging_service.log_custom_event(
            level="WARNING",
            message=f"Signup attempt with existing email: {request.email}",
            user_email=request.email
        )
        raise e

@auth_routes.post("/signin")
def signin(user: UserLoginRequest, db: Session = Depends(get_db), authjwt: AuthJWT = Depends()):
    try:
        auth_service = AuthService(db)
        result = auth_service.signin(user)
        
        # Log successful login
        logging_service.log_custom_event(
            level="INFO",
            message="User logged in successfully",
            user_email=user.email
        )
        
        return result
    except InvalidCredentialsError as e:
        # Log failed login attempt
        logging_service.log_custom_event(
            level="WARNING",
            message=f"Failed login attempt for email: {user.email}",
            user_email=user.email
        )
        raise e

@auth_routes.post("/signout")
def signout(authjwt: AuthJWT = Depends(validate_token), db: Session = Depends(get_db)):
    try:
        token = authjwt._token
        current_user_email = authjwt.get_jwt_subject()
        auth_service = AuthService(db)
        result = auth_service.signout(token)
        
        # Log signout
        logging_service.log_custom_event(
            level="INFO",
            message="User signed out",
            user_email=current_user_email
        )
        
        return result
    except Exception as e:
        logging_service.log_custom_event(
            level="ERROR",
            message=f"Signout error: {str(e)}",
            user_email=current_user_email if 'current_user_email' in locals() else "unknown"
        )
        raise e
        
from core.logging.logging_service import logging_service

# Log user actions
logging_service.log_custom_event(
    level="INFO",
    message="User uploaded file",
    user_email=user_email,
    extra_data={"file_name": "document.pdf", "file_size": 1024}
)

# Log errors
try:
    # some operation
except Exception as e:
    logging_service.log_custom_event(
        level="ERROR",
        message=f"Operation failed: {str(e)}",
        user_email=user_email
    )
    raise
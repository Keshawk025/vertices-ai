import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel

from auth.auth_service import get_db, User, get_password_hash, verify_password
from firebase.firebase_admin import verify_firebase_token, sync_user
from auth.jwt_service import create_access_token, verify_token  # Kept for backward compatibility

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer()


class UserCreate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None


class UserLogin(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    token = credentials.credentials
    email: Optional[str] = None
    uid: Optional[str] = None
    firebase_info: Dict[str, Any] = {}

    # Try Firebase ID Token verification
    try:
        payload = verify_firebase_token(token)
        email = payload.get("email") or payload.get("sub")
        uid = payload.get("uid") or payload.get("user_id") or payload.get("sub") or email
        firebase_info = payload.get("firebase", {})
    except Exception as fb_err:
        # Fallback to legacy JWT for backward compatibility during transition
        try:
            payload = verify_token(token)
            email = payload.get("sub")
            uid = f"uid_{email}"
            logger.info("Firebase token verified (legacy fallback)")
        except ValueError as jwt_err:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(fb_err) if str(fb_err) in ["Expired token", "Invalid token"] else str(jwt_err),
                headers={"WWW-Authenticate": "Bearer"},
            )

    if not email or not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Sync user document in Firestore (created_at, last_login, email, provider)
    sync_user(
        uid=uid,
        email=email,
        provider=firebase_info
    )

    # Sync or fetch local DB user record for relational endpoints
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            name=email.split("@")[0],
            email=email,
            password_hash="firebase_managed"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Attach Firebase metadata to runtime user object
    user.uid = uid
    user.provider = firebase_info.get("sign_in_provider", "firebase")
    return user


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    if not user_data.email or not user_data.password:
        raise HTTPException(status_code=400, detail="Email and password are required.")
    
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered.")
        
    hashed_pwd = get_password_hash(user_data.password)
    new_user = User(
        name=user_data.name or user_data.email.split("@")[0],
        email=user_data.email,
        password_hash=hashed_pwd
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    token = create_access_token({"sub": new_user.email})
    logger.info(f"User registered: {new_user.email}")
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": new_user.id,
            "email": new_user.email,
            "name": new_user.name
        }
    }


@router.post("/login")
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    if not login_data.email or not login_data.password:
        raise HTTPException(status_code=400, detail="Email and password are required.")
        
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user or not user.password_hash or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
        
    token = create_access_token({"sub": user.email})
    logger.info(f"User logged in: {user.email}")
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name
        }
    }



@router.get("/me")
def read_users_me(current_user: User = Depends(get_current_user)):
    return {
        "uid": getattr(current_user, "uid", f"uid_{current_user.id}"),
        "email": current_user.email,
        "provider": getattr(current_user, "provider", "firebase"),
        "id": current_user.id,
        "name": current_user.name
    }


@router.get("/status")
def auth_status(current_user: User = Depends(get_current_user)):
    return {
        "authenticated": True,
        "uid": getattr(current_user, "uid", f"uid_{current_user.id}"),
        "email": current_user.email,
        "provider": getattr(current_user, "provider", "firebase")
    }



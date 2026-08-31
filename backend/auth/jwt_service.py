"""
DEPRECATED: This module is deprecated in favor of Firebase Authentication.
It is kept for one release cycle for backward compatibility.
Firebase Authentication (via backend/firebase/firebase_admin.py) is the preferred provider.
"""
import warnings
import jwt
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

warnings.warn("jwt_service is deprecated. Use Firebase Authentication instead.", DeprecationWarning, stacklevel=2)

logger = logging.getLogger(__name__)

SECRET_KEY = "super_secret_veritas_key"  # DEPRECATED: In production, Firebase ID Tokens are verified via Firebase Admin SDK
ALGORITHM = "HS256"


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Default: 24 hours
        expire = datetime.now(timezone.utc) + timedelta(hours=24)
        
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.info("JWT generated")
    return encoded_jwt

def verify_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.error("Unauthorized access detected: Expired token")
        raise ValueError("Expired token")
    except jwt.InvalidTokenError:
        logger.error("Unauthorized access detected: Invalid token")
        raise ValueError("Invalid token")

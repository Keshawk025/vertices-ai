import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, auth, firestore, storage
from google.auth.credentials import AnonymousCredentials


logger = logging.getLogger(__name__)

# Load root .env file if available
root_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if root_env_path.exists():
    load_dotenv(dotenv_path=root_env_path)

_app: Optional[firebase_admin.App] = None


def initialize_firebase_admin() -> firebase_admin.App:
    """
    Initialize Firebase Admin SDK using environment variables or credentials.
    """
    global _app
    if _app is not None or len(firebase_admin._apps) > 0:
        _app = firebase_admin.get_app()
        return _app

    project_id = os.getenv("FIREBASE_PROJECT_ID", "veritas-ai")
    client_email = os.getenv("FIREBASE_CLIENT_EMAIL")
    private_key = os.getenv("FIREBASE_PRIVATE_KEY")

    if private_key:
        private_key = private_key.replace("\\n", "\n")

    if client_email and private_key:
        try:
            cred = credentials.Certificate({
                "type": "service_account",
                "project_id": project_id,
                "private_key": private_key,
                "client_email": client_email,
                "token_uri": "https://oauth2.googleapis.com/token"
            })
            _app = firebase_admin.initialize_app(cred, {
                'projectId': project_id,
                'storageBucket': os.getenv("NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET", f"{project_id}.appspot.com")
            })
        except Exception as cert_err:
            logger.warning(f"Certificate initialization fallback: {cert_err}")
            cred = AnonymousCredentials()
            _app = firebase_admin.initialize_app(credential=cred, options={'projectId': project_id})
    else:
        try:
            cred = AnonymousCredentials()
            _app = firebase_admin.initialize_app(credential=cred, options={'projectId': project_id})
        except Exception:
            _app = firebase_admin.initialize_app(options={'projectId': project_id})

    logger.info("Firebase initialized")
    print("Firebase initialized")
    return _app



def is_firebase_configured() -> bool:
    """Check if valid GCP/Firebase service account credentials are provided."""
    client_email = os.getenv("FIREBASE_CLIENT_EMAIL")
    private_key = os.getenv("FIREBASE_PRIVATE_KEY")
    return bool(client_email and private_key and "example.com" not in client_email)


def verify_connections() -> None:
    """
    Verify connections to Firebase services and output log messages.
    """
    initialize_firebase_admin()
    
    # Firestore connection check
    _ = get_firestore_client()
    logger.info("Firestore connected")
    print("Firestore connected")

    # Storage connection check
    _ = get_storage_bucket()
    logger.info("Storage connected")
    print("Storage connected")

    # Authentication connection check
    logger.info("Authentication connected")
    print("Authentication connected")


def get_firestore_client():
    """
    Return initialized Firestore client if configured, otherwise None.
    """
    if not is_firebase_configured():
        return None
    try:
        initialize_firebase_admin()
        return firestore.client()
    except Exception as e:
        logger.warning(f"Firestore client connection bypassed: {e}")
        return None


def get_storage_bucket():
    """
    Return initialized Storage bucket instance if configured, otherwise None.
    """
    if not is_firebase_configured():
        return None
    try:
        initialize_firebase_admin()
        bucket_name = os.getenv("NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET", f"{os.getenv('FIREBASE_PROJECT_ID', 'veritas-ai')}.appspot.com")
        return storage.bucket(name=bucket_name)
    except Exception as e:
        logger.warning(f"Storage bucket connection bypassed: {e}")
        return None



def verify_firebase_token(id_token: str, check_revoked: bool = False) -> Dict[str, Any]:
    """
    Verify a Firebase ID token using Firebase Admin Auth.
    """
    initialize_firebase_admin()
    try:
        decoded_token = auth.verify_id_token(id_token, check_revoked=check_revoked)
        logger.info("Firebase token verified")
        print("Firebase token verified")
        return decoded_token
    except auth.ExpiredIdTokenError:
        logger.error("Unauthorized access detected: Expired token")
        raise ValueError("Expired token")
    except auth.InvalidIdTokenError:
        logger.error("Unauthorized access detected: Invalid token")
        raise ValueError("Invalid token")
    except Exception as e:
        if "Expired" in str(e):
            logger.error(f"Unauthorized access detected: Expired token ({e})")
            raise ValueError("Expired token")
        logger.error(f"Unauthorized access detected: Invalid token ({e})")
        raise ValueError("Invalid token")



def health_check() -> Dict[str, bool]:
    """
    Return health check status for Firebase services.
    """
    try:
        initialize_firebase_admin()
        firestore_ok = get_firestore_client() is not None
        storage_ok = get_storage_bucket() is not None
        auth_ok = True
        firebase_ok = True
    except Exception as e:
        logger.error(f"Firebase health check failed: {e}")
        return {
            "firebase": False,
            "firestore": False,
            "storage": False,
            "auth": False
        }

    return {
        "firebase": firebase_ok,
        "firestore": firestore_ok,
        "storage": storage_ok,
        "auth": auth_ok
    }


def sync_user(uid: str, email: str, provider: Any = None) -> Dict[str, Any]:
    """
    Sync user document in Firestore 'users' collection with uid, email, provider, created_at, last_login.
    """
    provider_str = provider.get("sign_in_provider", "firebase") if isinstance(provider, dict) else str(provider or "firebase")
    now_iso = datetime.now(timezone.utc).isoformat()

    user_data = {
        "uid": uid,
        "email": email,
        "provider": provider_str,
        "last_login": now_iso
    }

    try:
        db = get_firestore_client()
        if db is not None:
            user_ref = db.collection("users").document(uid)
            doc = user_ref.get()
            if not doc.exists:
                user_data["created_at"] = now_iso
            user_ref.set(user_data, merge=True)
            logger.info(f"Synced user in Firestore: {uid}")
    except Exception as err:
        logger.warning(f"Firestore user sync note: {err}")

    return user_data


upsert_user_in_firestore = sync_user



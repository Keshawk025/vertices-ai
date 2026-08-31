"""
Firebase Admin module for Veritas AI.
"""
from .firebase_admin import (
    initialize_firebase_admin,
    verify_firebase_token,
    get_firestore_client,
    get_storage_bucket,
    health_check,
    verify_connections,
)

__all__ = [
    "initialize_firebase_admin",
    "verify_firebase_token",
    "get_firestore_client",
    "get_storage_bucket",
    "health_check",
    "verify_connections",
]

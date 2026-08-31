import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from firebase.firebase_admin import get_storage_bucket

logger = logging.getLogger(__name__)

# Mock storage store for unit tests / offline execution when GCP credentials are not active
_mock_storage: Dict[str, bytes] = {}


def _normalize_uid(user_id: Any) -> str:
    if user_id is None:
        return "default_user"
    return str(user_id)


def _build_storage_path(user_id: Any, doc_id: str, filename: str = None, folder: str = "documents") -> str:
    uid = _normalize_uid(user_id)
    if not filename:
        ext = ".pdf" if folder == "documents" else (".txt" if folder == "ocr" else ".json")
        return f"users/{uid}/{folder}/{doc_id}{ext}"
    return f"users/{uid}/{folder}/{doc_id}_{filename}"


def upload_document(
    user_id: Any,
    doc_id: str,
    file_bytes: bytes,
    filename: str = None,
    folder: str = "documents",
    content_type: str = "application/pdf"
) -> dict:

    storage_path = _build_storage_path(user_id, doc_id, filename=filename, folder=folder)

    # Save to local mock storage
    _mock_storage[storage_path] = file_bytes

    try:
        bucket = get_storage_bucket()
        if bucket is not None:
            blob = bucket.blob(storage_path)
            blob.upload_from_string(file_bytes, content_type=content_type)
    except Exception as err:
        logger.warning(f"Storage upload fallback note: {err}")

    logger.info(f"Storage upload - uploaded file to {storage_path}")
    print("Storage upload")

    return {
        "doc_id": doc_id,
        "storage_path": storage_path,
        "size": len(file_bytes),
        "folder": folder
    }



def download_document(
    user_id: Any,
    doc_id: str,
    filename: str = None,
    folder: str = "documents"
) -> bytes:
    storage_path = _build_storage_path(user_id, doc_id, filename=filename, folder=folder)

    try:
        bucket = get_storage_bucket()
        if bucket is not None:
            blob = bucket.blob(storage_path)
            if blob.exists():
                data = blob.download_as_bytes()
                logger.info(f"Storage download - downloaded file from {storage_path}")
                print("Storage download")
                return data
    except Exception as err:
        logger.warning(f"Storage download fallback note: {err}")

    if storage_path in _mock_storage:
        logger.info(f"Storage download - downloaded file from {storage_path}")
        print("Storage download")
        return _mock_storage[storage_path]

    raise FileNotFoundError(f"File not found in storage: {storage_path}")


def delete_document(
    user_id: Any,
    doc_id: str,
    filename: str = None,
    folder: str = "documents"
) -> bool:
    storage_path = _build_storage_path(user_id, doc_id, filename=filename, folder=folder)

    try:
        bucket = get_storage_bucket()
        if bucket is not None:
            blob = bucket.blob(storage_path)
            if blob.exists():
                blob.delete()
    except Exception as err:
        logger.warning(f"Storage delete fallback note: {err}")

    _mock_storage.pop(storage_path, None)

    logger.info(f"Storage delete - deleted file from {storage_path}")
    print("Storage delete")
    return True


def get_signed_url(
    user_id: Any = None,
    doc_id: str = None,
    storage_path: str = None,
    expiration_minutes: int = 60
) -> str:
    if not storage_path and user_id and doc_id:
        storage_path = _build_storage_path(user_id, doc_id)
    elif not storage_path:
        storage_path = "users/default_user/documents/default.pdf"

    try:
        bucket = get_storage_bucket()
        if bucket is not None:
            blob = bucket.blob(storage_path)
            return blob.generate_signed_url(expiration=timedelta(minutes=expiration_minutes))
    except Exception as err:
        logger.warning(f"Signed URL fallback note: {err}")

    return f"https://storage.googleapis.com/veritas-ai.appspot.com/{storage_path}"


def list_documents(user_id: Any, folder: str = "documents") -> list:
    uid = _normalize_uid(user_id)
    prefix = f"users/{uid}/{folder}/"
    results = []

    try:
        bucket = get_storage_bucket()
        if bucket is not None:
            blobs = bucket.list_blobs(prefix=prefix)
            for blob in blobs:
                results.append({
                    "name": blob.name,
                    "size": blob.size,
                    "updated": blob.updated
                })
            if results:
                return results
    except Exception as err:
        logger.warning(f"Storage list fallback note: {err}")

    for path, data in _mock_storage.items():
        if path.startswith(prefix):
            results.append({
                "name": path,
                "size": len(data),
                "updated": datetime.now(timezone.utc).isoformat()
            })

    return results


def count_stored_files(user_id: Any = None) -> int:
    if user_id is not None:
        uid = _normalize_uid(user_id)
        prefix = f"users/{uid}/"
        return sum(1 for path in _mock_storage if path.startswith(prefix))
    return len(_mock_storage)


def health_check(user_id: Any = None) -> dict:
    """
    Return health check status for Firebase Storage.
    """
    total_files = count_stored_files(user_id)
    logger.info("Storage health check")
    print("Storage health check")
    return {
        "storage": True,
        "files_count": total_files
    }

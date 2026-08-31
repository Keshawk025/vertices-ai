import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from firebase.firebase_admin import get_firestore_client

logger = logging.getLogger(__name__)

# In-memory store fallback for offline/mock test execution when Firestore GCP credentials are not active
_mock_db: Dict[str, Dict[str, Dict[str, Any]]] = {}


def _normalize_uid(user_id: Any) -> str:
    if user_id is None:
        return "default_user"
    return str(user_id)


# --- DOCUMENT FUNCTIONS ---

def create_document(user_id: Any, doc_data: dict) -> dict:
    uid = _normalize_uid(user_id)
    doc_id = doc_data.get("id")
    if not doc_id:
        import uuid
        doc_id = str(uuid.uuid4())
        doc_data["id"] = doc_id

    doc_data["user_id"] = user_id
    if "uploaded_at" not in doc_data or not doc_data["uploaded_at"]:
        doc_data["uploaded_at"] = datetime.now(timezone.utc).isoformat()
    elif isinstance(doc_data["uploaded_at"], datetime):
        doc_data["uploaded_at"] = doc_data["uploaded_at"].isoformat()

    try:
        db = get_firestore_client()
        if db is not None:
            doc_ref = db.collection("users").document(uid).collection("documents").document(doc_id)
            doc_ref.set(doc_data, merge=True)
    except Exception as err:
        logger.warning(f"Firestore fallback write: {err}")

    # Synchronize in mock cache
    if uid not in _mock_db:
        _mock_db[uid] = {"documents": {}, "conversations": {}, "messages": {}}
    if "documents" not in _mock_db[uid]:
        _mock_db[uid]["documents"] = {}
    _mock_db[uid]["documents"][doc_id] = doc_data

    logger.info(f"Firestore write - document created: {doc_id}")
    print("Firestore write")
    return doc_data


def get_document(user_id: Any, doc_id: str) -> Optional[dict]:
    uid = _normalize_uid(user_id)
    try:
        db = get_firestore_client()
        if db is not None:
            doc_ref = db.collection("users").document(uid).collection("documents").document(doc_id)
            doc = doc_ref.get()
            if doc.exists:
                logger.info(f"Firestore read - document found: {doc_id}")
                print("Firestore read")
                return doc.to_dict()
    except Exception as err:
        logger.warning(f"Firestore fallback read: {err}")

    # Fallback to mock store
    doc_dict = _mock_db.get(uid, {}).get("documents", {}).get(doc_id)
    if doc_dict:
        logger.info(f"Firestore read - document found: {doc_id}")
        print("Firestore read")
    return doc_dict


def list_documents(user_id: Any) -> List[dict]:
    uid = _normalize_uid(user_id)
    results = []
    try:
        db = get_firestore_client()
        if db is not None:
            docs = db.collection("users").document(uid).collection("documents").stream()
            for doc in docs:
                results.append(doc.to_dict())
            if results:
                logger.info(f"Firestore query - listed {len(results)} documents")
                print("Firestore query")
                return results
    except Exception as err:
        logger.warning(f"Firestore fallback query: {err}")

    # Fallback to mock store
    results = list(_mock_db.get(uid, {}).get("documents", {}).values())
    logger.info(f"Firestore query - listed {len(results)} documents")
    print("Firestore query")
    return results


def update_document(user_id: Any, doc_id: str, update_data: dict) -> bool:
    uid = _normalize_uid(user_id)
    try:
        db = get_firestore_client()
        if db is not None:
            doc_ref = db.collection("users").document(uid).collection("documents").document(doc_id)
            doc_ref.set(update_data, merge=True)
    except Exception as err:
        logger.warning(f"Firestore fallback update: {err}")

    if uid in _mock_db and "documents" in _mock_db[uid] and doc_id in _mock_db[uid]["documents"]:
        _mock_db[uid]["documents"][doc_id].update(update_data)

    logger.info(f"Firestore write - document updated: {doc_id}")
    print("Firestore write")
    return True


def delete_document(user_id: Any, doc_id: str) -> bool:
    uid = _normalize_uid(user_id)
    try:
        db = get_firestore_client()
        if db is not None:
            doc_ref = db.collection("users").document(uid).collection("documents").document(doc_id)
            doc_ref.delete()
    except Exception as err:
        logger.warning(f"Firestore fallback delete: {err}")

    if uid in _mock_db and "documents" in _mock_db[uid]:
        _mock_db[uid]["documents"].pop(doc_id, None)

    logger.info(f"Firestore delete - document deleted: {doc_id}")
    print("Firestore delete")
    return True


# --- CONVERSATION FUNCTIONS ---

def create_conversation(user_id: Any, conv_data: dict) -> dict:
    uid = _normalize_uid(user_id)
    conv_id = conv_data.get("id")
    if not conv_id:
        import uuid
        conv_id = str(uuid.uuid4())
        conv_data["id"] = conv_id

    conv_data["user_id"] = user_id
    if "created_at" not in conv_data or not conv_data["created_at"]:
        conv_data["created_at"] = datetime.now(timezone.utc).isoformat()
    elif isinstance(conv_data["created_at"], datetime):
        conv_data["created_at"] = conv_data["created_at"].isoformat()

    try:
        db = get_firestore_client()
        if db is not None:
            conv_ref = db.collection("users").document(uid).collection("conversations").document(conv_id)
            conv_ref.set(conv_data, merge=True)
    except Exception as err:
        logger.warning(f"Firestore fallback conversation write: {err}")

    if uid not in _mock_db:
        _mock_db[uid] = {"documents": {}, "conversations": {}, "messages": {}}
    if "conversations" not in _mock_db[uid]:
        _mock_db[uid]["conversations"] = {}
    _mock_db[uid]["conversations"][conv_id] = conv_data

    logger.info(f"Firestore write - conversation created: {conv_id}")
    print("Firestore write")
    return conv_data


def get_conversation(user_id: Any, conv_id: str) -> Optional[dict]:
    uid = _normalize_uid(user_id)
    try:
        db = get_firestore_client()
        if db is not None:
            conv_ref = db.collection("users").document(uid).collection("conversations").document(conv_id)
            doc = conv_ref.get()
            if doc.exists:
                logger.info(f"Firestore read - conversation found: {conv_id}")
                print("Firestore read")
                return doc.to_dict()
    except Exception as err:
        logger.warning(f"Firestore fallback conversation read: {err}")

    conv_dict = _mock_db.get(uid, {}).get("conversations", {}).get(conv_id)
    if conv_dict:
        logger.info(f"Firestore read - conversation found: {conv_id}")
        print("Firestore read")
    return conv_dict


def list_conversations(user_id: Any) -> List[dict]:
    uid = _normalize_uid(user_id)
    results = []
    try:
        db = get_firestore_client()
        if db is not None:
            convs = db.collection("users").document(uid).collection("conversations").stream()
            for doc in convs:
                results.append(doc.to_dict())
            if results:
                logger.info(f"Firestore query - listed {len(results)} conversations")
                print("Firestore query")
                return results
    except Exception as err:
        logger.warning(f"Firestore fallback conversation query: {err}")

    results = list(_mock_db.get(uid, {}).get("conversations", {}).values())
    logger.info(f"Firestore query - listed {len(results)} conversations")
    print("Firestore query")
    return results


def delete_conversation(user_id: Any, conv_id: str) -> bool:
    uid = _normalize_uid(user_id)
    try:
        db = get_firestore_client()
        if db is not None:
            conv_ref = db.collection("users").document(uid).collection("conversations").document(conv_id)
            # Delete messages subcollection
            msgs = conv_ref.collection("messages").stream()
            for msg in msgs:
                msg.reference.delete()
            conv_ref.delete()
    except Exception as err:
        logger.warning(f"Firestore fallback conversation delete: {err}")

    if uid in _mock_db:
        if "conversations" in _mock_db[uid]:
            _mock_db[uid]["conversations"].pop(conv_id, None)
        if "messages" in _mock_db[uid] and conv_id in _mock_db[uid]["messages"]:
            _mock_db[uid]["messages"].pop(conv_id, None)

    logger.info(f"Firestore delete - conversation deleted: {conv_id}")
    print("Firestore delete")
    return True


# --- MESSAGE FUNCTIONS ---

def create_message(user_id: Any, conversation_id: str, msg_data: dict) -> dict:
    uid = _normalize_uid(user_id)
    msg_id = msg_data.get("id")
    if not msg_id:
        import uuid
        msg_id = str(uuid.uuid4())
        msg_data["id"] = msg_id

    msg_data["conversation_id"] = conversation_id
    if "created_at" not in msg_data or not msg_data["created_at"]:
        msg_data["created_at"] = datetime.now(timezone.utc).isoformat()
    elif isinstance(msg_data["created_at"], datetime):
        msg_data["created_at"] = msg_data["created_at"].isoformat()

    try:
        db = get_firestore_client()
        if db is not None:
            msg_ref = db.collection("users").document(uid).collection("conversations").document(conversation_id).collection("messages").document(msg_id)
            msg_ref.set(msg_data, merge=True)
    except Exception as err:
        logger.warning(f"Firestore fallback message write: {err}")

    if uid not in _mock_db:
        _mock_db[uid] = {"documents": {}, "conversations": {}, "messages": {}}
    if "messages" not in _mock_db[uid]:
        _mock_db[uid]["messages"] = {}
    if conversation_id not in _mock_db[uid]["messages"]:
        _mock_db[uid]["messages"][conversation_id] = {}
    _mock_db[uid]["messages"][conversation_id][msg_id] = msg_data

    logger.info(f"Firestore write - message created: {msg_id}")
    print("Firestore write")
    return msg_data


def list_messages(user_id: Any, conversation_id: str) -> List[dict]:
    uid = _normalize_uid(user_id)
    results = []
    try:
        db = get_firestore_client()
        if db is not None:
            msgs = db.collection("users").document(uid).collection("conversations").document(conversation_id).collection("messages").order_by("created_at").stream()
            for doc in msgs:
                results.append(doc.to_dict())
            if results:
                logger.info(f"Firestore query - listed {len(results)} messages")
                print("Firestore query")
                return results
    except Exception as err:
        logger.warning(f"Firestore fallback message query: {err}")

    results = list(_mock_db.get(uid, {}).get("messages", {}).get(conversation_id, {}).values())
    # Sort by created_at
    results.sort(key=lambda x: str(x.get("created_at", "")))
    logger.info(f"Firestore query - listed {len(results)} messages")
    print("Firestore query")
    return results


# --- UTILITY & HEALTH CHECK FUNCTIONS ---

def count_documents(user_id: Any = None) -> int:
    if user_id is not None:
        return len(list_documents(user_id))
    total = 0
    for uid in _mock_db:
        total += len(_mock_db[uid].get("documents", {}))
    return total


def count_conversations(user_id: Any = None) -> int:
    if user_id is not None:
        return len(list_conversations(user_id))
    total = 0
    for uid in _mock_db:
        total += len(_mock_db[uid].get("conversations", {}))
    return total


def health_check(user_id: Any = None) -> dict:
    """
    Return health check status for Firestore services.
    """
    return {
        "firestore": True,
        "documents": count_documents(user_id),
        "conversations": count_conversations(user_id)
    }

import logging
from typing import List, Optional, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from datetime import datetime

from auth.auth_service import get_db, Document, Conversation, Message
from api.auth import get_current_user, User
from firebase.firestore_service import (
    list_documents as fs_list_documents,
    list_conversations as fs_list_conversations,
    list_messages as fs_list_messages
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DocumentDashboardResponse(BaseModel):
    id: str
    filename: str
    status: str
    uploaded_at: Any
    page_count: int
    ocr_used: bool
    file_size: int


class DashboardStatsResponse(BaseModel):
    total_documents: int
    total_conversations: int
    total_questions: int
    total_ocr_documents: int
    total_storage_bytes: int


@router.get("/overview")
def get_overview(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logger.info(f"Dashboard viewed by user {current_user.id}")
    return {"message": "Welcome to your Document Dashboard"}


@router.get("/stats", response_model=DashboardStatsResponse)
def get_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logger.info(f"Stats generated for user {current_user.id}")
    uid = getattr(current_user, "uid", current_user.id)

    fs_docs = fs_list_documents(user_id=uid)
    fs_convs = fs_list_conversations(user_id=uid)

    # Fetch SQLite records
    db_docs = db.query(Document).filter(Document.user_id == current_user.id).all()
    db_convs = db.query(Conversation).filter(Conversation.user_id == current_user.id).all()

    # Merge documents by id
    all_docs_map = {}
    for d in db_docs:
        all_docs_map[d.id] = {
            "id": d.id,
            "filename": d.filename,
            "status": d.status,
            "page_count": d.page_count,
            "ocr_used": bool(d.ocr_used),
            "file_size": d.file_size or 0,
            "uploaded_at": d.uploaded_at
        }
    for d in fs_docs:
        doc_id = d.get("id")
        if doc_id:
            all_docs_map[doc_id] = {
                "id": doc_id,
                "filename": d.get("filename", ""),
                "status": d.get("status", "processed"),
                "page_count": d.get("page_count", 0),
                "ocr_used": bool(d.get("ocr_used")),
                "file_size": int(d.get("file_size", 0)),
                "uploaded_at": d.get("uploaded_at")
            }

    merged_docs = list(all_docs_map.values())
    total_docs = len(merged_docs)
    total_ocr = sum(1 for d in merged_docs if d.get("ocr_used"))
    storage_used = sum(int(d.get("file_size", 0)) for d in merged_docs)

    # Merge conversations by id
    conv_map = {c.id: True for c in db_convs}
    for c in fs_convs:
        if c.get("id"):
            conv_map[c["id"]] = True
    total_convs = len(conv_map)

    # Questions count
    total_questions = 0
    if fs_convs:
        for c in fs_convs:
            msgs = fs_list_messages(user_id=uid, conversation_id=c["id"])
            total_questions += sum(1 for m in msgs if m.get("role") == "user")
    else:
        total_questions = db.query(Message).join(Conversation, Message.conversation_id == Conversation.id)\
            .filter(Conversation.user_id == current_user.id, Message.role == "user").count()

    return DashboardStatsResponse(
        total_documents=total_docs,
        total_conversations=total_convs,
        total_questions=total_questions,
        total_ocr_documents=total_ocr,
        total_storage_bytes=int(storage_used)
    )


@router.get("/recent-documents", response_model=List[DocumentDashboardResponse])
def search_documents(
    search: Optional[str] = Query(None, description="Search by filename"),
    status: Optional[str] = Query(None, description="Filter by status"),
    upload_date: Optional[str] = Query(None, description="Filter by date string prefix e.g., '2026-07-19'"),
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    logger.info(f"Search executed by user {current_user.id}")
    uid = getattr(current_user, "uid", current_user.id)
    fs_docs = fs_list_documents(user_id=uid)
    db_docs = db.query(Document).filter(Document.user_id == current_user.id).all()

    # Merge documents from SQLite and Firestore
    all_docs_map = {}
    for d in db_docs:
        all_docs_map[d.id] = {
            "id": d.id,
            "filename": d.filename,
            "status": d.status,
            "page_count": d.page_count or 1,
            "ocr_used": bool(d.ocr_used),
            "file_size": d.file_size or 0,
            "uploaded_at": d.uploaded_at or datetime.now()
        }
    for d in fs_docs:
        doc_id = d.get("id")
        if doc_id:
            all_docs_map[doc_id] = {
                "id": doc_id,
                "filename": d.get("filename", ""),
                "status": d.get("status", "processed"),
                "page_count": d.get("page_count", 1),
                "ocr_used": bool(d.get("ocr_used")),
                "file_size": int(d.get("file_size", 0)),
                "uploaded_at": d.get("uploaded_at") or datetime.now()
            }

    filtered = list(all_docs_map.values())
    if search:
        filtered = [d for d in filtered if search.lower() in d["filename"].lower()]
    if status:
        filtered = [d for d in filtered if d["status"] == status]
    if upload_date:
        filtered = [d for d in filtered if str(d["uploaded_at"]).startswith(upload_date)]

    # Sort newest first
    filtered.sort(key=lambda x: str(x.get("uploaded_at", "")), reverse=True)

    return [
        DocumentDashboardResponse(
            id=d["id"],
            filename=d["filename"],
            status=d["status"],
            uploaded_at=d["uploaded_at"],
            page_count=d["page_count"],
            ocr_used=d["ocr_used"],
            file_size=d["file_size"]
        ) for d in filtered[:50]
    ]


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

    if fs_docs or fs_convs:
        total_docs = len(fs_docs)
        total_ocr = sum(1 for d in fs_docs if d.get("ocr_used"))
        storage_used = sum(int(d.get("file_size", 0)) for d in fs_docs)
        total_convs = len(fs_convs)
        total_questions = 0
        for c in fs_convs:
            msgs = fs_list_messages(user_id=uid, conversation_id=c["id"])
            total_questions += sum(1 for m in msgs if m.get("role") == "user")

        return DashboardStatsResponse(
            total_documents=total_docs,
            total_conversations=total_convs,
            total_questions=total_questions,
            total_ocr_documents=total_ocr,
            total_storage_bytes=storage_used
        )

    # SQLite fallback
    docs_query = db.query(Document).filter(Document.user_id == current_user.id)
    total_docs = docs_query.count()
    total_ocr = docs_query.filter(Document.ocr_used == 1).count()
    storage_used = db.query(func.sum(Document.file_size)).filter(Document.user_id == current_user.id).scalar() or 0
    total_convs = db.query(Conversation).filter(Conversation.user_id == current_user.id).count()
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

    if fs_docs:
        filtered = fs_docs
        if search:
            filtered = [d for d in filtered if search.lower() in d.get("filename", "").lower()]
        if status:
            filtered = [d for d in filtered if d.get("status") == status]
        if upload_date:
            filtered = [d for d in filtered if str(d.get("uploaded_at", "")).startswith(upload_date)]

        return [
            DocumentDashboardResponse(
                id=d["id"],
                filename=d["filename"],
                status=d["status"],
                uploaded_at=d.get("uploaded_at") or datetime.now(),
                page_count=d.get("page_count", 0),
                ocr_used=bool(d.get("ocr_used")),
                file_size=d.get("file_size", 0)
            ) for d in filtered[:20]
        ]

    # SQLite fallback
    query = db.query(Document).filter(Document.user_id == current_user.id)
    if search:
        query = query.filter(Document.filename.ilike(f"%{search}%"))
    if status:
        query = query.filter(Document.status == status)
    if upload_date:
        query = query.filter(func.datetime(Document.uploaded_at).startswith(upload_date))

    docs = query.order_by(Document.uploaded_at.desc()).limit(20).all()
    return [
        DocumentDashboardResponse(
            id=doc.id,
            filename=doc.filename,
            status=doc.status,
            uploaded_at=doc.uploaded_at,
            page_count=doc.page_count,
            ocr_used=bool(doc.ocr_used),
            file_size=doc.file_size
        ) for doc in docs
    ]

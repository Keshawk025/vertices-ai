import logging
import os
from typing import List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from auth.auth_service import get_db, Document
from api.auth import get_current_user, User
from firebase.firestore_service import (
    list_documents as fs_list_documents,
    get_document as fs_get_document,
    delete_document as fs_delete_document
)
from firebase.storage_service import (
    delete_document as st_delete_document,
    get_signed_url as st_get_signed_url
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentResponse(BaseModel):
    id: str
    user_id: Any
    filename: str
    status: str
    uploaded_at: Any
    storage_path: Optional[str] = None
    download_url: Optional[str] = None


@router.get("", response_model=List[DocumentResponse])
def get_documents(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    uid = getattr(current_user, "uid", current_user.id)
    fs_docs = fs_list_documents(user_id=uid)
    db_docs = db.query(Document).filter(Document.user_id == current_user.id).all()

    logger.info(f"User document lookup for user {current_user.id}")

    if fs_docs:
        return [
            DocumentResponse(
                id=d["id"],
                user_id=d.get("user_id", current_user.id),
                filename=d["filename"],
                status=d["status"],
                uploaded_at=d.get("uploaded_at") or datetime.now(),
                storage_path=d.get("storage_path"),
                download_url=st_get_signed_url(user_id=uid, doc_id=d["id"], storage_path=d.get("storage_path")) if d.get("storage_path") else None
            ) for d in fs_docs
        ]
    return [
        DocumentResponse(
            id=d.id,
            user_id=d.user_id,
            filename=d.filename,
            status=d.status,
            uploaded_at=d.uploaded_at
        ) for d in db_docs
    ]


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    uid = getattr(current_user, "uid", current_user.id)
    fs_doc = fs_get_document(user_id=uid, doc_id=document_id)
    doc = db.query(Document).filter(Document.id == document_id).first()

    if not fs_doc and not doc:
        logger.error(f"Document not found: {document_id}")
        raise HTTPException(status_code=404, detail="Document not found")

    if doc and doc.user_id != current_user.id:
        logger.error(f"Unauthorized document access attempt by user {current_user.id} on document {document_id}")
        raise HTTPException(status_code=403, detail="Unauthorized document access")

    logger.info(f"User document lookup for document {document_id}")

    if fs_doc:
        s_path = fs_doc.get("storage_path")
        return DocumentResponse(
            id=fs_doc["id"],
            user_id=fs_doc.get("user_id", current_user.id),
            filename=fs_doc["filename"],
            status=fs_doc["status"],
            uploaded_at=fs_doc.get("uploaded_at") or datetime.now(),
            storage_path=s_path,
            download_url=st_get_signed_url(user_id=uid, doc_id=document_id, storage_path=s_path) if s_path else None
        )

    return DocumentResponse(
        id=doc.id,
        user_id=doc.user_id,
        filename=doc.filename,
        status=doc.status,
        uploaded_at=doc.uploaded_at
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    uid = getattr(current_user, "uid", current_user.id)
    fs_doc = fs_get_document(user_id=uid, doc_id=document_id)
    doc = db.query(Document).filter(Document.id == document_id).first()

    if not fs_doc and not doc:
        logger.error(f"Document not found for deletion: {document_id}")
        raise HTTPException(status_code=404, detail="Document not found")

    if doc and doc.user_id != current_user.id:
        logger.error(f"Unauthorized document access attempt for deletion by user {current_user.id} on document {document_id}")
        raise HTTPException(status_code=403, detail="Unauthorized document access")

    # Delete from Firebase Storage, Firestore, and SQLite
    st_delete_document(user_id=uid, doc_id=document_id)
    fs_delete_document(user_id=uid, doc_id=document_id)
    if doc:
        db.delete(doc)
        db.commit()

    logger.info("Document deleted")
    return

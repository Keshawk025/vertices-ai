import logging
import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from auth.auth_service import get_db, Conversation, Message
from api.auth import get_current_user, User

from services.embeddings.embedding_service import EmbeddingService
from services.vector_store.faiss_service import FAISSService
from retrieval.rag_service import RAGService
from verification.verification_service import VerificationService
from verification.self_correction_service import SelfCorrectionService
from evaluation.evaluation_service import EvaluationService

from firebase.firestore_service import (
    create_conversation as fs_create_conversation,
    get_conversation as fs_get_conversation,
    list_conversations as fs_list_conversations,
    delete_conversation as fs_delete_conversation,
    create_message as fs_create_message,
    list_messages as fs_list_messages
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationCreate(BaseModel):
    title: str


class ConversationResponse(BaseModel):
    id: str
    user_id: Any
    title: str
    created_at: Any


class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: Any


embedding_service = EmbeddingService()
faiss_service = FAISSService()
rag_service = RAGService(embedding_service, faiss_service)
verification_service = VerificationService()
self_correction_service = SelfCorrectionService()


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(conv: ConversationCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv_id = str(uuid.uuid4())
    uid = getattr(current_user, "uid", current_user.id)

    new_conv = Conversation(id=conv_id, user_id=current_user.id, title=conv.title)
    db.add(new_conv)
    db.commit()
    db.refresh(new_conv)

    # Dual-write to Firestore
    fs_create_conversation(
        user_id=uid,
        conv_data={
            "id": conv_id,
            "user_id": current_user.id,
            "title": conv.title,
            "created_at": datetime.now()
        }
    )

    logger.info(f"Conversation created: {new_conv.id}")
    return ConversationResponse(
        id=new_conv.id,
        user_id=new_conv.user_id,
        title=new_conv.title,
        created_at=new_conv.created_at
    )


@router.get("", response_model=List[ConversationResponse])
def get_conversations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    uid = getattr(current_user, "uid", current_user.id)
    fs_convs = fs_list_conversations(user_id=uid)
    db_convs = db.query(Conversation).filter(Conversation.user_id == current_user.id).all()

    if fs_convs:
        return [
            ConversationResponse(
                id=c["id"],
                user_id=c.get("user_id", current_user.id),
                title=c["title"],
                created_at=c.get("created_at") or datetime.now()
            ) for c in fs_convs
        ]

    return [
        ConversationResponse(
            id=c.id,
            user_id=c.user_id,
            title=c.title,
            created_at=c.created_at
        ) for c in db_convs
    ]


@router.get("/{conversation_id}", response_model=Dict[str, Any])
def get_conversation_history(conversation_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    uid = getattr(current_user, "uid", current_user.id)
    fs_conv = fs_get_conversation(user_id=uid, conv_id=conversation_id)
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()

    if not fs_conv and not conv:
        logger.error(f"Conversation not found: {conversation_id}")
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conv and conv.user_id != current_user.id:
        logger.error(f"Unauthorized access to conversation {conversation_id} by user {current_user.id}")
        raise HTTPException(status_code=403, detail="Unauthorized access")

    fs_msgs = fs_list_messages(user_id=uid, conversation_id=conversation_id)
    db_msgs = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()).all()

    messages = fs_msgs if fs_msgs else [{"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at} for m in db_msgs]
    title = fs_conv["title"] if fs_conv else conv.title
    created_at = fs_conv.get("created_at") if fs_conv else conv.created_at

    logger.info(f"History retrieved for conversation: {conversation_id}")

    return {
        "id": conversation_id,
        "title": title,
        "created_at": created_at,
        "messages": messages
    }


@router.post("/{conversation_id}/message", response_model=Dict[str, Any])
def add_message(conversation_id: str, msg: MessageCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not msg.content or not msg.content.strip():
        raise HTTPException(status_code=400, detail="Empty message")

    uid = getattr(current_user, "uid", current_user.id)
    fs_conv = fs_get_conversation(user_id=uid, conv_id=conversation_id)
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()

    if not fs_conv and not conv:
        logger.error(f"Conversation not found: {conversation_id}")
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conv and conv.user_id != current_user.id:
        logger.error(f"Unauthorized access to conversation {conversation_id} by user {current_user.id}")
        raise HTTPException(status_code=403, detail="Unauthorized access")

    user_msg_id = str(uuid.uuid4())
    user_msg = Message(id=user_msg_id, conversation_id=conversation_id, role="user", content=msg.content)
    db.add(user_msg)
    db.commit()

    # Firestore Dual-Write
    fs_create_message(
        user_id=uid,
        conversation_id=conversation_id,
        msg_data={
            "id": user_msg_id,
            "conversation_id": conversation_id,
            "role": "user",
            "content": msg.content,
            "created_at": datetime.now()
        }
    )
    logger.info("Message added")

    past_messages = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.desc()).limit(10).all()
    past_messages = past_messages[::-1]
    history = [{"role": m.role, "content": m.content} for m in past_messages if m.id != user_msg.id]

    original_query = msg.content
    question = original_query
    retry_count = 0
    answer = "I could not find sufficient information in the available documentation."
    citations = []

    while retry_count <= self_correction_service.max_retries:
        try:
            try:
                chunks = rag_service.retrieve_chunks(question, user_id=current_user.id)
            except ValueError:
                chunks = []

            if not chunks:
                answer = "I could not find sufficient information in the available documentation."
                citations = []
                break

            temp_citations = [{"page": c.get("page"), "chunk_id": c.get("chunk_id")} for c in chunks]
            verification_result = verification_service.verify_response(chunks, temp_citations)

            if verification_result["can_answer"]:
                ans = rag_service.answer_question(question, user_id=current_user.id, history=history)
                answer = ans["answer"]
                citations = ans["citations"]
                break

            action_result = self_correction_service.decide_action(verification_result, original_query, retry_count)

            if action_result["action"] == "CLARIFY":
                answer = action_result["message"]
                break
            elif action_result["action"] == "STOP":
                answer = action_result["message"]
                break
            elif action_result["action"] == "RETRY":
                question = action_result["new_query"]
                retry_count += 1
        except Exception as e:
            logger.error(f"Message generation failed: {e}")
            answer = "An error occurred while processing your request."
            break

    assistant_msg_id = str(uuid.uuid4())
    assistant_msg = Message(id=assistant_msg_id, conversation_id=conversation_id, role="assistant", content=answer)
    db.add(assistant_msg)
    db.commit()

    # Firestore Dual-Write
    fs_create_message(
        user_id=uid,
        conversation_id=conversation_id,
        msg_data={
            "id": assistant_msg_id,
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": answer,
            "created_at": datetime.now()
        }
    )
    logger.info("Message added")

    return {
        "answer": answer,
        "citations": citations
    }


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    uid = getattr(current_user, "uid", current_user.id)
    fs_conv = fs_get_conversation(user_id=uid, conv_id=conversation_id)
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()

    if not fs_conv and not conv:
        logger.error(f"Conversation not found: {conversation_id}")
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conv and conv.user_id != current_user.id:
        logger.error(f"Unauthorized access to conversation {conversation_id} by user {current_user.id}")
        raise HTTPException(status_code=403, detail="Unauthorized access")

    # Delete from Firestore & SQLite
    fs_delete_conversation(user_id=uid, conv_id=conversation_id)
    db.query(Message).filter(Message.conversation_id == conversation_id).delete()
    if conv:
        db.delete(conv)
        db.commit()

    logger.info(f"Conversation deleted: {conversation_id}")
    return

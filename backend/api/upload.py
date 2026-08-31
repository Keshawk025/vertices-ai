import os
import uuid
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status
from sqlalchemy.orm import Session

from api.auth import get_current_user, User
from auth.auth_service import get_db, Document
from ingestion.document_parser import DocumentParser
from ingestion.chunker import Chunker
from services.embeddings.embedding_service import EmbeddingService
from services.vector_store.faiss_service import FAISSService

from firebase.firestore_service import create_document as fs_create_document, update_document as fs_update_document

logger = logging.getLogger(__name__)


router = APIRouter()

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "documents")

# We can initialize services globally or inside the dependency
embedding_service = EmbeddingService()
faiss_service = FAISSService()
chunker = Chunker(chunk_size=500, chunk_overlap=100)

@router.post("/upload", status_code=status.HTTP_200_OK)
async def upload_pdf(file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logger.info(f"Upload started for file: {file.filename}")
    
    # Validation: Accept only PDF files
    if file.content_type != "application/pdf" and not file.filename.lower().endswith(".pdf"):
        logger.error(f"Upload failed: Invalid file type for {file.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted."
        )

    # Validation: Read file and check size
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE:
        logger.error(f"Upload failed: File size exceeded for {file.filename} ({len(file_content)} bytes)")
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="File size exceeds the 20 MB limit."
        )
    
    # Generate UUID
    file_id = str(uuid.uuid4())
    
    # Store locally
    os.makedirs(STORAGE_DIR, exist_ok=True)
    file_path = os.path.join(STORAGE_DIR, f"{file_id}_{file.filename}")
    
    try:
        with open(file_path, "wb") as f:
            f.write(file_content)
    except Exception as e:
        logger.error(f"Upload failed: Error saving file {file.filename}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save file."
        )
        
    uid = getattr(current_user, "uid", current_user.id)
    storage_res = st_upload_document(
        user_id=uid,
        doc_id=file_id,
        file_bytes=file_content,
        filename=file.filename,
        folder="documents",
        content_type="application/pdf"
    )
    storage_path = storage_res["storage_path"]

    # Database metadata persistence

    new_doc = Document(
        id=file_id, 
        user_id=current_user.id, 
        filename=file.filename, 
        file_path=file_path, 
        status="uploaded",
        file_size=len(file_content)
    )
    db.add(new_doc)
    db.commit()

    # Firestore Dual-Write
    fs_create_document(
        user_id=uid,
        doc_data={
            "id": file_id,
            "user_id": current_user.id,
            "filename": file.filename,
            "file_path": file_path,
            "storage_path": storage_path,
            "file_size": len(file_content),
            "status": "uploaded",
            "page_count": 0,
            "ocr_used": 0
        }
    )
    logger.info("Document uploaded")
    
    try:
        # Ingestion Pipeline
        with DocumentParser(file_path) as parser:
            parsed_data = parser.parse_document()
            
        parsed_data["metadata"]["file_id"] = file_id # Ensure parser metadata maps correctly
        page_count = parsed_data["metadata"].get("page_count", 0)
        ocr_used = 1 if parsed_data["metadata"].get("ocr_used") else 0
        new_doc.page_count = page_count
        new_doc.ocr_used = ocr_used
        
        chunks = chunker.chunk_document(parsed_data)
        embedded_chunks = embedding_service.generate_embeddings(chunks)
        
        # Inject user_id into each chunk before saving to FAISS
        for chunk in embedded_chunks:
            chunk["user_id"] = current_user.id
            
        faiss_service.add_embeddings(embedded_chunks)
        faiss_service.save_index()
        
        new_doc.status = "processed"
        db.commit()

        # Update Firestore
        fs_update_document(
            user_id=getattr(current_user, "uid", current_user.id),
            doc_id=file_id,
            update_data={
                "status": "processed",
                "page_count": page_count,
                "ocr_used": ocr_used
            }
        )
    except Exception as e:
        logger.error(f"Ingestion pipeline failed for {file_id}: {e}")
        new_doc.status = "failed"
        db.commit()
        fs_update_document(
            user_id=getattr(current_user, "uid", current_user.id),
            doc_id=file_id,
            update_data={"status": "failed"}
        )

    
    logger.info(f"Upload completed for file: {file.filename} (ID: {file_id})")
    
    return {
        "file_id": file_id,
        "filename": file.filename,
        "size": len(file_content),
        "status": new_doc.status
    }

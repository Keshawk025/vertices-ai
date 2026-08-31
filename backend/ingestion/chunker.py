import uuid
import logging

logger = logging.getLogger(__name__)

class Chunker:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        if chunk_size <= 0:
            raise ValueError("Chunk size must be greater than 0.")
        if chunk_overlap >= chunk_size:
            raise ValueError("Chunk overlap must be less than chunk size.")
        if chunk_overlap < 0:
            raise ValueError("Chunk overlap cannot be negative.")
            
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._total_chunks_created = 0

    def chunk_page(self, page_content: str, page_num: int) -> list:
        if not isinstance(page_content, str):
            raise TypeError("Page content must be a string.")
        
        chunks = []
        if not page_content.strip():
            logger.warning(f"Empty page encountered: Page {page_num}")
            return chunks

        start_idx = 0
        text_length = len(page_content)

        while start_idx < text_length:
            end_idx = min(start_idx + self.chunk_size, text_length)
            
            chunk_text = page_content[start_idx:end_idx]
            
            # Avoid trailing empty chunks
            if chunk_text.strip():
                chunk_id = str(uuid.uuid4())
                chunk_metadata = {
                    "chunk_id": chunk_id,
                    "page": page_num,
                    "content": chunk_text,
                    "start_index": start_idx,
                    "end_index": end_idx
                }
                chunks.append(chunk_metadata)
                logger.info(f"Chunk created: {chunk_id} on page {page_num} [{start_idx}:{end_idx}]")
                self._total_chunks_created += 1

            # If we reached the end of the text, break to prevent infinite loops 
            # if chunk_size - overlap is somehow processed weirdly, though math ensures progression
            if end_idx >= text_length:
                break
                
            start_idx += (self.chunk_size - self.chunk_overlap)
            
        return chunks

    def chunk_document(self, parsed_document: dict) -> dict:
        if not isinstance(parsed_document, dict):
            raise TypeError("Parsed document must be a dictionary.")
            
        metadata = parsed_document.get("metadata")
        pages = parsed_document.get("pages")
        
        if not metadata or "file_id" not in metadata:
            logger.error("Chunking failed: Missing document metadata or file_id.")
            raise ValueError("Parsed document is missing required metadata or 'file_id'.")
            
        if pages is None or not isinstance(pages, list):
            logger.error("Chunking failed: Document is missing pages data.")
            raise ValueError("Parsed document is missing pages data.")
            
        document_id = metadata["file_id"]
        
        logger.info(f"Chunking started for document ID: {document_id}")
        
        all_chunks = []
        
        for page_data in pages:
            page_num = page_data.get("page")
            content = page_data.get("content")
            
            if page_num is None or content is None:
                logger.error(f"Chunking failed: Invalid page format in document {document_id}")
                raise ValueError("Invalid page format: missing 'page' or 'content'.")
                
            page_chunks = self.chunk_page(content, page_num)
            all_chunks.extend(page_chunks)
            
        logger.info(f"Chunking completed for document ID: {document_id}. Total chunks: {len(all_chunks)}")
        
        return {
            "document_id": document_id,
            "chunks": all_chunks
        }

    def get_chunk_count(self) -> int:
        return self._total_chunks_created

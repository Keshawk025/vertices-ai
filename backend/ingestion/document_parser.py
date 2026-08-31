import os
import logging
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

class DocumentParser:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self._doc = None

    def _open_document(self):
        try:
            # fitz.open can throw exceptions for corrupted or non-PDF files
            self._doc = fitz.open(self.file_path)
            if not self._doc.is_pdf:
                raise ValueError("File is not a valid PDF document.")
        except Exception as e:
            logger.error(f"Parsing failed: Error opening file {self.file_path}: {e}")
            raise ValueError(f"Failed to open document: {e}")

    def get_page_count(self) -> int:
        if not self._doc:
            self._open_document()
        return self._doc.page_count

    def extract_metadata(self) -> dict:
        if not self._doc:
            self._open_document()
        
        # Extract filename and potentially file_id if filename is {file_id}_{original_filename}
        base_name = os.path.basename(self.file_path)
        parts = base_name.split("_", 1)
        if len(parts) == 2:
            file_id, filename = parts[0], parts[1]
        else:
            file_id, filename = None, base_name

        pdf_metadata = self._doc.metadata or {}
        
        return {
            "filename": filename,
            "file_id": file_id,
            "page_count": self.get_page_count(),
            "title": pdf_metadata.get("title", ""),
            "author": pdf_metadata.get("author", ""),
            "creation_date": pdf_metadata.get("creationDate", ""),
            "modification_date": pdf_metadata.get("modDate", "")
        }

    def extract_text(self) -> dict:
        if not self._doc:
            self._open_document()

        pages_content = []
        page_count = self.get_page_count()

        if page_count == 0:
            logger.error(f"Parsing failed: Document is empty {self.file_path}")
            raise ValueError("Document is empty (0 pages).")

        for page_num in range(page_count):
            try:
                page = self._doc.load_page(page_num)
                text = page.get_text()
                # Use 1-based indexing for page numbers as per standard convention
                pages_content.append({
                    "page": page_num + 1,
                    "content": text
                })
            except Exception as e:
                logger.error(f"Parsing failed: Error reading page {page_num + 1} from {self.file_path}: {e}")
                raise ValueError(f"Failed to extract text from page {page_num + 1}: {e}")
                
        return {
            "pages": pages_content
        }

    def parse_document(self) -> dict:
        logger.info(f"Parsing started for document: {self.file_path}")
        
        try:
            metadata = self.extract_metadata()
            text_data = self.extract_text()
            
            metadata["ocr_used"] = False
            
            # Check if we need to trigger OCR
            total_extracted_length = sum(len(page.get("content", "")) for page in text_data["pages"])
            
            if metadata["page_count"] > 0 and total_extracted_length < 100:
                logger.info(f"Scanned PDF detected. Triggering OCR for {self.file_path}")
                # We defer import to avoid cyclic or missing dependency issues if ocr_service isn't loaded
                from services.ocr.ocr_service import OCRService
                ocr_service = OCRService()
                
                # Use OCR instead
                ocr_result = ocr_service.process_document(self.file_path)
                
                # Merge OCR pages and metadata back (preserving existing metadata like filename)
                metadata["page_count"] = ocr_result["metadata"]["page_count"]
                metadata["ocr_used"] = True
                text_data["pages"] = ocr_result["pages"]
            
            result = {
                "metadata": metadata,
                "pages": text_data["pages"]
            }
            logger.info(f"Parsing completed for document: {self.file_path}")
            return result
        except Exception as e:
            logger.error(f"Parsing failed for document {self.file_path}: {e}")
            raise
        finally:
            self.close()

    def close(self):
        if self._doc:
            self._doc.close()
            self._doc = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

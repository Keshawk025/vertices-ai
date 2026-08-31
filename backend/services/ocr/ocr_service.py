import logging
import os
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class OCRService:
    def __init__(self):
        try:
            import pytesseract
            from pdf2image import convert_from_path
            self.pytesseract = pytesseract
            self.convert_from_path = convert_from_path
        except ImportError:
            self.pytesseract = None
            self.convert_from_path = None
            logger.error("Required Python dependencies (pytesseract, pdf2image) are missing.")

    def is_scanned_pdf(self, extracted_text_length: int) -> bool:
        return extracted_text_length < 100

    def convert_pdf_to_images(self, file_path: str) -> List[Any]:
        if not self.convert_from_path:
            raise RuntimeError("pdf2image library is not installed.")
            
        logger.info(f"PDF converted to images for: {file_path}")
        try:
            # We don't want to actually run this if we are just testing missing dependencies
            # But we wrap it in a try-except to catch poppler missing issues.
            images = self.convert_from_path(file_path)
            if not images:
                logger.error("Empty images returned from PDF conversion.")
                raise ValueError("Empty images: PDF could not be converted to images.")
            return images
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to convert PDF to images: {e}")
            raise RuntimeError(f"Corrupted PDF or conversion failure: {e}")

    def extract_text_from_images(self, images: List[Any]) -> List[Dict[str, Any]]:
        if not self.pytesseract:
            raise RuntimeError("pytesseract library is not installed.")
            
        logger.info("OCR processing started")
        pages_content = []
        
        try:
            # Check if tesseract is installed by asking for its version
            self.pytesseract.get_tesseract_version()
        except self.pytesseract.TesseractNotFoundError:
            logger.error("OCR failed: Missing Tesseract installation")
            raise RuntimeError("Missing Tesseract installation")
        
        for idx, image in enumerate(images):
            try:
                # Add timeout support if possible or just rely on default
                text = self.pytesseract.image_to_string(image, timeout=60)
                pages_content.append({
                    "page": idx + 1,
                    "content": text.strip()
                })
            except RuntimeError as e:
                if "timeout" in str(e).lower():
                    logger.error(f"OCR failed: OCR timeout on page {idx + 1}")
                    raise RuntimeError("OCR timeout")
                else:
                    logger.error(f"OCR failed on page {idx + 1}: {e}")
                    raise RuntimeError(f"OCR failed: {e}")
            except Exception as e:
                logger.error(f"OCR failed on page {idx + 1}: {e}")
                raise RuntimeError(f"OCR failed: {e}")
                
        logger.info("OCR completed")
        return pages_content

    def process_document(self, file_path: str) -> Dict[str, Any]:
        logger.info(f"OCR started for document: {file_path}")
        
        if not os.path.exists(file_path):
            logger.error(f"Invalid PDF: File does not exist {file_path}")
            raise ValueError("Invalid PDF: File not found.")
            
        try:
            images = self.convert_pdf_to_images(file_path)
            
            pages_content = self.extract_text_from_images(images)
            
            # Reconstruct metadata to match expected format
            metadata = {
                "page_count": len(pages_content)
            }
            
            return {
                "metadata": metadata,
                "pages": pages_content
            }
        except RuntimeError as e:
            logger.error(f"OCR failed for {file_path}: {e}")
            raise
        except ValueError as e:
            logger.error(f"OCR failed for {file_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"OCR failed for {file_path}: {e}")
            raise RuntimeError(f"OCR failed: {e}")

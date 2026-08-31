import pytest
from unittest.mock import MagicMock, patch
from services.ocr.ocr_service import OCRService

@pytest.fixture
def ocr_service():
    mock_pytesseract = MagicMock()
    mock_convert = MagicMock()
    # We manually inject the mocks to simulate a working environment
    service = OCRService()
    service.pytesseract = mock_pytesseract
    service.convert_from_path = mock_convert
    yield service

def test_is_scanned_pdf(ocr_service):
    assert ocr_service.is_scanned_pdf(50) is True
    assert ocr_service.is_scanned_pdf(150) is False

@patch("os.path.exists", return_value=True)
def test_scanned_pdf_workflow(mock_exists, ocr_service):
    # Mock images returned
    mock_image = MagicMock()
    ocr_service.convert_from_path.return_value = [mock_image]
    
    # Mock text extracted
    ocr_service.pytesseract.image_to_string.return_value = "This contract is entered into..."
    
    result = ocr_service.process_document("scanned_contract.pdf")
    
    assert result["metadata"]["page_count"] == 1
    assert len(result["pages"]) == 1
    assert result["pages"][0]["page"] == 1
    assert result["pages"][0]["content"] == "This contract is entered into..."
    
    ocr_service.convert_from_path.assert_called_once_with("scanned_contract.pdf")
    ocr_service.pytesseract.image_to_string.assert_called_once()

@patch("os.path.exists", return_value=True)
def test_empty_images(mock_exists, ocr_service):
    ocr_service.convert_from_path.return_value = []
    
    with pytest.raises(ValueError, match="Empty images: PDF could not be converted"):
        ocr_service.process_document("scanned_contract.pdf")

@patch("os.path.exists", return_value=True)
def test_ocr_failure(mock_exists, ocr_service):
    mock_image = MagicMock()
    ocr_service.convert_from_path.return_value = [mock_image]
    ocr_service.pytesseract.image_to_string.side_effect = RuntimeError("timeout")
    
    with pytest.raises(RuntimeError, match="OCR timeout"):
        ocr_service.process_document("scanned_contract.pdf")

@patch("os.path.exists", return_value=False)
def test_invalid_pdf(mock_exists, ocr_service):
    with pytest.raises(ValueError, match="Invalid PDF: File not found."):
        ocr_service.process_document("nonexistent.pdf")

def test_missing_tesseract_installation():
    # If we initialize without mocks, it should detect missing dependencies gracefully if missing
    # Since we can't guarantee missing Python dependencies, we test the TesseractNotFoundError logic
    service = OCRService()
    if service.pytesseract is not None:
        service.pytesseract.get_tesseract_version = MagicMock(side_effect=service.pytesseract.TesseractNotFoundError)
        with pytest.raises(RuntimeError, match="Missing Tesseract installation"):
            service.extract_text_from_images([MagicMock()])

import os
import pytest
import fitz
from ingestion.document_parser import DocumentParser

TEST_DIR = os.path.join(os.path.dirname(__file__), "test_files")

@pytest.fixture(scope="session", autouse=True)
def setup_test_files():
    os.makedirs(TEST_DIR, exist_ok=True)
    
    # 1. Create a valid PDF
    valid_pdf_path = os.path.join(TEST_DIR, "uuid123_valid.pdf")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "This is a valid test PDF.")
    doc.set_metadata({
        "title": "Test Title",
        "author": "Test Author"
    })
    doc.save(valid_pdf_path)
    doc.close()

    # 2. Create an empty PDF (0 pages or 0 bytes)
    empty_pdf_path = os.path.join(TEST_DIR, "uuid456_empty.pdf")
    with open(empty_pdf_path, "wb") as f:
        f.write(b"")

    # 3. Create a corrupted PDF
    corrupted_pdf_path = os.path.join(TEST_DIR, "uuid789_corrupted.pdf")
    with open(corrupted_pdf_path, "wb") as f:
        f.write(b"Not a PDF content at all")

    yield

    # Cleanup
    for file in os.listdir(TEST_DIR):
        os.remove(os.path.join(TEST_DIR, file))
    os.rmdir(TEST_DIR)

def test_valid_pdf():
    valid_pdf_path = os.path.join(TEST_DIR, "uuid123_valid.pdf")
    
    with DocumentParser(valid_pdf_path) as parser:
        result = parser.parse_document()
        
        # Check metadata
        assert result["metadata"]["filename"] == "valid.pdf"
        assert result["metadata"]["file_id"] == "uuid123"
        assert result["metadata"]["page_count"] == 1
        assert result["metadata"]["title"] == "Test Title"
        assert result["metadata"]["author"] == "Test Author"
        
        # Check text
        assert len(result["pages"]) == 1
        assert result["pages"][0]["page"] == 1
        assert "This is a valid test PDF." in result["pages"][0]["content"]

def test_empty_pdf():
    empty_pdf_path = os.path.join(TEST_DIR, "uuid456_empty.pdf")
    
    with DocumentParser(empty_pdf_path) as parser:
        with pytest.raises(ValueError, match="Failed to open document"):
            parser.parse_document()

def test_corrupted_pdf():
    corrupted_pdf_path = os.path.join(TEST_DIR, "uuid789_corrupted.pdf")
    
    with DocumentParser(corrupted_pdf_path) as parser:
        with pytest.raises(ValueError, match="Failed to open document"):
            parser.parse_document()

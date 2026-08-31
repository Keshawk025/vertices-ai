import pytest
from ingestion.chunker import Chunker

def test_single_page_document():
    chunker = Chunker(chunk_size=500, chunk_overlap=100)
    doc = {
        "metadata": {"file_id": "doc123"},
        "pages": [
            {"page": 1, "content": "This is a short test document."}
        ]
    }
    
    result = chunker.chunk_document(doc)
    
    assert result["document_id"] == "doc123"
    assert len(result["chunks"]) == 1
    
    chunk = result["chunks"][0]
    assert chunk["page"] == 1
    assert chunk["content"] == "This is a short test document."
    assert chunk["start_index"] == 0
    assert chunk["end_index"] == len("This is a short test document.")
    assert "chunk_id" in chunk
    
    assert chunker.get_chunk_count() == 1

def test_multi_page_document():
    chunker = Chunker(chunk_size=500, chunk_overlap=100)
    doc = {
        "metadata": {"file_id": "doc456"},
        "pages": [
            {"page": 1, "content": "Page 1 content."},
            {"page": 2, "content": "Page 2 content."}
        ]
    }
    
    result = chunker.chunk_document(doc)
    
    assert result["document_id"] == "doc456"
    assert len(result["chunks"]) == 2
    
    assert result["chunks"][0]["page"] == 1
    assert result["chunks"][0]["content"] == "Page 1 content."
    
    assert result["chunks"][1]["page"] == 2
    assert result["chunks"][1]["content"] == "Page 2 content."
    
    assert chunker.get_chunk_count() == 2

def test_empty_document():
    chunker = Chunker(chunk_size=500, chunk_overlap=100)
    doc = {
        "metadata": {"file_id": "doc789"},
        "pages": [
            {"page": 1, "content": "   "}, # Empty page
            {"page": 2, "content": ""}      # Empty page
        ]
    }
    
    result = chunker.chunk_document(doc)
    
    assert result["document_id"] == "doc789"
    assert len(result["chunks"]) == 0
    assert chunker.get_chunk_count() == 0

def test_long_document_multiple_chunks():
    chunker = Chunker(chunk_size=10, chunk_overlap=2) # Using small sizes for easy testing
    doc = {
        "metadata": {"file_id": "doc000"},
        "pages": [
            {"page": 1, "content": "0123456789abcdefghij"} # 20 chars
        ]
    }
    
    result = chunker.chunk_document(doc)
    
    assert result["document_id"] == "doc000"
    chunks = result["chunks"]
    
    # Text: "0123456789abcdefghij"
    # Chunk 1: [0:10] "0123456789" (step = 10-2 = 8)
    # Chunk 2: [8:18] "89abcdefgh" (step = 8)
    # Chunk 3: [16:20] "ghij" (length 4)
    
    assert len(chunks) == 3
    
    assert chunks[0]["start_index"] == 0
    assert chunks[0]["end_index"] == 10
    assert chunks[0]["content"] == "0123456789"
    
    assert chunks[1]["start_index"] == 8
    assert chunks[1]["end_index"] == 18
    assert chunks[1]["content"] == "89abcdefgh"
    
    assert chunks[2]["start_index"] == 16
    assert chunks[2]["end_index"] == 20
    assert chunks[2]["content"] == "ghij"

def test_error_handling():
    chunker = Chunker()
    
    # Missing metadata
    with pytest.raises(ValueError, match="Parsed document is missing required metadata or 'file_id'."):
        chunker.chunk_document({"pages": [{"page": 1, "content": "test"}]})
        
    # Invalid input format
    with pytest.raises(TypeError, match="Parsed document must be a dictionary."):
        chunker.chunk_document(["list_instead_of_dict"])
        
    # Missing pages
    with pytest.raises(ValueError, match="Parsed document is missing pages data."):
        chunker.chunk_document({"metadata": {"file_id": "doc_err"}})
        
    # Invalid page format
    with pytest.raises(ValueError, match="Invalid page format"):
        chunker.chunk_document({
            "metadata": {"file_id": "doc_err2"},
            "pages": [{"wrong_key": 1, "content": "test"}]
        })

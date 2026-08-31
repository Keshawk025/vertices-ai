import pytest
from services.embeddings.embedding_service import EmbeddingService

# We'll use a session-scoped fixture to avoid reloading the model multiple times in tests
@pytest.fixture(scope="session")
def embedding_service():
    return EmbeddingService()

def test_single_chunk(embedding_service):
    text = "This is a single chunk of text for testing."
    embedding = embedding_service.generate_embedding(text)
    
    assert isinstance(embedding, list)
    assert len(embedding) == embedding_service.get_embedding_dimension()

def test_multiple_chunks(embedding_service):
    chunks = [
        {"chunk_id": "1", "content": "First chunk of text."},
        {"chunk_id": "2", "content": "Second chunk of text."}
    ]
    
    doc = {
        "document_id": "doc123",
        "chunks": chunks
    }
    
    result = embedding_service.generate_embeddings(doc)
    
    assert result["document_id"] == "doc123"
    assert len(result["embedded_chunks"]) == 2
    
    for ec in result["embedded_chunks"]:
        assert "embedding" in ec
        assert isinstance(ec["embedding"], list)
        assert len(ec["embedding"]) == embedding_service.get_embedding_dimension()

def test_empty_chunk(embedding_service):
    # Test single empty text
    with pytest.raises(ValueError, match="Text cannot be empty."):
        embedding_service.generate_embedding("   ")
        
    # Test batch with empty chunks
    doc = {
        "document_id": "doc456",
        "chunks": [
            {"chunk_id": "1", "content": ""},
            {"chunk_id": "2", "content": "   "}
        ]
    }
    
    result = embedding_service.generate_embeddings(doc)
    
    # Based on the implementation, empty chunks in batch are skipped.
    assert result["document_id"] == "doc456"
    assert len(result["embedded_chunks"]) == 0

def test_embedding_dimension_validation(embedding_service):
    dim = embedding_service.get_embedding_dimension()
    assert dim > 0
    # For all-MiniLM-L6-v2, the dimension is 384
    assert dim == 384
    
def test_missing_metadata(embedding_service):
    with pytest.raises(ValueError, match="Missing document_id in input."):
        embedding_service.generate_embeddings({"chunks": []})
        
    with pytest.raises(ValueError, match="Missing or invalid chunks array in input."):
        embedding_service.generate_embeddings({"document_id": "doc123"})

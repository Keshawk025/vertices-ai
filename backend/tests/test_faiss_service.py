import os
import pytest
from services.vector_store.faiss_service import FAISSService

# Use a test-specific path for index and metadata to avoid polluting storage
TEST_INDEX_PATH = "storage/test_vector_store/index.faiss"
TEST_META_PATH = "storage/test_vector_store/metadata.json"

@pytest.fixture(autouse=True)
def cleanup_files():
    # Setup - clear any existing test files
    if os.path.exists(TEST_INDEX_PATH):
        os.remove(TEST_INDEX_PATH)
    if os.path.exists(TEST_META_PATH):
        os.remove(TEST_META_PATH)
    yield
    # Teardown
    if os.path.exists(TEST_INDEX_PATH):
        os.remove(TEST_INDEX_PATH)
    if os.path.exists(TEST_META_PATH):
        os.remove(TEST_META_PATH)
        
    test_dir = os.path.dirname(TEST_INDEX_PATH)
    if os.path.exists(test_dir) and not os.listdir(test_dir):
        os.rmdir(test_dir)

@pytest.fixture
def faiss_service():
    return FAISSService(dimension=4, index_path=TEST_INDEX_PATH, meta_path=TEST_META_PATH)

def test_create_index(faiss_service):
    faiss_service.create_index()
    health = faiss_service.health_check()
    assert health["status"] == "healthy"
    assert health["total_vectors"] == 0
    assert health["dimension"] == 4

def test_add_embeddings(faiss_service):
    # Dummy embedding of size 4
    embedded_chunks = [
        {
            "document_id": "doc1",
            "chunk_id": "chunk1",
            "page": 1,
            "content": "Test chunk",
            "filename": "test.pdf",
            "embedding": [0.1, 0.2, 0.3, 0.4]
        }
    ]
    
    faiss_service.add_embeddings(embedded_chunks)
    health = faiss_service.health_check()
    assert health["total_vectors"] == 1

def test_search(faiss_service):
    # Perfect match will have high cosine similarity (near 1.0)
    embedded_chunks = [
        {
            "document_id": "doc1",
            "chunk_id": "chunk1",
            "page": 1,
            "content": "Target chunk",
            "filename": "target.pdf",
            "embedding": [1.0, 0.0, 0.0, 0.0]
        },
        {
            "document_id": "doc2",
            "chunk_id": "chunk2",
            "page": 2,
            "content": "Other chunk",
            "filename": "other.pdf",
            "embedding": [0.0, 1.0, 0.0, 0.0]
        }
    ]
    
    faiss_service.add_embeddings(embedded_chunks)
    
    # Query matching doc1
    results = faiss_service.search([1.0, 0.0, 0.0, 0.0], top_k=1)
    
    assert len(results) == 1
    assert results[0]["chunk_id"] == "chunk1"
    assert results[0]["score"] > 0.99  # Normalized dot product should be close to 1

def test_save_load_index(faiss_service):
    faiss_service.create_index()
    embedded_chunks = [
        {
            "document_id": "doc1",
            "chunk_id": "chunk1",
            "page": 1,
            "content": "Test chunk",
            "filename": "test.pdf",
            "embedding": [0.5, 0.5, 0.5, 0.5]
        }
    ]
    faiss_service.add_embeddings(embedded_chunks)
    faiss_service.save_index()
    
    # Create new instance and load
    new_service = FAISSService(dimension=4, index_path=TEST_INDEX_PATH, meta_path=TEST_META_PATH)
    new_service.load_index()
    
    health = new_service.health_check()
    assert health["status"] == "healthy"
    assert health["total_vectors"] == 1
    
    # Verify metadata is loaded
    results = new_service.search([0.5, 0.5, 0.5, 0.5], top_k=1)
    assert len(results) == 1
    assert results[0]["chunk_id"] == "chunk1"

def test_delete_document(faiss_service):
    embedded_chunks = [
        {
            "document_id": "doc1",
            "chunk_id": "chunk1",
            "page": 1,
            "content": "Doc1 chunk",
            "filename": "test1.pdf",
            "embedding": [0.5, 0.5, 0.5, 0.5]
        },
        {
            "document_id": "doc2",
            "chunk_id": "chunk2",
            "page": 1,
            "content": "Doc2 chunk",
            "filename": "test2.pdf",
            "embedding": [0.0, 0.0, 0.0, 1.0]
        }
    ]
    faiss_service.add_embeddings(embedded_chunks)
    assert faiss_service.health_check()["total_vectors"] == 2
    
    faiss_service.delete_document("doc1")
    
    health = faiss_service.health_check()
    assert health["total_vectors"] == 1
    
    # Check that doc2 still exists
    results = faiss_service.search([0.0, 0.0, 0.0, 1.0], top_k=1)
    assert results[0]["chunk_id"] == "chunk2"

def test_error_handling(faiss_service):
    faiss_service.create_index()
    
    # Missing metadata
    with pytest.raises(ValueError, match="Missing required metadata"):
        faiss_service.add_embeddings([{"embedding": [0.1, 0.2, 0.3, 0.4]}]) # Missing all meta
        
    # Invalid dimension
    with pytest.raises(ValueError, match="Invalid embeddings: Dimension mismatch"):
        faiss_service.add_embeddings([{
            "document_id": "doc1", "chunk_id": "chunk1", "page": 1, "content": "text", "filename": "file.pdf",
            "embedding": [0.1, 0.2] # Dimension 2 instead of 4
        }])
        
    # Empty index search
    empty_service = FAISSService(dimension=4)
    with pytest.raises(RuntimeError, match="Empty index: Cannot search on an empty index"):
        empty_service.search([0.1, 0.2, 0.3, 0.4])

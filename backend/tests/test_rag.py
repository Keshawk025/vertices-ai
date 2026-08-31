import os
import pytest
from unittest.mock import MagicMock, patch

from services.embeddings.embedding_service import EmbeddingService
from services.vector_store.faiss_service import FAISSService
from retrieval.rag_service import RAGService
from services.llm.llm_service import get_llm_service
from services.llm.groq_service import GroqService
from services.llm.featherless_service import FeatherlessService

@pytest.fixture
def mock_embedding_service():
    service = MagicMock(spec=EmbeddingService)
    # Mock embedding generation
    service.generate_embedding.return_value = [0.1] * 384
    return service

@pytest.fixture
def mock_faiss_service():
    service = MagicMock(spec=FAISSService)
    return service

@pytest.fixture
def rag_service(mock_embedding_service, mock_faiss_service):
    # Temporarily set valid API key to avoid RAGService init error
    with patch.dict(os.environ, {"GROQ_API_KEY": "fake_key", "LLM_PROVIDER": "groq"}):
        rag = RAGService(mock_embedding_service, mock_faiss_service)
        # Mock the LLM to avoid real API calls
        rag.llm_service.generate_response = MagicMock(return_value="Mocked LLM Answer")
        return rag

def test_successful_answer(rag_service, mock_faiss_service):
    # Setup mock FAISS response
    mock_faiss_service.search.return_value = [
        {"chunk_id": "abc123", "page": 1, "content": "Veritas AI is a RAG platform.", "score": 0.9}
    ]
    
    result = rag_service.answer_question("What is Veritas AI?")
    
    assert result["answer"] == "Mocked LLM Answer"
    assert len(result["citations"]) == 1
    assert result["citations"][0]["chunk_id"] == "abc123"
    assert result["citations"][0]["page"] == 1
    
    # Verify the LLM was called with correct context
    rag_service.llm_service.generate_response.assert_called_once()
    args, kwargs = rag_service.llm_service.generate_response.call_args
    assert "Veritas AI is a RAG platform." in args[1] # user prompt

def test_empty_query(rag_service):
    with pytest.raises(ValueError, match="Empty query"):
        rag_service.answer_question("")

def test_no_retrieval_results(rag_service, mock_faiss_service):
    # Setup mock FAISS to return no results
    mock_faiss_service.search.return_value = []
    
    result = rag_service.answer_question("What is Veritas AI?")
    
    assert result["answer"] == "I could not find sufficient information in the available documentation."
    assert len(result["citations"]) == 0
    # LLM should not be called
    rag_service.llm_service.generate_response.assert_not_called()

def test_empty_faiss_index(rag_service, mock_faiss_service):
    mock_faiss_service.search.side_effect = RuntimeError("Empty index: Cannot search on an empty index.")
    
    with pytest.raises(ValueError, match="Empty FAISS index"):
        rag_service.answer_question("query")

def test_citation_generation(rag_service, mock_faiss_service):
    mock_faiss_service.search.return_value = [
        {"chunk_id": "c1", "page": 1, "content": "Info 1"},
        {"chunk_id": "c2", "page": 5, "content": "Info 2"}
    ]
    
    result = rag_service.answer_question("query")
    
    assert len(result["citations"]) == 2
    assert result["citations"][0]["chunk_id"] == "c1"
    assert result["citations"][0]["page"] == 1
    assert result["citations"][1]["chunk_id"] == "c2"
    assert result["citations"][1]["page"] == 5

def test_provider_fallback():
    # Test fallback to Groq when provider is not set but key exists
    with patch.dict(os.environ, {"GROQ_API_KEY": "fake_groq", "FEATHERLESS_API_KEY": "fake_feather"}, clear=True):
        service = get_llm_service()
        assert isinstance(service, GroqService)
        
    # Test fallback to Featherless when Groq key is missing
    with patch.dict(os.environ, {"FEATHERLESS_API_KEY": "fake_feather"}, clear=True):
        service = get_llm_service()
        assert isinstance(service, FeatherlessService)
        
    # Test explicit provider set
    with patch.dict(os.environ, {"LLM_PROVIDER": "featherless", "FEATHERLESS_API_KEY": "fake_feather"}, clear=True):
        service = get_llm_service()
        assert isinstance(service, FeatherlessService)
        
    # Test missing keys error
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="No valid LLM_PROVIDER or API keys found."):
            get_llm_service()

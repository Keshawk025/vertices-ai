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
    service.generate_embedding.return_value = [0.1] * 384
    return service


@pytest.fixture
def mock_faiss_service():
    service = MagicMock(spec=FAISSService)
    service.search.return_value = [
        {"chunk_id": "abc123", "page": 1, "content": "Veritas AI is a RAG platform.", "score": 0.9}
    ]
    service.get_chunks.return_value = [
        {"chunk_id": "abc123", "page": 1, "content": "Veritas AI is a RAG platform.", "document_id": "d1", "user_id": 1}
    ]
    return service


@pytest.fixture
def rag_service(mock_embedding_service, mock_faiss_service):
    with patch.dict(os.environ, {"GROQ_API_KEY": "fake_key", "LLM_PROVIDER": "groq"}):
        rag = RAGService(mock_embedding_service, mock_faiss_service)
        rag.llm_service.generate_response = MagicMock(return_value="Mocked LLM Answer")
        return rag


def test_successful_answer(rag_service, mock_faiss_service):
    result = rag_service.answer_question("What is Veritas AI?")
    
    assert result["answer"] == "Mocked LLM Answer"
    assert len(result["citations"]) == 1
    assert result["citations"][0]["chunk_id"] == "abc123"
    assert result["citations"][0]["page"] == 1
    
    # Verify the LLM was called with correct context
    rag_service.llm_service.generate_response.assert_called_once()
    args, kwargs = rag_service.llm_service.generate_response.call_args
    assert "Veritas AI is a RAG platform." in args[1]


def test_hybrid_retrieval_string_query(rag_service, mock_faiss_service):
    # Testing that retrieve_chunks with raw string invokes the hybrid pipeline
    chunks = rag_service.retrieve_chunks("What is Veritas AI?", user_id=1, top_k=2)
    assert len(chunks) >= 1
    assert chunks[0]["chunk_id"] == "abc123"


def test_backward_compatibility_embedding_retrieval(rag_service, mock_faiss_service):
    # Testing that retrieve_chunks with list of floats calls FAISS directly
    query_vec = [0.1] * 384
    chunks = rag_service.retrieve_chunks(query_vec, user_id=1, top_k=5)
    assert len(chunks) == 1
    assert chunks[0]["chunk_id"] == "abc123"
    mock_faiss_service.search.assert_called()


def test_empty_query(rag_service):
    with pytest.raises(ValueError, match="Empty query"):
        rag_service.answer_question("")


def test_no_retrieval_results(rag_service, mock_faiss_service):
    mock_faiss_service.search.return_value = []
    mock_faiss_service.get_chunks.return_value = []
    
    result = rag_service.answer_question("What is Veritas AI?")
    
    assert result["answer"] == "I could not find sufficient information in the available documentation."
    assert len(result["citations"]) == 0
    rag_service.llm_service.generate_response.assert_not_called()


def test_empty_faiss_index(rag_service, mock_faiss_service):
    mock_faiss_service.search.side_effect = RuntimeError("Empty index: Cannot search on an empty index.")
    mock_faiss_service.get_chunks.return_value = []
    
    with pytest.raises(ValueError, match="Empty FAISS index"):
        rag_service.retrieve_chunks([0.1] * 384)


def test_citation_generation(rag_service, mock_faiss_service):
    mock_faiss_service.search.return_value = [
        {"chunk_id": "c1", "page": 1, "content": "Info 1"},
        {"chunk_id": "c2", "page": 5, "content": "Info 2"}
    ]
    mock_faiss_service.get_chunks.return_value = [
        {"chunk_id": "c1", "page": 1, "content": "Info 1"},
        {"chunk_id": "c2", "page": 5, "content": "Info 2"}
    ]
    
    result = rag_service.answer_question("query")
    
    assert len(result["citations"]) == 2
    cited_ids = {c["chunk_id"] for c in result["citations"]}
    assert cited_ids == {"c1", "c2"}


def test_provider_fallback():
    with patch.dict(os.environ, {"GROQ_API_KEY": "fake_groq", "FEATHERLESS_API_KEY": "fake_feather"}, clear=True):
        service = get_llm_service()
        assert isinstance(service, GroqService)
        
    with patch.dict(os.environ, {"FEATHERLESS_API_KEY": "fake_feather"}, clear=True):
        service = get_llm_service()
        assert isinstance(service, FeatherlessService)
        
    with patch.dict(os.environ, {"LLM_PROVIDER": "featherless", "FEATHERLESS_API_KEY": "fake_feather"}, clear=True):
        service = get_llm_service()
        assert isinstance(service, FeatherlessService)
        
    with patch.dict(os.environ, {"LLM_PROVIDER": "unsupported_provider"}, clear=True):
        with pytest.raises(ValueError, match="No valid LLM_PROVIDER or API keys found."):
            get_llm_service()

import time
import pytest
from unittest.mock import MagicMock
from retrieval.hybrid_search import (
    bm25_search,
    faiss_search,
    merge_results,
    rerank_results,
    hybrid_search,
    health_check,
)


@pytest.fixture
def sample_chunks():
    return [
        {
            "chunk_id": "c1",
            "content": "Veritas AI is an advanced document processing platform with multi-doc support.",
            "document_id": "doc_01",
            "page": 1,
            "filename": "veritas_overview.pdf",
            "user_id": "user_101"
        },
        {
            "chunk_id": "c2",
            "content": "Firebase Authentication and Firestore handle user sessions and data persistence.",
            "document_id": "doc_01",
            "page": 2,
            "filename": "veritas_overview.pdf",
            "user_id": "user_101"
        },
        {
            "chunk_id": "c3",
            "content": "FAISS vector search provides high-speed semantic retrieval over embedded document chunks.",
            "document_id": "doc_02",
            "page": 1,
            "filename": "vector_search.pdf",
            "user_id": "user_101"
        }
    ]


def test_bm25_search_and_logging(sample_chunks, capsys):
    results = bm25_search(query="Firebase Authentication", chunks=sample_chunks, top_k=2)
    assert len(results) >= 1
    assert results[0]["chunk_id"] == "c2"
    assert results[0]["source"] == "bm25"

    captured = capsys.readouterr().out
    assert "BM25 search" in captured


def test_faiss_search_and_logging(capsys):
    mock_faiss = MagicMock()
    mock_faiss.search.return_value = [
        {
            "chunk_id": "c3",
            "score": 0.95,
            "content": "FAISS vector search content",
            "page": 1,
            "document_id": "doc_02",
            "filename": "vector_search.pdf",
            "user_id": "user_101"
        }
    ]
    mock_embedder = MagicMock()
    mock_embedder.generate_embedding.return_value = [0.1] * 384

    results = faiss_search(
        query="vector search",
        user_id="user_101",
        faiss_service=mock_faiss,
        embedding_service=mock_embedder,
        top_k=5
    )

    assert len(results) == 1
    assert results[0]["chunk_id"] == "c3"
    assert results[0]["source"] == "faiss"

    captured = capsys.readouterr().out
    assert "FAISS search" in captured


def test_merge_results_and_weighted_scoring(capsys):
    bm25_res = [
        {"chunk_id": "c1", "score": 0.8, "source": "bm25", "content": "Sample c1"},
        {"chunk_id": "c2", "score": 0.8, "source": "bm25", "content": "Sample c2"}
    ]
    faiss_res = [
        {"chunk_id": "c2", "score": 0.9, "source": "faiss", "content": "Sample c2"},
        {"chunk_id": "c3", "score": 0.7, "source": "faiss", "content": "Sample c3"}
    ]

    merged = merge_results(bm25_res, faiss_res)
    captured = capsys.readouterr().out
    assert "Merge completed" in captured

    assert len(merged) == 3
    c2_item = next(item for item in merged if item["chunk_id"] == "c2")
    assert c2_item["source"] == "hybrid"
    # Weighted score: 0.4 * 0.8 + 0.6 * 0.9 = 0.86
    assert c2_item["score"] == 0.86


def test_rerank_results_and_logging(capsys):
    merged_items = [
        {"chunk_id": "c1", "score": 0.5, "source": "bm25", "content": "General text"},
        {"chunk_id": "c2", "score": 0.8, "source": "hybrid", "content": "Highly relevant query match text"}
    ]

    reranked = rerank_results(merged_items, query="query match", top_k=2)
    captured = capsys.readouterr().out
    assert "Rerank completed" in captured

    assert len(reranked) == 2
    assert reranked[0]["chunk_id"] == "c2"


def test_hybrid_search_pipeline_and_latency(sample_chunks):
    start_time = time.time()

    mock_faiss = MagicMock()
    mock_faiss.search.return_value = [
        {
            "chunk_id": "c1",
            "score": 0.88,
            "content": "Veritas AI is an advanced document processing platform",
            "page": 1,
            "document_id": "doc_01",
            "filename": "veritas_overview.pdf",
            "user_id": "user_101"
        }
    ]
    mock_embedder = MagicMock()
    mock_embedder.generate_embedding.return_value = [0.1] * 384

    results = hybrid_search(
        query="Veritas document platform",
        user_id="user_101",
        chunks=sample_chunks,
        faiss_service=mock_faiss,
        embedding_service=mock_embedder,
        top_k=5
    )

    elapsed = time.time() - start_time
    assert elapsed < 1.5, f"Latency exceeded goal: {elapsed:.3f}s"

    assert len(results) >= 1
    assert "chunk_id" in results[0]
    assert "score" in results[0]
    assert "source" in results[0]
    assert "content" in results[0]


def test_error_handling(sample_chunks):
    with pytest.raises(ValueError, match="Empty query"):
        hybrid_search(query="  ")

    with pytest.raises(ValueError, match="Empty query"):
        bm25_search(query="", chunks=sample_chunks)

    empty_res = hybrid_search(query="anything", chunks=[])
    assert empty_res == []


def test_health_check():
    status = health_check()
    assert status["bm25"] is True
    assert status["faiss"] is True
    assert status["hybrid"] is True

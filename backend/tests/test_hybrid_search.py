import time
import pytest
from unittest.mock import MagicMock, patch
from retrieval.hybrid_search import (
    _tokenize,
    bm25_search,
    faiss_search,
    reciprocal_rank_fusion,
    merge_results,
    CrossEncoderReranker,
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


def test_bm25_search_and_logging(sample_chunks, caplog):
    with caplog.at_level("INFO"):
        results = bm25_search(query="Firebase Authentication", chunks=sample_chunks, top_k=2)
    assert len(results) >= 1
    assert results[0]["chunk_id"] == "c2"
    assert results[0]["source"] == "bm25"
    assert "bm25_rank" in results[0]
    assert any("BM25 retrieval" in record.message for record in caplog.records)


def test_faiss_search_and_logging(caplog):
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

    with caplog.at_level("INFO"):
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
    assert results[0]["faiss_rank"] == 1
    assert any("FAISS retrieval" in record.message for record in caplog.records)


def test_rrf_mathematical_correctness_and_ordering():
    # Setup controlled BM25 & FAISS rank lists
    bm25_res = [
        {"chunk_id": "c1", "content": "Doc 1", "page": 1, "filename": "d1.pdf", "user_id": 1},
        {"chunk_id": "c2", "content": "Doc 2", "page": 2, "filename": "d2.pdf", "user_id": 1},
    ]
    faiss_res = [
        {"chunk_id": "c2", "content": "Doc 2", "page": 2, "filename": "d2.pdf", "user_id": 1},
        {"chunk_id": "c3", "content": "Doc 3", "page": 3, "filename": "d3.pdf", "user_id": 1},
    ]

    # k=60
    # c1: BM25 rank 1 -> 1 / (60 + 1) = 1/61 approx 0.016393
    # c2: BM25 rank 2 + FAISS rank 1 -> 1/62 + 1/61 approx 0.016129 + 0.016393 = 0.032522
    # c3: FAISS rank 2 -> 1 / (60 + 2) = 1/62 approx 0.016129
    fused = reciprocal_rank_fusion(bm25_res, faiss_res, k=60)

    assert len(fused) == 3
    # c2 must rank first as it appears in both lists
    assert fused[0]["chunk_id"] == "c2"
    assert fused[0]["source"] == "hybrid"
    assert abs(fused[0]["rrf_score"] - (1/62 + 1/61)) < 1e-4

    # c1 must rank second (rank 1 in BM25 vs rank 2 in FAISS for c3)
    assert fused[1]["chunk_id"] == "c1"
    assert fused[1]["source"] == "bm25"
    assert abs(fused[1]["rrf_score"] - (1/61)) < 1e-4

    # c3 is third
    assert fused[2]["chunk_id"] == "c3"
    assert fused[2]["source"] == "faiss"
    assert abs(fused[2]["rrf_score"] - (1/62)) < 1e-4


def test_rrf_configurable_k():
    bm25_res = [{"chunk_id": "c1", "content": "Doc 1"}]
    faiss_res = [{"chunk_id": "c1", "content": "Doc 1"}]

    fused_k10 = reciprocal_rank_fusion(bm25_res, faiss_res, k=10)
    # 1/(10+1) + 1/(10+1) = 2/11 approx 0.181818
    assert abs(fused_k10[0]["rrf_score"] - (2 / 11)) < 1e-4

    fused_k60 = reciprocal_rank_fusion(bm25_res, faiss_res, k=60)
    assert abs(fused_k60[0]["rrf_score"] - (2 / 61)) < 1e-4


def test_rrf_metadata_preservation():
    bm25_res = [
        {
            "chunk_id": "c_meta",
            "document_id": "doc_xyz",
            "page": 4,
            "content": "Detailed text snippet",
            "filename": "report.pdf",
            "user_id": "u42"
        }
    ]
    fused = reciprocal_rank_fusion(bm25_res, [])
    assert len(fused) == 1
    item = fused[0]
    assert item["chunk_id"] == "c_meta"
    assert item["document_id"] == "doc_xyz"
    assert item["page"] == 4
    assert item["content"] == "Detailed text snippet"
    assert item["filename"] == "report.pdf"
    assert item["user_id"] == "u42"


def test_cross_encoder_reranker_mocked():
    reranker = CrossEncoderReranker(model_name="mock-model")
    reranker._model = MagicMock()
    # Mock predict to return custom scores for candidates
    reranker._model.predict.return_value = [0.12, 0.95, 0.45]

    candidates = [
        {"chunk_id": "c1", "content": "Doc 1"},
        {"chunk_id": "c2", "content": "Doc 2"},
        {"chunk_id": "c3", "content": "Doc 3"}
    ]

    results = reranker.rerank(query="test query", candidates=candidates, top_k=2)

    assert len(results) == 2
    # c2 had highest score (0.95)
    assert results[0]["chunk_id"] == "c2"
    assert results[0]["score"] == 0.95
    assert results[0]["rerank_method"] == "cross_encoder"

    # c3 had second highest score (0.45)
    assert results[1]["chunk_id"] == "c3"
    assert results[1]["score"] == 0.45


def test_cross_encoder_fallback_mode(caplog):
    reranker = CrossEncoderReranker(model_name="nonexistent-model")
    reranker._fallback_mode = True

    candidates = [
        {"chunk_id": "c1", "content": "Random unmatching text", "score": 0.01},
        {"chunk_id": "c2", "content": "Exact matching query term inside", "score": 0.02}
    ]

    with caplog.at_level("INFO"):
        results = reranker.rerank(query="matching query", candidates=candidates, top_k=2)

    assert len(results) == 2
    assert results[0]["chunk_id"] == "c2"
    assert results[0]["rerank_method"] == "lexical_overlap_fallback"
    assert any("fallback" in record.message.lower() for record in caplog.records)


def test_hybrid_search_end_to_end(sample_chunks, caplog):
    mock_faiss = MagicMock()
    mock_faiss.search.return_value = [
        {
            "chunk_id": "c1",
            "score": 0.88,
            "content": "Veritas AI is an advanced document processing platform with multi-doc support.",
            "page": 1,
            "document_id": "doc_01",
            "filename": "veritas_overview.pdf",
            "user_id": "user_101"
        }
    ]
    mock_embedder = MagicMock()
    mock_embedder.generate_embedding.return_value = [0.1] * 384

    # Use a reranker with mock model to test full deterministic pipeline
    reranker = CrossEncoderReranker(model_name="mock-model")
    reranker._model = MagicMock()
    reranker._model.predict.return_value = [0.92, 0.45]

    start_time = time.time()
    with caplog.at_level("INFO"):
        results = hybrid_search(
            query="Veritas document platform",
            user_id="user_101",
            chunks=sample_chunks,
            faiss_service=mock_faiss,
            embedding_service=mock_embedder,
            reranker=reranker,
            top_k=2
        )
    elapsed = time.time() - start_time

    assert elapsed < 1.5, f"Latency exceeded goal: {elapsed:.3f}s"
    assert len(results) == 2
    assert results[0]["chunk_id"] == "c1"
    assert results[0]["score"] == 0.92

    # Verify all explicit log messages required by Step 1
    log_text = " ".join(record.message for record in caplog.records)
    assert "BM25 retrieval" in log_text
    assert "FAISS retrieval" in log_text
    assert "RRF fusion" in log_text
    assert "Cross-Encoder reranking" in log_text
    assert "Hybrid retrieval completed" in log_text


def test_error_and_empty_handling(sample_chunks):
    # Empty query
    with pytest.raises(ValueError, match="Empty query"):
        hybrid_search(query="  ")

    with pytest.raises(ValueError, match="Empty query"):
        bm25_search(query="", chunks=sample_chunks)

    # Empty corpus
    empty_res = hybrid_search(query="anything", chunks=[])
    assert empty_res == []

    # Single source returning results (FAISS empty, BM25 returns results)
    mock_empty_faiss = MagicMock()
    mock_empty_faiss.search.return_value = []
    mock_embedder = MagicMock()
    mock_embedder.generate_embedding.return_value = [0.1] * 384

    single_res = hybrid_search(
        query="Firebase",
        chunks=sample_chunks,
        faiss_service=mock_empty_faiss,
        embedding_service=mock_embedder,
        top_k=2
    )
    assert len(single_res) >= 1
    assert single_res[0]["chunk_id"] == "c2"


def test_health_check():
    status = health_check()
    assert status["bm25"] is True
    assert status["faiss"] is True
    assert status["rrf"] is True
    assert status["cross_encoder"] is True
    assert status["hybrid"] is True

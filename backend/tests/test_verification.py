import pytest
from unittest.mock import MagicMock, patch
from verification.verification_service import (
    VerificationService,
    NLIService,
    EvidenceAssessment,
    ContradictionPair,
    _extract_content_tokens
)


@pytest.fixture
def mock_nli_service():
    """Mock NLI service to avoid heavy network downloads during unit tests."""
    service = MagicMock(spec=NLIService)
    # Default neutral/entailment prediction
    service.evaluate_pair.return_value = {
        "contradiction": 0.05,
        "entailment": 0.85,
        "neutral": 0.10
    }
    return service


@pytest.fixture
def verification_service(mock_nli_service):
    return VerificationService(
        min_score_threshold=0.40,
        min_coverage_threshold=0.35,
        contradiction_threshold=0.60,
        sufficiency_threshold=0.50,
        min_chunks=1,
        min_length=20,
        nli_service=mock_nli_service
    )


# 1. Clearly Sufficient Evidence
def test_clearly_sufficient_evidence(verification_service):
    chunks = [
        {
            "chunk_id": "c1",
            "document_id": "doc1",
            "page": 1,
            "filename": "policy.pdf",
            "content": "Veritas AI provides evidence-guided self-correcting RAG for multi-document research.",
            "score": 0.88,
            "source": "hybrid"
        }
    ]
    query = "What does Veritas AI provide?"
    assessment = verification_service.assess_evidence(query=query, retrieved_chunks=chunks)

    assert assessment.sufficient is True
    assert assessment.can_answer is True
    assert assessment.failure_mode == "SUFFICIENT"
    assert assessment.overall_score >= 0.50
    assert assessment.coverage_score > 0.35
    assert len(assessment.conflicting_pairs) == 0


# 2. Clearly Insufficient Evidence (Too Short / Low Relevance)
def test_clearly_insufficient_evidence(verification_service):
    short_chunks = [
        {"chunk_id": "c1", "document_id": "doc1", "page": 1, "content": "Short", "score": 0.8}
    ]
    assessment = verification_service.assess_evidence(query="Tell me everything", retrieved_chunks=short_chunks)
    assert assessment.sufficient is False
    assert assessment.can_answer is False
    assert assessment.failure_mode == "COVERAGE_GAP"


# 3. Empty Evidence
def test_empty_evidence(verification_service):
    assessment = verification_service.assess_evidence(query="Any question", retrieved_chunks=[])
    assert assessment.sufficient is False
    assert assessment.can_answer is False
    assert assessment.failure_mode == "OUT_OF_DOMAIN"
    assert assessment.overall_score == 0.0
    assert len(assessment.supporting_chunks) == 0


# 4. One Relevant Chunk
def test_one_relevant_chunk(verification_service):
    chunks = [
        {
            "chunk_id": "c10",
            "document_id": "doc1",
            "page": 3,
            "content": "The speed of light in vacuum is approximately 299,792 kilometers per second.",
            "score": 0.95
        }
    ]
    assessment = verification_service.assess_evidence(query="What is the speed of light?", retrieved_chunks=chunks)
    assert assessment.sufficient is True
    assert assessment.failure_mode == "SUFFICIENT"
    assert len(assessment.supporting_chunks) == 1


# 5. Multiple Supporting Chunks
def test_multiple_supporting_chunks(verification_service):
    chunks = [
        {"chunk_id": "c1", "document_id": "doc1", "page": 1, "content": "Project Apollo was launched in 1961.", "score": 0.85},
        {"chunk_id": "c2", "document_id": "doc1", "page": 2, "content": "Apollo 11 landed humans on the Moon in July 1969.", "score": 0.90}
    ]
    assessment = verification_service.assess_evidence(query="When was Apollo launched and when did it land?", retrieved_chunks=chunks)
    assert assessment.sufficient is True
    assert assessment.failure_mode == "SUFFICIENT"
    assert len(assessment.supporting_chunks) == 2


# 6. Two Genuinely Contradictory Passages
def test_genuinely_contradictory_passages(verification_service, mock_nli_service):
    # Mock NLI to return high contradiction probability
    mock_nli_service.evaluate_pair.return_value = {
        "contradiction": 0.92,
        "entailment": 0.02,
        "neutral": 0.06
    }

    chunks = [
        {"chunk_id": "c1", "document_id": "doc_A", "page": 1, "filename": "Handbook_2022.pdf", "content": "Minimum attendance required is 75% for all students.", "score": 0.85},
        {"chunk_id": "c2", "document_id": "doc_B", "page": 4, "filename": "Handbook_2024.pdf", "content": "Minimum attendance required is 80% for all students.", "score": 0.85}
    ]

    assessment = verification_service.assess_evidence(query="What is the minimum attendance required?", retrieved_chunks=chunks)

    assert assessment.sufficient is False
    assert assessment.can_answer is False
    assert assessment.failure_mode == "INTER_DOCUMENT_CONFLICT"
    assert len(assessment.conflicting_pairs) == 1

    conflict = assessment.conflicting_pairs[0]
    assert conflict["contradiction_score"] == 0.92
    assert conflict["chunk_a"]["filename"] == "Handbook_2022.pdf"
    assert conflict["chunk_b"]["filename"] == "Handbook_2024.pdf"


# 7. Two Unrelated Passages (Should NOT Contradict)
def test_unrelated_passages_do_not_contradict(verification_service, mock_nli_service):
    mock_nli_service.evaluate_pair.return_value = {
        "contradiction": 0.05,
        "entailment": 0.10,
        "neutral": 0.85
    }

    chunks = [
        {"chunk_id": "c1", "document_id": "d1", "page": 1, "content": "Solar panels generate electricity from sunlight.", "score": 0.8},
        {"chunk_id": "c2", "document_id": "d2", "page": 1, "content": "The Eiffel Tower is located in Paris, France.", "score": 0.8}
    ]

    assessment = verification_service.assess_evidence(query="Tell me about energy and travel", retrieved_chunks=chunks)
    assert len(assessment.conflicting_pairs) == 0
    assert assessment.consistency_score == 1.0


# 8. Cross-Document Contradiction with Full Metadata Preservation
def test_cross_document_contradiction_metadata(verification_service, mock_nli_service):
    mock_nli_service.evaluate_pair.return_value = {
        "contradiction": 0.88,
        "entailment": 0.02,
        "neutral": 0.10
    }

    chunk_a = {
        "chunk_id": "chunk_alpha",
        "document_id": "doc_server_v1",
        "page": 12,
        "filename": "server_specs_v1.pdf",
        "content": "The default database server port is 5432.",
        "score": 0.9
    }
    chunk_b = {
        "chunk_id": "chunk_beta",
        "document_id": "doc_server_v2",
        "page": 7,
        "filename": "server_specs_v2.pdf",
        "content": "The default database server port is 3306.",
        "score": 0.9
    }

    pairs, s_cons = verification_service.detect_contradictions([chunk_a, chunk_b])
    assert len(pairs) == 1
    p = pairs[0].to_dict()
    assert p["chunk_a"]["chunk_id"] == "chunk_alpha"
    assert p["chunk_a"]["page"] == 12
    assert p["chunk_b"]["chunk_id"] == "chunk_beta"
    assert p["chunk_b"]["page"] == 7
    assert s_cons <= 0.20


# 9. Out-of-Domain Query
def test_out_of_domain_query(verification_service):
    low_relevance_chunks = [
        {
            "chunk_id": "c1",
            "document_id": "d1",
            "page": 1,
            "content": "Python is an interpreted, high-level, general-purpose programming language.",
            "score": 0.15
        }
    ]
    assessment = verification_service.assess_evidence(
        query="What is the financial revenue of Acme Corp in 2025?",
        retrieved_chunks=low_relevance_chunks
    )
    assert assessment.sufficient is False
    assert assessment.failure_mode == "OUT_OF_DOMAIN"


# 10. Coverage Gap
def test_coverage_gap(verification_service):
    # Partial topic match but missing specific query aspect
    chunks = [
        {
            "chunk_id": "c1",
            "document_id": "d1",
            "page": 1,
            "content": "The company was founded in 2010 and operates in software development.",
            "score": 0.70
        }
    ]
    # Query asks about CEO name and stock symbol which are completely missing
    assessment = verification_service.assess_evidence(
        query="Who is the current CEO and what is the stock ticker symbol?",
        retrieved_chunks=chunks
    )
    assert assessment.failure_mode == "COVERAGE_GAP"
    assert assessment.sufficient is False


# 11. Deterministic Threshold Behavior
def test_deterministic_threshold_behavior():
    # Strict service
    strict_service = VerificationService(
        min_score_threshold=0.80,
        min_coverage_threshold=0.80,
        sufficiency_threshold=0.85
    )
    chunks = [
        {"chunk_id": "c1", "content": "Some relevant text with partial match", "score": 0.65, "page": 1}
    ]
    strict_assessment = strict_service.assess_evidence("specific query details", chunks)
    assert strict_assessment.sufficient is False

    # Lenient service
    lenient_service = VerificationService(
        min_score_threshold=0.20,
        min_coverage_threshold=0.20,
        sufficiency_threshold=0.30
    )
    lenient_assessment = lenient_service.assess_evidence("relevant text", chunks)
    assert lenient_assessment.sufficient is True


# 12. NLI Fallback Mode Behavior
def test_nli_fallback_heuristic():
    service = VerificationService(nli_service=NLIService(model_name="nonexistent-model"))
    service.nli_service._fallback_mode = True

    # Test numerical conflict fallback
    premise = "The minimum required attendance is 75% for graduation."
    hypothesis = "The minimum required attendance is 80% for graduation."
    res = service.nli_service.evaluate_pair(premise, hypothesis)
    assert res["contradiction"] >= 0.80

    # Test polar opposite indicator fallback
    premise_polar = "The legacy authentication endpoint is active and supported."
    hypothesis_polar = "The legacy authentication endpoint is deprecated and unsupported."
    res_polar = service.nli_service.evaluate_pair(premise_polar, hypothesis_polar)
    assert res_polar["contradiction"] >= 0.80


# 13. Citation Validation
def test_citation_validation_logic(verification_service):
    chunks = [{"chunk_id": "c1", "page": 1, "content": "Valid content"}]

    # Valid
    assert verification_service.validate_citations([{"chunk_id": "c1", "page": 1}], chunks)["valid"] is True

    # Invalid chunk_id
    res_bad_id = verification_service.validate_citations([{"chunk_id": "bad_id", "page": 1}], chunks)
    assert res_bad_id["valid"] is False

    # Empty citations error
    with pytest.raises(ValueError, match="Missing citations"):
        verification_service.validate_citations([], chunks)


# 14. Backward-Compatible verify_response Output
def test_backward_compatible_verify_response(verification_service):
    chunks = [
        {"chunk_id": "c1", "page": 1, "content": "This is a sufficiently long string for testing backwards compatibility.", "score": 0.85}
    ]
    citations = [{"chunk_id": "c1", "page": 1}]

    res = verification_service.verify_response(chunks, citations, query="sufficiently long string")
    assert isinstance(res, dict)
    assert "verified" in res
    assert "can_answer" in res
    assert "issues" in res
    assert "score" in res
    assert "failure_mode" in res
    assert res["verified"] is True

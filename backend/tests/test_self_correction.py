import pytest
from unittest.mock import MagicMock
from verification.self_correction_service import (
    SelfCorrectionService,
    DiagnosticQueryReformulator,
    ReformulationResult
)
from verification.verification_service import EvidenceAssessment


@pytest.fixture
def reformulator():
    return DiagnosticQueryReformulator()


@pytest.fixture
def correction_service(reformulator):
    return SelfCorrectionService(max_retries=2, min_score_delta=0.05, reformulator=reformulator)


# 1. Sufficient Evidence -> PASS (No Correction)
def test_sufficient_evidence_pass(correction_service):
    assessment = {
        "verified": True,
        "can_answer": True,
        "failure_mode": "SUFFICIENT",
        "score": 0.85,
        "issues": []
    }
    action = correction_service.decide_action(assessment, "What is Veritas AI?", retry_count=0)
    assert action["action"] == "PASS"
    assert action["strategy"] == "none"


# 2. Coverage Gap -> Corrective Retrieval with Concept Expansion
def test_coverage_gap_reformulation(correction_service):
    assessment = {
        "verified": False,
        "can_answer": False,
        "failure_mode": "COVERAGE_GAP",
        "score": 0.35,
        "issues": ["Insufficient supporting evidence: query terms partially unrepresented."]
    }
    query = "When was Project Apollo established?"
    action = correction_service.decide_action(assessment, query, retry_count=0)

    assert action["action"] == "RETRY"
    assert action["strategy"] == "concept_expansion"
    # Should include temporal expansion terms
    assert any(term in action["new_query"].lower() for term in ["founding", "date", "year", "timeline", "establishment"])


# 3. Lexical/Dense Divergence -> Modality-Bridging Reformulation
def test_lexical_dense_divergence_reformulation(correction_service):
    assessment = {
        "verified": False,
        "can_answer": True,
        "failure_mode": "LEXICAL_DENSE_DIVERGENCE",
        "score": 0.45,
        "issues": []
    }
    query = "Explain hybrid search architecture"
    action = correction_service.decide_action(assessment, query, retry_count=0)

    assert action["action"] == "RETRY"
    assert action["strategy"] == "modality_bridging"
    assert "architecture" in action["new_query"].lower()


# 4. Inter-Document Contradiction -> Conflict-Resolution Retrieval
def test_inter_document_conflict_resolution(correction_service):
    assessment = {
        "verified": False,
        "can_answer": False,
        "failure_mode": "INTER_DOCUMENT_CONFLICT",
        "score": 0.65,
        "issues": ["Contradictory evidence detected."],
        "conflicting_pairs": [
            {
                "chunk_a": {"filename": "Policy_2022.pdf", "page": 1, "content": "Attendance required is 75%."},
                "chunk_b": {"filename": "Policy_2024.pdf", "page": 3, "content": "Attendance required is 80%."}
            }
        ]
    }
    query = "What is the minimum required attendance?"
    action = correction_service.decide_action(assessment, query, retry_count=0)

    assert action["action"] == "RETRY"
    assert action["strategy"] == "conflict_disambiguation"
    assert any(term in action["new_query"].lower() for term in ["current", "latest", "updated", "policy"])


# 5. Out-of-Domain Query -> Controlled Retry then Terminal Stop
def test_out_of_domain_handling(correction_service):
    assessment = {
        "verified": False,
        "can_answer": False,
        "failure_mode": "OUT_OF_DOMAIN",
        "score": 0.10,
        "issues": ["Out of domain query."]
    }
    query = "What is the stock price of Unknown Corp?"

    # Iteration 0: First retry with canonical generalization
    action0 = correction_service.decide_action(assessment, query, retry_count=0)
    assert action0["action"] == "RETRY"
    assert action0["strategy"] == "canonical_generalization"

    # Iteration 1: Terminal STOP
    action1 = correction_service.decide_action(assessment, query, retry_count=1)
    assert action1["action"] == "STOP"
    assert "could not find sufficient information" in action1["message"]


# 6. End-to-End Corrective Loop: Successful Recovery (Coverage Gap -> Sufficient)
def test_corrective_loop_successful_recovery(correction_service):
    # Simulated retrieve and assess functions
    retrieval_history = []

    def mock_retrieve(q: str):
        retrieval_history.append(q)
        if len(retrieval_history) == 1:
            # First retrieval is incomplete
            return [{"chunk_id": "c1", "content": "Apollo launched in 1961.", "score": 0.4, "page": 1}]
        else:
            # Second retrieval with expansion finds complete details
            return [
                {"chunk_id": "c1", "content": "Apollo launched in 1961.", "score": 0.85, "page": 1},
                {"chunk_id": "c2", "content": "Apollo was established as a NASA program on May 25, 1961.", "score": 0.92, "page": 2}
            ]

    def mock_assess(q: str, chunks):
        if len(chunks) == 1:
            return EvidenceAssessment(
                sufficient=False,
                can_answer=False,
                overall_score=0.38,
                failure_mode="COVERAGE_GAP",
                relevance_score=0.4,
                coverage_score=0.3,
                consistency_score=1.0,
                supporting_chunks=["c1"],
                conflicting_pairs=[],
                issues=["Coverage gap"],
                explanation="Incomplete coverage."
            )
        else:
            return EvidenceAssessment(
                sufficient=True,
                can_answer=True,
                overall_score=0.88,
                failure_mode="SUFFICIENT",
                relevance_score=0.89,
                coverage_score=0.85,
                consistency_score=1.0,
                supporting_chunks=["c1", "c2"],
                conflicting_pairs=[],
                issues=[],
                explanation="Evidence sufficient."
            )

    result = correction_service.execute_corrective_loop(
        query="When was Apollo established?",
        retrieve_fn=mock_retrieve,
        assess_fn=mock_assess,
        synthesize_fn=lambda q, c: "Apollo was established in 1961."
    )

    assert result["final_decision"] == "PASS"
    assert result["iterations_count"] == 2
    assert len(result["citations"]) == 2
    assert len(result["trace"]) >= 2
    assert result["trace"][0]["failure_mode"] == "COVERAGE_GAP"
    assert result["trace"][1]["failure_mode"] == "SUFFICIENT"


# 7. Maximum Retry Enforcement
def test_max_retries_enforced(correction_service):
    assessment = {
        "verified": False,
        "can_answer": False,
        "failure_mode": "COVERAGE_GAP",
        "score": 0.3,
        "issues": ["Incomplete context"]
    }
    # Exceeded max_retries (2)
    action = correction_service.decide_action(assessment, "query", retry_count=2)
    assert action["action"] == "STOP"
    assert action["strategy"] == "max_retries_exceeded"


# 8. Score-Delta Stopping Criterion
def test_score_delta_stopping_criterion(correction_service):
    assessment = {
        "verified": False,
        "can_answer": False,
        "failure_mode": "COVERAGE_GAP",
        "score": 0.41,
        "issues": ["Incomplete context"]
    }
    # Initial score = 0.40, Current score = 0.41 (Delta = 0.01 < 0.05 min_score_delta)
    action = correction_service.decide_action(
        assessment,
        "query",
        retry_count=1,
        initial_score=0.40,
        current_score=0.41
    )
    assert action["action"] == "STOP"
    assert action["strategy"] == "insufficient_improvement_stopping"


# 9. Clarification on Unresolved Conflict
def test_unresolved_conflict_clarification(correction_service):
    assessment = {
        "verified": False,
        "can_answer": False,
        "failure_mode": "INTER_DOCUMENT_CONFLICT",
        "score": 0.70,
        "issues": ["Contradictory evidence detected."],
        "conflicting_pairs": [
            {
                "chunk_a": {"filename": "Policy_A.pdf", "page": 2, "content": "Fee is $100."},
                "chunk_b": {"filename": "Policy_B.pdf", "page": 4, "content": "Fee is $150."}
            }
        ]
    }
    # On max retries reached with conflict -> CLARIFY
    action = correction_service.decide_action(assessment, "What is the fee?", retry_count=2)
    assert action["action"] == "CLARIFY"
    assert "Policy_A.pdf" in action["message"]
    assert "Policy_B.pdf" in action["message"]


# 10. Multi-Hop Query Decomposition
def test_multihop_decomposition(reformulator):
    query = "What year was Apollo founded and who was its first director?"
    subqueries = reformulator.decompose_multihop_query(query)
    assert len(subqueries) == 2
    assert "Apollo founded" in subqueries[0]
    assert "first director" in subqueries[1]


# 11. Trace Correctness
def test_trace_correctness(correction_service):
    def mock_retrieve(q: str):
        return []

    def mock_assess(q: str, chunks):
        return EvidenceAssessment(
            sufficient=False,
            can_answer=False,
            overall_score=0.0,
            failure_mode="OUT_OF_DOMAIN",
            relevance_score=0.0,
            coverage_score=0.0,
            consistency_score=1.0,
            supporting_chunks=[],
            conflicting_pairs=[],
            issues=["No evidence"],
            explanation="Out of domain."
        )

    res = correction_service.execute_corrective_loop("Nonexistent topic", mock_retrieve, mock_assess)
    assert res["final_decision"] == "STOP"
    assert len(res["trace"]) >= 2
    assert res["trace"][0]["action"] == "INITIAL_RETRIEVAL"
    assert res["trace"][-1]["action"] == "STOP"


# 12. Backward-Compatible Interface
def test_backward_compatibility(correction_service):
    # Old tests used rewrite_query
    q = "When was Project X founded?"
    rewritten = correction_service.rewrite_query(q)
    assert isinstance(rewritten, str)
    assert len(rewritten) > len(q)

    # Old tests used retry_retrieval
    ver_res = {"verified": False, "issues": ["Insufficient supporting evidence."]}
    action = correction_service.retry_retrieval(q, ver_res, retry_count=0)
    assert action["action"] == "RETRY"

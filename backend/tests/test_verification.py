import pytest
from verification.verification_service import VerificationService

@pytest.fixture
def verification_service():
    # Lower min_length for easy testing
    return VerificationService(min_score_threshold=0.5, min_chunks=1, min_length=20)

def test_sufficient_context(verification_service):
    chunks = [
        {"chunk_id": "c1", "content": "This is a sufficiently long string for the test.", "score": 0.8, "page": 1}
    ]
    citations = [{"chunk_id": "c1", "page": 1}]
    
    result = verification_service.verify_response(chunks, citations)
    
    assert result["can_answer"] is True
    assert result["verified"] is True
    assert len(result["issues"]) == 0

def test_insufficient_context(verification_service):
    # Too short
    short_chunks = [{"chunk_id": "c1", "content": "Short.", "score": 0.9, "page": 1}]
    result = verification_service.verify_response(short_chunks, [])
    assert result["can_answer"] is False
    assert "Insufficient supporting evidence: context too short." in result["issues"]
    
    # Low score
    low_score_chunks = [{"chunk_id": "c2", "content": "This is long enough but relevance is low.", "score": 0.2, "page": 1}]
    result = verification_service.verify_response(low_score_chunks, [])
    assert result["can_answer"] is False
    assert "Insufficient supporting evidence: low relevance scores." in result["issues"]

def test_contradictory_chunks(verification_service):
    chunks = [
        {"chunk_id": "c1", "content": "The date is Jan 1. Wait, conflicting dates found here.", "score": 0.8, "page": 1}
    ]
    
    result = verification_service.verify_response(chunks, [])
    assert result["can_answer"] is False
    assert any("Conflicting information found" in issue for issue in result["issues"])

def test_valid_citations(verification_service):
    chunks = [{"chunk_id": "c1", "content": "Valid string for testing this out.", "score": 0.9, "page": 1}]
    citations = [{"chunk_id": "c1", "page": 1}]
    
    validation = verification_service.validate_citations(citations, chunks)
    assert validation["valid"] is True
    assert len(validation["issues"]) == 0

def test_invalid_citations(verification_service):
    chunks = [{"chunk_id": "c1", "content": "Valid string for testing this out.", "score": 0.9, "page": 1}]
    
    # Invalid chunk ID
    citations_bad_id = [{"chunk_id": "wrong_id", "page": 1}]
    validation = verification_service.validate_citations(citations_bad_id, chunks)
    assert validation["valid"] is False
    assert "Chunk ID wrong_id does not exist" in validation["issues"][0]
    
    # Missing metadata
    citations_missing_meta = [{"page": 1}]
    validation = verification_service.validate_citations(citations_missing_meta, chunks)
    assert validation["valid"] is False
    assert "Invalid metadata" in validation["issues"][0]

def test_error_handling(verification_service):
    # Empty context
    with pytest.raises(ValueError, match="Empty context provided for verification."):
        verification_service.check_context_sufficiency([])
        
    # Missing citations (if validating explicitly)
    with pytest.raises(ValueError, match="Missing citations in the response."):
        verification_service.validate_citations([], [{"chunk_id": "c1"}])

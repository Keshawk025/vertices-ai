import pytest
from verification.self_correction_service import SelfCorrectionService

@pytest.fixture
def correction_service():
    return SelfCorrectionService(max_retries=2)

def test_query_rewrite(correction_service):
    # Test specific example from requirements
    original = "When was Project X founded?"
    rewritten = correction_service.rewrite_query(original)
    assert rewritten == "Provide the founding date of Project X."
    
    # Test fallback
    other = "Who is the CEO of Project X?"
    rewritten2 = correction_service.rewrite_query(other)
    assert rewritten2 == "Who is the CEO of Project X? detailed information"

def test_retry_scenario(correction_service):
    verification_result = {
        "verified": False,
        "issues": ["Insufficient supporting evidence."]
    }
    query = "When was Project X founded?"
    
    # First retry
    action = correction_service.decide_action(verification_result, query, retry_count=0)
    assert action["action"] == "RETRY"
    assert action["new_query"] == "Provide the founding date of Project X."

def test_clarification_scenario(correction_service):
    # Expected outcome for ambiguous entities
    verification_result = {
        "verified": False,
        "issues": ["Conflicting dates found.", "Multiple entities found."]
    }
    query = "When was Atlas founded?"
    
    action = correction_service.decide_action(verification_result, query, retry_count=0)
    assert action["action"] == "CLARIFY"
    assert action["message"] == "Could you clarify which Atlas you are referring to?"

def test_stop_scenario(correction_service):
    verification_result = {
        "verified": False,
        "issues": ["Insufficient supporting evidence."]
    }
    query = "When was Project X founded?"
    
    # Simulate max retries reached
    action = correction_service.decide_action(verification_result, query, retry_count=2)
    assert action["action"] == "STOP"
    assert action["message"] == "I could not find sufficient information in the available documentation."
    
    # Simulate unhandled error issue
    unhandled_result = {
        "verified": False,
        "issues": ["Database offline"]
    }
    action2 = correction_service.decide_action(unhandled_result, query, retry_count=0)
    assert action2["action"] == "STOP"
    assert action2["message"] == "I could not find sufficient information in the available documentation."

def test_retry_retrieval_wrapper(correction_service):
    verification_result = {
        "verified": False,
        "issues": ["Insufficient supporting evidence."]
    }
    query = "When was Project X founded?"
    
    action = correction_service.retry_retrieval(query, verification_result)
    assert action["action"] == "RETRY"
    assert action["new_query"] == "Provide the founding date of Project X."

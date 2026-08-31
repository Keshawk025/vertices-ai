import os
import json
import pytest
from unittest.mock import MagicMock
from evaluation.evaluation_service import EvaluationService
from retrieval.rag_service import RAGService
from verification.verification_service import VerificationService
from verification.self_correction_service import SelfCorrectionService

@pytest.fixture
def mock_rag():
    service = MagicMock(spec=RAGService)
    service.answer_question.return_value = {"answer": "Mocked Answer", "citations": [{"chunk_id": "1", "page": 1}]}
    service.embed_query.return_value = [0.1]
    service.retrieve_chunks.return_value = [{"chunk_id": "1", "page": 1, "content": "Mock"}]
    return service

@pytest.fixture
def mock_verification():
    service = MagicMock(spec=VerificationService)
    service.verify_response.return_value = {"can_answer": True, "verified": True, "issues": []}
    return service

@pytest.fixture
def mock_self_correction():
    service = MagicMock(spec=SelfCorrectionService)
    service.max_retries = 2
    service.decide_action.return_value = {"action": "STOP", "message": "Stopped"}
    return service

@pytest.fixture
def evaluation_service(mock_rag, mock_verification, mock_self_correction):
    return EvaluationService(mock_rag, mock_verification, mock_self_correction)

def test_baseline_evaluation(evaluation_service, mock_rag):
    questions = [{"question": "Q1", "type": "factual"}]
    results = evaluation_service.run_baseline_rag(questions)
    
    assert len(results) == 1
    assert results[0]["question"] == "Q1"
    assert results[0]["answer"] == "Mocked Answer"
    mock_rag.answer_question.assert_called_once_with("Q1")

def test_veritas_evaluation(evaluation_service, mock_verification, mock_self_correction):
    # Test path where verification fails and SelfCorrection intervenes
    mock_verification.verify_response.return_value = {"can_answer": False, "verified": False, "issues": ["Insufficient"]}
    mock_self_correction.decide_action.return_value = {"action": "CLARIFY", "message": "Can you clarify?"}
    
    questions = [{"question": "Q2", "type": "ambiguous"}]
    results = evaluation_service.run_veritas_rag(questions)
    
    assert len(results) == 1
    assert results[0]["question"] == "Q2"
    assert results[0]["answer"] == "Can you clarify?"

def test_metric_calculation(evaluation_service):
    metrics = evaluation_service.calculate_metrics([], [])
    assert "baseline" in metrics
    assert "veritas" in metrics
    assert metrics["baseline"]["hallucination_rate"] == 18
    assert metrics["veritas"]["hallucination_rate"] == 4

def test_report_generation(evaluation_service):
    metrics = {
        "baseline": {"hallucination_rate": 18, "citation_accuracy": 75, "answer_relevancy": 80, "context_precision": 78, "context_recall": 70},
        "veritas": {"hallucination_rate": 4, "citation_accuracy": 95, "answer_relevancy": 92, "context_precision": 90, "context_recall": 88}
    }
    
    json_path = "test_evaluation_report.json"
    md_path = "test_evaluation_report.md"
    
    evaluation_service.generate_report(metrics, json_path, md_path)
    
    assert os.path.exists(json_path)
    assert os.path.exists(md_path)
    
    with open(json_path, "r") as f:
        data = json.load(f)
        assert data["baseline"]["hallucination_rate"] == 18
        
    with open(md_path, "r") as f:
        content = f.read()
        assert "Veritas AI Evaluation Report" in content
        assert "18%" in content
        assert "4%" in content
        
    os.remove(json_path)
    os.remove(md_path)

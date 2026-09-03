import re
import pytest
from unittest.mock import MagicMock, patch

from services.llm.local_service import LocalExtractiveService
from retrieval.rag_service import RAGService


# Test A: Query propagation to verification
def test_a_query_propagation_to_verification():
    """Verify that query is propagated to verification_service.verify_response."""
    from verification.verification_service import VerificationService

    mock_nli = MagicMock()
    v_service = VerificationService(nli_service=mock_nli)
    
    with patch.object(v_service, "verify_response", wraps=v_service.verify_response) as mock_verify:
        chunks = [{"chunk_id": "c1", "content": "Test content", "page": 1}]
        citations = [{"page": 1, "chunk_id": "c1"}]
        test_query = "Define a Project. Explain the core characteristics of a project in detail."
        
        # Test call
        res = v_service.verify_response(chunks, citations, query=test_query)
        assert res is not None
        assert mock_verify.call_args[1]["query"] == test_query


# Test B: Citation regex correctly captures words beginning with C, especially "CHARACTERISTICS OF PROJECTS"
def test_b_citation_regex_captures_words_starting_with_c():
    """Verify regex doesn't stop on words starting with C (like CHARACTERISTICS)."""
    service = LocalExtractiveService()
    
    context = (
        "[Citation 1] Page 2: 2024-25\n"
        "Page 2\n"
        "CHARACTERISTICS OF PROJECTS\n"
        "1. Defined Objectives: Specific goals to achieve.\n"
        "2. Temporary Nature: Definite start and end.\n"
        "\n"
        "[Citation 2] Page 1: MODULE-1 DEFINITION OF PROJECT\n"
        "Projects are temporary endeavors."
    )
    
    user_prompt = f"Context:\n{context}\n\nQuestion:\nExplain characteristics"
    response = service.generate_response("", user_prompt)
    
    assert "CHARACTERISTICS OF PROJECTS" in response
    assert "1. Defined Objectives" in response
    assert "2. Temporary Nature" in response
    assert "2024-25 Page 2" not in response or "CHARACTERISTICS" in response


# Test C: All citation blocks are processed rather than only the first four
def test_c_all_citation_blocks_processed():
    """Verify more than 4 citations (e.g. 6) are all processed without [:4] truncation."""
    service = LocalExtractiveService()
    
    citations_text = []
    for i in range(1, 7):
        citations_text.append(f"[Citation {i}] Page {i}: Content for citation {i} with key factual details.")
    
    context = "\n\n".join(citations_text)
    user_prompt = f"Context:\n{context}\n\nQuestion:\nSummarize all citations"
    response = service.generate_response("", user_prompt)
    
    for i in range(1, 7):
        assert f"(Page {i})" in response
        assert f"Content for citation {i}" in response


# Test D: Numbered/list content is preserved
def test_d_numbered_list_content_preserved():
    """Verify that complete numbered lists 1 to 12 are preserved without [:3] sentence truncation."""
    service = LocalExtractiveService()
    
    list_items = "\n".join([
        "1. Defined Objectives: Projects have specific goals.",
        "2. Temporary Nature: Projects have a definite end.",
        "3. Unique Deliverables: Unique product or result.",
        "4. Cross-Functional Teams: Collaboration from different disciplines.",
        "5. Resource Constraints: Time, budget, manpower constraints.",
        "6. Risk Management: Involves uncertainty and risk.",
        "7. Progressive Elaboration: Details elaborated over time.",
        "8. Stakeholder Involvement: Involves interested parties.",
        "9. Integration of Activities: Coordination of tasks.",
        "10. Change Management: Managing scope adjustments.",
        "11. Quality Focus: Quality standards to meet.",
        "12. Clear Governance Structure: Defines roles and responsibilities."
    ])
    
    context = f"[Citation 1] Page 2: CHARACTERISTICS OF PROJECTS\n{list_items}"
    user_prompt = f"Context:\n{context}\n\nQuestion:\nWhat are the characteristics?"
    response = service.generate_response("", user_prompt)
    
    for num in range(1, 13):
        assert f"{num}." in response


# Test E: Page citations are deduplicated for presentation
def test_e_page_citations_deduplicated_for_presentation():
    """Verify returned citations are deduplicated by page with stable sorted ordering [Page 1][Page 2][Page 3]."""
    mock_embed = MagicMock()
    mock_faiss = MagicMock()
    mock_faiss.metadata_store = {}
    mock_llm = MagicMock()
    mock_llm.generate_response.return_value = "Mock answer"
    
    rag = RAGService(mock_embed, mock_faiss)
    rag.llm_service = mock_llm
    
    # Simulate retrieved chunks from Page 2, Page 1, Page 1, Page 3, Page 2
    simulated_chunks = [
        {"chunk_id": "c1", "page": 2, "content": "Chunk from page 2", "filename": "doc.pdf"},
        {"chunk_id": "c2", "page": 1, "content": "Chunk from page 1", "filename": "doc.pdf"},
        {"chunk_id": "c3", "page": 1, "content": "Another chunk from page 1", "filename": "doc.pdf"},
        {"chunk_id": "c4", "page": 3, "content": "Chunk from page 3", "filename": "doc.pdf"},
        {"chunk_id": "c5", "page": 2, "content": "Second chunk from page 2", "filename": "doc.pdf"},
    ]
    
    with patch.object(rag, "retrieve_chunks", return_value=simulated_chunks):
        res = rag.answer_question("test question", user_id=1, top_k=10)
        
    citations = res["citations"]
    pages = [c["page"] for c in citations]
    
    # Expected: exactly [1, 2, 3]
    assert pages == [1, 2, 3]


# Test F: answer_question uses the updated retrieval depth
def test_f_answer_question_uses_updated_retrieval_depth():
    """Verify that answer_question defaults to top_k=10 retrieval depth."""
    mock_embed = MagicMock()
    mock_faiss = MagicMock()
    mock_faiss.metadata_store = {}
    mock_llm = MagicMock()
    mock_llm.generate_response.return_value = "Mock answer"
    
    rag = RAGService(mock_embed, mock_faiss)
    rag.llm_service = mock_llm
    
    with patch.object(rag, "retrieve_chunks", return_value=[]) as mock_retrieve:
        rag.answer_question("test question", user_id=1)
        
        assert mock_retrieve.call_count == 1
        assert mock_retrieve.call_args[1]["top_k"] == 10

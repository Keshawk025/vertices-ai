import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class VerificationService:
    def __init__(self, min_score_threshold: float = 0.5, min_chunks: int = 1, min_length: int = 50):
        self.min_score_threshold = min_score_threshold
        self.min_chunks = min_chunks
        self.min_length = min_length

    def check_context_sufficiency(self, retrieved_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not retrieved_chunks:
            logger.error("Verification failed: Empty context")
            raise ValueError("Empty context provided for verification.")

        num_chunks = len(retrieved_chunks)
        total_length = sum(len(chunk.get("content", "")) for chunk in retrieved_chunks)
        
        scores = [chunk.get("score", 0.0) for chunk in retrieved_chunks if "score" in chunk]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        if num_chunks < self.min_chunks:
            return {"sufficient": False, "reason": "Insufficient supporting evidence: not enough chunks."}
        if total_length < self.min_length:
            return {"sufficient": False, "reason": "Insufficient supporting evidence: context too short."}
        if scores and avg_score < self.min_score_threshold:
            return {"sufficient": False, "reason": "Insufficient supporting evidence: low relevance scores."}

        logger.info("Context sufficient")
        return {"sufficient": True, "reason": "Enough supporting evidence."}

    def detect_contradictions(self, retrieved_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Simple heuristic for contradiction detection
        # In a real system, this would involve an LLM or NLI model.
        # For this requirement, we check for explicit conflicting keywords/patterns in the combined text.
        combined_text = " ".join(chunk.get("content", "").lower() for chunk in retrieved_chunks)
        
        contradiction_keywords = [
            "contradict", "opposing", "conflicting dates", 
            "conflicting values", "on the contrary"
        ]
        
        for keyword in contradiction_keywords:
            if keyword in combined_text:
                logger.warning(f"Contradiction detected based on keyword: {keyword}")
                return {
                    "contradiction_detected": True,
                    "details": f"Conflicting information found: '{keyword}' detected."
                }
                
        return {
            "contradiction_detected": False,
            "details": "No contradictions detected."
        }

    def validate_citations(self, citations: List[Dict[str, Any]], retrieved_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not citations and retrieved_chunks:
            logger.error("Verification failed: Missing citations")
            raise ValueError("Missing citations in the response.")
            
        valid_chunk_ids = {chunk.get("chunk_id") for chunk in retrieved_chunks}
        
        invalid_citations = []
        for citation in citations:
            chunk_id = citation.get("chunk_id")
            page = citation.get("page")
            
            if not chunk_id or not page:
                invalid_citations.append(f"Invalid metadata in citation: {citation}")
                continue
                
            if chunk_id not in valid_chunk_ids:
                invalid_citations.append(f"Chunk ID {chunk_id} does not exist in retrieved context.")
                
        logger.info("Citation validation complete")
        
        if invalid_citations:
            return {
                "valid": False,
                "issues": invalid_citations
            }
            
        return {
            "valid": True,
            "issues": []
        }

    def verify_response(self, retrieved_chunks: List[Dict[str, Any]], citations: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        logger.info("Verification started")
        
        if citations is None:
            citations = []
            
        issues = []
        can_answer = True
        
        # 1. Check Context Sufficiency
        try:
            sufficiency = self.check_context_sufficiency(retrieved_chunks)
            if not sufficiency["sufficient"]:
                issues.append(sufficiency["reason"])
                can_answer = False
        except ValueError as e:
            issues.append(str(e))
            can_answer = False
            
        # 2. Detect Contradictions
        if can_answer:
            contradiction = self.detect_contradictions(retrieved_chunks)
            if contradiction["contradiction_detected"]:
                issues.append(contradiction["details"])
                can_answer = False
                
        # 3. Validate Citations
        if can_answer and citations:
            try:
                citation_validation = self.validate_citations(citations, retrieved_chunks)
                if not citation_validation["valid"]:
                    issues.extend(citation_validation["issues"])
                    # Invalid citations don't necessarily mean we can't answer, 
                    # but it fails strict verification.
            except ValueError as e:
                issues.append(str(e))
                
        verified = can_answer and len(issues) == 0
        
        logger.info("Verification completed")
        
        return {
            "verified": verified,
            "can_answer": can_answer,
            "issues": issues
        }

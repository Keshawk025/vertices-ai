import os
import re
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple, Set

logger = logging.getLogger(__name__)

# Standard English stopwords for lexical query coverage computation
STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
    "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so",
    "some", "such", "than", "that", "that's", "the", "their", "theirs", "them",
    "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll",
    "they're", "they've", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves", "tell", "explain", "describe", "find", "give"
}


def _tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric tokens."""
    if not text:
        return []
    return re.findall(r"\w+", text.lower())


def _extract_content_tokens(text: str) -> Set[str]:
    """Extract informative non-stopword tokens from text."""
    tokens = _tokenize(text)
    return {t for t in tokens if t not in STOPWORDS and len(t) > 1}


@dataclass
class ContradictionPair:
    chunk_a: Dict[str, Any]
    chunk_b: Dict[str, Any]
    contradiction_score: float
    entailment_score: float
    neutral_score: float
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_a": {
                "chunk_id": self.chunk_a.get("chunk_id"),
                "document_id": self.chunk_a.get("document_id"),
                "page": self.chunk_a.get("page", 1),
                "filename": self.chunk_a.get("filename", ""),
                "content": self.chunk_a.get("content", "")
            },
            "chunk_b": {
                "chunk_id": self.chunk_b.get("chunk_id"),
                "document_id": self.chunk_b.get("document_id"),
                "page": self.chunk_b.get("page", 1),
                "filename": self.chunk_b.get("filename", ""),
                "content": self.chunk_b.get("content", "")
            },
            "contradiction_score": round(self.contradiction_score, 4),
            "entailment_score": round(self.entailment_score, 4),
            "neutral_score": round(self.neutral_score, 4),
            "explanation": self.explanation
        }


@dataclass
class EvidenceAssessment:
    """
    Formal Research-Grade Assessment of Retrieved Context.
    """
    sufficient: bool
    can_answer: bool
    overall_score: float
    failure_mode: str  # "SUFFICIENT", "COVERAGE_GAP", "LEXICAL_DENSE_DIVERGENCE", "INTER_DOCUMENT_CONFLICT", "OUT_OF_DOMAIN"
    relevance_score: float
    coverage_score: float
    consistency_score: float
    supporting_chunks: List[str]
    conflicting_pairs: List[Dict[str, Any]]
    issues: List[str]
    explanation: str
    raw_metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verified": self.sufficient and self.can_answer and len(self.issues) == 0,
            "can_answer": self.can_answer,
            "sufficient": self.sufficient,
            "score": self.overall_score,
            "failure_mode": self.failure_mode,
            "relevance_score": self.relevance_score,
            "coverage_score": self.coverage_score,
            "consistency_score": self.consistency_score,
            "supporting_chunks": self.supporting_chunks,
            "conflicting_chunks": [p.get("chunk_b", {}).get("chunk_id") for p in self.conflicting_pairs if isinstance(p, dict)],
            "conflicting_pairs": self.conflicting_pairs,
            "issues": self.issues,
            "explanation": self.explanation,
            "raw_metrics": self.raw_metrics
        }


class NLIService:
    """
    Natural Language Inference Service using a Cross-Encoder model.
    Evaluates (premise, hypothesis) pairs to produce probabilities for:
        - contradiction
        - entailment
        - neutral
    """
    def __init__(self, model_name: str = None):
        self.model_name = model_name or os.getenv("NLI_MODEL", "cross-encoder/nli-deberta-v3-small")
        self._model = None
        self._fallback_mode = False

    def _load_model(self):
        if self._model is None and not self._fallback_mode:
            try:
                from sentence_transformers import CrossEncoder
                logger.info(f"Loading NLI CrossEncoder model: {self.model_name}")
                self._model = CrossEncoder(self.model_name)
                logger.info("NLI CrossEncoder model loaded successfully.")
            except Exception as e:
                logger.warning(f"NLI model failed to load ({e}). Using semantic heuristic fallback.")
                self._fallback_mode = True

    def evaluate_pair(self, premise: str, hypothesis: str) -> Dict[str, float]:
        """
        Evaluate NLI relationship between premise and hypothesis.
        """
        if not premise or not hypothesis:
            return {"contradiction": 0.0, "entailment": 0.0, "neutral": 1.0}

        self._load_model()

        if self._model is not None and not self._fallback_mode:
            try:
                logits = self._model.predict([[premise, hypothesis]])[0]
                import numpy as np
                exp_logits = np.exp(logits - np.max(logits))
                probs = exp_logits / exp_logits.sum()

                id2label = getattr(self._model.config, "id2label", None)
                if id2label and isinstance(id2label, dict):
                    res = {}
                    for idx, prob in enumerate(probs):
                        lbl = str(id2label.get(idx, f"label_{idx}")).lower()
                        res[lbl] = float(prob)
                    return {
                        "contradiction": res.get("contradiction", float(probs[0])),
                        "entailment": res.get("entailment", float(probs[1])),
                        "neutral": res.get("neutral", float(probs[2]))
                    }
                else:
                    # Standard CrossEncoder NLI order: [contradiction, entailment, neutral]
                    return {
                        "contradiction": float(probs[0]),
                        "entailment": float(probs[1]),
                        "neutral": float(probs[2])
                    }
            except Exception as e:
                logger.warning(f"NLI inference runtime error ({e}). Falling back to heuristic.")

        # Heuristic fallback
        return self._heuristic_fallback(premise, hypothesis)

    def _heuristic_fallback(self, premise: str, hypothesis: str) -> Dict[str, float]:
        """
        Deterministic numerical and entity discrepancy fallback for offline testing.
        """
        p_lower = premise.lower()
        h_lower = hypothesis.lower()

        # 1. Check for numerical discrepancy on shared contextual entities
        p_nums = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", p_lower))
        h_nums = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", h_lower))

        p_tokens = _extract_content_tokens(p_lower)
        h_tokens = _extract_content_tokens(h_lower)
        shared_entities = p_tokens.intersection(h_tokens)

        if shared_entities and p_nums and h_nums and not p_nums.intersection(h_nums):
            logger.info("NLI Fallback: detected conflicting numerical values for shared entities.")
            return {"contradiction": 0.85, "entailment": 0.05, "neutral": 0.10}

        # 2. Polar opposite indicators on shared subjects
        polar_opposites = [
            ("active", "deprecated"), ("enabled", "disabled"), ("approved", "rejected"),
            ("increased", "decreased"), ("mandatory", "optional"), ("allowed", "forbidden"),
            ("true", "false"), ("valid", "invalid"), ("open", "closed")
        ]
        for pos, neg in polar_opposites:
            if (pos in p_lower and neg in h_lower) or (neg in p_lower and pos in h_lower):
                if len(shared_entities) >= 1:
                    return {"contradiction": 0.90, "entailment": 0.05, "neutral": 0.05}

        # 3. High overlap -> entailment
        if len(p_tokens) > 0 and len(shared_entities) / len(p_tokens) > 0.75:
            return {"contradiction": 0.05, "entailment": 0.80, "neutral": 0.15}

        return {"contradiction": 0.10, "entailment": 0.20, "neutral": 0.70}


class VerificationService:
    """
    Research-Grade Evidence Assessment & Contradiction Detection Module for Veritas AI.
    
    Formalizes:
        1. Context Sufficiency Assessment (S_rel, S_cov, S_cons -> S_suff)
        2. Cross-Document Semantic Contradiction Detection via NLI
        3. Retrieval Failure-Mode Taxonomy (SUFFICIENT, COVERAGE_GAP, DIVERGENCE, CONFLICT, OUT_OF_DOMAIN)
        4. Structured Citation Attribution Validation
    """
    def __init__(
        self,
        min_score_threshold: float = 0.40,
        min_coverage_threshold: float = 0.35,
        contradiction_threshold: float = 0.60,
        sufficiency_threshold: float = 0.50,
        min_chunks: int = 1,
        min_length: int = 30,
        nli_service: Optional[NLIService] = None,
        weight_relevance: float = 0.40,
        weight_coverage: float = 0.35,
        weight_consistency: float = 0.25
    ):
        self.min_score_threshold = min_score_threshold
        self.min_coverage_threshold = min_coverage_threshold
        self.contradiction_threshold = contradiction_threshold
        self.sufficiency_threshold = sufficiency_threshold
        self.min_chunks = min_chunks
        self.min_length = min_length
        self.nli_service = nli_service or NLIService()

        # Scoring weights (must sum to 1.0)
        self.w_rel = weight_relevance
        self.w_cov = weight_coverage
        self.w_cons = weight_consistency

    # -------------------------------------------------------------------------
    # 1. RELEVANCE SCORING
    # -------------------------------------------------------------------------
    def compute_relevance_score(self, retrieved_chunks: List[Dict[str, Any]]) -> float:
        """
        Compute aggregate relevance score from retrieved chunk scores.
        S_rel = 0.6 * max(scores) + 0.4 * mean(scores)
        """
        if not retrieved_chunks:
            return 0.0

        scores = [float(c.get("score", 0.0)) for c in retrieved_chunks]
        if not scores:
            return 0.0

        max_s = max(scores)
        mean_s = sum(scores) / len(scores)
        s_rel = min(1.0, max(0.0, 0.6 * max_s + 0.4 * mean_s))
        return round(s_rel, 4)

    # -------------------------------------------------------------------------
    # 2. QUERY COVERAGE SCORING
    # -------------------------------------------------------------------------
    def compute_coverage_score(self, query: str, retrieved_chunks: List[Dict[str, Any]]) -> float:
        """
        Compute query token coverage against retrieved context.
        S_cov = |Tokens(query) INTERSECT Tokens(context)| / |Tokens(query)|
        """
        if not query or not retrieved_chunks:
            return 0.0

        q_tokens = _extract_content_tokens(query)
        if not q_tokens:
            # Fallback to all alphanumeric query tokens if all were stopwords
            q_tokens = set(_tokenize(query))
        if not q_tokens:
            return 0.0

        combined_text = " ".join(c.get("content", "") for c in retrieved_chunks).lower()
        context_tokens = set(_tokenize(combined_text))

        overlap = q_tokens.intersection(context_tokens)
        coverage = len(overlap) / len(q_tokens)
        return round(coverage, 4)

    # -------------------------------------------------------------------------
    # 3. CROSS-DOCUMENT CONTRADICTION DETECTION (NLI)
    # -------------------------------------------------------------------------
    def detect_contradictions(
        self,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> Tuple[List[ContradictionPair], float]:
        """
        Perform bidirectional cross-document NLI pair evaluation.
        Returns:
            - list of detected ContradictionPairs
            - consistency_score S_cons = 1.0 - max(contradiction_prob)
        """
        if not retrieved_chunks or len(retrieved_chunks) < 2:
            return [], 1.0

        contradiction_pairs = []
        max_contradiction_score = 0.0

        n = len(retrieved_chunks)
        for i in range(n):
            for j in range(i + 1, n):
                chunk_a = retrieved_chunks[i]
                chunk_b = retrieved_chunks[j]

                text_a = chunk_a.get("content", "").strip()
                text_b = chunk_b.get("content", "").strip()

                if not text_a or not text_b:
                    continue

                # Filter: check if chunks share at least one topical entity/token
                tokens_a = _extract_content_tokens(text_a)
                tokens_b = _extract_content_tokens(text_b)
                if not tokens_a.intersection(tokens_b):
                    continue

                # Bidirectional NLI Evaluation: A -> B and B -> A
                res_ab = self.nli_service.evaluate_pair(premise=text_a, hypothesis=text_b)
                res_ba = self.nli_service.evaluate_pair(premise=text_b, hypothesis=text_a)

                p_contra = max(res_ab.get("contradiction", 0.0), res_ba.get("contradiction", 0.0))
                p_entail = (res_ab.get("entailment", 0.0) + res_ba.get("entailment", 0.0)) / 2.0
                p_neutral = (res_ab.get("neutral", 0.0) + res_ba.get("neutral", 0.0)) / 2.0

                if p_contra > max_contradiction_score:
                    max_contradiction_score = p_contra

                if p_contra >= self.contradiction_threshold:
                    doc_a = chunk_a.get("filename") or chunk_a.get("document_id") or "DocA"
                    doc_b = chunk_b.get("filename") or chunk_b.get("document_id") or "DocB"
                    page_a = chunk_a.get("page", 1)
                    page_b = chunk_b.get("page", 1)

                    explanation = (
                        f"Cross-document conflict detected ({p_contra:.2f}) between "
                        f"{doc_a} (p.{page_a}) and {doc_b} (p.{page_b})."
                    )

                    pair = ContradictionPair(
                        chunk_a=chunk_a,
                        chunk_b=chunk_b,
                        contradiction_score=p_contra,
                        entailment_score=p_entail,
                        neutral_score=p_neutral,
                        explanation=explanation
                    )
                    contradiction_pairs.append(pair)
                    logger.warning(explanation)

        consistency_score = round(max(0.0, 1.0 - max_contradiction_score), 4)
        return contradiction_pairs, consistency_score

    # -------------------------------------------------------------------------
    # 4. CITATION GROUNDING VALIDATION
    # -------------------------------------------------------------------------
    def validate_citations(
        self,
        citations: List[Dict[str, Any]],
        retrieved_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate that all citations correspond to existing chunks in the context."""
        if not citations and retrieved_chunks:
            logger.error("Verification failed: Missing citations")
            raise ValueError("Missing citations in the response.")

        valid_chunk_ids = {chunk.get("chunk_id") for chunk in retrieved_chunks if chunk.get("chunk_id")}

        invalid_citations = []
        for citation in citations:
            chunk_id = citation.get("chunk_id")
            page = citation.get("page")

            if not chunk_id or page is None:
                invalid_citations.append(f"Invalid metadata in citation: {citation}")
                continue

            if valid_chunk_ids and chunk_id not in valid_chunk_ids:
                invalid_citations.append(f"Chunk ID {chunk_id} does not exist in retrieved context.")

        return {
            "valid": len(invalid_citations) == 0,
            "issues": invalid_citations
        }

    # -------------------------------------------------------------------------
    # 5. CORE EVIDENCE ASSESSMENT PIPELINE
    # -------------------------------------------------------------------------
    def assess_evidence(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        citations: Optional[List[Dict[str, Any]]] = None
    ) -> EvidenceAssessment:
        """
        Executes full multi-facet evidence assessment:
            1. Relevance computation (S_rel)
            2. Coverage computation (S_cov)
            3. Cross-document NLI contradiction detection (S_cons)
            4. Sufficiency score combination (S_suff)
            5. Failure taxonomy classification
        """
        logger.info(f"Evidence assessment started for query: '{query}' ({len(retrieved_chunks)} chunks)")

        issues: List[str] = []
        supporting_chunks: List[str] = []

        # Handle empty context
        if not retrieved_chunks:
            logger.info("Evidence assessment: Empty context -> OUT_OF_DOMAIN")
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
                issues=["Empty context: no evidence retrieved."],
                explanation="No relevant documents found matching the query in the knowledge base.",
                raw_metrics={"total_chunks": 0, "total_chars": 0}
            )

        total_length = sum(len(c.get("content", "")) for c in retrieved_chunks)
        supporting_chunks = [c.get("chunk_id", f"chunk_{i}") for i, c in enumerate(retrieved_chunks)]

        # 1. Relevance Score
        s_rel = self.compute_relevance_score(retrieved_chunks)

        # 2. Coverage Score
        s_cov = self.compute_coverage_score(query, retrieved_chunks)

        # 3. Cross-document NLI Contradictions & Consistency Score
        contradiction_pairs, s_cons = self.detect_contradictions(retrieved_chunks)
        conflicting_dicts = [p.to_dict() for p in contradiction_pairs]

        # 4. Overall Sufficiency Formulation
        s_suff = round(self.w_rel * s_rel + self.w_cov * s_cov + self.w_cons * s_cons, 4)

        # Check for citation errors if citations are provided
        if citations:
            try:
                cit_val = self.validate_citations(citations, retrieved_chunks)
                if not cit_val["valid"]:
                    issues.extend(cit_val["issues"])
            except ValueError as e:
                issues.append(str(e))

        # 5. Failure Taxonomy Classification
        failure_mode: str
        can_answer: bool = True
        explanation: str

        if contradiction_pairs:
            failure_mode = "INTER_DOCUMENT_CONFLICT"
            can_answer = False
            pair_explanations = "; ".join(p.explanation for p in contradiction_pairs)
            issues.append(f"Contradictory evidence detected: {pair_explanations}")
            explanation = f"Conflicting information found across retrieved documents: {pair_explanations}"

        elif s_rel < self.min_score_threshold and s_cov < self.min_coverage_threshold:
            failure_mode = "OUT_OF_DOMAIN"
            can_answer = False
            issues.append("Insufficient supporting evidence: low relevance and query coverage.")
            explanation = "The query appears out-of-domain with respect to the ingested documents."

        elif len(retrieved_chunks) < self.min_chunks or total_length < self.min_length:
            failure_mode = "COVERAGE_GAP"
            can_answer = False
            issues.append("Insufficient supporting evidence: context too short.")
            explanation = "Retrieved context length is below minimum required threshold."

        elif s_cov < self.min_coverage_threshold or s_suff < self.sufficiency_threshold:
            failure_mode = "COVERAGE_GAP"
            can_answer = False
            issues.append("Insufficient supporting evidence: query terms partially unrepresented.")
            explanation = f"Evidence coverage ({s_cov:.2f}) or sufficiency ({s_suff:.2f}) is below threshold."

        else:
            # Check for lexical/dense divergence
            sources = {c.get("source") for c in retrieved_chunks if c.get("source")}
            if len(sources) == 1 and s_cov < 0.5:
                failure_mode = "LEXICAL_DENSE_DIVERGENCE"
                explanation = "Single retrieval modality dominated with moderate coverage divergence."
            else:
                failure_mode = "SUFFICIENT"
                explanation = f"Evidence is sufficient and consistent (score: {s_suff:.2f})."

        sufficient = (failure_mode == "SUFFICIENT")

        raw_metrics = {
            "query": query,
            "total_chunks": len(retrieved_chunks),
            "total_length": total_length,
            "s_rel": s_rel,
            "s_cov": s_cov,
            "s_cons": s_cons,
            "s_suff": s_suff,
            "thresholds": {
                "min_score": self.min_score_threshold,
                "min_coverage": self.min_coverage_threshold,
                "contradiction_threshold": self.contradiction_threshold,
                "sufficiency_threshold": self.sufficiency_threshold
            }
        }

        logger.info(
            f"Evidence assessment completed: mode={failure_mode}, sufficient={sufficient}, "
            f"S_suff={s_suff:.3f}, S_rel={s_rel:.3f}, S_cov={s_cov:.3f}, S_cons={s_cons:.3f}"
        )

        return EvidenceAssessment(
            sufficient=sufficient,
            can_answer=can_answer,
            overall_score=s_suff,
            failure_mode=failure_mode,
            relevance_score=s_rel,
            coverage_score=s_cov,
            consistency_score=s_cons,
            supporting_chunks=supporting_chunks,
            conflicting_pairs=conflicting_dicts,
            issues=issues,
            explanation=explanation,
            raw_metrics=raw_metrics
        )

    # -------------------------------------------------------------------------
    # Backward-Compatible Helper Methods for Existing Callers & Tests
    # -------------------------------------------------------------------------
    def check_context_sufficiency(self, retrieved_chunks: List[Dict[str, Any]], query: str = "") -> Dict[str, Any]:
        """Backward-compatible sufficiency wrapper."""
        if not retrieved_chunks:
            logger.error("Verification failed: Empty context")
            raise ValueError("Empty context provided for verification.")

        assessment = self.assess_evidence(query=query or "context verification", retrieved_chunks=retrieved_chunks)
        return {
            "sufficient": assessment.sufficient,
            "score": assessment.overall_score,
            "reason": assessment.explanation
        }

    def verify_response(
        self,
        retrieved_chunks: List[Dict[str, Any]],
        citations: Optional[List[Dict[str, Any]]] = None,
        query: str = ""
    ) -> Dict[str, Any]:
        """
        Backward-compatible interface for existing verification callers.
        Returns a dictionary structure containing the formal assessment.
        """
        logger.info("Verification started")
        assessment = self.assess_evidence(
            query=query or "query",
            retrieved_chunks=retrieved_chunks,
            citations=citations
        )
        logger.info("Verification completed")
        return assessment.to_dict()

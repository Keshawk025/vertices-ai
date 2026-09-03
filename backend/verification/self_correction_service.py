import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Set, Callable

from verification.verification_service import (
    EvidenceAssessment,
    _extract_content_tokens,
    _tokenize,
    STOPWORDS
)

logger = logging.getLogger(__name__)


@dataclass
class ReformulationResult:
    """Structured output from DiagnosticQueryReformulator."""
    reformulated_query: str
    strategy: str  # "concept_expansion", "modality_bridging", "conflict_disambiguation", "canonical_generalization", "multihop_decomposition"
    failure_mode: str
    missing_concepts: List[str]
    subqueries: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reformulated_query": self.reformulated_query,
            "strategy": self.strategy,
            "failure_mode": self.failure_mode,
            "missing_concepts": self.missing_concepts,
            "subqueries": self.subqueries,
            "metadata": self.metadata
        }


class DiagnosticQueryReformulator:
    """
    Research-Grade Diagnostic Query Reformulation Module.
    
    Transforms queries based on the diagnosed retrieval failure mode:
        1. COVERAGE_GAP -> Targeted concept & answer-type expansion
        2. LEXICAL_DENSE_DIVERGENCE -> Modality-bridging reformulation
        3. INTER_DOCUMENT_CONFLICT -> Temporal & disambiguation resolution
        4. OUT_OF_DOMAIN -> Canonical entity generalization
        5. MULTI-HOP -> Compound query decomposition
    """
    def __init__(self, use_llm_reformulation: bool = False, llm_service: Any = None):
        self.use_llm_reformulation = use_llm_reformulation
        self.llm_service = llm_service

    # -------------------------------------------------------------------------
    # Multi-Hop Query Decomposition
    # -------------------------------------------------------------------------
    def decompose_multihop_query(self, query: str) -> List[str]:
        """
        Decomposes compound multi-hop queries into independent subqueries.
        Example: "What year was Apollo founded and who was the first astronaut?"
        -> ["Apollo founded year", "first astronaut Apollo"]
        """
        if not query:
            return []

        # Split on coordinating conjunctions with question-like clauses
        conjunction_patterns = [
            r"\s+and\s+(?=who|what|when|where|which|how|why)\b",
            r"\s+as\s+well\s+as\s+(?=who|what|when|where|which|how|why)\b",
            r"\s+along\s+with\s+(?=who|what|when|where|which|how|why)\b",
            r",\s+and\s+",
            r";\s+"
        ]

        subqueries = [query]
        for pat in conjunction_patterns:
            new_subqueries = []
            for sq in subqueries:
                parts = re.split(pat, sq, flags=re.IGNORECASE)
                new_subqueries.extend([p.strip(" ?.,;") for p in parts if p.strip()])
            subqueries = new_subqueries

        if len(subqueries) <= 1:
            # Check for "both X and Y" structure
            both_match = re.match(r"^.*?\b(both|between)\s+(.+?)\s+and\s+(.+?)(?:\?|$)", query, re.IGNORECASE)
            if both_match:
                prefix_tokens = _extract_content_tokens(query[:both_match.start(2)])
                prefix = " ".join(prefix_tokens)
                subqueries = [f"{prefix} {both_match.group(2)}".strip(), f"{prefix} {both_match.group(3)}".strip()]

        cleaned = [sq for sq in subqueries if len(sq) > 3]
        return cleaned if len(cleaned) > 1 else [query]

    # -------------------------------------------------------------------------
    # Category Expansion Terms
    # -------------------------------------------------------------------------
    def _get_answer_type_expansions(self, query: str) -> List[str]:
        q_lower = query.lower()
        expansions = []

        if re.search(r"\b(when|year|date|founded|established|started|created|launched)\b", q_lower):
            expansions.extend(["founding", "establishment", "date", "year", "timeline", "founded"])
        elif re.search(r"\b(who|ceo|founder|leader|director|president|author|creator)\b", q_lower):
            expansions.extend(["executive", "founder", "leadership", "author", "role", "name"])
        elif re.search(r"\b(how much|how many|percentage|rate|cost|fee|attendance|limit|minimum|maximum|requirement)\b", q_lower):
            expansions.extend(["percentage", "rate", "requirement", "threshold", "policy", "rule", "criteria"])
        elif re.search(r"\b(where|headquarters|location|city|country|based|address)\b", q_lower):
            expansions.extend(["headquarters", "location", "address", "city", "campus", "based"])
        elif re.search(r"\b(how|process|workflow|architecture|mechanism|method|pipeline)\b", q_lower):
            expansions.extend(["pipeline", "architecture", "workflow", "steps", "methodology", "process"])
        elif re.search(r"\b(what is|define|definition|meaning|overview|summary)\b", q_lower):
            expansions.extend(["overview", "specification", "details", "definition", "summary"])

        return expansions

    # -------------------------------------------------------------------------
    # Core Reformulation Orchestration
    # -------------------------------------------------------------------------
    def reformulate(
        self,
        query: str,
        failure_mode: str,
        evidence_assessment: Optional[Any] = None,
        retrieved_chunks: Optional[List[Dict[str, Any]]] = None
    ) -> ReformulationResult:
        """
        Executes mode-specific diagnostic query reformulation.
        """
        logger.info(f"Diagnostic query reformulation started for mode '{failure_mode}': '{query}'")

        query_tokens = _extract_content_tokens(query)
        context_tokens = set()
        if retrieved_chunks:
            combined_context = " ".join(c.get("content", "") for c in retrieved_chunks).lower()
            context_tokens = set(_tokenize(combined_context))

        missing_concepts = list(query_tokens - context_tokens)
        subqueries = self.decompose_multihop_query(query)

        # 1. Strategy: Multi-Hop Decomposition
        if len(subqueries) > 1 and failure_mode in ["COVERAGE_GAP", "LEXICAL_DENSE_DIVERGENCE"]:
            logger.info(f"Multi-hop decomposition applied: {subqueries}")
            combined_reformulation = " ".join(subqueries)
            return ReformulationResult(
                reformulated_query=combined_reformulation,
                strategy="multihop_decomposition",
                failure_mode=failure_mode,
                missing_concepts=missing_concepts,
                subqueries=subqueries,
                metadata={"subqueries_count": len(subqueries)}
            )

        # 2. Strategy: COVERAGE_GAP
        if failure_mode == "COVERAGE_GAP":
            expansions = self._get_answer_type_expansions(query)
            # Add missing tokens and relevant answer-type expansions
            expansion_set = set(missing_concepts).union(expansions)
            expansion_str = " ".join([t for t in expansion_set if t not in query.lower()])

            # Extract core query entities
            clean_q = re.sub(r"[^\w\s]", "", query).strip()
            if expansion_str:
                reformulated = f"{clean_q} {expansion_str}".strip()
            else:
                reformulated = f"{clean_q} detailed information overview".strip()

            return ReformulationResult(
                reformulated_query=reformulated,
                strategy="concept_expansion",
                failure_mode=failure_mode,
                missing_concepts=missing_concepts,
                subqueries=[reformulated],
                metadata={"expansions_added": list(expansion_set)}
            )

        # 3. Strategy: LEXICAL_DENSE_DIVERGENCE
        elif failure_mode == "LEXICAL_DENSE_DIVERGENCE":
            clean_q = re.sub(r"[^\w\s]", "", query).strip()
            # Bridge lexical inverted index with dense semantic concepts
            modality_terms = ["system", "documentation", "details", "specifications", "records"]
            added_terms = [t for t in modality_terms if t not in clean_q.lower()][:2]
            reformulated = f"{clean_q} {' '.join(added_terms)}".strip()

            return ReformulationResult(
                reformulated_query=reformulated,
                strategy="modality_bridging",
                failure_mode=failure_mode,
                missing_concepts=missing_concepts,
                subqueries=[reformulated],
                metadata={"bridging_terms": added_terms}
            )

        # 4. Strategy: INTER_DOCUMENT_CONFLICT
        elif failure_mode == "INTER_DOCUMENT_CONFLICT":
            clean_q = re.sub(r"[^\w\s]", "", query).strip()
            # Search specifically for resolving, latest version, or temporal metadata
            temporal_resolving_terms = "current policy latest updated effective version 2024 2025"
            reformulated = f"{clean_q} {temporal_resolving_terms}".strip()

            return ReformulationResult(
                reformulated_query=reformulated,
                strategy="conflict_disambiguation",
                failure_mode=failure_mode,
                missing_concepts=missing_concepts,
                subqueries=[reformulated],
                metadata={"disambiguation_terms": temporal_resolving_terms.split()}
            )

        # 5. Strategy: OUT_OF_DOMAIN
        elif failure_mode == "OUT_OF_DOMAIN":
            # Canonical generalization: strip noise and isolate core entities
            clean_tokens = [t for t in _tokenize(query) if t not in STOPWORDS]
            if clean_tokens:
                reformulated = " ".join(clean_tokens)
            else:
                reformulated = query.strip()

            return ReformulationResult(
                reformulated_query=reformulated,
                strategy="canonical_generalization",
                failure_mode=failure_mode,
                missing_concepts=missing_concepts,
                subqueries=[reformulated],
                metadata={"canonical_tokens": clean_tokens}
            )

        # Default fallback
        clean_q = re.sub(r"[^\w\s]", "", query).strip()
        reformulated = f"{clean_q} detailed information".strip()
        return ReformulationResult(
            reformulated_query=reformulated,
            strategy="default_fallback",
            failure_mode=failure_mode,
            missing_concepts=missing_concepts,
            subqueries=[reformulated],
            metadata={}
        )


class SelfCorrectionService:
    """
    Research-Grade Diagnostic Self-Correction & Corrective Retrieval Engine for Veritas AI.
    
    Coordinates the feedback loop:
        DETECT -> DIAGNOSE -> REFORMULATE -> RETRIEVE AGAIN -> RE-ASSESS -> STOP / CLARIFY / PASS
    """
    def __init__(
        self,
        max_retries: int = 2,
        min_score_delta: float = 0.05,
        reformulator: Optional[DiagnosticQueryReformulator] = None
    ):
        self.max_retries = max_retries
        self.min_score_delta = min_score_delta
        self.reformulator = reformulator or DiagnosticQueryReformulator()

    # -------------------------------------------------------------------------
    # Decision Action Logic (Backward-Compatible & Extended)
    # -------------------------------------------------------------------------
    def decide_action(
        self,
        verification_result: Dict[str, Any],
        query: str,
        retry_count: int = 0,
        initial_score: Optional[float] = None,
        current_score: Optional[float] = None,
        retrieved_chunks: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Determines corrective action based on evidence assessment and retry state.
        Returns action dictionary:
            - "action": "PASS" | "RETRY" | "CLARIFY" | "STOP"
            - "new_query": str (when action == RETRY)
            - "strategy": str
            - "message": str (when action == STOP or CLARIFY)
            - "metadata": dict
        """
        logger.info(f"Self-correction decision started (retry_count={retry_count}/{self.max_retries})")

        # 1. Check if verified
        if verification_result.get("verified", False) or verification_result.get("failure_mode") == "SUFFICIENT":
            logger.info("Decision: PASS (Verification passed)")
            return {
                "action": "PASS",
                "message": "Verification passed.",
                "new_query": query,
                "strategy": "none",
                "metadata": {"retry_count": retry_count}
            }

        failure_mode = verification_result.get("failure_mode", "COVERAGE_GAP")
        issues = verification_result.get("issues", [])
        combined_issues = " ".join(issues).lower()

        # 2. Maximum Retries Enforced
        if retry_count >= self.max_retries:
            logger.info("Decision: STOP (Max retries reached)")
            if failure_mode == "INTER_DOCUMENT_CONFLICT" or "contradict" in combined_issues or "conflict" in combined_issues:
                return {
                    "action": "CLARIFY",
                    "message": self.ask_clarifying_question(query, issues, verification_result),
                    "strategy": "unresolved_conflict_clarification",
                    "metadata": {"retry_count": retry_count, "failure_mode": failure_mode}
                }
            return {
                "action": "STOP",
                "message": "I could not find sufficient information in the available documentation.",
                "strategy": "max_retries_exceeded",
                "metadata": {"retry_count": retry_count, "failure_mode": failure_mode}
            }

        # 3. Score-Delta Improvement Stopping Criterion
        if initial_score is not None and current_score is not None and retry_count >= 1:
            score_delta = current_score - initial_score
            if score_delta < self.min_score_delta and failure_mode not in ["INTER_DOCUMENT_CONFLICT"]:
                logger.info(f"Decision: STOP (Insufficient improvement: delta={score_delta:.3f} < {self.min_score_delta})")
                return {
                    "action": "STOP",
                    "message": "I could not find sufficient information in the available documentation.",
                    "strategy": "insufficient_improvement_stopping",
                    "metadata": {"score_delta": score_delta, "retry_count": retry_count}
                }

        # 4. Out-of-Domain Terminal Check (Only 1 retry permitted for out-of-domain)
        if failure_mode == "OUT_OF_DOMAIN" and retry_count >= 1:
            logger.info("Decision: STOP (Persistent out-of-domain query)")
            return {
                "action": "STOP",
                "message": "I could not find sufficient information in the available documentation.",
                "strategy": "out_of_domain_terminal",
                "metadata": {"retry_count": retry_count, "failure_mode": failure_mode}
            }

        # 5. Diagnostic Query Reformulation for RETRY
        ref_res = self.reformulator.reformulate(
            query=query,
            failure_mode=failure_mode,
            evidence_assessment=verification_result,
            retrieved_chunks=retrieved_chunks
        )

        logger.info(f"Decision: RETRY via strategy '{ref_res.strategy}' -> '{ref_res.reformulated_query}'")
        return {
            "action": "RETRY",
            "new_query": ref_res.reformulated_query,
            "strategy": ref_res.strategy,
            "missing_concepts": ref_res.missing_concepts,
            "subqueries": ref_res.subqueries,
            "metadata": ref_res.metadata
        }

    # -------------------------------------------------------------------------
    # Clarification Generation with Attribution Preservation
    # -------------------------------------------------------------------------
    def ask_clarifying_question(
        self,
        query: str,
        issues: List[str] = None,
        verification_result: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Constructs a transparent, citation-aware clarification message
        preserving conflicting sources without hallucinating a single truth.
        """
        conflicts = []
        if verification_result:
            conflicts = verification_result.get("conflicting_pairs", [])

        if conflicts and isinstance(conflicts, list):
            pair = conflicts[0]
            if isinstance(pair, dict):
                c_a = pair.get("chunk_a", {})
                c_b = pair.get("chunk_b", {})
                doc_a = c_a.get("filename") or c_a.get("document_id") or "Source A"
                doc_b = c_b.get("filename") or c_b.get("document_id") or "Source B"
                page_a = c_a.get("page", 1)
                page_b = c_b.get("page", 1)
                text_a = c_a.get("content", "").strip()
                text_b = c_b.get("content", "").strip()

                return (
                    f"Conflicting information was detected across your documents regarding this question:\n\n"
                    f"- **[{doc_a}, Page {page_a}]**: \"{text_a}\"\n"
                    f"- **[{doc_b}, Page {page_b}]**: \"{text_b}\"\n\n"
                    f"Please clarify which version or policy you would like to reference."
                )

        return "Could you clarify your request with more specific details or document references?"

    # -------------------------------------------------------------------------
    # Backward-Compatible Query Rewrite Wrapper
    # -------------------------------------------------------------------------
    def rewrite_query(self, query: str) -> str:
        """Backward-compatible query rewrite wrapper."""
        logger.info("Query rewritten")
        res = self.reformulator.reformulate(query=query, failure_mode="COVERAGE_GAP")
        return res.reformulated_query

    def retry_retrieval(
        self,
        original_query: str,
        verification_result: Dict[str, Any],
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """Backward-compatible retry_retrieval wrapper."""
        return self.decide_action(verification_result, original_query, retry_count)

    # -------------------------------------------------------------------------
    # End-to-End Corrective Retrieval Pipeline Execution
    # -------------------------------------------------------------------------
    def execute_corrective_loop(
        self,
        query: str,
        retrieve_fn: Callable[[str], List[Dict[str, Any]]],
        assess_fn: Callable[[str, List[Dict[str, Any]]], EvidenceAssessment],
        synthesize_fn: Optional[Callable[[str, List[Dict[str, Any]]], str]] = None
    ) -> Dict[str, Any]:
        """
        Executes full evidence-guided self-correction loop:
            Iteration 0: Initial retrieval & assessment
            Iteration 1..max_retries: Diagnostic reformulation -> Corrective retrieval -> Re-assessment
            Final decision: PASS / CLARIFY / STOP
        """
        trace: List[Dict[str, Any]] = []
        current_query = query
        retry_count = 0
        initial_score: Optional[float] = None
        best_chunks: List[Dict[str, Any]] = []
        final_assessment: Optional[EvidenceAssessment] = None

        logger.info(f"Initiating corrective RAG loop for query: '{query}'")

        while retry_count <= self.max_retries:
            # 1. Retrieve Chunks
            chunks = retrieve_fn(current_query)

            # 2. Assess Evidence
            assessment = assess_fn(current_query, chunks)
            final_assessment = assessment
            current_score = assessment.overall_score

            if initial_score is None:
                initial_score = current_score

            score_delta = round(current_score - initial_score, 4)

            # Record iteration trace
            trace_entry = {
                "iteration": retry_count,
                "query": current_query,
                "action": "INITIAL_RETRIEVAL" if retry_count == 0 else "CORRECTIVE_RETRIEVAL",
                "failure_mode": assessment.failure_mode,
                "evidence_score": round(current_score, 4),
                "score_delta": score_delta,
                "retrieval_count": len(chunks),
                "sufficient": assessment.sufficient
            }
            trace.append(trace_entry)

            # Update best chunks if score improved or chunks are valid
            if chunks and (not best_chunks or current_score >= (trace[0]["evidence_score"] if trace else 0.0)):
                best_chunks = chunks

            # 3. If Evidence is Sufficient -> PASS
            if assessment.sufficient and assessment.can_answer:
                logger.info(f"Corrective loop SUFFICIENT at iteration {retry_count}. Decision: PASS")
                trace.append({
                    "iteration": retry_count,
                    "action": "PASS",
                    "reason": "Evidence is sufficient and consistent."
                })

                answer = "Sufficient information found."
                if synthesize_fn and best_chunks:
                    answer = synthesize_fn(query, best_chunks)

                citations = [{"page": c.get("page", 1), "chunk_id": c.get("chunk_id")} for c in best_chunks]
                return {
                    "final_decision": "PASS",
                    "answer": answer,
                    "citations": citations,
                    "final_assessment": assessment.to_dict(),
                    "iterations_count": retry_count + 1,
                    "trace": trace
                }

            # 4. Decide Next Action (RETRY / CLARIFY / STOP)
            action_result = self.decide_action(
                verification_result=assessment.to_dict(),
                query=current_query,
                retry_count=retry_count,
                initial_score=initial_score,
                current_score=current_score,
                retrieved_chunks=chunks
            )

            action = action_result["action"]

            if action == "CLARIFY":
                logger.info("Corrective loop terminated with CLARIFY")
                trace.append({
                    "iteration": retry_count,
                    "action": "CLARIFY",
                    "reason": action_result.get("strategy", "conflict_clarification")
                })
                return {
                    "final_decision": "CLARIFY",
                    "answer": action_result["message"],
                    "citations": [{"page": c.get("page", 1), "chunk_id": c.get("chunk_id")} for c in chunks],
                    "final_assessment": assessment.to_dict(),
                    "iterations_count": retry_count + 1,
                    "trace": trace
                }

            elif action == "STOP":
                logger.info("Corrective loop terminated with STOP")
                trace.append({
                    "iteration": retry_count,
                    "action": "STOP",
                    "reason": action_result.get("strategy", "stop_criteria_met")
                })
                return {
                    "final_decision": "STOP",
                    "answer": action_result["message"],
                    "citations": [],
                    "final_assessment": assessment.to_dict(),
                    "iterations_count": retry_count + 1,
                    "trace": trace
                }

            elif action == "RETRY":
                current_query = action_result["new_query"]
                trace[-1]["reformulation"] = {
                    "strategy": action_result.get("strategy"),
                    "new_query": current_query,
                    "missing_concepts": action_result.get("missing_concepts", [])
                }
                retry_count += 1

        # Fallback termination if while loop exits
        trace.append({"iteration": retry_count, "action": "STOP", "reason": "MAX_RETRIES"})
        return {
            "final_decision": "STOP",
            "answer": "I could not find sufficient information in the available documentation.",
            "citations": [],
            "final_assessment": final_assessment.to_dict() if final_assessment else {},
            "iterations_count": retry_count,
            "trace": trace
        }

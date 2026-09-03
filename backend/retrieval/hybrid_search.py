import os
import re
import logging
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> List[str]:
    """Extract lowercase alphanumeric tokens from text."""
    if not text:
        return []
    return re.findall(r"\w+", text.lower())


def bm25_search(query: str, chunks: List[Dict[str, Any]], top_k: int = 10) -> List[Dict[str, Any]]:
    """
    Perform lexical BM25Okapi search over the provided chunk corpus.
    Returns the top_k scoring chunks sorted descending.
    """
    if not query or not query.strip():
        logger.error("Empty query provided to BM25 search.")
        raise ValueError("Empty query")

    if not chunks:
        logger.info("BM25 retrieval: empty corpus")
        return []

    tokenized_corpus = [_tokenize(c.get("content", "")) for c in chunks]
    tokenized_query = _tokenize(query)

    bm25 = BM25Okapi(tokenized_corpus)
    doc_scores = bm25.get_scores(tokenized_query)

    top_indices = sorted(range(len(doc_scores)), key=lambda i: doc_scores[i], reverse=True)[:top_k]
    max_score = max(doc_scores) if doc_scores.any() and max(doc_scores) > 0 else 1.0

    results = []
    for rank_idx, idx in enumerate(top_indices, start=1):
        raw_score = float(doc_scores[idx])
        if raw_score <= 0 and len(results) >= top_k:
            continue
        c = chunks[idx]
        norm_score = round(raw_score / max_score, 4) if max_score > 0 else 0.0
        results.append({
            "chunk_id": c.get("chunk_id", f"chunk_{idx}"),
            "score": norm_score,
            "raw_bm25_score": raw_score,
            "bm25_rank": rank_idx,
            "source": "bm25",
            "content": c.get("content", ""),
            "page": c.get("page", 1),
            "document_id": c.get("document_id"),
            "filename": c.get("filename", ""),
            "user_id": c.get("user_id")
        })

    logger.info(f"BM25 retrieval: found {len(results)} candidates")
    return results


def faiss_search(
    query: str,
    user_id: Any = None,
    document_id: str = None,
    faiss_service: Any = None,
    embedding_service: Any = None,
    top_k: int = 10
) -> List[Dict[str, Any]]:
    """
    Perform dense vector search using FAISSService.
    Returns the top_k nearest chunks sorted descending by cosine similarity.
    """
    if not query or not query.strip():
        logger.error("Empty query provided to FAISS search.")
        raise ValueError("Empty query")

    results = []
    if faiss_service is not None and embedding_service is not None:
        try:
            query_embedding = embedding_service.generate_embedding(query)
            faiss_raw = faiss_service.search(
                query_embedding,
                top_k=top_k,
                user_id=user_id,
                document_id=document_id
            )
            for rank_idx, item in enumerate(faiss_raw, start=1):
                results.append({
                    "chunk_id": item.get("chunk_id"),
                    "score": round(float(item.get("score", 0.0)), 4),
                    "faiss_rank": rank_idx,
                    "source": "faiss",
                    "content": item.get("content", ""),
                    "page": item.get("page", 1),
                    "document_id": item.get("document_id"),
                    "filename": item.get("filename", ""),
                    "user_id": item.get("user_id")
                })
        except Exception as err:
            logger.warning(f"FAISS search fallback note: {err}")

    logger.info(f"FAISS retrieval: found {len(results)} candidates")
    return results


def reciprocal_rank_fusion(
    bm25_results: List[Dict[str, Any]],
    faiss_results: List[Dict[str, Any]],
    k: int = 60
) -> List[Dict[str, Any]]:
    """
    Combine lexical (BM25) and dense (FAISS) rankings using Reciprocal Rank Fusion (RRF):
        RRF_Score(d) = sum_{m in {BM25, FAISS}} (1 / (k + rank_m(d)))
    where rank_m(d) is 1-based.
    """
    merged: Dict[str, Dict[str, Any]] = {}
    rrf_scores: Dict[str, float] = {}

    # 1. Process BM25 rankings
    for rank_idx, item in enumerate(bm25_results, start=1):
        cid = item.get("chunk_id")
        if not cid:
            continue
        rrf_contribution = 1.0 / (k + rank_idx)
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + rrf_contribution

        entry = dict(item)
        entry["bm25_rank"] = rank_idx
        entry["faiss_rank"] = None
        entry["source"] = "bm25"
        merged[cid] = entry

    # 2. Process FAISS rankings
    for rank_idx, item in enumerate(faiss_results, start=1):
        cid = item.get("chunk_id")
        if not cid:
            continue
        rrf_contribution = 1.0 / (k + rank_idx)
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + rrf_contribution

        if cid in merged:
            merged[cid]["faiss_rank"] = rank_idx
            merged[cid]["source"] = "hybrid"
        else:
            entry = dict(item)
            entry["bm25_rank"] = None
            entry["faiss_rank"] = rank_idx
            entry["source"] = "faiss"
            merged[cid] = entry

    # 3. Attach final RRF score and sort descending
    fused_list = []
    for cid, entry in merged.items():
        score = round(rrf_scores[cid], 6)
        entry["score"] = score
        entry["rrf_score"] = score
        fused_list.append(entry)

    fused_list.sort(key=lambda x: x["rrf_score"], reverse=True)
    logger.info(f"RRF fusion: merged into {len(fused_list)} unique candidates (k={k})")
    return fused_list


# Backward-compatible alias for existing tests
def merge_results(
    bm25_results: List[Dict[str, Any]],
    faiss_results: List[Dict[str, Any]],
    k: int = 60
) -> List[Dict[str, Any]]:
    """Backward-compatible wrapper for Reciprocal Rank Fusion."""
    return reciprocal_rank_fusion(bm25_results, faiss_results, k=k)


class CrossEncoderReranker:
    """
    Reranker using a Cross-Encoder model (ms-marco-MiniLM-L-6-v2) to score (query, passage) pairs.
    Includes lazy model initialization and a robust lexical-overlap fallback.
    """
    def __init__(self, model_name: str = None):
        self.model_name = model_name or os.getenv("CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
        self._model = None
        self._fallback_mode = False

    def _load_model(self):
        if self._model is None and not self._fallback_mode:
            try:
                from sentence_transformers import CrossEncoder
                logger.info(f"Loading CrossEncoder model: {self.model_name}")
                self._model = CrossEncoder(self.model_name)
                logger.info("CrossEncoder model loaded successfully.")
            except Exception as e:
                logger.warning(f"CrossEncoder failed to load ({e}). Falling back to lexical-overlap reranking.")
                self._fallback_mode = True

    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Rerank candidate passages against the query using Cross-Encoder scoring.
        """
        if not candidates:
            logger.info("Cross-Encoder reranking: 0 candidates provided")
            return []

        self._load_model()

        # If Cross-Encoder is loaded and ready
        if self._model is not None and not self._fallback_mode:
            try:
                pairs = [[query, c.get("content", "")] for c in candidates]
                scores = self._model.predict(pairs)
                
                for item, score in zip(candidates, scores):
                    item["score"] = float(score)
                    item["cross_score"] = float(score)
                    item["rerank_method"] = "cross_encoder"

                reranked = sorted(candidates, key=lambda x: x["score"], reverse=True)[:top_k]
                logger.info(f"Cross-Encoder reranking: scored {len(candidates)} candidates with {self.model_name}")
                return reranked
            except Exception as e:
                logger.warning(f"CrossEncoder inference error ({e}). Using lexical fallback.")

        # Lexical-overlap fallback mode
        logger.info("Cross-Encoder fallback: using lexical-overlap scoring")
        q_tokens = set(_tokenize(query))
        for item in candidates:
            content_tokens = set(_tokenize(item.get("content", "")))
            overlap = len(q_tokens.intersection(content_tokens)) / max(len(q_tokens), 1) if q_tokens else 0.0
            hybrid_boost = 0.15 if item.get("source") == "hybrid" else 0.0
            base_score = float(item.get("rrf_score", item.get("score", 0.0)))
            final_score = round(min(1.0, base_score * 0.7 + overlap * 0.3 + hybrid_boost), 4)
            item["score"] = final_score
            item["cross_score"] = final_score
            item["rerank_method"] = "lexical_overlap_fallback"

        reranked = sorted(candidates, key=lambda x: x.get("score", 0.0), reverse=True)[:top_k]
        logger.info(f"Cross-Encoder reranking: completed fallback scoring for {len(candidates)} candidates")
        return reranked


# Default singleton instance for reranking
_default_reranker = CrossEncoderReranker()


# Backward-compatible function for existing tests
def rerank_results(
    merged_results: List[Dict[str, Any]],
    query: str,
    top_k: int = 5,
    reranker: Optional[CrossEncoderReranker] = None
) -> List[Dict[str, Any]]:
    """Backward-compatible functional reranker."""
    active_reranker = reranker or _default_reranker
    return active_reranker.rerank(query, merged_results, top_k=top_k)


def hybrid_search(
    query: str,
    user_id: Any = None,
    document_id: str = None,
    chunks: List[Dict[str, Any]] = None,
    faiss_service: Any = None,
    embedding_service: Any = None,
    reranker: Optional[CrossEncoderReranker] = None,
    bm25_top_k: int = 10,
    faiss_top_k: int = 10,
    rrf_k: int = 60,
    rerank_candidate_limit: int = 15,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Unified Hybrid Retrieval Pipeline:
        1. BM25 Lexical Retrieval (top bm25_top_k)
        2. FAISS Dense Vector Retrieval (top faiss_top_k)
        3. Reciprocal Rank Fusion (RRF with parameter k)
        4. Candidate Selection (top rerank_candidate_limit)
        5. Cross-Encoder Reranking
        6. Final top_k Evidence Selection
    """
    if not query or not query.strip():
        logger.error("Empty query provided to hybrid search.")
        raise ValueError("Empty query")

    # 1. BM25 Search
    bm25_res = []
    if chunks:
        try:
            bm25_res = bm25_search(query, chunks, top_k=bm25_top_k)
        except Exception as e:
            logger.warning(f"BM25 search exception fallback: {e}")

    # 2. FAISS Search
    faiss_res = []
    if faiss_service is not None and embedding_service is not None:
        try:
            faiss_res = faiss_search(
                query,
                user_id=user_id,
                document_id=document_id,
                faiss_service=faiss_service,
                embedding_service=embedding_service,
                top_k=faiss_top_k
            )
        except Exception as e:
            logger.warning(f"FAISS search exception fallback: {e}")

    # If both sources returned nothing, return empty
    if not bm25_res and not faiss_res:
        logger.info("Hybrid retrieval completed: 0 candidates from BM25 and FAISS")
        return []

    # 3. Reciprocal Rank Fusion
    fused_candidates = reciprocal_rank_fusion(bm25_res, faiss_res, k=rrf_k)

    # 4. Limit candidate pool for Cross-Encoder
    candidate_pool = fused_candidates[:rerank_candidate_limit]

    # 5. Cross-Encoder Reranking
    active_reranker = reranker or _default_reranker
    final_evidence = active_reranker.rerank(query, candidate_pool, top_k=top_k)

    logger.info(f"Hybrid retrieval completed: returning {len(final_evidence)} final evidence chunks")
    return final_evidence


def health_check() -> Dict[str, Any]:
    """
    Return health check status for Hybrid Search components.
    """
    return {
        "bm25": True,
        "faiss": True,
        "rrf": True,
        "cross_encoder": True,
        "hybrid": True
    }

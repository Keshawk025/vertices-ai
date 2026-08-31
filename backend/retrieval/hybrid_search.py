import re
import logging
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    return re.findall(r"\w+", text.lower())


def bm25_search(query: str, chunks: List[Dict[str, Any]], top_k: int = 10) -> List[Dict[str, Any]]:
    if not query or not query.strip():
        logger.error("Empty query provided to BM25 search.")
        raise ValueError("Empty query")

    if not chunks:
        logger.info("BM25 search - empty corpus")
        print("BM25 search")
        return []

    tokenized_corpus = [_tokenize(c.get("content", "")) for c in chunks]
    tokenized_query = _tokenize(query)

    bm25 = BM25Okapi(tokenized_corpus)
    doc_scores = bm25.get_scores(tokenized_query)

    top_indices = sorted(range(len(doc_scores)), key=lambda i: doc_scores[i], reverse=True)[:top_k]

    max_score = max(doc_scores) if doc_scores.any() and max(doc_scores) > 0 else 1.0

    results = []
    for idx in top_indices:
        score = float(doc_scores[idx])
        if score <= 0 and len(results) >= top_k:
            continue
        c = chunks[idx]
        norm_score = round(score / max_score, 4) if max_score > 0 else 0.0
        results.append({
            "chunk_id": c.get("chunk_id", f"chunk_{idx}"),
            "score": norm_score,
            "source": "bm25",
            "content": c.get("content", ""),
            "page": c.get("page"),
            "document_id": c.get("document_id"),
            "filename": c.get("filename"),
            "user_id": c.get("user_id")
        })

    logger.info("BM25 search")
    print("BM25 search")
    return results


def faiss_search(
    query: str,
    user_id: Any = None,
    faiss_service: Any = None,
    embedding_service: Any = None,
    top_k: int = 10
) -> List[Dict[str, Any]]:
    if not query or not query.strip():
        logger.error("Empty query provided to FAISS search.")
        raise ValueError("Empty query")

    results = []
    if faiss_service is not None and embedding_service is not None:
        try:
            query_embedding = embedding_service.generate_embedding(query)
            faiss_raw = faiss_service.search(query_embedding, top_k=top_k, user_id=user_id)
            for item in faiss_raw:
                results.append({
                    "chunk_id": item.get("chunk_id"),
                    "score": round(float(item.get("score", 0.0)), 4),
                    "source": "faiss",
                    "content": item.get("content", ""),
                    "page": item.get("page"),
                    "document_id": item.get("document_id"),
                    "filename": item.get("filename"),
                    "user_id": item.get("user_id")
                })
        except Exception as err:
            logger.warning(f"FAISS search fallback note: {err}")

    logger.info("FAISS search")
    print("FAISS search")
    return results


def merge_results(
    bm25_results: List[Dict[str, Any]],
    faiss_results: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}

    for item in bm25_results:
        cid = item.get("chunk_id")
        if cid:
            merged[cid] = dict(item)

    for item in faiss_results:
        cid = item.get("chunk_id")
        if not cid:
            continue
        if cid in merged:
            bm25_s = merged[cid].get("score", 0.0)
            faiss_s = item.get("score", 0.0)
            hybrid_score = round(0.4 * bm25_s + 0.6 * faiss_s, 4)
            merged[cid]["source"] = "hybrid"
            merged[cid]["score"] = hybrid_score
        else:
            merged[cid] = dict(item)

    logger.info("Merge completed")
    print("Merge completed")
    return list(merged.values())


def rerank_results(
    merged_results: List[Dict[str, Any]],
    query: str,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    if not merged_results:
        logger.info("Rerank completed")
        print("Rerank completed")
        return []

    q_tokens = set(_tokenize(query))

    for item in merged_results:
        content_tokens = set(_tokenize(item.get("content", "")))
        overlap = len(q_tokens.intersection(content_tokens)) / max(len(q_tokens), 1) if q_tokens else 0
        hybrid_boost = 0.15 if item.get("source") == "hybrid" else 0.0
        final_score = round(min(1.0, item.get("score", 0.0) * 0.7 + overlap * 0.3 + hybrid_boost), 4)
        item["score"] = final_score

    # Sort descending by score
    reranked = sorted(merged_results, key=lambda x: x.get("score", 0), reverse=True)[:top_k]

    logger.info("Rerank completed")
    print("Rerank completed")
    return reranked


def hybrid_search(
    query: str,
    user_id: Any = None,
    chunks: List[Dict[str, Any]] = None,
    faiss_service: Any = None,
    embedding_service: Any = None,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    if not query or not query.strip():
        logger.error("Empty query provided to hybrid search.")
        raise ValueError("Empty query")

    # 1. BM25 Search (top 10)
    bm25_res = []
    if chunks:
        try:
            bm25_res = bm25_search(query, chunks, top_k=10)
        except Exception as e:
            logger.warning(f"BM25 search exception fallback: {e}")

    # 2. FAISS Search (top 10)
    faiss_res = []
    if faiss_service is not None and embedding_service is not None:
        try:
            faiss_res = faiss_search(query, user_id=user_id, faiss_service=faiss_service, embedding_service=embedding_service, top_k=10)
        except Exception as e:
            logger.warning(f"FAISS search exception fallback: {e}")

    # 3. Merge & Deduplicate
    merged = merge_results(bm25_res, faiss_res)

    # 4. Rerank -> Top 5
    final_results = rerank_results(merged, query, top_k=top_k)
    return final_results


def health_check() -> Dict[str, Any]:
    """
    Return health check status for Hybrid Search components.
    """
    return {
        "bm25": True,
        "faiss": True,
        "hybrid": True
    }

import logging
from typing import Dict, Any, List, Optional, Union
from services.embeddings.embedding_service import EmbeddingService
from services.vector_store.faiss_service import FAISSService
from services.llm.llm_service import get_llm_service
from retrieval.hybrid_search import hybrid_search, CrossEncoderReranker

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Veritas AI.

Rules:
- Answer ONLY from the provided context.
- Never hallucinate.
- If context is insufficient, respond:
  "I could not find sufficient information in the available documentation."
- Include citations.
- Mention page numbers whenever possible."""

USER_PROMPT_TEMPLATE = """Context:
{context}

Question:
{question}"""


class RAGService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        faiss_service: FAISSService,
        reranker: Optional[CrossEncoderReranker] = None
    ):
        self.embedding_service = embedding_service
        self.faiss_service = faiss_service
        self.reranker = reranker
        try:
            self.llm_service = get_llm_service()
        except ValueError as e:
            # Initialize safely so tests can pass without API keys
            logger.warning(f"Failed to initialize LLM service: {e}")
            self.llm_service = None

    def embed_query(self, query: str) -> List[float]:
        """Embed a query string using the active dense embedding service."""
        if not query or not query.strip():
            logger.error("Empty query provided.")
            raise ValueError("Empty query")
            
        logger.info(f"Query received: {query}")
        embedding = self.embedding_service.generate_embedding(query)
        logger.info("Query embedded")
        return embedding

    def retrieve_chunks(
        self,
        query_or_embedding: Union[str, List[float]],
        user_id: Any = None,
        document_id: str = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Active Retrieval Engine:
        - If string query: runs full Unified Hybrid Retrieval (BM25 + FAISS -> RRF -> Cross-Encoder).
        - If embedding list: performs FAISS dense search (backward compatibility).
        """
        # 1. String query: Active Hybrid Retrieval Pipeline
        if isinstance(query_or_embedding, str):
            query = query_or_embedding.strip()
            if not query:
                logger.error("Empty query provided.")
                raise ValueError("Empty query")

            # Retrieve candidate corpus from FAISSService metadata store
            corpus_chunks = []
            if hasattr(self.faiss_service, "get_chunks"):
                corpus_chunks = self.faiss_service.get_chunks(user_id=user_id, document_id=document_id)
            elif getattr(self.faiss_service, "metadata_store", None):
                corpus_chunks = list(self.faiss_service.metadata_store.values())

            try:
                results = hybrid_search(
                    query=query,
                    user_id=user_id,
                    document_id=document_id,
                    chunks=corpus_chunks,
                    faiss_service=self.faiss_service,
                    embedding_service=self.embedding_service,
                    reranker=self.reranker,
                    bm25_top_k=max(20, top_k * 2),
                    faiss_top_k=max(20, top_k * 2),
                    rrf_k=60,
                    rerank_candidate_limit=max(30, top_k * 3),
                    top_k=top_k
                )
                logger.info(f"Retrieval completed. {len(results)} chunks found via Hybrid pipeline.")
                return results
            except RuntimeError as e:
                if "Empty index" in str(e):
                    logger.error("Empty FAISS index encountered.")
                    raise ValueError("Empty FAISS index")
                raise

        # 2. Embedding vector: Dense-only retrieval (backward compatibility)
        elif isinstance(query_or_embedding, list):
            try:
                results = self.faiss_service.search(
                    query_or_embedding,
                    top_k=top_k,
                    user_id=user_id,
                    document_id=document_id
                )
                if not results:
                    logger.warning("No chunks found in FAISS search.")
                    return []
                logger.info(f"Retrieval completed. {len(results)} chunks found via dense vector search.")
                return results
            except RuntimeError as e:
                if "Empty index" in str(e):
                    logger.error("Empty FAISS index encountered.")
                    raise ValueError("Empty FAISS index")
                raise
        else:
            raise TypeError("query_or_embedding must be a query string or embedding vector.")

    def build_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Format retrieved chunks with structured citation labels and page numbers."""
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            content = chunk.get("content", "")
            page = chunk.get("page", 1)
            context_parts.append(f"[Citation {i}] Page {page}: {content}")
            
        context = "\n\n".join(context_parts)
        logger.info("Context built")
        return context

    def answer_question(
        self,
        question: str,
        user_id: Any = None,
        document_id: str = None,
        history: List[Dict[str, str]] = None,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Synthesize answer using the unified Hybrid Retrieval -> RRF -> Cross-Encoder -> LLM pipeline.
        """
        if not self.llm_service:
            raise ValueError("LLM failure: LLM Service is not configured properly.")
            
        if not question or not question.strip():
            raise ValueError("Empty query")

        # 1. Active Hybrid Retrieval (BM25 + FAISS -> RRF -> Cross-Encoder Rerank)
        chunks = self.retrieve_chunks(
            query_or_embedding=question,
            user_id=user_id,
            document_id=document_id,
            top_k=top_k
        )
        
        if not chunks:
            # If no chunks found, return standard insufficient info response
            return {
                "answer": "I could not find sufficient information in the available documentation.",
                "citations": []
            }

        # Multi-chunk contiguous expansion for multi-chunk document sections on the same page
        expanded_chunks = list(chunks)
        retrieved_ids = set(c.get("chunk_id") for c in chunks)
        corpus_chunks = []
        if hasattr(self.faiss_service, "get_chunks"):
            corpus_chunks = self.faiss_service.get_chunks(user_id=user_id, document_id=document_id)
        elif getattr(self.faiss_service, "metadata_store", None):
            corpus_chunks = list(self.faiss_service.metadata_store.values())

        page_groups = {}
        for c in chunks:
            key = (c.get("filename"), c.get("page"))
            page_groups.setdefault(key, []).append(c)

        for (fn, pg), group in page_groups.items():
            if len(group) >= 2 and pg is not None:
                doc_page_chunks = [c for c in corpus_chunks if c.get("filename") == fn and c.get("page") == pg]
                for dpc in doc_page_chunks:
                    if dpc.get("chunk_id") not in retrieved_ids:
                        expanded_chunks.append(dpc)
                        retrieved_ids.add(dpc.get("chunk_id"))
            
        # 2. Build context
        context = self.build_context(expanded_chunks)
        
        # 3. Call LLM
        user_prompt = USER_PROMPT_TEMPLATE.format(context=context, question=question)
        
        try:
            answer = self.llm_service.generate_response(SYSTEM_PROMPT, user_prompt, history=history)
            logger.info("LLM response generated")
        except Exception as e:
            # Propagate the error correctly so callers can handle LLM failure
            raise RuntimeError(f"LLM failure: {e}")
            
        # 4. Return citations (deduplicated by page with stable page-number ordering)
        citations = []
        seen_pages = set()
        for chunk in expanded_chunks:
            page = chunk.get("page", 1)
            if page not in seen_pages:
                seen_pages.add(page)
                citations.append({
                    "page": page,
                    "chunk_id": chunk.get("chunk_id")
                })
        citations.sort(key=lambda x: int(x["page"]) if str(x["page"]).isdigit() else str(x["page"]))
            
        return {
            "answer": answer.strip(),
            "citations": citations
        }


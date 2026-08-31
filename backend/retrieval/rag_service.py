import logging
from typing import Dict, Any, List
from services.embeddings.embedding_service import EmbeddingService
from services.vector_store.faiss_service import FAISSService
from services.llm.llm_service import get_llm_service

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
    def __init__(self, embedding_service: EmbeddingService, faiss_service: FAISSService):
        self.embedding_service = embedding_service
        self.faiss_service = faiss_service
        try:
            self.llm_service = get_llm_service()
        except ValueError as e:
            # We will initialize this safely so tests can pass without API keys
            # if we explicitly handle it or let it fail gracefully.
            logger.warning(f"Failed to initialize LLM service: {e}")
            self.llm_service = None

    def embed_query(self, query: str) -> List[float]:
        if not query or not query.strip():
            logger.error("Empty query provided.")
            raise ValueError("Empty query")
            
        logger.info(f"Query received: {query}")
        embedding = self.embedding_service.generate_embedding(query)
        logger.info("Query embedded")
        return embedding

    def retrieve_chunks(self, query_embedding: List[float], user_id: int = None, document_id: str = None) -> List[Dict[str, Any]]:
        try:
            results = self.faiss_service.search(query_embedding, top_k=5, user_id=user_id, document_id=document_id)
            if not results:
                logger.warning("No chunks found in FAISS search.")
                return []
            
            logger.info(f"Retrieval completed. {len(results)} chunks found.")
            return results
        except RuntimeError as e:
            if "Empty index" in str(e):
                logger.error("Empty FAISS index encountered.")
                raise ValueError("Empty FAISS index")
            raise

    def build_context(self, chunks: List[Dict[str, Any]]) -> str:
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            content = chunk.get("content", "")
            page = chunk.get("page", "?")
            context_parts.append(f"[Citation {i}] Page {page}: {content}")
            
        context = "\n\n".join(context_parts)
        logger.info("Context built")
        return context

    def answer_question(self, question: str, user_id: int = None, document_id: str = None, history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        if not self.llm_service:
            raise ValueError("LLM failure: LLM Service is not configured properly.")
            
        # 1. Generate Query Embedding
        query_embedding = self.embed_query(question)
        
        # 2. Search FAISS (Top 5)
        chunks = self.retrieve_chunks(query_embedding, user_id=user_id, document_id=document_id)
        
        if not chunks:
            # If no chunks found, return standard insufficient info response
            return {
                "answer": "I could not find sufficient information in the available documentation.",
                "citations": []
            }
            
        # 3. Build context
        context = self.build_context(chunks)
        
        # 4. Call LLM
        user_prompt = USER_PROMPT_TEMPLATE.format(context=context, question=question)
        
        try:
            answer = self.llm_service.generate_response(SYSTEM_PROMPT, user_prompt, history=history)
            logger.info("LLM response generated")
        except Exception as e:
            # Propagate the error correctly so callers can handle LLM failure
            raise RuntimeError(f"LLM failure: {e}")
            
        # 5. Return citations
        citations = []
        for chunk in chunks:
            citations.append({
                "page": chunk.get("page"),
                "chunk_id": chunk.get("chunk_id")
            })
            
        return {
            "answer": answer.strip(),
            "citations": citations
        }

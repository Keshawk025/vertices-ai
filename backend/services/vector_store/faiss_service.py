import os
import json
import logging
import numpy as np
import faiss
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class FAISSService:
    def __init__(self, dimension: int = 384, index_path: str = "storage/vector_store/index.faiss", meta_path: str = "storage/vector_store/metadata.json"):
        self.dimension = dimension
        self.index_path = index_path
        self.meta_path = meta_path
        self.index = None
        self.metadata_store = {}  # Map integer IDs to metadata dict
        self._next_id = 0
        if os.path.exists(self.index_path) and os.path.exists(self.meta_path):
            try:
                self.load_index()
            except Exception as e:
                logger.warning(f"Could not auto-load index from {self.index_path}: {e}")

    def create_index(self):
        """Initializes a new FAISS index using Inner Product (for Cosine Similarity on normalized vectors)."""
        # IndexFlatIP calculates inner product. If vectors are normalized, IP == Cosine Similarity.
        self.index = faiss.IndexIDMap(faiss.IndexFlatIP(self.dimension))
        self.metadata_store = {}
        self._next_id = 0
        logger.info(f"Index created with dimension {self.dimension} and Cosine Similarity (IndexFlatIP).")

    def _normalize_vectors(self, vectors: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        # Avoid division by zero
        norms[norms == 0] = 1
        return vectors / norms

    def add_embeddings(self, embedded_chunks: List[Dict[str, Any]]):
        if self.index is None:
            if os.path.exists(self.index_path) and os.path.exists(self.meta_path):
                try:
                    self.load_index()
                except Exception:
                    self.create_index()
            else:
                self.create_index()
            
        if not embedded_chunks:
            logger.warning("Empty embeddings list provided.")
            return

        vectors = []
        ids = []
        
        for chunk in embedded_chunks:
            if "embedding" not in chunk or not isinstance(chunk["embedding"], list):
                logger.error("Invalid embeddings: Missing or malformed embedding field.")
                raise ValueError("Invalid embeddings: Missing or malformed embedding field.")
                
            if "filename" not in chunk:
                chunk["filename"] = ""
            if "user_id" not in chunk:
                chunk["user_id"] = None
                
            required_meta = ["document_id", "chunk_id", "page", "content"]
            missing = [m for m in required_meta if m not in chunk]
            if missing:
                logger.error(f"Missing metadata in chunk {chunk.get('chunk_id')}: {missing}")
                raise ValueError(f"Missing required metadata: {missing}")

            embedding_array = np.array(chunk["embedding"], dtype=np.float32)
            if embedding_array.shape[0] != self.dimension:
                logger.error(f"Invalid embeddings: Dimension mismatch. Expected {self.dimension}, got {embedding_array.shape[0]}")
                raise ValueError(f"Invalid embeddings: Dimension mismatch.")
                
            vectors.append(embedding_array)
            ids.append(self._next_id)
            
            # Store metadata
            self.metadata_store[str(self._next_id)] = {
                "document_id": chunk["document_id"],
                "chunk_id": chunk["chunk_id"],
                "page": chunk["page"],
                "content": chunk["content"],
                "filename": chunk["filename"],
                "user_id": chunk["user_id"]
            }
            
            self._next_id += 1
            
        vectors_np = np.array(vectors, dtype=np.float32)
        # Normalize vectors for cosine similarity
        vectors_np = self._normalize_vectors(vectors_np)
        ids_np = np.array(ids, dtype=np.int64)
        
        self.index.add_with_ids(vectors_np, ids_np)
        logger.info(f"Embeddings added. {len(ids)} chunks indexed.")

    def search(self, query_embedding: List[float], top_k: int = 5, user_id: int = None, document_id: str = None) -> List[Dict[str, Any]]:
        if (self.index is None or self.index.ntotal == 0) and os.path.exists(self.index_path) and os.path.exists(self.meta_path):
            try:
                self.load_index()
            except Exception as e:
                logger.warning(f"Could not load index in search: {e}")

        if self.index is None or self.index.ntotal == 0:
            logger.error("Empty index: Cannot search on an empty index.")
            raise RuntimeError("Empty index: Cannot search on an empty index.")
            
        if len(query_embedding) != self.dimension:
            raise ValueError(f"Invalid embeddings: Query dimension must be {self.dimension}")
            
        query_np = np.array([query_embedding], dtype=np.float32)
        query_np = self._normalize_vectors(query_np)
        
        # Search a larger pool if filtering is required
        search_k = min(max(top_k * 100, 1000), self.index.ntotal) if (user_id is not None or document_id is not None) else top_k
        distances, indices = self.index.search(query_np, search_k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue # No more results
            
            str_idx = str(idx)
            if str_idx in self.metadata_store:
                meta = self.metadata_store[str_idx]
                
                # Apply filters
                if user_id is not None and str(meta.get("user_id")) != str(user_id):
                    continue
                if document_id is not None and meta.get("document_id") != document_id:
                    continue
                    
                results.append({
                    "chunk_id": meta["chunk_id"],
                    "score": float(dist),
                    "content": meta["content"],
                    "page": meta["page"],
                    "document_id": meta["document_id"],
                    "filename": meta["filename"],
                    "user_id": meta.get("user_id")
                })
                
                if len(results) >= top_k:
                    break
                
        if user_id is not None:
            logger.info(f"Multi-document search executed for user {user_id}. Found {len(results)} results.")
        else:
            logger.info(f"Search completed. Found {len(results)} results.")
            
        return results

    def save_index(self):
        if self.index is None:
            raise RuntimeError("Cannot save an uninitialized index.")
            
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        faiss.write_index(self.index, self.index_path)
        
        with open(self.meta_path, "w") as f:
            json.dump({
                "next_id": self._next_id,
                "store": self.metadata_store
            }, f)
            
        logger.info("Index saved.")

    def load_index(self):
        if not os.path.exists(self.index_path) or not os.path.exists(self.meta_path):
            raise FileNotFoundError("Index or metadata file not found.")
            
        loaded_index = faiss.read_index(self.index_path)
        if loaded_index.d != self.dimension:
            logger.warning(f"Index dimension mismatch: file has {loaded_index.d}, service requires {self.dimension}")
            self.create_index()
            return

        self.index = loaded_index
        
        with open(self.meta_path, "r") as f:
            data = json.load(f)
            self._next_id = data.get("next_id", 0)
            self.metadata_store = data.get("store", {})
            
        logger.info("Index loaded.")

    def delete_document(self, document_id: str):
        if self.index is None or self.index.ntotal == 0:
            return
            
        # Find all integer IDs related to this document
        ids_to_remove = []
        for int_id_str, meta in self.metadata_store.items():
            if meta["document_id"] == document_id:
                ids_to_remove.append(int(int_id_str))
                
        if not ids_to_remove:
            logger.info(f"No chunks found for document_id {document_id} to delete.")
            return
            
        # FAISS allows removing IDs from IndexIDMap
        self.index.remove_ids(np.array(ids_to_remove, dtype=np.int64))
        
        # Remove from metadata store
        for idx in ids_to_remove:
            del self.metadata_store[str(idx)]
            
        logger.info(f"Deleted document {document_id}. Removed {len(ids_to_remove)} chunks.")

    def get_chunks(self, user_id: Any = None, document_id: str = None) -> List[Dict[str, Any]]:
        """
        Returns all chunk metadata stored in the vector store matching the optional
        user_id and document_id filters. Required for lexical indexing (BM25)
        over the active multi-document corpus.
        """
        if (self.index is None or not self.metadata_store) and os.path.exists(self.index_path) and os.path.exists(self.meta_path):
            try:
                self.load_index()
            except Exception as e:
                logger.warning(f"Could not load index in get_chunks: {e}")

        if not self.metadata_store:
            return []

        chunks = []
        for meta in self.metadata_store.values():
            if user_id is not None and str(meta.get("user_id")) != str(user_id):
                continue
            if document_id is not None and meta.get("document_id") != document_id:
                continue
            chunks.append({
                "chunk_id": meta["chunk_id"],
                "document_id": meta["document_id"],
                "page": meta.get("page", 1),
                "content": meta["content"],
                "filename": meta.get("filename", ""),
                "user_id": meta.get("user_id")
            })
        return chunks

    def health_check(self) -> Dict[str, Any]:
        if self.index is None:
            return {"status": "uninitialized"}
            
        return {
            "status": "healthy",
            "total_vectors": self.index.ntotal,
            "dimension": self.dimension,
            "next_id": self._next_id
        }

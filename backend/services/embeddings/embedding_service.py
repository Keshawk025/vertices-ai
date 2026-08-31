import time
import logging
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._load_model()

    def _load_model(self):
        try:
            # sentence-transformers loads the model and keeps it in memory
            self._model = SentenceTransformer(self.model_name)
        except Exception as e:
            logger.error(f"Model loading failure for {self.model_name}: {e}")
            raise RuntimeError(f"Failed to load embedding model {self.model_name}: {e}")

    def get_embedding_dimension(self) -> int:
        if not self._model:
            raise RuntimeError("Model is not loaded.")
        return self._model.get_embedding_dimension()

    def generate_embedding(self, text: str) -> List[float]:
        if not text or not text.strip():
            logger.warning("Invalid text detected: Empty text provided for embedding.")
            raise ValueError("Text cannot be empty.")
            
        try:
            embedding = self._model.encode(text, convert_to_numpy=True)
            embedding_list = embedding.tolist()
            
            # Validate embedding dimension
            if len(embedding_list) != self.get_embedding_dimension():
                raise ValueError("Generated embedding dimension mismatch.")
                
            return embedding_list
        except Exception as e:
            logger.error(f"Invalid embedding generation: {e}")
            raise RuntimeError(f"Failed to generate embedding: {e}")

    def generate_embeddings(self, chunked_document: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(chunked_document, dict):
            raise TypeError("Input must be a dictionary containing chunks.")
            
        document_id = chunked_document.get("document_id")
        chunks = chunked_document.get("chunks")
        
        if not document_id:
            raise ValueError("Missing document_id in input.")
        if chunks is None or not isinstance(chunks, list):
            raise ValueError("Missing or invalid chunks array in input.")
            
        logger.info(f"Embedding generation started for document {document_id} with {len(chunks)} chunks.")
        start_time = time.time()
        
        # Filter valid chunks and keep track of them
        valid_chunks = []
        texts_to_embed = []
        
        for chunk in chunks:
            content = chunk.get("content", "")
            if not content or not content.strip():
                logger.warning(f"Invalid text detected: Empty chunk encountered. Chunk ID: {chunk.get('chunk_id')}")
                continue # Skip empty chunks or throw? Requirements say "Error Handling: Empty chunks". Let's raise ValueError to be strict.
                
            valid_chunks.append(chunk)
            texts_to_embed.append(content)
            
        if not texts_to_embed:
            # All chunks were empty or no chunks provided
            logger.info(f"Batch embedding completed in {time.time() - start_time:.4f}s. No valid chunks to embed.")
            return {
                "document_id": document_id,
                "embedded_chunks": []
            }
            
        try:
            embeddings_matrix = self._model.encode(texts_to_embed, convert_to_numpy=True)
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise RuntimeError(f"Failed to generate batch embeddings: {e}")
            
        embedded_chunks = []
        expected_dim = self.get_embedding_dimension()
        
        for i, chunk in enumerate(valid_chunks):
            embedding_list = embeddings_matrix[i].tolist()
            
            if len(embedding_list) != expected_dim:
                logger.error(f"Invalid embedding dimension for chunk {chunk.get('chunk_id')}")
                raise ValueError(f"Invalid embedding dimension. Expected {expected_dim}, got {len(embedding_list)}")
                
            # Preserve original chunk metadata, just add "embedding" key
            embedded_chunk = chunk.copy()
            embedded_chunk["embedding"] = embedding_list
            embedded_chunks.append(embedded_chunk)
            
        elapsed_time = time.time() - start_time
        logger.info(f"Batch embedding completed in {elapsed_time:.4f}s for document {document_id}")
        
        return {
            "document_id": document_id,
            "embedded_chunks": embedded_chunks
        }

import os
import logging
from typing import Dict, Any, List
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class LLMService(ABC):
    @abstractmethod
    def generate_response(self, system_prompt: str, user_prompt: str, history: List[Dict[str, str]] = None) -> str:
        """Generates a response from the LLM provider."""
        pass

def get_llm_service() -> LLMService:
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    
    if provider == "groq":
        from services.llm.groq_service import GroqService
        return GroqService()
    elif provider == "featherless":
        from services.llm.featherless_service import FeatherlessService
        return FeatherlessService()
    else:
        # Fallback to Groq if key exists, otherwise Featherless
        if os.getenv("GROQ_API_KEY"):
            logger.info("LLM_PROVIDER not set, falling back to GroqService based on API key.")
            from services.llm.groq_service import GroqService
            return GroqService()
        elif os.getenv("FEATHERLESS_API_KEY"):
            logger.info("LLM_PROVIDER not set, falling back to FeatherlessService based on API key.")
            from services.llm.featherless_service import FeatherlessService
            return FeatherlessService()
        else:
            logger.error("No valid LLM_PROVIDER or API keys found.")
            raise ValueError("No valid LLM_PROVIDER or API keys found.")

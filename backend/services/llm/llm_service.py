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
    elif provider == "local":
        from services.llm.local_service import LocalExtractiveService
        return LocalExtractiveService()
    elif provider != "":
        raise ValueError(f"No valid LLM_PROVIDER or API keys found. Unknown provider: {provider}")
    else:
        # Fallback to Groq if key exists, otherwise Featherless, otherwise Local
        if os.getenv("GROQ_API_KEY"):
            logger.info("Using GroqService based on GROQ_API_KEY environment variable.")
            from services.llm.groq_service import GroqService
            return GroqService()
        elif os.getenv("FEATHERLESS_API_KEY"):
            logger.info("Using FeatherlessService based on FEATHERLESS_API_KEY environment variable.")
            from services.llm.featherless_service import FeatherlessService
            return FeatherlessService()
        elif os.getenv("REQUIRE_CLOUD_LLM", "false").lower() == "true":
            raise ValueError("No valid LLM_PROVIDER or API keys found.")
        else:
            logger.info("No cloud LLM API key detected. Using built-in LocalExtractiveService for grounded synthesis.")
            from services.llm.local_service import LocalExtractiveService
            return LocalExtractiveService()

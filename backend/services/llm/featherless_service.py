import os
import httpx
import logging
from services.llm.llm_service import LLMService

logger = logging.getLogger(__name__)

class FeatherlessService(LLMService):
    def __init__(self):
        self.api_key = os.getenv("FEATHERLESS_API_KEY")
        if not self.api_key:
            raise ValueError("FEATHERLESS_API_KEY is missing.")
        self.endpoint = "https://api.featherless.ai/v1/chat/completions"
        self.model = "meta-llama/Meta-Llama-3-8B-Instruct"

    def generate_response(self, system_prompt: str, user_prompt: str, history: list = None) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0
        }
        
        try:
            with httpx.Client() as client:
                response = client.post(self.endpoint, headers=headers, json=payload, timeout=30.0)
                response.raise_for_status()
                
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
                else:
                    logger.error("LLM failure: Unexpected response format from Featherless API.")
                    raise RuntimeError("LLM failure: Unexpected response format from Featherless API.")
                    
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("Invalid API key for Featherless.")
                raise ValueError("Invalid API key for Featherless.")
            else:
                logger.error(f"LLM failure: HTTP error occurred: {e}")
                raise RuntimeError(f"LLM failure: HTTP error occurred: {e}")
        except Exception as e:
            logger.error(f"LLM failure: Request to Featherless API failed: {e}")
            raise RuntimeError(f"LLM failure: {e}")

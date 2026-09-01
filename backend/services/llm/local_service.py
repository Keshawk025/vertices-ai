import logging
import re
from typing import Dict, Any, List
from services.llm.llm_service import LLMService

logger = logging.getLogger(__name__)

class LocalExtractiveService(LLMService):
    """
    Built-in extractive synthesis engine for Veritas AI.
    Works entirely offline without external API keys by extracting,
    ranking, and formatting relevant context chunks into coherent answers.
    """
    def __init__(self):
        logger.info("LocalExtractiveService initialized as active synthesis provider.")

    def generate_response(self, system_prompt: str, user_prompt: str, history: List[Dict[str, str]] = None) -> str:
        # Parse context and question from user_prompt
        context_match = re.search(r"Context:\s*(.*?)\s*Question:\s*(.*)", user_prompt, re.DOTALL)
        
        if not context_match:
            context_text = user_prompt
            question = ""
        else:
            context_text = context_match.group(1).strip()
            question = context_match.group(2).strip()

        if not context_text or context_text == "None" or "I could not find" in context_text:
            return "I could not find sufficient information in the available documentation."

        # Parse citations from context: [Citation X] Page Y: Content
        citation_pattern = re.findall(r"\[Citation\s*(\d+)\]\s*Page\s*(\d+|\?):\s*([^\n]+(?:\n(?![\[Citation]).*)*)", context_text)
        
        if not citation_pattern:
            # Simple text context without citation tags
            lines = [line.strip() for line in context_text.split("\n") if line.strip()]
            if not lines:
                return "I could not find sufficient information in the available documentation."
            return "Based on the retrieved document context:\n\n" + "\n".join(f"- {line}" for line in lines[:4])

        response_paragraphs = []
        response_paragraphs.append(f"Based on the analyzed document records:")

        for cite_num, page_num, content in citation_pattern[:4]:
            clean_content = re.sub(r"\s+", " ", content).strip()
            if clean_content:
                # Truncate clean sentences if too long
                sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean_content) if len(s.strip()) > 10]
                summary = " ".join(sentences[:3]) if sentences else clean_content[:250]
                response_paragraphs.append(f"- **(Page {page_num})**: {summary}")

        if len(response_paragraphs) == 1:
            return "I could not find sufficient information in the available documentation."

        return "\n\n".join(response_paragraphs)

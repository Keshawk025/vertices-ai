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
        # Uses robust negative lookahead/lookahead to match complete multiline content without stopping on letters like C
        citation_pattern = re.findall(
            r"\[Citation\s*(\d+)\]\s*Page\s*(\d+|\?):\s*([\s\S]*?)(?=(?:\n*\s*\[Citation\s*\d+\])|$)",
            context_text
        )
        
        if not citation_pattern:
            # Simple text context without citation tags
            lines = [line.strip() for line in context_text.split("\n") if line.strip()]
            if not lines:
                return "I could not find sufficient information in the available documentation."
            return "Based on the retrieved document context:\n\n" + "\n".join(f"- {line}" for line in lines)

        response_paragraphs = []
        response_paragraphs.append("Based on the analyzed document records:")

        seen_snippets = set()

        for cite_num, page_num, content in citation_pattern:
            raw_lines = [l.strip() for l in content.split("\n") if l.strip()]
            content_lines = []
            for l in raw_lines:
                if re.match(r"^\d{4}-\d{2}$", l) or re.match(r"^Page\s*\d+$", l, re.I):
                    continue
                content_lines.append(l)

            if not content_lines:
                continue

            joined = " ".join(content_lines)
            joined = re.sub(r"\s+", " ", joined).strip()

            # Preserve numbered list items (e.g. 1. , 2. , 12. ) and bullet points
            joined = re.sub(r"(\d+\.\s+[A-Z])", r"\n\1", joined)
            joined = re.sub(r"([•\-])\s+", r"\n• ", joined)

            items = [it.strip() for it in joined.split("\n") if it.strip()]
            deduped_items = []
            for item in items:
                norm_key = re.sub(r"[^a-zA-Z0-9]", "", item)[:80].lower()
                if norm_key and norm_key in seen_snippets:
                    continue
                if norm_key:
                    seen_snippets.add(norm_key)
                deduped_items.append(item)

            if deduped_items:
                if len(deduped_items) == 1:
                    response_paragraphs.append(f"- **(Page {page_num})**: {deduped_items[0]}")
                else:
                    response_paragraphs.append(f"- **(Page {page_num})**:\n" + "\n".join(deduped_items))

        if len(response_paragraphs) == 1:
            return "I could not find sufficient information in the available documentation."

        return "\n\n".join(response_paragraphs)


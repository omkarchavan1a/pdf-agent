import os
from langchain_core.language_models.llms import LLM
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from openai import OpenAI
from typing import Any, Optional
from dotenv import load_dotenv

load_dotenv()


class SarvamLLM(LLM):
    """
    LangChain-compatible wrapper around the Sarvam AI OpenAI-compatible API.
    Uses sarvam-30b by default.
    """
    model: str = os.getenv("SARVAM_MODEL", "sarvam-30b")
    max_tokens: int = 4096
    temperature: float = 0.0

    @property
    def _llm_type(self) -> str:
        return "sarvam-ai"

    def _call(
        self,
        prompt: str,
        stop: Optional[list] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        api_key = os.getenv("SARVAM_API_KEY")
        if not api_key:
            return "Error: SARVAM_API_KEY not set in .env"

        client = OpenAI(
            base_url="https://api.sarvam.ai/v1",
            api_key=api_key,
            default_headers={"api-subscription-key": api_key}
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            
            content = response.choices[0].message.content
            if not content:
                content = getattr(response.choices[0].message, 'reasoning_content', None)
                
            if not content:
                return "Error: Empty response received from Sarvam AI model"
                
            return content.strip()
        except Exception as e:
            return f"Sarvam AI Error: {str(e)}"


# Singleton instance — avoids rebuilding on every call
_llm_instance = None

def get_gemma_llm() -> SarvamLLM:
    """
    Returns the LLM instance (singleton to avoid repeated init overhead).
    Name kept as get_gemma_llm() for backward-compatibility with agent_graph.py.
    Now powered by Sarvam AI.
    """
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = SarvamLLM()
        print(f"[OK] Sarvam AI LLM initialized ({_llm_instance.model})")
    return _llm_instance


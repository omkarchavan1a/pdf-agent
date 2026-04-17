import os
from langchain_core.language_models.llms import LLM
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from openai import OpenAI
from typing import Any, Optional
from dotenv import load_dotenv

load_dotenv()

class NvidiaLLM(LLM):
    """
    LangChain-compatible wrapper around the NVIDIA NIM OpenAI-compatible API.
    Uses meta/llama-3.3-70b-instruct — proven stable and supports text-generation.
    This replaces HuggingFaceEndpoint which requires 'Inference Providers' permission
    that the current HF token does not have.
    """
    model: str = "meta/llama-3.3-70b-instruct"
    max_tokens: int = 1024
    temperature: float = 0.7

    @property
    def _llm_type(self) -> str:
        return "nvidia-nim"

    def _call(
        self,
        prompt: str,
        stop: Optional[list] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key:
            return "Error: NVIDIA_API_KEY not set in .env"

        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key,
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"NVIDIA NIM Error: {str(e)}"


# Singleton instance — avoids rebuilding on every call
_llm_instance = None

def get_gemma_llm() -> NvidiaLLM:
    """
    Returns the LLM instance (singleton to avoid repeated init overhead).
    Name kept as get_gemma_llm() for backward-compatibility with agent_graph.py.
    Now powered by NVIDIA NIM (Llama-3.3-70B) instead of HuggingFace Gemma.
    """
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = NvidiaLLM()
        print("[OK] NVIDIA NIM LLM initialized (meta/llama-3.3-70b-instruct)")
    return _llm_instance

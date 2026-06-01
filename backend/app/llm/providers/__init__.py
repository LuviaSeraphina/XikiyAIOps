"""
LLM Provider 工厂 — 根据 LLM_PROVIDER 环境变量返回对应的 Provider 实例

用法:
    from app.llm.providers import get_llm_provider
    provider = get_llm_provider()
    async for event in provider.chat_stream(messages, tools):
        ...
"""
from app.llm.config import LLM_PROVIDER, LLM_BASE_URL, LLM_MODEL, LLM_API_KEY, REQUEST_TIMEOUT
from app.llm.providers.ollama import OllamaProvider
from app.llm.providers.openai_compat import OpenAICompatProvider


def get_llm_provider():
    if LLM_PROVIDER == "ollama":
        return OllamaProvider(LLM_BASE_URL, LLM_MODEL, REQUEST_TIMEOUT)
    if LLM_PROVIDER in ("deepseek", "qwen", "openai"):
        return OpenAICompatProvider(LLM_BASE_URL, LLM_MODEL, LLM_API_KEY, REQUEST_TIMEOUT)
    raise ValueError(
        "不支持的 LLM_PROVIDER: '{}'。支持: ollama / deepseek / qwen / openai".format(
            LLM_PROVIDER
        )
    )
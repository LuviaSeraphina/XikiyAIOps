"""
LLM Provider 工厂 — 根据动态配置返回对应的 Provider 实例

用法:
    from app.llm.providers import get_llm_provider
    provider = get_llm_provider()
    async for event in provider.chat_stream(messages, tools):
        ...
"""
from app.llm.config import get_llm_config, REQUEST_TIMEOUT
from app.llm.providers.ollama import OllamaProvider
from app.llm.providers.openai_compat import OpenAICompatProvider


def get_llm_provider():
    config=get_llm_config()
    active_preset=config.get("active_preset","deepseek")
    presets=config.get("presets",{})
    preset=presets.get(active_preset,{})
    provider=preset.get("provider","deepseek")
    base_url=preset.get("base_url","https://api.deepseek.com")
    model=preset.get("model","deepseek-chat")
    api_key=preset.get("api_key","")

    if provider=="ollama":
        return OllamaProvider(base_url, model, REQUEST_TIMEOUT)
    if provider in ("deepseek","qwen","openai"):
        return OpenAICompatProvider(base_url, model, api_key, REQUEST_TIMEOUT)
    raise ValueError(
        "不支持的 LLM_PROVIDER: '{}'。支持: ollama / deepseek / qwen / openai".format(
            provider
        )
    )
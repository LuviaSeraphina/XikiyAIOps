import os
import json
from pathlib import Path
from dotenv import load_dotenv
import logging

logger = logging.getLogger("xikiy_aiops.llm")

# 显式指定 .env 路径，避免依赖 CWD
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)

# JSON 配置文件路径 (前端设置持久化)
LLM_CONFIG_PATH=Path(__file__).resolve().parent.parent.parent / "llm_config.json"

REQUEST_TIMEOUT=int(os.getenv("REQUEST_TIMEOUT","120"))
MAX_TOOL_ROUNDS=5

# ── 预设模型列表 — 前端下拉选项 ──

PRESET_MODELS=[
    {
        "id":"deepseek",
        "label":"DeepSeek",
        "provider":"deepseek",
        "base_url":"https://api.deepseek.com",
        "requires_key":True,
    },
    {
        "id":"qwen",
        "label":"Qwen",
        "provider":"qwen",
        "base_url":"https://dashscope.aliyuncs.com/compatible-mode",
        "hint":"请到阿里云百炼控制台 API-KEY 管理界面复制专属 URL",
        "requires_key":True,
    },
    {
        "id":"doubao",
        "label":"DoubaoSeed",
        "provider":"openai",
        "base_url":"https://ark.cn-beijing.volces.com/api/v3",
        "requires_key":True,
    },
]

# ── JSON 文件优先，已无 .env 兜底 ──

# 预设默认值（仅首次初始化时使用）
_DEFAULT_PROVIDER="deepseek"
_DEFAULT_BASE_URL="https://api.deepseek.com"
_DEFAULT_MODEL="deepseek-v4-flash"
_DEFAULT_API_KEY=""

"""
方法: get_llm_config(), 读取 LLM 配置 — JSON 文件优先, .env 兜底

返回 dict: {provider, base_url, model, api_key}
"""
def get_llm_config():
    """读取 LLM 配置 — JSON 文件优先, .env 兜底

    返回 dict: {active_preset, presets: {id: {provider, base_url, model, api_key}}}
    """
    if LLM_CONFIG_PATH.is_file():
        try:
            cfg=json.loads(LLM_CONFIG_PATH.read_text(encoding="utf-8"))
            # 新格式：包含 presets
            if "presets" in cfg:
                return cfg
            # 旧格式：单配置，转换为新格式
            if cfg.get("provider") and cfg.get("model"):
                return {
                    "active_preset": cfg.get("active_preset", "deepseek"),
                    "presets": {
                        "deepseek": {
                            "provider": cfg["provider"],
                            "base_url": cfg.get("base_url", ""),
                            "model": cfg["model"],
                            "api_key": cfg.get("api_key", ""),
                        },
                        "qwen": {"provider": "qwen", "base_url": "https://dashscope.aliyuncs.com/compatible-mode", "model": "", "api_key": ""},
                        "doubao": {"provider": "openai", "base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "", "api_key": ""},
                    },
                }
        except (json.JSONDecodeError,KeyError):
            logger.warning("llm_config.json 格式错误, 回退 .env")

    #回退到默认预设结构（无 JSON 文件时）
    return {
        "active_preset": "deepseek",
        "presets": {
            "deepseek": {"provider": _DEFAULT_PROVIDER, "base_url": _DEFAULT_BASE_URL, "model": _DEFAULT_MODEL, "api_key": _DEFAULT_API_KEY},
            "qwen": {"provider": "qwen", "base_url": "https://dashscope.aliyuncs.com/compatible-mode", "model": "", "api_key": ""},
            "doubao": {"provider": "openai", "base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "", "api_key": ""},
        },
    }

"""
方法: save_preset_config(preset_id, cfg), 保存单个预设的配置

preset_id: 预设 ID (deepseek/qwen/doubao)
cfg: {provider, base_url, model, api_key}
"""
def save_preset_config(preset_id, cfg):
    config = get_llm_config()
    if "presets" not in config:
        config["presets"] = {}
    existing = config["presets"].get(preset_id, {})
    incoming_key = cfg.get("api_key", "")
    # 前端留空时保留已有 Key，有输入时覆盖
    api_key = incoming_key if incoming_key else existing.get("api_key", "")
    # 更新 label（如果有传入），否则保留已有
    label = cfg.get("label", "") or existing.get("label", preset_id)
    config["presets"][preset_id] = {
        "provider": cfg.get("provider", ""),
        "base_url": cfg.get("base_url", ""),
        "model": cfg.get("model", ""),
        "api_key": api_key,
        "label": label,
    }
    config["active_preset"] = preset_id
    LLM_CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("预设配置已保存: preset=%s provider=%s model=%s label=%s", preset_id, cfg.get("provider"), cfg.get("model"), label)
"""
LLM 公共工具函数

提供跨 Provider 和 Adapter 共享的防御性处理逻辑。
"""
import json


def normalize_arguments(arguments):
    """防御性参数规范化: JSON 字符串 → dict

    各 Provider 在解析 LLM 响应时已做第一轮规范化,
    此处作为 adapter 层的兜底防护, 确保 tool call 的 arguments 始终为 dict。

    Args:
        arguments: str | dict | None | ...

    Returns:
        dict: 规范化后的参数字典 (无效输入返回 {})
    """
    if isinstance(arguments, str):
        try:
            return json.loads(arguments)
        except json.JSONDecodeError:
            return {}
    return arguments or {}

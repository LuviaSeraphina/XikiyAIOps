"""
LLM 公共工具函数

提供跨 Provider 和 Adapter 共享的防御性处理逻辑。
"""
import json


"""
方法: normalize_arguments(arguments), 防御性参数规范化: JSON 字符串 → dict      各 Provider 在解析 LLM 响应时已做第一轮规范化,     此处作为 adapter 层的兜底防护, 确保 tool call

"""

def normalize_arguments(arguments):
    if isinstance(arguments, str):
        try:
            return json.loads(arguments)
        except json.JSONDecodeError:
            return {}
    return arguments or {}

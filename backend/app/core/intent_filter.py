"""
意图分类器 v3.0 — 精简版

只保留两层:
Layer 1 — 越狱/角色劫持检测 (正则, 微秒级)
Layer 2 — 运维操作关键词 (需二次确认)

移除 v2.0 的 Layer 2 (高危命令) 和 Layer 3 (注入检测):
Agent 无法直接执行 shell 命令, 只能通过 MCP Tool 间接操作,
每个 Tool 有 inputSchema 约束 + handler 逻辑 + _common.py 白名单兜底,
正则拦截命令字符串无实际安全价值。
"""
import re
from enum import Enum


class IntentCategory(str, Enum):
    JAILBREAK="jailbreak"         # 越狱尝试, 直接拒绝
    OPS_ACTION="ops_action"       # 运维操作, 需二次确认
    SAFE_QUERY="safe_query"       # 安全查询, 直接放行


""" Layer 1: 越狱/角色劫持检测 (最高优先级) """

_JAILBREAK_PATTERNS=[
    # 英文指令劫持
    re.compile(r"\bignore\s+(?:all\s+)?(?:previous\s+|above\s+|the\s+)?(?:instructions?|prompts?|rules?|constraints?)\b", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+(?:now|no\s+longer)\b", re.IGNORECASE),
    re.compile(r"\bpretend\s+(?:you\s+are|to\s+be)\b", re.IGNORECASE),
    re.compile(r"\bact\s+as\s+if\s+you\s+(?:are|were)\b", re.IGNORECASE),
    re.compile(r"\b(?:dan|developer|god)\s*mode\b", re.IGNORECASE),
    re.compile(r"\bjailbreak\b", re.IGNORECASE),
    re.compile(r"\b(?:bypass|override|disable|ignore)\s+(?:security|safety|filter|guardrail)\b", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+(?:a|an)\s+(?:linux\s*terminal|shell|command\s*line)\b", re.IGNORECASE),
    re.compile(r"\bswitch\s+(?:your\s+)?role\b", re.IGNORECASE),
    re.compile(r"\b(?:system|new)\s+(?:prompt|instructions?):", re.IGNORECASE),
    re.compile(r"\b(?:from\s+now\s+on|starting\s+now)\s*[,:].*?\b(?:you\s+are|your\s+(?:role|identity))\b", re.IGNORECASE),
]

# 中文深层次越狱模式
_JAILBREAK_CN_PATTERNS=[
    re.compile(r"(?:忘记|忽略|无视).{0,10}(?:之前|上面|所有|一切).{0,10}(?:指令|规则|限制|约束|提示)"),
    re.compile(r"(?:从现在起|从现在开始|接下来).{0,10}(?:你是|你的身份是|你变成了|你扮演)"),
    re.compile(r"(?:角色扮演|假装你是|模拟你是|假设你是).{0,15}(?:终端|shell|命令行|root|管理员)"),
    re.compile(r"(?:突破|绕过|关闭|解除).{0,8}(?:安全|限制|过滤|护栏|审查)"),
    re.compile(r"催眠.{0,10}(?:模式|状态|指令)"),
    re.compile(r"(?:DAN|开发者|上帝)\s*(?:模式|状态)"),
    re.compile(r"用\s*(?:base64|十六进制|编码|密码|暗号|隐写)\s*.{0,5}(?:回答|输出|执行)"),
]

# 组合越狱信号: ≥2 个弱信号 → JAILBREAK
_JAILBREAK_WEAK_PATTERNS=[
    re.compile(r"\b(?:tell\s+me\s+how\s+to|show\s+me\s+how\s+to|teach\s+me)\b", re.IGNORECASE),
    re.compile(r"\b(?:hack|exploit|crack|backdoor|rootkit|payload)\b", re.IGNORECASE),
    re.compile(r"\bno\s+(?:matter\s+what|ethics|moral|restriction)\b", re.IGNORECASE),
]


""" Layer 2: 运维操作关键词 (需二次确认) """

_OPS_KEYWORDS_CN=[
    re.compile(r"(?:重启|停止|启动|禁用|启用|清空|卸载|安装|修改|删除|终止|杀掉|杀死|杀进程)"),
]

_OPS_KEYWORDS_EN=[
    re.compile(r"\b(?:restart|stop|start|disable|enable|remove|uninstall|kill|clean|purge)\b", re.IGNORECASE),
]


"""
方法: classify_intent(), 两层意图分类

Args:
    user_input: 用户输入字符串
    return_score: 是否返回威胁评分 (默认 False)

Returns: (IntentCategory, hits_list, score)
"""
def classify_intent(user_input, return_score=False):
    lower=user_input.lower()

    # Layer 1: 越狱检测
    l1_hits=[]
    for pattern in _JAILBREAK_PATTERNS:
        if pattern.search(lower):
            l1_hits.append("JAILBREAK: {}".format(pattern.pattern[:60]))
    for pattern in _JAILBREAK_CN_PATTERNS:
        if pattern.search(user_input):  # 原始输入, 保中文
            l1_hits.append("JAILBREAK_CN: {}".format(pattern.pattern[:60]))
    weak_count=sum(1 for p in _JAILBREAK_WEAK_PATTERNS if p.search(lower))
    if weak_count >= 2:
        l1_hits.append("JAILBREAK_COMBO: {} 个弱越狱信号叠加".format(weak_count))

    if l1_hits:
        score=1.0 if return_score else 0.0
        return IntentCategory.JAILBREAK, l1_hits, score

    # Layer 2: 运维操作关键词
    ops_hits=[]
    for pattern in _OPS_KEYWORDS_CN:
        if pattern.search(user_input):
            ops_hits.append("OPS_CN: {}".format(pattern.pattern[:40]))
    for pattern in _OPS_KEYWORDS_EN:
        if pattern.search(lower):
            ops_hits.append("OPS_EN: {}".format(pattern.pattern[:40]))

    if ops_hits:
        score=0.2 if return_score else 0.0
        return IntentCategory.OPS_ACTION, ops_hits, score

    # 默认: 安全查询
    return IntentCategory.SAFE_QUERY, [], 0.0


"""
方法: get_threat_level(), 获取威胁等级摘要

Returns: dict with category, threat_score, threat_level, hits, blocked, requires_confirmation
"""
def get_threat_level(user_input):
    cat, hits, score=classify_intent(user_input, return_score=True)
    if score >= 0.9:
        level="CRITICAL"
    elif score >= 0.2:
        level="LOW"
    else:
        level="SAFE"

    return {
        "category": cat.value,
        "threat_score": score,
        "threat_level": level,
        "hits": hits,
        "blocked": cat == IntentCategory.JAILBREAK,
        "requires_confirmation": cat == IntentCategory.OPS_ACTION,
    }

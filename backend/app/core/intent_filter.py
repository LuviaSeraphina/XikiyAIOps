"""
越狱签名检测器 v4.0 — 仅拦截确定性攻击模式

职责: 0.1ms 内快速识别已知越狱签名, 直接拦截。
不分类意图、不检测命令、不识别注入 — 全部交给 LLM 语义审查。

保留: 英文/中文越狱签名正则 (角色劫持/指令覆写/模式绕过)
移除: 高危命令检测 (v3.0 已删)、运维关键词 (交给 Agent 判断)、
      注入检测 (LLM 语义理解更准确)
"""
import re


# ── 已知越狱签名 (确定性攻击, 0.1ms 拦截) ──

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

_JAILBREAK_CN_PATTERNS=[
    re.compile(r"(?:忘记|忽略|无视).{0,10}(?:之前|上面|所有|一切).{0,10}(?:指令|规则|限制|约束|提示)"),
    re.compile(r"(?:从现在起|从现在开始|接下来).{0,10}(?:你是|你的身份是|你变成了|你扮演)"),
    re.compile(r"(?:角色扮演|假装你是|模拟你是|假设你是).{0,15}(?:终端|shell|命令行|root|管理员)"),
    re.compile(r"(?:突破|绕过|关闭|解除).{0,8}(?:安全|限制|过滤|护栏|审查)"),
    re.compile(r"催眠.{0,10}(?:模式|状态|指令)"),
    re.compile(r"(?:DAN|开发者|上帝)\s*(?:模式|状态)"),
    re.compile(r"用\s*(?:base64|十六进制|编码|密码|暗号|隐写)\s*.{0,5}(?:回答|输出|执行)"),
]

# 组合弱信号: ≥2 个 → JAILBREAK
_JAILBREAK_WEAK_PATTERNS=[
    re.compile(r"\b(?:tell\s+me\s+how\s+to|show\s+me\s+how\s+to|teach\s+me)\b", re.IGNORECASE),
    re.compile(r"\b(?:hack|exploit|crack|backdoor|rootkit|payload)\b", re.IGNORECASE),
    re.compile(r"\bno\s+(?:matter\s+what|ethics|moral|restriction)\b", re.IGNORECASE),
]


"""
方法: check_jailbreak(), 快速越狱签名检测

Returns: (is_jailbreak: bool, matched_patterns: list)
"""
def check_jailbreak(user_input):
    lower=user_input.lower()
    hits=[]

    for pattern in _JAILBREAK_PATTERNS:
        if pattern.search(lower):
            hits.append(pattern.pattern[:60])
    for pattern in _JAILBREAK_CN_PATTERNS:
        if pattern.search(user_input):
            hits.append(pattern.pattern[:60])

    weak_count=sum(1 for p in _JAILBREAK_WEAK_PATTERNS if p.search(lower))
    if weak_count >= 2:
        hits.append("COMBO: {} 弱信号叠加".format(weak_count))

    return bool(hits), hits

"""
Prompt 注入检测器 v2.0 — 安全护栏第二道防线

与 intent_filter 协作:
- intent_filter      → 检测明显的高危指令和越狱 (第一道防线)
- injection_detector → 检测隐蔽的注入技巧 (第二道防线)

v2.0 新增:
- Unicode 同形字/混淆字符检测 (拉丁/西里尔/希腊字母替换)
- 零宽字符隐蔽注入检测 (U+200B/U+200C/U+200D/U+FEFF)
- 大小写交替混淆检测 (rM -Rf / 等)
- 双向文本覆盖注入 (RTL override)
"""
import re
import base64
import unicodedata
from app.core.intent_filter import IntentCategory, classify_intent


""" Layer 1: 分隔符注入检测 """

_SEPARATOR_DANGER_RE=re.compile(
    r"\b(?:rm|wget|curl|bash|sh|nc|python\s*-c|chmod|sudo|scp|tcpdump)\b",
    re.IGNORECASE
)

""" Layer 2: 编码绕过检测 (Base64 / Hex) """

_BASE64_DANGER_RE=re.compile(
    r"\b(?:rm|wget|curl|passwd|shadow|chmod|bash|/bin/sh|/etc/passwd|/etc/shadow)\b",
    re.IGNORECASE
)
_BASE64_CANDIDATE_RE=re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")
_HEX_ESCAPE_RE=re.compile(r"(\\x[0-9a-fA-F]{2}){4,}")


""" Layer 3: 间接指令注入 """

_INDIRECT_PATTERNS=[
    (re.compile(r"从现在开始.*?(?:你是|你的身份是|你的角色是)"), "中文角色切换"),
    (re.compile(r"(?:翻译|总结|复述|重复)以下.*?\b(?:rm|wget|curl|chmod|sudo|kill)\b", re.IGNORECASE), "任务嵌套指令"),
    (re.compile(r"忽略.*?(?:规则|限制|安全|指令).*?(?:执行|运行|输出)"), "中文规则绕过"),
    (re.compile(r"\b(?:translate|summarize|repeat|paraphrase)\s+(?:the\s+)?following.*?\b(?:rm|wget|curl|chmod|sudo|kill)\b", re.IGNORECASE), "英文任务嵌套"),
    (re.compile(r"\bignore\s+all\s+(?:rules?|constraints?|instructions?|safety)\b", re.IGNORECASE), "英文规则绕过"),
    (re.compile(r"\boutput\s+only\s+(?:the\s+)?(?:command|code|script)\b", re.IGNORECASE), "强制输出命令"),
]


""" Layer 4: Unicode 同形字/混淆字符检测 (v2.0) """

# 常见同形字映射: 拉丁/西里尔/希腊/全角/数学符号中与 ASCII 视觉相同的字符
_HOMOGLYPH_MAP={
    # 拉丁扩展 (带重音)
    'à': 'a', 'á': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a', 'å': 'a',
    'è': 'e', 'é': 'e', 'ê': 'e', 'ë': 'e',
    'ì': 'i', 'í': 'i', 'î': 'i', 'ï': 'i',
    'ò': 'o', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ö': 'o',
    'ù': 'u', 'ú': 'u', 'û': 'u', 'ü': 'u',
    # 西里尔 (与拉丁视觉相同) — 最常用于绕过过滤
    'а': 'a',  # U+0430 西里尔 а ≠ U+0061 拉丁 a
    'е': 'e',  # U+0435 西里尔 е ≠ U+0065 拉丁 e
    'о': 'o',  # U+043E 西里尔 о ≠ U+006F 拉丁 o
    'р': 'p',  # U+0440 西里尔 р ≠ U+0070 拉丁 p
    'с': 'c',  # U+0441 西里尔 с ≠ U+0063 拉丁 c
    'у': 'y',  # U+0443 西里尔 у ≠ U+0079 拉丁 y
    'х': 'x',  # U+0445 西里尔 х ≠ U+0078 拉丁 x
    'і': 'i',  # U+0456 西里尔 і ≠ U+0069 拉丁 i
    'ј': 'j',  # U+0458 西里尔 ј ≠ U+006A 拉丁 j
    # 希腊 (与拉丁视觉相同)
    'ο': 'o',  # U+03BF 希腊 ο ≠ U+006F 拉丁 o
    'ν': 'v',  # U+03BD 希腊 ν ≠ U+0076 拉丁 v
    'α': 'a',  # U+03B1 希腊 α
    'ε': 'e',  # U+03B5 希腊 ε
    'ι': 'i',  # U+03B9 希腊 ι
    'κ': 'k',  # U+03BA 希腊 κ
    # 全角拉丁字母 (U+FF01-U+FF5E) — 也常用于绕过
    'ａ': 'a', 'ｂ': 'b', 'ｃ': 'c', 'ｄ': 'd', 'ｅ': 'e',
    'ｆ': 'f', 'ｇ': 'g', 'ｈ': 'h', 'ｉ': 'i', 'ｊ': 'j',
    'ｋ': 'k', 'ｌ': 'l', 'ｍ': 'm', 'ｎ': 'n', 'ｏ': 'o',
    'ｐ': 'p', 'ｑ': 'q', 'ｒ': 'r', 'ｓ': 's', 'ｔ': 't',
    'ｕ': 'u', 'ｖ': 'v', 'ｗ': 'w', 'ｘ': 'x', 'ｙ': 'y', 'ｚ': 'z',
    'Ａ': 'A', 'Ｂ': 'B', 'Ｃ': 'C', 'Ｄ': 'D', 'Ｅ': 'E',
    'Ｆ': 'F', 'Ｇ': 'G', 'Ｈ': 'H', 'Ｉ': 'I', 'Ｊ': 'J',
    'Ｋ': 'K', 'Ｌ': 'L', 'Ｍ': 'M', 'Ｎ': 'N', 'Ｏ': 'O',
    'Ｐ': 'P', 'Ｑ': 'Q', 'Ｒ': 'R', 'Ｓ': 'S', 'Ｔ': 'T',
    'Ｕ': 'U', 'Ｖ': 'V', 'Ｗ': 'W', 'Ｘ': 'X', 'Ｙ': 'Y', 'Ｚ': 'Z',
}

# Unicode 类别: 非 ASCII 字母类字符
_NON_ASCII_LETTER=re.compile(r'[^\x00-\x7F]')

# 危险命令关键词 (用于同形字检测后的匹配)
_HOMOGLYPH_DANGER_KEYWORDS=[
    'rm', 'wget', 'curl', 'bash', 'sh', 'chmod', 'sudo', 'kill',
    'nc', 'passwd', 'shadow', 'reboot', 'shutdown', 'mkfs',
]

""" Layer 5: 零宽字符隐蔽注入 (v2.0) """

_ZERO_WIDTH_CHARS={
    '\u200B': 'ZERO_WIDTH_SPACE',      # 零宽空格
    '\u200C': 'ZERO_WIDTH_NON_JOINER', # 零宽不连字
    '\u200D': 'ZERO_WIDTH_JOINER',     # 零宽连字
    '\uFEFF': 'BOM/ZERO_WIDTH_NO_BREAK_SPACE', # 字节序标记/零宽不换行空格
    '\u2060': 'WORD_JOINER',           # 单词连接符
    '\u2061': 'FUNCTION_APPLICATION',
    '\u2062': 'INVISIBLE_TIMES',
    '\u2063': 'INVISIBLE_SEPARATOR',
    '\u2064': 'INVISIBLE_PLUS',
}

# 双向文本覆盖字符 (可用于隐藏代码)
_BIDI_OVERRIDE={
    '\u202A': 'LRE (Left-to-Right Embedding)',
    '\u202B': 'RLE (Right-to-Left Embedding)',
    '\u202C': 'PDF (Pop Directional Formatting)',
    '\u202D': 'LRO (Left-to-Right Override)',
    '\u202E': 'RLO (Right-to-Left Override)',
    '\u2066': 'LRI (Left-to-Right Isolate)',
    '\u2067': 'RLI (Right-to-Left Isolate)',
    '\u2068': 'FSI (First Strong Isolate)',
    '\u2069': 'PDI (Pop Directional Isolate)',
}


""" Layer 6: 大小写交替混淆检测 (v2.0) """

# 检测如 rM, rM -Rf, ChMoD 777, WgEt 等大小写交替模式
_CASE_ALTERNATION_RE=re.compile(
    r'\b(?:'
    r'[a-z][A-Z][a-z][A-Z]\w*|'   # aAaA... 模式 (4+ chars)
    r'[A-Z][a-z][A-Z][a-z]\w*|'   # AaAa... 模式 (4+ chars)
    r'[a-z][A-Z](?:\s+-[a-z][A-Z])?'  # 2-char alternating pair (like rM or rM -rF)
    r')\b'
)

# 大小写混淆版危险命令
_DANGEROUS_KEYWORDS_LOWER=[
    'rm', 'wget', 'curl', 'bash', 'chmod', 'chown', 'sudo', 'kill',
    'reboot', 'shutdown', 'mkfs', 'dd', 'nc', 'nmap', 'tcpdump',
    'iptables', 'nft', 'passwd', 'shadow', 'sshd',
]

""" Layer 7: LLM 输出黑名单校验 """

_LLM_OUTPUT_BLACKLIST=[
    (re.compile(r"rm\s+-rf\s+/"), "递归删除根目录"),
    (re.compile(r"dd\s+if="), "磁盘直接写入"),
    (re.compile(r">\s*/dev/sd[a-z]"), "覆盖磁盘设备"),
    (re.compile(r"mkfs\."), "格式化文件系统"),
    (re.compile(r"chmod\s+777"), "开放所有权限"),
    (re.compile(r":\(\)\s*\{\s*:\|:&\s*\};:"), "Fork 炸弹"),
    (re.compile(r"(?:wget|curl)\s+\S+\s+-(?:O|o)\s+/etc/"), "下载覆盖系统文件"),
]#方法: 检测通过换行/回车隐藏的注入指令
def _detect_separator_injection(user_input):
    hits = []

    if "\n" in user_input or "\r" in user_input:
        lines = user_input.replace("\r", "\n").split("\n")
        for i, line in enumerate(lines[1:], 1):
            if not line.strip():
                continue
            if _SEPARATOR_DANGER_RE.search(line):
                hits.append("SEPARATOR: 第{}行隐藏指令".format(i + 1))
                break

    if "\x00" in user_input:
        hits.append("NULL_BYTE: 检测到空字节截断")

    return hits

#方法: 检测 Base64 / Hex 编码的隐藏内容
def _detect_encoding_bypass(user_input):
    hits = []

    candidates = re.findall(_BASE64_CANDIDATE_RE, user_input)[:5]
    for candidate in candidates:
        try:
            decoded = base64.b64decode(candidate).decode("utf-8", errors="ignore")
            if _BASE64_DANGER_RE.search(decoded):
                hits.append("BASE64: 解码后含危险内容: {}".format(decoded[:50]))
                break
        except Exception:
            pass

    if _HEX_ESCAPE_RE.search(user_input):
        hits.append("HEX_ESCAPE: 检测到连续十六进制转义序列")

    return hits

#方法: 检测通过翻译/总结/复述等任务进行的间接指令注入
def _detect_indirect_injection(user_input):
    hits = []
    for pattern, desc in _INDIRECT_PATTERNS:
        if pattern.search(user_input):
            hits.append("INDIRECT: {}".format(desc))
    return hits

#方法: 检测 Unicode 同形字混淆攻击
def _detect_homoglyph_injection(user_input):
    hits = []

    # 检查是否含非 ASCII 字符
    non_ascii_chars = _NON_ASCII_LETTER.findall(user_input)
    if not non_ascii_chars:
        return hits

    # 标识具体使用的同形字
    used_homoglyphs = set()
    normalized = []
    for ch in user_input:
        if ch in _HOMOGLYPH_MAP:
            used_homoglyphs.add("U+{:04X} ({}) → '{}'".format(
                ord(ch), unicodedata.name(ch, 'UNKNOWN'), _HOMOGLYPH_MAP[ch]))
            normalized.append(_HOMOGLYPH_MAP[ch])
        else:
            normalized.append(ch)

    normalized_text = ''.join(normalized)

    # 检测标准化后是否出现危险关键词 (仅在确实使用了同形字时才报告)
    if used_homoglyphs:
        for keyword in _HOMOGLYPH_DANGER_KEYWORDS:
            if re.search(r"\b" + re.escape(keyword) + r"\b", normalized_text, re.IGNORECASE):
                hits.append(
                "HOMOGLYPH: 同形字伪装 '{}' — 使用字符: {}".format(
                    keyword,
                    ', '.join(sorted(used_homoglyphs)[:3])
                ))
                break  # 一个命中即足够

    return hits

#方法: 检测零宽字符隐蔽注入
def _detect_zero_width_injection(user_input):
    hits = []

    for ch, name in _ZERO_WIDTH_CHARS.items():
        if ch in user_input:
            count = user_input.count(ch)
            hits.append(
                "ZERO_WIDTH: {} 出现 {} 次 — {}".format(name, count, ch.encode('unicode_escape').decode()))

    for ch, name in _BIDI_OVERRIDE.items():
        if ch in user_input:
            hits.append(
                "BIDI_OVERRIDE: {} — {}".format(name, ch.encode('unicode_escape').decode()))

    return hits

#方法: 检测大小写交替混淆
def _detect_case_alternation(user_input):
    hits = []

    # 模式检测: 连续大小写交替的单词
    alternations = _CASE_ALTERNATION_RE.findall(user_input)
    if not alternations:
        return hits

    for word in alternations:
        word_lower = word.lower()
        for danger_kw in _DANGEROUS_KEYWORDS_LOWER:
            # 大小写混淆词可能包含参数 (如 "rM -rF"), 检查是否以危险关键词开头
            if word_lower == danger_kw or word_lower.startswith(danger_kw + " "):
                hits.append(
                    "CASE_ALTERNATION: '{}' → 大小写混淆版 '{}'".format(word, danger_kw))
                break

    return hits

#方法: 校验 LLM 生成的文字中是否意外包含危险命令
def validate_llm_output(llm_output):
    hits = []
    for pattern, description in _LLM_OUTPUT_BLACKLIST:
        if pattern.search(llm_output):
            hits.append("LLM_OUTPUT: {} — 匹配: {}".format(description, pattern.pattern[:40]))
    return hits


"""
方法: detect_injection(), 综合六层注入检测 (v2.0)

Layer 1: 分隔符注入, Layer 2: 编码绕过, Layer 3: 间接指令注入
Layer 4: Unicode 同形字, Layer 5: 零宽字符, Layer 6: 大小写交替混淆
"""
def detect_injection(user_input):
    all_hits = []

    # Layer 1: 分隔符注入
    all_hits.extend(_detect_separator_injection(user_input))

    # Layer 2: 编码绕过
    all_hits.extend(_detect_encoding_bypass(user_input))

    # Layer 3: 间接指令注入
    all_hits.extend(_detect_indirect_injection(user_input))

    # Layer 4: Unicode 同形字混淆 (NEW)
    all_hits.extend(_detect_homoglyph_injection(user_input))

    # Layer 5: 零宽字符隐蔽注入 (NEW)
    all_hits.extend(_detect_zero_width_injection(user_input))

    # Layer 6: 大小写交替混淆 (NEW)
    all_hits.extend(_detect_case_alternation(user_input))

    return all_hits


#方法: 综合安全判定 (intent_filter + injection_detector)
"""
方法: is_safe(user_input, intent_cat), 综合 intent_filter + injection_detector 的安全判定

"""

def is_safe(user_input, intent_cat=None):
    injection_hits = detect_injection(user_input)
    if injection_hits:
        return False, injection_hits

    if intent_cat is not None and intent_cat in (IntentCategory.JAILBREAK, IntentCategory.DANGEROUS_ACTION):
        return False, [intent_cat.value]

    return True, []


"""
方法: safe_pipeline(), 完整安全流水线: 意图 → 注入 → LLM输出校验

Returns: (is_safe: bool, reason: str)
"""
def safe_pipeline(user_input, llm_output=None):
    # 第一道: 意图分类 (v2.0 含威胁评分)
    intent_cat, intent_hits, _ = classify_intent(user_input)
    if intent_cat in (IntentCategory.JAILBREAK, IntentCategory.DANGEROUS_ACTION):
        return False, "意图拦截: {}".format(intent_hits)

    # 第二道: 注入检测 (v2.0 六层)
    injection_hits = detect_injection(user_input)
    if injection_hits:
        return False, "注入拦截: {}".format(injection_hits)

    # 第三道: LLM 输出校验
    if llm_output:
        output_hits = validate_llm_output(llm_output)
        if output_hits:
            return False, "LLM输出拦截: {}".format(output_hits)

    if intent_cat == IntentCategory.OPS_ACTION:
        return True, "OPS_CONFIRM: 运维操作需二次确认"

    return True, "PASS"


#方法: 注入检测摘要 (用于仪表盘)
def get_injection_summary(user_input):
    hits = detect_injection(user_input)
    return {
        "injections_detected": len(hits),
        "is_clean": len(hits) == 0,
        "hits": hits,
        "layers": {
            "separator": any("SEPARATOR" in h for h in hits),
            "encoding": any("BASE64" in h or "HEX" in h for h in hits),
            "indirect": any("INDIRECT" in h for h in hits),
            "homoglyph": any("HOMOGLYPH" in h for h in hits),
            "zero_width": any("ZERO_WIDTH" in h for h in hits),
            "case_alternation": any("CASE_ALTERNATION" in h for h in hits),
        }
    }

"""
多层意图分类器 v2.0 — 安全护栏第一道防线

四层递进检测 + 加权评分:
Layer 1 — 越狱/角色劫持检测 (最高优先级, 一击即杀)
Layer 2 — 高危命令检测 (词边界正则 + 组合加权)
Layer 3 — 注入特殊字符检测 (分隔符/管道/重定向)
Layer 4 — 运维操作关键词 (需二次确认)

v2.0 改进:
- 词边界正则 (\\b) 消除误匹配 (如 "start" 不再匹配 "restart")
- 组合风险评分: 多条弱信号叠加 → 升级为高危
- 中文深层次越狱模式 (角色扮演/催眠/编码绕过)
- 威胁置信度 (0.0~1.0) 替代二元判断
"""
import re
from enum import Enum


class IntentCategory(str, Enum):
    JAILBREAK="jailbreak"         # 越狱尝试, 直接拒绝
    DANGEROUS_ACTION="dangerous_action"  # 高危操作, 拦截并告警
    OPS_ACTION="ops_action"       # 运维操作, 需二次确认
    SAFE_QUERY="safe_query"       # 安全查询, 直接放行
    UNKNOWN="unknown"


""" Layer 1: 越狱/角色劫持检测 (最高优先级) — v2.0: 增加中文越狱 + 词边界正则 """

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


""" Layer 2: 高危命令/模式检测 — v2.0: 全部 \\b 词边界, 消灭误匹配 """

_DANGEROUS_PATTERNS=[
    # 文件系统破坏
    (re.compile(r"\brm\s+(?:-r[fd]+\s+|--recursive\s+)/(?:etc|var|home|boot|usr|bin|sbin|lib|opt|root|sys|proc|dev)\b", re.IGNORECASE), "递归删除系统关键目录"),
    (re.compile(r"\brm\s+-(?:rf|fr|r\s+-f|f\s+-r)\b", re.IGNORECASE), "递归强制删除"),
    (re.compile(r"\brm\s+-r\b", re.IGNORECASE), "递归删除"),
    (re.compile(r"\bmkfs\.?\b", re.IGNORECASE), "格式化文件系统"),
    (re.compile(r"\bdd\s+if=", re.IGNORECASE), "磁盘直接写入"),
    (re.compile(r">\s*/dev/sd[a-z]", re.IGNORECASE), "覆盖磁盘设备"),
    (re.compile(r"\b(?:fdisk|parted|gdisk)\b.*?/dev/", re.IGNORECASE), "磁盘分区操作"),

    # 权限提升/破坏
    (re.compile(r"\bchmod\s+(?:-R\s+)?777\b", re.IGNORECASE), "开放所有权限"),
    (re.compile(r"\bchmod\s+(?:-R\s+)?(?:a\+rwx|ugo\+rwx|0777)\b", re.IGNORECASE), "开放所有权限 (变体)"),
    (re.compile(r"\bchown\s+-R\b", re.IGNORECASE), "递归修改所有者"),
    (re.compile(r"\bsetfacl\s+-m\b", re.IGNORECASE), "修改 ACL"),
    (re.compile(r"\bchattr\s+-i[a]?\b", re.IGNORECASE), "修改文件不可变属性"),

    # 网络危险操作
    (re.compile(r"\biptables\s+(?:-F|--flush)\b", re.IGNORECASE), "清空防火墙规则"),
    (re.compile(r"\biptables\s+-P\s+ACCEPT\b", re.IGNORECASE), "防火墙全放行"),
    (re.compile(r"\bnft\s+flush\s+ruleset\b", re.IGNORECASE), "清空 nftables 规则"),
    (re.compile(r"\b(?:ufw|firewall-cmd)\s+disable\b", re.IGNORECASE), "禁用防火墙"),

    # 系统破坏
    (re.compile(r"\b(?:shutdown|reboot|halt|poweroff|init\s*[06])\b", re.IGNORECASE), "系统关机/重启"),
    (re.compile(r"\bkill\s+-9\s+(?:-1|1)\b", re.IGNORECASE), "杀掉 init 进程"),
    (re.compile(r"\b(?:systemctl|service)\s+(?:stop|disable)\s+(?:sshd|systemd-journald|auditd)\b", re.IGNORECASE), "停止关键服务"),

    # 数据破坏
    (re.compile(r"\bDROP\s+(?:TABLE|DATABASE)\b", re.IGNORECASE), "删除数据库表/库"),
    (re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE), "批量删除数据库记录"),
    (re.compile(r"\bTRUNCATE\s+(?:TABLE\s+)?\w+", re.IGNORECASE), "截断数据库表"),

    # 远程下载执行
    (re.compile(r"\b(?:wget|curl)\s+\S+\s*(?:-[Oo]\s+|--output-document\s*=\s*|>\s*)(?:/etc/|/bin/|/usr/)", re.IGNORECASE), "下载覆盖系统文件"),
    (re.compile(r"\b(?:wget|curl)\s+\S+\s*\|\s*(?:ba)?sh\b", re.IGNORECASE), "下载并执行脚本"),
    (re.compile(r"\b(?:bash|python|perl|ruby)\s+-c\s*['\"].*?(?:rm\s+|wget\s+|curl\s+|nc\s+|/dev/tcp)", re.IGNORECASE), "解释器执行危险命令"),
    (re.compile(r"\bnc\s+(?:-e\s+|--exec\s+|-[lp]\s+\d+\s+-e\s+)", re.IGNORECASE), "netcat 反弹 shell"),

    # 内核/引导破坏
    (re.compile(r"\b(?:grub|efibootmgr|bootctl)\s+(?:install|update|remove)", re.IGNORECASE), "修改引导加载器"),
    (re.compile(r"\bmodprobe\s+-r\b", re.IGNORECASE), "卸载内核模块"),
]

# 组合升级规则: Layer 2 命中 ≥2 → DANGEROUS_ACTION
_COMBO_UPGRADE_THRESHOLD=2


""" Layer 3: 命令注入与特殊字符检测 — v2.0: 新增反斜杠续行/管道注入组合检测 """

_INJECTION_PATTERNS=[
    (re.compile(r";\s*(?:rm|wget|curl|bash|sh|nc|chmod|sudo|kill|reboot|shutdown|dd|mkfs|iptables|systemctl)\b", re.IGNORECASE), "分号+危险命令"),
    (re.compile(r"&&\s*(?:rm|wget|curl|bash|sh|nc|chmod|sudo|kill)\b", re.IGNORECASE), "&& + 危险命令"),
    (re.compile(r"\|\|\s*(?:rm|wget|curl|bash)\b", re.IGNORECASE), "|| + 危险命令"),
    (re.compile(r"\|\s*(?:ba)?sh\b", re.IGNORECASE), "管道到 shell"),
    (re.compile(r"\$\(\s*(?:rm|wget|curl|cat|id|whoami|uname|ps|ls)\b", re.IGNORECASE), "命令替换 $(...)"),
    (re.compile(r"`[^`]{2,}`"), "反引号执行"),
    (re.compile(r"\$\{\s*\w+"), "变量注入 ${...}"),
    (re.compile(r">\s*/[^>\s]{2,}"), "输出重定向到绝对路径"),
    (re.compile(r"\\\n\s*(?:rm|wget|curl|bash|chmod|sudo)\b", re.IGNORECASE), "反斜杠续行隐藏命令"),
    (re.compile(r"\bexec\s+(?:rm|bash|sh|nc|python)\b", re.IGNORECASE), "exec 执行命令"),
    (re.compile(r"\beval\s+['\"$]"), "eval 执行字符串"),
    (re.compile(r"\bsource\s+/(?:etc|tmp|var|dev)"), "source 执行绝对路径脚本"),
    (re.compile(r"\$'\s*(?:\\x[0-9a-fA-F]{2}){2,}"), "ANSI-C 引用编码绕过"),
    (re.compile(r"[<>]\s*\(\s*(?:rm|wget|curl|bash|sh|nc|cat)\b", re.IGNORECASE), "进程替换注入 <()/ >()"),
    (re.compile(r"<<\s*(?:EOF|END|FIN)\b.*?\b(?:rm|wget|curl|bash|sh)\b", re.IGNORECASE), "heredoc 注入"),
]


""" Layer 4: 运维操作关键词 (需确认) — v2.0: 词边界 + 中文 """

_OPS_KEYWORDS_CN=[
    (re.compile(r"(?:重启|停止|启动|禁用|启用|清空|卸载|安装|修改|删除|终止|杀掉|杀死|杀进程)"), "中文运维操作"),
]

_OPS_KEYWORDS_EN=[
    (re.compile(r"\b(?:restart|stop|start|disable|enable|remove|uninstall|kill|clean|purge)\b", re.IGNORECASE), "英文运维操作"),
]


#方法: 计算综合威胁评分 (0.0 ~ 1.0)
"""
方法: _calculate_threat_score(layer1_hits, layer2_hits, layer3_hits), Layer 1 → 1.0, Layer 2×2 → 0.9, Layer 2×1 → 0.7, Layer 3×3 → 0.6, Layer 3×1 → 0.3

"""

def _calculate_threat_score(layer1_hits, layer2_hits, layer3_hits):
    if layer1_hits:
        return 1.0
    if len(layer2_hits) >= _COMBO_UPGRADE_THRESHOLD:
        return 0.9
    if layer2_hits:
        return 0.7
    if len(layer3_hits) >= 3:
        return 0.6
    if layer3_hits:
        return 0.3
    return 0.0


"""
方法: classify_intent(), 多层意图分类, 始终返回 3 元组 (IntentCategory, hits, score)

Args:
    user_input: 用户输入字符串
    return_score: 是否计算威胁评分 (默认 False 时 score 返回 0.0)
"""
def classify_intent(user_input, return_score=False):
    lower=user_input.lower()
    all_hits=[]

    # Layer 1: 越狱检测
    l1_hits=[]
    for pattern in _JAILBREAK_PATTERNS:
        if pattern.search(lower):
            l1_hits.append("JAILBREAK: {}".format(pattern.pattern[:60]))
    # 中文深层次越狱
    for pattern in _JAILBREAK_CN_PATTERNS:
        if pattern.search(user_input):  # 原始输入, 保中文
            l1_hits.append("JAILBREAK_CN: {}".format(pattern.pattern[:60]))
    weak_count=sum(1 for p in _JAILBREAK_WEAK_PATTERNS if p.search(lower))
    if weak_count >= 2:
        l1_hits.append("JAILBREAK_COMBO: {} 个弱越狱信号叠加".format(weak_count))

    if l1_hits:
        return IntentCategory.JAILBREAK, l1_hits, 1.0

    # Layer 2: 高危命令检测
    l2_hits=[]
    for pattern, description in _DANGEROUS_PATTERNS:
        if pattern.search(lower):
            l2_hits.append("DANGEROUS: {} ({})".format(description, pattern.pattern[:50]))
    if l2_hits:
        score=_calculate_threat_score([], l2_hits, []) if return_score else 0.0
        return IntentCategory.DANGEROUS_ACTION, l2_hits, score

    # Layer 3: 注入字符检测
    l3_hits=[]
    for pattern, description in _INJECTION_PATTERNS:
        if pattern.search(user_input):  # 原始输入, 不 lower (保精确)
            l3_hits.append("INJECTION: {} — {}".format(description, pattern.pattern[:40]))
    if len(l3_hits) >= _COMBO_UPGRADE_THRESHOLD:
        score=_calculate_threat_score([], [], l3_hits) if return_score else 0.0
        return IntentCategory.DANGEROUS_ACTION, l3_hits, score
    if l3_hits:
        all_hits.extend(l3_hits)

    # Layer 4: 运维操作关键词
    ops_hits=[]
    for pattern, description in _OPS_KEYWORDS_CN:
        if pattern.search(user_input):
            ops_hits.append("OPS: {} — {}".format(description, pattern.pattern[:40]))
    for pattern, description in _OPS_KEYWORDS_EN:
        if pattern.search(lower):
            ops_hits.append("OPS: {} — {}".format(description, pattern.pattern[:40]))

    if ops_hits:
        all_hits.extend(ops_hits)
        score=0.2 if return_score else 0.0
        return IntentCategory.OPS_ACTION, all_hits, score

    # 默认: 安全查询 (保留 all_hits 中的低危注入信号)
    score=0.0 if return_score else 0.0
    return IntentCategory.SAFE_QUERY, all_hits if all_hits else [], score

"""
方法: get_threat_level(), 获取威胁等级摘要 (用于仪表盘)
返回 threat_score (0~1), threat_level (CRITICAL/HIGH/MEDIUM/LOW/SAFE), blocked, requires_confirmation
"""
def get_threat_level(user_input):
    cat, hits, score=classify_intent(user_input, return_score=True)
    if score >= 0.9:
        level="CRITICAL"
    elif score >= 0.7:
        level="HIGH"
    elif score >= 0.3:
        level="MEDIUM"
    elif score >= 0.1:
        level="LOW"
    else:
        level="SAFE"

    return {
        "category": cat.value,
        "threat_score": score,
        "threat_level": level,
        "hits": hits,
        "blocked": cat in (IntentCategory.JAILBREAK, IntentCategory.DANGEROUS_ACTION),
        "requires_confirmation": cat == IntentCategory.OPS_ACTION,
    }

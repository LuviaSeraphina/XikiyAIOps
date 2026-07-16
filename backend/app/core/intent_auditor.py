"""
动态意图审计模块 v1.0 — 安全护栏第五道防线

功能:
1. 危险意图模式匹配 — 已知恶意/高危意图关键词检测
2. 意图漂移检测 — 与历史意图对比, 检测突变
3. 意图-工具一致性校验 — 检查 Planner 规划的步骤是否与意图匹配
4. 输出审计结果: {passed, risk_score, alerts, recommendation}

集成点: langchain_agent 规划阶段后, 执行阶段前
"""
import re
import logging
from typing import List, Dict, Any, Optional

_logger=logging.getLogger("xikiy_aiops.intent_auditor")

# ══════════════════════════════════════════
# 1. 危险意图模式库
# ══════════════════════════════════════════

#高风险意图关键词 → 风险分 (0-100)
_DANGEROUS_INTENT_PATTERNS={
    #致命操作 (90-100分)
    "删除.*用户":95,
    "删除.*全部":98,
    "格式化.*磁盘":100,
    "清空.*数据库":100,
    "关闭.*防火墙":90,
    "禁用.*安全":92,
    "篡改.*日志":95,
    "提权|越权|绕过.*权限":100,
    "后门|反弹shell|reverse.shell":100,
    r"rm\s+-rf\s+/":100,
    
    #高危操作 (70-89分)
    "停止.*服务":75,
    "卸载.*关键|卸载.*内核":85,
    "修改.*密码":78,
    "添加.*管理员|创建.*root":88,
    "关闭.*SELinux|禁用.*AppArmor":82,
    "修改.*sudoers":90,
    "写入.*/etc/":80,
    
    #可疑操作 (50-69分)
    "扫描.*端口|端口.*扫描":55,
    "暴力.*破解|密码.*爆破":65,
    "下载.*执行|curl.*pipe.*sh":70,
    "隐藏.*进程|进程.*隐藏":68,
    
    #异常指令 (30-49分)
    "拒绝.*服务|DDoS":45,
    "伪造.*日志|伪造.*记录":48,
    "窃取.*信息|导出.*敏感":60,
}

#工具-意图不匹配模式 (某工具不应出现在某种意图下)
_TOOL_INTENT_MISMATCH={
    "user_delete":["查看","检查","巡检","监控","查询","列表"],
    "process_kill":["查看","检查","巡检","监控"],
    "firewall_rule_del":["查看","检查","巡检"],
    "package_remove":["查看","检查","巡检","更新"],
}


# ══════════════════════════════════════════
# 2. 审计函数
# ══════════════════════════════════════════

def audit_intent(intent: str, steps: List[Dict], history_intents: List[str] = None) -> Dict[str,Any]:
    """
    审计单次意图, 返回审计结果
    
    Args:
        intent: Planner 输出的意图文本
        steps: 规划的步骤列表
        history_intents: 历史意图列表 (最近N次), 用于漂移检测
    
    Returns:
        {passed, risk_score, alerts, recommendation, blocked}
    """
    alerts=[]
    risk_score=0
    
    #1. 危险模式匹配 (内置 + 自定义规则)
    extra_patterns,extra_mismatch=_load_extra_rules()
    all_patterns={**_DANGEROUS_INTENT_PATTERNS, **extra_patterns}
    for pattern, score in all_patterns.items():
        if re.search(pattern, intent, re.IGNORECASE):
            risk_score=max(risk_score, score)
            alerts.append({
                "type":"dangerous_pattern",
                "pattern":pattern,
                "score":score,
                "msg":f"意图命中危险模式: '{pattern}' → 风险分 {score}",
            })
    
    #2. 工具-意图一致性 (内置 + 自定义)
    all_mismatch={**_TOOL_INTENT_MISMATCH, **extra_mismatch}
    for step in steps:
        tool_name=step.get("tool","")
        if tool_name in all_mismatch:
            safe_keywords=all_mismatch[tool_name]
            if any(kw in intent for kw in safe_keywords):
                risk_score=max(risk_score, 60)
                alerts.append({
                    "type":"tool_intent_mismatch",
                    "tool":tool_name,
                    "intent":intent[:50],
                    "score":60,
                    "msg":f"工具 '{tool_name}' 与意图 '{intent[:30]}...' 不匹配 (疑似危险操作伪装)",
                })
    
    #3. 意图漂移检测 (相比历史)
    if history_intents and len(history_intents)>=2:
        drift_score=_detect_intent_drift(intent, history_intents)
        if drift_score>40:
            risk_score=max(risk_score, drift_score)
            alerts.append({
                "type":"intent_drift",
                "score":drift_score,
                "msg":f"意图漂移: 从 '{history_intents[-1][:30]}' 突变至 '{intent[:30]}' (漂移分 {drift_score})",
            })
    
    #4. 判定
    if risk_score>=90:
        passed=False
        blocked=True
        recommendation="致命危险意图, 已自动拦截。请管理员审核。"
    elif risk_score>=70:
        passed=False
        blocked=False
        recommendation="高危意图, 需要二次确认。建议审查操作步骤。"
    elif risk_score>=50:
        passed=True
        blocked=False
        recommendation="可疑意图, 已放行但建议关注。"
    else:
        passed=True
        blocked=False
        recommendation="意图审计通过。"
    
    result={
        "passed":passed,
        "blocked":blocked,
        "risk_score":risk_score,
        "alerts":alerts,
        "recommendation":recommendation,
        "intent":intent,
    }
    
    if alerts:
        _logger.warning(f"意图审计: risk={risk_score}, alerts={len(alerts)}, blocked={blocked}, intent={intent[:60]}")
    
    return result


def _detect_intent_drift(current_intent: str, history: List[str]) -> int:
    """
    检测意图漂移程度 (0-100)
    
    比较当前意图与历史意图的关键词变化,
    如果从"查看/巡检"突然变成"删除/关闭", 则漂移分高
    """
    if not history:
        return 0
    
    #低风险操作词
    safe_ops=["查看","检查","巡检","监控","查询","列表","统计","显示","获取"]
    #高风险操作词
    danger_ops=["删除","停止","关闭","禁用","卸载","修改","创建","安装","写入","格式化"]
    
    #检查历史意图是否主要为低风险
    hist_safe=sum(1 for op in safe_ops if any(op in h for h in history[-3:]))
    hist_danger=sum(1 for op in danger_ops if any(op in h for h in history[-3:]))
    
    #当前意图是否含高风险词
    cur_danger=sum(1 for op in danger_ops if op in current_intent)
    cur_safe=sum(1 for op in safe_ops if op in current_intent)
    
    #历史安全→当前危险: 高漂移
    if hist_safe>=2 and cur_danger>=1:
        return 75
    
    #历史安全→当前有风险词
    if hist_safe>=1 and hist_danger==0 and cur_danger>=1:
        return 60
    
    #历史有危险→当前危险(累计升级)
    if hist_danger>=1 and cur_danger>=2:
        return 45
    
    #无明显漂移
    return 10 if cur_danger>0 else 0


def audit_steps_safety(steps: List[Dict]) -> Dict[str,Any]:
    """
    审计步骤安全性 — 检查是否有步骤组合构成攻击链
    
    如: 关闭防火墙 → 添加用户 → 提权 = 攻击链
    """
    tool_sequence=[s.get("tool","") for s in steps]
    alerts=[]
    
    #攻击链模式检测
    _ATTACK_CHAINS=[
        (["firewall_rule_del","user_create","user_password"],"防火墙开后门攻击链"),
        (["process_kill","process_kill","process_kill"],"批量杀进程攻击"),
        (["package_remove","package_remove","package_remove"],"批量卸载攻击"),
        (["user_create","user_lock"],"用户操作异常组合"),
    ]
    
    for chain, desc in _ATTACK_CHAINS:
        #检查子序列是否匹配
        if _subsequence_match(tool_sequence, chain):
            alerts.append({
                "type":"attack_chain",
                "chain":chain,
                "msg":f"检测到疑似攻击链: {desc}",
            })
    
    return {
        "safe":len(alerts)==0,
        "alerts":alerts,
        "tools_used":tool_sequence,
    }


def _subsequence_match(sequence, pattern):
    """检查 pattern 是否为 sequence 的子序列"""
    it=iter(sequence)
    return all(p in it for p in pattern)


def _load_extra_rules():
    """
    从 sensitive_rules.json 加载自定义意图审计规则
    
    返回: (extra_patterns: dict, extra_mismatch: dict)
    """
    extra_patterns={}
    extra_mismatch={}
    try:
        import json
        from pathlib import Path
        rules_file=Path(__file__).resolve().parent.parent.parent / "config" / "sensitive_rules.json"
        if rules_file.exists():
            with open(rules_file,"r",encoding="utf-8") as f:
                rules=json.load(f)
            audit_rules=rules.get("intent_audit",{})
            #加载额外危险模式
            for entry in audit_rules.get("extra_dangerous_patterns",[]):
                if isinstance(entry,dict) and "pattern" in entry:
                    extra_patterns[entry["pattern"]]=entry.get("score",70)
            #加载额外工具-意图不匹配
            extra_mismatch=audit_rules.get("extra_tool_intent_mismatch",{})
    except Exception:
        pass
    return extra_patterns, extra_mismatch

"""
SecurityAgent — 输入审查、工具审批、事后审计

不调MCP Tool, 纯逻辑守门员
"""
import json
import logging
from typing import Dict, Tuple
from app.core.intent_filter import classify_intent, IntentCategory
from app.core.injection_detector import detect_injection
from app.mcp_plugins._common import sanitize_response

_logger=logging.getLogger("xikiy_aiops.security_agent")


class SecurityAgent:
    """安全守门员 — 三道防线"""

    # ── 第一道: 输入审查 ──────────────────

    def review_input(self, user_input:str)->Tuple[bool,str,str]:
    # 审查用户输入         Returns: (allowed, reason, risk_level)           allowed=True,  r
        if not user_input or not user_input.strip():
            return False, "输入为空", "blocked"

        cat, hits, score=classify_intent(user_input, return_score=True)

        if cat==IntentCategory.JAILBREAK:
            return False, f"越狱尝试 (评分 {score:.1f})", "jailbreak"

        if cat==IntentCategory.DANGEROUS_ACTION:
            detail=hits[0] if hits else "高危操作"
            return False, f"高危操作: {detail} (评分 {score:.1f})", "dangerous"

        injection_hits=detect_injection(user_input)
        if injection_hits:
            return False, f"注入攻击: {injection_hits[0]}", "injection"

        if cat==IntentCategory.OPS_ACTION:
            return True, "CONFIRM", "restricted"

        return True, "OK", "safe"

    # ── 第二道: 工具审批 ──────────────────

    def approve_tool(self, tool_name:str, arguments:Dict, risk_level:str)->Tuple[bool,str]:
    # 审批每次工具调用         Returns: (approved, reason)
        #参数注入检测
        args_str=json.dumps(arguments, ensure_ascii=False)
        injection_hits=detect_injection(args_str)
        if injection_hits:
            _logger.warning(f"安全拦截: {tool_name} 参数注入 — {injection_hits[0]}")
            return False, f"参数注入拦截: {injection_hits[0]}"

        #权限检查
        if risk_level=="blocked":
            return False, "工具已被阻止"

        if risk_level in ("dangerous","restricted"):
            #需要用户二次确认 — 抛出确认请求
            return True, "NEED_CONFIRM"  #外部Orchestrator处理确认流程

        if risk_level=="read_only":
            return True, "自动放行"

        return False, f"未知风险等级: {risk_level}"

    # ── 第三道: 事后审计 ──────────────────

    def audit(self, session_id:str, tool_name:str, arguments:Dict, result:Dict):
    # 记录工具调用审计日志
        try:
            #脱敏后记录
            safe_result=sanitize_response(tool_name, result.get("data",{})) if result else {}
            audit_entry={
                "session_id":session_id,
                "tool":tool_name,
                "args":json.dumps(arguments, ensure_ascii=False),
                "risk_level":result.get("risk_level","unknown") if result else "unknown",
                "success":not bool(result.get("summary",{}).get("error")) if result else True,
            }
            _logger.info(f"审计: {json.dumps(audit_entry, ensure_ascii=False)}")
            #TODO: 写入 audit_log 表
        except Exception as e:
            _logger.warning(f"审计记录失败: {e}")

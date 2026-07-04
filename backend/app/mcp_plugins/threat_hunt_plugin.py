"""
威胁狩猎 Agent — 基于 MITRE ATT&CK 框架的攻击链还原

通过编排现有安全工具, 主动搜索可疑行为, 关联分析生成攻击链报告。

覆盖 ATT&CK 战术阶段:
- 初始访问 (Initial Access)
- 执行 (Execution)
- 持久化 (Persistence)
- 权限提升 (Privilege Escalation)
- 防御规避 (Defense Evasion)
- 凭证访问 (Credential Access)
- 横向移动 (Lateral Movement)
- 数据外传 (Exfiltration)

"""
import asyncio
import logging
import time
from app.mcp_plugins._common import make_response as _make_response, error_response as _error_response
from app.mcp_plugins.security_plugin import (
    security_auth_failures,
    security_crontab_audit,
    security_suid_scan,
    security_kernel_modules,
    security_user_audit,
    security_open_files,
)
from app.mcp_plugins.network_plugin import network_connections_summary
from app.mcp_plugins.process_plugin import process_zombie_scan_handler

#日志配置
logger=logging.getLogger(__name__)

#威胁检测阈值
THREAT_THRESHOLDS={
    "ssh_brute_force_min_failures": 100,
    "suspicious_connections_min_count": 5,
    "zombie_process_min_count": 10,
    "max_findings_count": 50,
    "tool_timeout_seconds": 30,
}

#MITRE ATT&CK 战术阶段映射
ATTACK_PHASES={
    "Initial Access": {
        "tactic_id": "TA0001",
        "indicators": ["ssh_failures", "suspicious_login"]
    },
    "Execution": {
        "tactic_id": "TA0002",
        "indicators": ["crontab_backdoor", "suspicious_process", "zombie_process"]
    },
    "Persistence": {
        "tactic_id": "TA0003",
        "indicators": ["suid_backdoor", "crontab_persistence", "kernel_module"]
    },
    "Privilege Escalation": {
        "tactic_id": "TA0004",
        "indicators": ["suid_abnormal", "user_privilege_abuse", "zero_uid_user"]
    },
    "Defense Evasion": {
        "tactic_id": "TA0005",
        "indicators": ["kernel_module_hidden", "process_hide"]
    },
    "Credential Access": {
        "tactic_id": "TA0006",
        "indicators": ["ssh_brute_force", "empty_password", "password_policy_weak"]
    },
    "Lateral Movement": {
        "tactic_id": "TA0008",
        "indicators": ["suspicious_outbound", "ssh_tunnel"]
    },
    "Exfiltration": {
        "tactic_id": "TA0010",
        "indicators": ["outbound_anomaly", "data_transfer"]
    }
}

#威胁等级评分
SEVERITY_SCORES={
    "suid_backdoor": 90,
    "kernel_module_hidden": 85,
    "crontab_backdoor": 80,
    "ssh_brute_force": 70,
    "empty_password": 75,
    "zero_uid_user": 80,
    "user_privilege_abuse": 65,
    "suspicious_outbound": 60,
    "outbound_anomaly": 55,
    "zombie_process": 40,
    "high_file_handles": 50,
}


"""
方法: threat_hunt(), 执行一轮完整的威胁狩猎扫描

"""
def threat_hunt():
    """
    执行一轮完整的威胁狩猎扫描
    编排安全工具, 关联分析生成攻击链报告
    """
    start_time=time.time()
    try:
        #运行异步扫描（使用 asyncio.run 自动处理事件循环）
        results=asyncio.run(_run_all_checks())
        
        #提取工具结果
        tool_outputs={
            "auth_failures": results.get("auth_failures", {}),
            "crontab_audit": results.get("crontab_audit", {}),
            "suid_scan": results.get("suid_scan", {}),
            "kernel_modules": results.get("kernel_modules", {}),
            "user_audit": results.get("user_audit", {}),
            "open_files": results.get("open_files", {}),
            "network": results.get("network", {}),
            "zombie_process": results.get("zombie_process", {}),
        }
        
        #提取可疑发现
        findings=_extract_findings(tool_outputs)
        
        #映射到 ATT&CK 战术阶段
        attack_chain=_map_to_attack_phases(findings)
        
        #生成报告
        report=_generate_report(attack_chain, findings, tool_outputs)
        report["execution_time_seconds"]=round(time.time()-start_time, 2)
        
        return _make_response("threat_hunt",
            data={
                "findings": findings,
                "attack_chain": attack_chain,
                "report": report,
                "tool_outputs": tool_outputs,
            },
            summary={
                "total_findings": len(findings),
                "attack_phases_hit": [p["phase"] for p in attack_chain],
                "risk_score": report["risk_score"],
                "risk_level": report["risk_level"],
            },
        )
    except Exception as e:
        return _error_response("threat_hunt", e)


async def _run_all_checks():
    """并行执行所有安全检查"""
    results=await asyncio.gather(
        _safe_call(security_auth_failures, hours=24),
        _safe_call(security_crontab_audit),
        _safe_call(security_suid_scan),
        _safe_call(security_kernel_modules),
        _safe_call(security_user_audit),
        _safe_call(security_open_files, top_n=20),
        _safe_call(network_connections_summary),
        _safe_call(process_zombie_scan_handler),
        return_exceptions=True
    )
    
    return {
        "auth_failures": results[0] if not isinstance(results[0], Exception) else {},
        "crontab_audit": results[1] if not isinstance(results[1], Exception) else {},
        "suid_scan": results[2] if not isinstance(results[2], Exception) else {},
        "kernel_modules": results[3] if not isinstance(results[3], Exception) else {},
        "user_audit": results[4] if not isinstance(results[4], Exception) else {},
        "open_files": results[5] if not isinstance(results[5], Exception) else {},
        "network": results[6] if not isinstance(results[6], Exception) else {},
        "zombie_process": results[7] if not isinstance(results[7], Exception) else {},
    }


async def _safe_call(func, **kwargs):
    """安全调用: 带超时控制, 捕获异常并记录日志"""
    timeout=THREAT_THRESHOLDS["tool_timeout_seconds"]
    try:
        #使用 to_thread 在线程中执行同步函数，避免阻塞
        result=await asyncio.wait_for(
            asyncio.to_thread(func, **kwargs),
            timeout=timeout
        )
        return result
    except asyncio.TimeoutError:
        logger.warning(f"安全检查工具 {func.__name__} 执行超时 ({timeout}s)")
        return {"error": "timeout", "tool": func.__name__}
    except Exception as e:
        logger.warning(f"安全检查工具 {func.__name__} 执行失败: {e}")
        return {"error": str(e), "tool": func.__name__}


def _extract_findings(tool_outputs):
    """从工具输出中提取可疑发现"""
    findings=[]
    
    #1. SUID 后门检测
    suid_data=tool_outputs.get("suid_scan", {}).get("data", {})
    for item in suid_data.get("suspicious", []):
        findings.append({
            "type": "suid_backdoor",
            "severity": SEVERITY_SCORES.get("suid_backdoor", 80),
            "detail": f"SUID 可疑文件: {item.get('path', 'unknown')}",
            "evidence": item
        })
    
    #2. Crontab 后门检测
    crontab_data=tool_outputs.get("crontab_audit", {}).get("data", {})
    for item in crontab_data.get("suspicious", []):
        findings.append({
            "type": "crontab_backdoor",
            "severity": SEVERITY_SCORES.get("crontab_backdoor", 80),
            "detail": f"可疑定时任务: {item.get('user', 'unknown')} - {item.get('command', '')}",
            "evidence": item
        })
    
    #3. 内核模块检测
    kernel_data=tool_outputs.get("kernel_modules", {}).get("data", {})
    for item in kernel_data.get("suspicious", []):
        findings.append({
            "type": "kernel_module_hidden",
            "severity": SEVERITY_SCORES.get("kernel_module_hidden", 85),
            "detail": f"可疑内核模块: {item.get('name', 'unknown')}",
            "evidence": item
        })
    
    #4. SSH 暴力破解检测
    auth_data=tool_outputs.get("auth_failures", {}).get("data", {})
    ssh_failures=auth_data.get("ssh_failures", 0)
    if ssh_failures > THREAT_THRESHOLDS["ssh_brute_force_min_failures"]:
        findings.append({
            "type": "ssh_brute_force",
            "severity": SEVERITY_SCORES.get("ssh_brute_force", 70),
            "detail": f"SSH 登录失败 {ssh_failures} 次",
            "evidence": {"ssh_failures": ssh_failures}
        })
    
    #5. 用户权限异常检测
    user_data=tool_outputs.get("user_audit", {}).get("data", {})
    for item in user_data.get("zero_uid_users", []):
        if item.get("username") != "root":
            findings.append({
                "type": "zero_uid_user",
                "severity": SEVERITY_SCORES.get("zero_uid_user", 80),
                "detail": f"非 root 用户拥有 UID 0: {item.get('username', 'unknown')}",
                "evidence": item
            })
    
    for item in user_data.get("empty_password_users", []):
        findings.append({
            "type": "empty_password",
            "severity": SEVERITY_SCORES.get("empty_password", 75),
            "detail": f"空密码用户: {item.get('username', 'unknown')}",
            "evidence": item
        })
    
    #6. 僵尸进程检测
    zombie_data=tool_outputs.get("zombie_process", {}).get("data", {})
    zombie_count=zombie_data.get("zombie_count", 0)
    if zombie_count > THREAT_THRESHOLDS["zombie_process_min_count"]:
        findings.append({
            "type": "zombie_process",
            "severity": SEVERITY_SCORES.get("zombie_process", 40),
            "detail": f"检测到 {zombie_count} 个僵尸进程",
            "evidence": zombie_data.get("zombies", [])[:10]  #只保留前10个
        })
    
    #7. 网络连接异常检测
    network_data=tool_outputs.get("network", {}).get("data", {})
    suspicious_connections=network_data.get("suspicious_connections", 0)
    if suspicious_connections > THREAT_THRESHOLDS["suspicious_connections_min_count"]:
        findings.append({
            "type": "suspicious_outbound",
            "severity": SEVERITY_SCORES.get("suspicious_outbound", 60),
            "detail": f"检测到 {suspicious_connections} 个可疑出站连接",
            "evidence": network_data.get("suspicious", [])[:20]  #只保留前20个
        })
    
    #限制 findings 数量，避免数据过大
    max_findings=THREAT_THRESHOLDS["max_findings_count"]
    if len(findings) > max_findings:
        logger.warning(f"Finding 数量过多 ({len(findings)})，截断到 {max_findings} 条")
        findings=findings[:max_findings]
    
    return findings


def _map_to_attack_phases(findings):
    """将发现映射到 MITRE ATT&CK 战术阶段"""
    attack_chain=[]
    
    for phase_name, phase_info in ATTACK_PHASES.items():
        phase_findings=[]
        for finding in findings:
            if finding["type"] in phase_info["indicators"]:
                phase_findings.append(finding)
        
        if phase_findings:
            max_severity=max(f["severity"] for f in phase_findings)
            attack_chain.append({
                "phase": phase_name,
                "tactic_id": phase_info["tactic_id"],
                "findings_count": len(phase_findings),
                "max_severity": max_severity,
                "findings": phase_findings
            })
    
    #按战术阶段顺序排序
    attack_chain.sort(key=lambda x: x["tactic_id"])
    return attack_chain


def _generate_report(attack_chain, findings, tool_outputs):
    """生成威胁狩猎报告"""
    #计算风险评分（综合最高值和平均值）
    if findings:
        max_severity=max(f["severity"] for f in findings)
        avg_severity=sum(f["severity"] for f in findings) / len(findings)
        #最高值占 60%，平均值占 40%
        risk_score=min(100, max_severity * 0.6 + avg_severity * 0.4)
    else:
        risk_score=0
    
    #风险等级
    if risk_score >= 80:
        risk_level="critical"
    elif risk_score >= 60:
        risk_level="high"
    elif risk_score >= 40:
        risk_level="medium"
    else:
        risk_level="low"
    
    #生成摘要
    summary_parts=[]
    for phase in attack_chain:
        summary_parts.append(f"{phase['phase']}: {phase['findings_count']} 个可疑发现")
    
    summary="; ".join(summary_parts) if summary_parts else "未发现可疑威胁"
    
    #生成建议
    recommendations=[]
    if risk_level in ["critical", "high"]:
        recommendations.append("立即隔离受影响系统, 进行深度取证分析")
    if any(f["type"] == "suid_backdoor" for f in findings):
        recommendations.append("审查所有 SUID 文件, 移除不必要的 SUID 位")
    if any(f["type"] == "crontab_backdoor" for f in findings):
        recommendations.append("审计所有 crontab, 删除可疑定时任务")
    if any(f["type"] == "ssh_brute_force" for f in findings):
        recommendations.append("启用 fail2ban, 限制 SSH 登录尝试次数")
    if any(f["type"] == "empty_password" for f in findings):
        recommendations.append("强制所有用户设置强密码")
    
    return {
        "risk_score": round(risk_score, 2),
        "risk_level": risk_level,
        "summary": summary,
        "recommendations": recommendations,
        "tools_executed": list(tool_outputs.keys()),
    }

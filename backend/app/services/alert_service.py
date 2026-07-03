"""
告警处理服务 — 接收 Alertmanager webhook → Agent 自动诊断 → 存库

核心流程:
  1. 解析 Alertmanager JSON
  2. 去重检查 (fingerprint + 5 分钟窗口)
  3. 创建 Alert 记录 (status=processing)
  4. 生成诊断 prompt, 调 Orchestrator
  5. 收集工具调用结果 + LLM 分析
  6. 更新 Alert 记录 (status=resolved/ignored)
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from sqlalchemy import select
from app.db import async_session
from app.models.alert import Alert
from app.agents.orchestrator import Orchestrator

_logger=logging.getLogger("xikiy_aiops.alert")

#去重窗口: 同一 fingerprint 5 分钟内不重复处理
_DEDUP_WINDOW_MINUTES=int(os.getenv("ALERT_DEDUP_WINDOW", "5"))

#Webhook Secret (环境变量配置, 不配置则不校验)
_WEBHOOK_SECRET=os.getenv("ALERT_WEBHOOK_SECRET", "")


async def verify_webhook_secret(secret_header: str) -> bool:
    """校验 webhook secret"""
    if not _WEBHOOK_SECRET:
        return True  #未配置则不校验
    return secret_header == _WEBHOOK_SECRET


async def is_duplicate(fingerprint: str) -> bool:
    """检查是否 5 分钟内已有相同 fingerprint 的告警"""
    if not fingerprint:
        return False
    cutoff=datetime.now() - timedelta(minutes=_DEDUP_WINDOW_MINUTES)
    async with async_session() as db:
        result=await db.execute(
            select(Alert).where(
                Alert.fingerprint == fingerprint,
                Alert.created_at >= cutoff
            )
        )
        return result.scalar_one_or_none() is not None


async def process_alerts(payload: Dict[str, Any]) -> list:
    """
    处理 Alertmanager webhook payload

    返回: [{"alert_id": "...", "alert_name": "...", "status": "processing|duplicate|error"}]
    """
    results=[]
    alerts=payload.get("alerts", [])

    for alert_data in alerts:
        result=await _process_single_alert(alert_data)
        results.append(result)

    return results


async def _process_single_alert(alert_data: Dict[str, Any]) -> Dict[str, Any]:
    """处理单条告警"""
    labels=alert_data.get("labels", {})
    annotations=alert_data.get("annotations", {})
    fingerprint=alert_data.get("fingerprint", "")
    alert_name=labels.get("alertname", "UnknownAlert")
    instance=labels.get("instance", "")
    severity=labels.get("severity", "warning")
    status=alert_data.get("status", "firing")

    #去重检查
    if await is_duplicate(fingerprint):
        _logger.info(f"告警去重: {alert_name} ({fingerprint})")
        return {
            "alert_id": None,
            "alert_name": alert_name,
            "fingerprint": fingerprint,
            "status": "duplicate",
            "message": f"5 分钟内已处理过相同告警, 跳过"
        }

    #创建告警记录
    starts_at=None
    if alert_data.get("startsAt"):
        try:
            starts_at=datetime.fromisoformat(alert_data["startsAt"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

    async with async_session() as db:
        alert=Alert(
            fingerprint=fingerprint,
            alert_name=alert_name,
            instance=instance,
            severity=severity,
            status=status,
            labels=labels,
            annotations=annotations,
            starts_at=starts_at,
        )
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        alert_id=alert.id

    _logger.info(f"告警已记录: {alert_id} — {alert_name} ({severity})")

    #已 resolved 的告警不需要诊断
    if status == "resolved":
        async with async_session() as db:
            result=await db.execute(select(Alert).where(Alert.id == alert_id))
            alert=result.scalar_one_or_none()
            if alert:
                alert.resolved=True
                alert.resolved_at=datetime.now()
                alert.resolution="告警已自动恢复"
                await db.commit()
        return {
            "alert_id": alert_id,
            "alert_name": alert_name,
            "fingerprint": fingerprint,
            "status": "resolved",
            "message": "告警已恢复"
        }

    #异步触发诊断 (不阻塞 webhook 响应)
    asyncio.create_task(_run_diagnosis(alert_id, alert_name, instance, severity, annotations))

    return {
        "alert_id": alert_id,
        "alert_name": alert_name,
        "fingerprint": fingerprint,
        "status": "processing",
        "message": "告警已接收, Agent 正在诊断"
    }


async def _run_diagnosis(alert_id: str, alert_name: str, instance: str, severity: str, annotations: Dict):
    """异步运行 Agent 诊断"""
    summary=annotations.get("summary", "")
    description=annotations.get("description", "")

    #生成诊断 prompt
    prompt=f"""收到一条 Prometheus 告警, 请诊断原因并提供修复建议。

告警信息:
- 告警名: {alert_name}
- 实例: {instance}
- 严重度: {severity}
- 摘要: {summary}
- 描述: {description}

请执行以下步骤:
1. 查看当前系统状态 (CPU/内存/磁盘/网络)
2. 检查相关进程和日志
3. 如果知识库有匹配的修复方案, 一并给出
4. 给出根因分析和修复建议
"""

    try:
        orch=Orchestrator()
        tool_results=[]
        llm_analysis=""

        async for event in orch.run(prompt, session_id=f"alert-{alert_id}"):
            event_type=event.get("event", "")
            data=event.get("data", {})

            if event_type == "tool_result":
                tool_results.append({
                    "agent": data.get("agent", ""),
                    "tool": data.get("tool", ""),
                    "result": data.get("result", {}),
                })
            elif event_type == "token":
                llm_analysis += data.get("text", "")

        #提取工具列表
        tools_called=list(set(
            f"{tr['agent']}/{tr['tool']}" for tr in tool_results
        ))

        #生成修复建议 (从 LLM 分析中提取)
        resolution=llm_analysis[:500] if llm_analysis else "诊断完成, 请查看详细分析"

        #更新告警记录
        async with async_session() as db:
            result=await db.execute(select(Alert).where(Alert.id == alert_id))
            alert=result.scalar_one_or_none()
            if alert:
                alert.diagnosis={
                    "tools_called": tools_called,
                    "tool_results": tool_results,
                    "llm_analysis": llm_analysis,
                }
                alert.resolution=resolution
                alert.status="diagnosed"
                await db.commit()

        _logger.info(f"告警诊断完成: {alert_id} — 调用了 {len(tools_called)} 个工具")

    except Exception as e:
        _logger.error(f"告警诊断失败: {alert_id} — {e}", exc_info=True)
        async with async_session() as db:
            result=await db.execute(select(Alert).where(Alert.id == alert_id))
            alert=result.scalar_one_or_none()
            if alert:
                alert.status="error"
                alert.diagnosis={"error": str(e)}
                await db.commit()

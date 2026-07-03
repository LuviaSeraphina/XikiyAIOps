"""
告警 API — 接收 Alertmanager webhook + 告警列表/详情

POST /api/alerts/webhook         — 接收 Alertmanager webhook
GET  /api/alerts/list            — 告警列表 (分页)
GET  /api/alerts/{alert_id}      — 告警详情 (含诊断结果)
POST /api/alerts/{alert_id}/resolve  — 标记告警已解决
"""
from fastapi import APIRouter, Request, Depends, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from app.db import get_db
from app.models.alert import Alert
from app.services.alert_service import process_alerts, verify_webhook_secret

router=APIRouter()


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    x_webhook_secret: str = Header(None, alias="X-Webhook-Secret"),
):
    """接收 Alertmanager webhook"""
    #Secret 校验
    if not await verify_webhook_secret(x_webhook_secret or ""):
        return {"code": 401, "message": "Webhook secret 不匹配"}

    payload=await request.json()
    results=await process_alerts(payload)

    return {
        "code": 0,
        "data": results,
        "message": f"已处理 {len(results)} 条告警",
    }


@router.get("/list")
async def alert_list(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=50),
    status: str = Query(None),
    severity: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """告警列表 (分页, 支持按状态/严重度过滤)"""
    q=select(Alert).order_by(Alert.created_at.desc())
    if status:
        q=q.where(Alert.status == status)
    if severity:
        q=q.where(Alert.severity == severity)

    #总数
    count_q=select(func.count(Alert.id))
    if status:
        count_q=count_q.where(Alert.status == status)
    if severity:
        count_q=count_q.where(Alert.severity == severity)
    total_result=await db.execute(count_q)
    total=total_result.scalar() or 0

    #分页
    q=q.offset((page-1)*size).limit(size)
    result=await db.execute(q)
    items=result.scalars().all()

    return {
        "code": 0,
        "data": {
            "items": [_alert_to_dict(a) for a in items],
            "total": total,
            "page": page,
            "page_size": size,
        },
        "message": "ok",
    }


@router.get("/{alert_id}")
async def alert_detail(alert_id: str, db: AsyncSession = Depends(get_db)):
    """告警详情 (含 Agent 诊断结果)"""
    result=await db.execute(select(Alert).where(Alert.id == alert_id))
    alert=result.scalar_one_or_none()
    if not alert:
        return {"code": 404, "message": f"告警 {alert_id} 不存在"}

    return {
        "code": 0,
        "data": _alert_to_dict(alert, include_diagnosis=True),
        "message": "ok",
    }


@router.post("/{alert_id}/resolve")
async def resolve_alert(alert_id: str, db: AsyncSession = Depends(get_db)):
    """标记告警已解决"""
    result=await db.execute(select(Alert).where(Alert.id == alert_id))
    alert=result.scalar_one_or_none()
    if not alert:
        return {"code": 404, "message": f"告警 {alert_id} 不存在"}

    alert.resolved=True
    alert.resolved_at=datetime.now()
    alert.status="resolved"
    await db.commit()

    return {"code": 0, "message": "告警已标记为已解决"}


def _alert_to_dict(alert: Alert, include_diagnosis: bool = False) -> dict:
    """Alert 模型转 dict"""
    d={
        "id": alert.id,
        "fingerprint": alert.fingerprint,
        "alert_name": alert.alert_name,
        "instance": alert.instance,
        "severity": alert.severity,
        "status": alert.status,
        "labels": alert.labels or {},
        "annotations": alert.annotations or {},
        "starts_at": alert.starts_at.isoformat() if alert.starts_at else None,
        "resolved": alert.resolved,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "resolution": alert.resolution,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
        "updated_at": alert.updated_at.isoformat() if alert.updated_at else None,
    }
    if include_diagnosis:
        d["diagnosis"] = alert.diagnosis
    return d

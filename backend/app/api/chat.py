"""
对话 API — SSE 流式对话 + 历史查询

POST /api/chat/send              — SSE 流式对话 (自动持久化)
POST /api/chat/confirm           — 危险操作确认回调
GET  /api/chat/history           — 会话列表
GET  /api/chat/history/{id}      — 会话消息详情

事件格式: event: <type>\ndata: <json>\n\n
"""
from fastapi import APIRouter, Depends, Query,Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import get_db, async_session
from app.llm.adapter import chat_stream
from app.models import Conversation
from app.services.confirm_state import PENDING_CONFIRMS, CONFIRM_RESULTS
from app.services.causal_chain import fmt_summary, classify_anomaly, build_causal_chain
from app.services.audit_writer import save_conversation, save_audit_logs_batch
from datetime import datetime
import json
import logging

_logger=logging.getLogger("xikiy_aiops.api")

router=APIRouter()


@router.post("/send")
async def chat_send(request: Request):
    body=await request.json()
    user_input=body.get("message","")
    session_id=body.get("session_id","")
    history=body.get("history",None)

    #会话冲突检查: 如果该 session 正在等待确认, 拒绝新请求
    if session_id and session_id in PENDING_CONFIRMS:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=409,
            content={"code":409,"data":None,"message":"上一个操作正在等待确认, 请先处理确认框"},
        )

    #收集流事件用于事后写入审计日志
    collected_events=[]

    async def sse_generator():
        collector=[]
        #阶段 1: 接收指令
        stage_input_event={"raw_input":user_input,"timestamp":datetime.now().isoformat(),"user":"anonymous"}

        async for event in chat_stream(user_input, history, session_id=session_id):
            if await request.is_disconnected():
                break

            collected_events.append(event)
            event_type=event.get("event","")

            #收集工具调用信息
            if event_type=="tool_call":
                collector.append(event.get("data",{}).get("tool_name",""))

            yield f"event: {event['event']}\ndata: {json.dumps(event['data'],ensure_ascii=False)}\n\n"

        #流结束后持久化
        if session_id and collected_events:
            try:
                await _persist_chat(session_id, user_input, collected_events, collector, stage_input_event)
            except Exception as e:
                _logger.error(f"持久化对话失败 session={session_id}: {e}", exc_info=True)
                yield f"event: error\ndata: {json.dumps({'message':'持久化对话失败'},ensure_ascii=False)}\n\n"
                return

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/confirm")
async def chat_confirm(request: Request):
    """危险操作确认回调 — v2: 接收 decisions dict, 唤醒等待中的 SSE generator

    请求体:
    {
        "session_id": "...",
        "decisions": {     #可选, 缺失=全部取消
            "tool_call_id_1": true,
            "tool_call_id_2": false
        }
    }

    通过 asyncio.Event 唤醒 chat_stream() 中等待的 generator,
    decisions 决定哪些工具放行、哪些跳过。
    """
    body=await request.json()
    session_id=body.get("session_id","")
    decisions=body.get("decisions",None)
    if not session_id:
        return {"success":False,"message":"缺少 session_id"}

    event=PENDING_CONFIRMS.get(session_id)
    if not event:
        return {"success":False,"message":"该会话没有等待中的确认, 可能已超时"}

    if decisions is None:
        #全部取消
        CONFIRM_RESULTS[session_id]={}
    else:
        CONFIRM_RESULTS[session_id]=decisions
    event.set()
    return {"success":True,"message":"确认已记录, 继续执行"}


@router.get("/history")
async def chat_history(
    page:int=Query(1,ge=1),
    size:int=Query(20,ge=1,le=50),
    db:AsyncSession=Depends(get_db),
):
    """会话历史列表 (按更新时间倒序)"""
    q=select(Conversation).order_by(Conversation.updated_at.desc()).offset((page-1)*size).limit(size)
    result=await db.execute(q)
    items=result.scalars().all()
    return {
        "code": 0,
        "data": {
            "items": [{
                "id": c.id,
                "session_id": c.session_id,
                "title":c.title or "",
                "created_at":c.created_at.isoformat() if c.created_at else "",
                "updated_at":c.updated_at.isoformat() if c.updated_at else "",
            } for c in items],
            "page": page,
            "page_size": size,
        },
        "message":"ok",
    }


@router.get("/history/{session_id}")
async def chat_history_detail(
    session_id:str,
    db:AsyncSession=Depends(get_db),
):
    """查询指定会话的全部消息"""
    result=await db.execute(select(Conversation).where(Conversation.session_id==session_id))
    conv=result.scalar_one_or_none()
    if conv is None:
        return {"code":4004,"data":None,"message":"会话不存在"}

    #eager loaded via relationship
    messages=[{
        "id":m.id,
        "role":m.role,
        "content":m.content,
        "tool_calls":m.tool_calls,
        "timestamp":m.timestamp.isoformat() if m.timestamp else "",
    } for m in conv.messages]

    return {"code":0,"data":{"session_id":session_id,"messages":messages},"message":"ok"}


"""
方法: _persist_chat(), 流结束后异步写入 Conversation + Message + AuditLog

在 SSE 生成器结束后调用, 使用独立数据库会话 (不阻塞 HTTP 响应)

v2: 阶段 5 采集真实工具执行数据 (stdout/stderr/duration_ms),
    每个 tool 独立一条 AuditLog (支持细粒度审计回溯),
    增加 is_anomaly/anomaly_type 列 + 因果链
"""
async def _persist_chat(session_id,user_input,events,tools_called,stage_input_event):
    async with async_session() as db:
        #拆解事件, 构建消息列表
        messages=[]
        assistant_content=""
        tool_calls_collected=[]
        security_rules=[]  #每个 tool 的安全校验信息: [{tool_name, summary, risk_level}]
        #每个工具的真实执行结果 (包含 stdout/stderr/duration_ms)
        tool_executions=[]

        for evt in events:
            etype=evt.get("event","")
            edata=evt.get("data",{})

            if etype=="token":
                assistant_content+=edata.get("text","")

            elif etype=="tool_call":
                tool_calls_collected.append({
                    "id":edata.get("tool_name",""),
                    "tool_name":edata.get("tool_name",""),
                    "arguments":edata.get("arguments",{}),
                    "status":"running",
                    "risk_level":edata.get("risk_level",""),
                })

            elif etype=="tool_result":
                #更新最近匹配的 tool_call 状态
                result_data=edata.get("result",{})
                for tc in tool_calls_collected:
                    if tc["tool_name"]==edata.get("tool_name",""):
                        tc["status"]=edata.get("status","done")
                        tc["result"]=result_data
                        break
                #采集真实执行数据 (stdout/stderr/duration_ms 来自 result_data)
                tname=edata.get("tool_name") or edata.get("tool","")
                summary=result_data.get("summary",{})
                data=result_data.get("data",{})
                is_error=edata.get("status")=="error" or result_data.get("risk_level") in ("error","blocked")
                #注: stdout/stderr/duration_ms 由 run_command() 返回, 但当前插件层
                #通过 run_command_text() 仅提取 stdout 字符串, 未透传结构化 dict。
                #后续优化: 插件 handler 改用 run_command() 并在 make_response().data 中
                #包含 _exec_meta={stdout,stderr,exit_code,duration_ms}, 此处即可采集。
                raw_stdout=str(data.get("stdout",""))[:500] if data.get("stdout") else ""
                raw_stderr=str(data.get("stderr",""))[:500] if data.get("stderr") else ""
                raw_duration=data.get("duration_ms",0) if isinstance(data.get("duration_ms"),(int,float)) else 0
                tool_executions.append({
                    "tool_name":tname,
                    "status":edata.get("status","done"),
                    "is_anomaly":is_error,
                    "exit_code":1 if is_error else 0,
                    "output_summary":summary.get("error","") if is_error else fmt_summary(summary),
                    "detail_keys":list(data.keys()) if data else [],
                    "stdout":raw_stdout,
                    "stderr":raw_stderr,
                    "duration_ms":raw_duration,
                })

            elif etype=="security_check":
                security_rules.append({
                    "tool_name":edata.get("tool_name",""),
                    "summary":edata.get("summary",""),
                    "risk_level":edata.get("risk_level",""),
                })

            elif etype=="tool_skipped":
                tname_skipped=edata.get("tool_name") or edata.get("tool","")
                tool_executions.append({
                    "tool_name":tname_skipped,
                    "status":"skipped",
                    "is_anomaly":False,
                    "exit_code":-1,
                    "output_summary":edata.get("reason","用户未确认"),
                    "detail_keys":[],
                    "stdout":"",
                    "stderr":"",
                    "duration_ms":0,
                })

            elif etype=="error":
                assistant_content+=f"\n\n❌ {edata.get('message','')}"

        #构建消息记录
        title=user_input[:100] if user_input else ""
        messages.append({"role":"user","content":user_input})
        if assistant_content or tool_calls_collected:
            messages.append({
                "role":"assistant",
                "content":assistant_content,
                "tool_calls":tool_calls_collected if tool_calls_collected else None,
            })

        risk_level=_derive_risk_level(events)
        has_error=any(e.get("event")=="error" for e in events)
        error_messages=[e.get("data",{}).get("message","") for e in events if e.get("event")=="error"]
        blocked=has_error

        #先保存 Conversation + Messages
        await save_conversation(db, session_id, messages, title)

        #阶段 1/3 是共享的 (同一轮对话所有 tool 共用)
        perception_summary=", ".join(tools_called) if tools_called else "无工具调用"
        shared_perception={
            "tools_called":tools_called,
            "snapshot_summary":perception_summary,
        }
        shared_reasoning={
            "llm_model":"",
            "llm_raw_output":assistant_content[:500] if assistant_content else "",
            "tool_calls_planned":tools_called,
        }
        #阶段 4: 安全校验 (共享)
        if security_rules:
            shared_validation={
                "rules_hit":[r["summary"] for r in security_rules],
                "risk_score":100 if has_error else 50,
                "decision":"blocked" if has_error else "confirmed",
                "reason":"; ".join(r["summary"] for r in security_rules),
            }
        else:
            shared_validation={
                "rules_hit":[],
                "risk_score":100 if has_error else 0,
                "decision":"blocked" if blocked else "allowed",
                "reason":("; ".join(error_messages) if error_messages else "安全检查通过"),
            }

        #无 tool 调用时仍产生一条审计记录 (如纯对话被拦截)
        if not tool_executions:
            is_anomaly=blocked or has_error
            anomaly_type=classify_anomaly(events, [])
            stage_exec={
                "action_taken":"对话完成" if not is_anomaly else "被拦截",
                "tool_executions":[],
                "is_anomaly":is_anomaly,
                "anomaly_type":anomaly_type,
                "duration_ms":0,
            }
            stage_exec["causal_chain"]=build_causal_chain(
                stage_input_event, shared_perception, shared_reasoning,
                shared_validation, stage_exec,
            )
            await save_audit_logs_batch(db, session_id, "anonymous", risk_level, [
                _build_audit_item(stage_input_event, shared_perception, shared_reasoning, shared_validation, stage_exec, is_anomaly, anomaly_type),
            ])
        else:
            #v3: 一次对话一条 AuditLog, 记录全部调用的工具
            tool_names=[te["tool_name"] for te in tool_executions]
            any_anomaly=any(te["is_anomaly"] for te in tool_executions)
            any_skipped=any(te.get("status")=="skipped" for te in tool_executions)

            tool_perception={
                "tools_called":tool_names,
            }

            #聚合安全规则
            all_rules=[]
            for te in tool_executions:
                tn=te["tool_name"]
                all_rules.extend(r["summary"] for r in security_rules if r.get("tool_name")==tn)
            if all_rules:
                tool_validation={
                    "rules_hit":all_rules,
                    "risk_score":50,
                    "decision":"user_cancelled" if all(te.get("status")=="skipped" for te in tool_executions) else "confirmed",
                    "reason":"; ".join(all_rules),
                }
            else:
                tool_validation=dict(shared_validation)

            tool_exec={
                "action_taken":f"执行 {len(tool_executions)} 个工具" if not any_anomaly else f"{'部分' if any_anomaly else ''}工具执行异常",
                "tool_executions":tool_executions,
                "is_anomaly":any_anomaly,
                "anomaly_type":"tool_error" if any_anomaly else "none",
                "duration_ms":sum(te.get("duration_ms",0) for te in tool_executions),
            }
            tool_exec["causal_chain"]=build_causal_chain(
                stage_input_event, tool_perception, shared_reasoning,
                tool_validation, tool_exec,
            )

            await save_audit_logs_batch(db, session_id, "anonymous", risk_level, [
                _build_audit_item(stage_input_event, tool_perception, shared_reasoning, tool_validation, tool_exec, any_anomaly, "tool_error" if any_anomaly else "none"),
            ])

        #提交事务 — async_session() 不会 auto-commit
        await db.commit()



"""
方法: _build_audit_item(), 构建单条审计记录的 stages + 标记
"""
def _build_audit_item(s1, s2, s3, s4, s5, is_anomaly, anomaly_type):
    s5["causal_chain"]=build_causal_chain(s1, s2, s3, s4, s5)
    return {"stages":[s1, s2, s3, s4, s5], "is_anomaly":is_anomaly, "anomaly_type":anomaly_type}


"""
方法: _derive_risk_level(), 从事件流推断风险等级
"""
def _derive_risk_level(events):
    for evt in events:
        data=evt.get("data", {})
        rl=data.get("risk_level", "")
        if rl in ("dangerous", "restricted"):
            return rl
        if evt.get("event")=="error":
            return "dangerous"
    return "read_only"

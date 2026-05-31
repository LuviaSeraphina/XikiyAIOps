"""
对话 API — SSE 流式对话端点

POST /api/chat/send
    body: { "message": "...", "session_id": "...", "history": [...] }
    返回: SSE text/event-stream

事件格式: event: <type>\ndata: <json>\n\n
"""
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from app.llm.adapter import chat_stream
import json

router=APIRouter()


@router.post("/send")
async def chat_send(request: Request):
    body=await request.json()
    user_input=body.get("message", "")
    history=body.get("history", None)

    async def sse_generator():
        async for event in chat_stream(user_input, history):
            yield "event: {}\ndata: {}\n\n".format(
                event["event"],
                json.dumps(event["data"], ensure_ascii=False),
            )

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
    """危险操作确认回调 — 收到确认后恢复 chat_stream 中的等待"""
    body=await request.json()
    confirmed=body.get("confirmed", False)
    if not confirmed:
        return {"success": False, "message": "操作已取消"}
    # TODO: Phase 2 — 通过 asyncio.Event 恢复 chat_stream 中暂停的 tool 执行
    return {"success": True, "message": "确认已收到"}

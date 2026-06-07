"""
模型共享工具 — UUID 生成 + UTC 时间

避免在各模型文件中重复定义相同的辅助函数。
"""
from datetime import datetime, timezone
import uuid


"""
方法: _new_uuid(), 生成 UUID4 字符串 (36 字符, 如 'a1b2c3d4-...')
"""
def _new_uuid() -> str:
    return str(uuid.uuid4())


"""
方法: _utcnow(), 返回带 UTC 时区的当前时间 (替代已弃用的 datetime.utcnow)
"""
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

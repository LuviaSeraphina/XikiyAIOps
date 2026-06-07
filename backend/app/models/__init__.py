"""
SQLAlchemy 模型基类 + 模型注册

所有模型继承 Base, 通过 models/__init__.py 统一导入,
确保 Base.metadata.create_all() 能发现全部表。
"""
from app.models.base import Base

#模型注册 — 导入即注册到 Base.metadata
from app.models.conversation import Conversation, Message  # noqa: F401, E402
from app.models.audit_log import AuditLog  # noqa: F401, E402

__all__=["Base", "Conversation", "Message", "AuditLog"]

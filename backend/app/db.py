"""
数据库引擎与异步会话管理

开发环境: SQLite + aiosqlite
生产环境: PostgreSQL + asyncpg (通过 DATABASE_URL 切换)

用法:
    # FastAPI 路由中 (依赖注入):
    from fastapi import Depends
    from app.db import get_db

    @router.get("/example")
    async def example(db: AsyncSession = Depends(get_db)):
        result = await db.execute(...)

    # 独立脚本中 (直接使用会话工厂):
    from app.db import async_session
    async with async_session() as db:
        result = await db.execute(...)
"""
import os
from pathlib import Path
from typing import AsyncGenerator
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.models import Base

#显式加载 .env, 避免依赖 CWD
_env_path=Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

DATABASE_URL=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///sre_agent.db")

#自动纠正: sqlite:/// → sqlite+aiosqlite:/// (异步引擎必需)
if DATABASE_URL.startswith("sqlite:///"):
    DATABASE_URL=DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

#异步引擎 — SQLite 需 check_same_thread=False
_connect_args={}
if "sqlite" in DATABASE_URL:
    _connect_args["check_same_thread"]=False

engine=create_async_engine(
    DATABASE_URL,
    echo=False,  #调试时改为 True 可查看 SQL 日志
    connect_args=_connect_args,
)

#异步会话工厂
async_session=async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

"""
方法: get_db(), FastAPI 依赖注入 — yield session, 请求结束后自动 commit/rollback + 关闭
"""
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

"""
方法: init_db(), 首次启动时创建所有表 — 生产环境应使用 Alembic 迁移
"""
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

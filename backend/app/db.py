"""
数据库引擎与异步会话管理

环境: SQLite + aiosqlite

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

DATABASE_URL=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///xikiy_aiops.db")

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
方法: _migrate_db(), 数据库迁移 — 为已有表添加缺失的列

create_all 只建新表, 不修改已有表。模型新增列时必须在此处
补充 ALTER TABLE 逻辑, 确保新旧数据库均能正常启动。

当前迁移:
v2 — audit_logs 新增 is_anomaly / anomaly_type 列
"""
def _migrate_db(conn):
    #获取方言 — SQLite 用 PRAGMA, PostgreSQL 用 information_schema
    dialect=conn.dialect.name

    if dialect=="sqlite":
        #检查 audit_logs 是否有 is_anomaly 列
        result=conn.exec_driver_sql("PRAGMA table_info(audit_logs)")
        cols={row[1] for row in result.fetchall()}
        if "is_anomaly" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE audit_logs ADD COLUMN is_anomaly BOOLEAN NOT NULL DEFAULT 0"
            )
        if "anomaly_type" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE audit_logs ADD COLUMN anomaly_type VARCHAR(32) NOT NULL DEFAULT 'none'"
            )
        #索引 — SQLite 的 IF NOT EXISTS 从 3.25 开始支持
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_audit_anomaly ON audit_logs(is_anomaly)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_audit_atype ON audit_logs(anomaly_type)"
        )

    #后续新增列在此追加 elif dialect=="xxx": 分支


"""
方法: init_db(), 首次启动时创建所有表 + 执行迁移

生产环境应使用 Alembic 管理迁移, 此处的 _migrate_db 为轻量级替代方案。
"""
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_db)

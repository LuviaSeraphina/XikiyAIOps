"""
SQLAlchemy 声明式基类

独立文件避免 app.models → conversation → app.models 循环导入。
所有模型直接 from app.models.base import Base。
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

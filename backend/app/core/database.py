from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import settings

engine=create_engine(settings.database_url, 
                     pool_pre_ping=True,
                     pool_size=10, 
                     max_overflow=20, 
                     future=True)
SessionLocal=sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base=declarative_base()

def get_db() -> Generator[Session, None, None]:
    """获取数据库会话。"""
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_db_connection() -> bool:
    """检查数据库连接是否正常。"""

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
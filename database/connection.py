"""
資料庫連線設定
提供 SQLAlchemy 連線引擎與 Session 創建器
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from config import settings

# 建立 SQLAlchemy 連線引擎
# connect_args={"check_same_thread": False} 是 SQLite 特有的參數，允許在多執行緒中使用同一個連線
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)

# 建立 Session 類別
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 宣告式基底類別
Base = declarative_base()


def get_db():
    """
    資料庫 Session 生命週期管理
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

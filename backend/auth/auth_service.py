import os
import logging
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from passlib.context import CryptContext
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Ensure storage directory exists
os.makedirs("storage", exist_ok=True)

# SQLAlchemy setup (using SQLite)
SQLALCHEMY_DATABASE_URL = "sqlite:///./storage/veritas_auth.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    filename = Column(String)
    file_path = Column(String)
    status = Column(String)
    page_count = Column(Integer, default=0)
    ocr_used = Column(Integer, default=0) # using Integer as sqlite boolean mapping
    file_size = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    title = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True, index=True)
    conversation_id = Column(String, index=True)
    role = Column(String) # 'user' or 'assistant'
    content = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(bind=engine)

# Auto-migrate SQLite schema for missing columns in existing databases
def _ensure_sqlite_columns():
    try:
        with engine.connect() as conn:
            result = conn.execute(
                __import__("sqlalchemy").text("PRAGMA table_info(documents);")
            ).fetchall()
            existing_cols = [r[1] for r in result]
            if existing_cols:
                if "page_count" not in existing_cols:
                    conn.execute(__import__("sqlalchemy").text("ALTER TABLE documents ADD COLUMN page_count INTEGER DEFAULT 0;"))
                if "ocr_used" not in existing_cols:
                    conn.execute(__import__("sqlalchemy").text("ALTER TABLE documents ADD COLUMN ocr_used INTEGER DEFAULT 0;"))
                if "file_size" not in existing_cols:
                    conn.execute(__import__("sqlalchemy").text("ALTER TABLE documents ADD COLUMN file_size INTEGER DEFAULT 0;"))
                conn.commit()
    except Exception as e:
        logger.warning(f"SQLite column migration note: {e}")

_ensure_sqlite_columns()

# Password hashing setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

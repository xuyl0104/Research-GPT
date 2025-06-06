from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime,   timezone
import uuid
from sqlalchemy.dialects.postgresql import UUID, JSONB

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    embeddings = relationship("Embedding", back_populates="user", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")

class Embedding(Base):
    __tablename__ = 'embeddings'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    faiss_path = Column(String, nullable=True)  # local path or S3 key
    chunks_path = Column(String, nullable=True)  # local path or S3 key

    user = relationship("User", back_populates="embeddings")
    messages = relationship("Message", back_populates="embedding", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = 'messages'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    embedding_id = Column(UUID(as_uuid=True), ForeignKey("embeddings.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(String(10), nullable=False)  # 'user' or 'bot'
    content = Column(Text, nullable=False)
    evidence = Column(JSONB, nullable=True) # JSONB for pgsql
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    embedding = relationship("Embedding", back_populates="messages")
    user = relationship("User", back_populates="messages")

Index("ix_messages_embedding_id", Message.embedding_id)
Index("ix_messages_user_id", Message.user_id)
Index("ix_messages_created_at", Message.created_at)


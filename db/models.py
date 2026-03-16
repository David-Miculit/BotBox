from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func, Index
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import relationship

from db.database import Base

class UserRecord(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    files = relationship("FileRecord", back_populates="user", cascade="all, delete-orphan")

class FileRecord(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    original_name = Column(String, nullable=False)
    random_name = Column(String, nullable=False, index=True)
    content_type = Column(String, nullable=False)
    size = Column(Integer, nullable=False)
    path = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("UserRecord", back_populates="files")
    content = relationship(
        "FileContentRecord",
        back_populates="file",
        uselist=False,
        cascade="all, delete-orphan",
    )

class FileContentRecord(Base):
    __tablename__ = "file_content"

    file_id = Column(Integer, ForeignKey("files.id"), primary_key=True)
    content_tsv = Column(TSVECTOR, nullable=False)

    __table_args__ = (
        Index(
            "ix_file_content_content_tsv",
            "content_tsv",
            postgresql_using="gin",
        ),
    )

    file = relationship("FileRecord", back_populates="content")
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    func,
)

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
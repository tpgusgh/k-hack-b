from sqlalchemy import Column, Integer, String
from .database import Base

# 회원 인터페이스

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(200))

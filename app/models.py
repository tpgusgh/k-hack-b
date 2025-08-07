from sqlalchemy import Column, Integer, String, DateTime
from .database import Base
from datetime import datetime

# 회원 인터페이스

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(200))


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)         # 종목 이름
    code = Column(String, index=True)         # 고유번호
    price = Column(Integer)                   # 현재 가격

class StockPriceHistory(Base):
    __tablename__ = "stock_price_history"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), index=True)
    price = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)
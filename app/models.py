

# models.py
from sqlalchemy import Column, Integer, String, DateTime, DECIMAL, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

# -------------------------
# 유저
# -------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)

    # 관계
    wallet = relationship("UserWallet", back_populates="user", uselist=False)
    ownerships = relationship("StockOwnership", back_populates="user")


# -------------------------
# 유저 지갑
# -------------------------
class UserWallet(Base):
    __tablename__ = "user_wallet"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    money = Column(DECIMAL(15, 2), default=0)

    user = relationship("User", back_populates="wallet")


# -------------------------
# 주식 정보
# -------------------------
class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), index=True, nullable=False)  # 종목 이름
    code = Column(String(20), index=True, nullable=False)   # 종목 코드
    price = Column(DECIMAL(15, 2), nullable=False)          # 현재 가격

    ownerships = relationship("StockOwnership", back_populates="stock")


# -------------------------
# 주식 보유 현황
# -------------------------
class StockOwnership(Base):
    __tablename__ = "stock_ownership"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    price_at_time = Column(DECIMAL(15, 2), nullable=False)  # 매수 당시 가격
    quantity = Column(Integer, default=0)

    user = relationship("User", back_populates="ownerships")
    stock = relationship("Stock", back_populates="ownerships")


# -------------------------
# 주식 가격 기록
# -------------------------
class StockPriceHistory(Base):
    __tablename__ = "stock_price_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(20), index=True, nullable=False)
    price = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)


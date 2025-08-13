



from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from fastapi.middleware.cors import CORSMiddleware
from . import models, schemas
from .database import engine, SessionLocal
from .auth import create_access_token, verify_token
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
from .models import StockPriceHistory
from datetime import datetime
from decimal import Decimal
from sqlalchemy import desc

# 테이블 생성
models.Base.metadata.create_all(bind=engine)
app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="signin")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
scheduler = BackgroundScheduler()

# 종목 코드 + 설명 매핑
STOCK_INFOS = {
    "삼성전자": {"code": "005930", "desc": "메모리 반도체와 스마트폰 제조를 주력으로 하는 세계적 IT 기업"},
    "화일전자": {"code": "061250", "desc": "전자부품 제조업체로, 주로 LED 관련 제품을 생산"},
    "LG전자": {"code": "066570", "desc": "가전제품, 전자부품, 모바일 기기 등을 생산하는 글로벌 제조사"},
    "GS리테일": {"code": "007070", "desc": "편의점 GS25 등 유통업을 주력으로 하는 GS그룹 계열사"},
    "GS": {"code": "078930", "desc": "에너지, 건설, 유통 등 다양한 분야를 영위하는 대기업"},
    "POSCO홀딩스": {"code": "005490", "desc": "세계적인 철강 제조 기업"},
    "SK하이닉스": {"code": "000660", "desc": "메모리 반도체 제조를 주력으로 하는 글로벌 기업"},
    "NAVER": {"code": "035420", "desc": "대한민국 대표 포털 및 IT 서비스 기업"},
    "카카오": {"code": "035720", "desc": "메신저, 모빌리티, 금융 등 다양한 IT 서비스를 제공"},
    "현대차": {"code": "005380", "desc": "대한민국 대표 자동차 제조 기업"}
}

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB 세션
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 네이버 금융에서 주가 가져오기
def get_stock_price(code: str):
    url = f"https://finance.naver.com/item/main.nhn?code={code}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    price_tag = soup.select_one("p.no_today span.blind")
    if price_tag:
        return price_tag.text.replace(",", "")
    return None

# 모든 종목 가격 저장
def fetch_and_save_all_stock_prices():
    db = SessionLocal()
    try:
        for name, info in STOCK_INFOS.items():
            code = info["code"]
            price_str = get_stock_price(code)
            if price_str:
                price = int(price_str)
                save_stock_price_history(db, code, price)
    finally:
        db.close()

# 주식 DB 저장
def save_stock_to_db(db: Session, name: str, code: str, price: int):
    stock = db.query(models.Stock).filter(models.Stock.code == code).first()
    if stock:
        stock.price = price
    else:
        stock = models.Stock(name=name, code=code, price=price)
        db.add(stock)
    db.commit()

# 가격 기록 저장
def save_stock_price_history(db: Session, code: str, price: int):
    history = StockPriceHistory(code=code, price=price, timestamp=datetime.utcnow())
    db.add(history)
    db.commit()

# 회원가입
@app.post("/signup")
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    hashed = pwd_context.hash(user.password)
    new_user = models.User(username=user.username, hashed_password=hashed)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"msg": "successfully"}

# 로그인
@app.post("/signin", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(data={"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

# 내 정보
@app.get("/me")
def get_me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    username = verify_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(models.User).filter(models.User.username == username).first()
    return {"username": user.username}

# 모든 사용자
@app.get("/hi")
def get_hi(db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    result = [{"id": user.id, "username": user.username} for user in users]
    return {"msg": result}

# 삼성전자 단일 조회
@app.get("/samsung/price")
def read_stock_price():
    price = get_stock_price("005930")
    if price:
        return {"ticker": "삼성전자", "price": int(price)}
    else:
        return {"error": "가격을 불러오지 못했습니다."}

# 여러 종목 가격 + 설명 조회
@app.get("/stocks")
def read_multiple_stock_prices(db: Session = Depends(get_db)):
    results = []
    for name, info in STOCK_INFOS.items():
        code = info["code"]
        desc = info["desc"]
        price = get_stock_price(code)
        if price:
            price_int = int(price)
            results.append({"name": name, "code": code, "price": price_int, "description": desc})
            save_stock_to_db(db, name, code, price_int)
        else:
            results.append({"name": name, "code": code, "error": "가격을 불러오지 못했습니다.", "description": desc})
    return results

# DB 저장된 종목 조회
@app.get("/stocks/db")
def get_stocks_from_db(db: Session = Depends(get_db)):
    stocks = db.query(models.Stock).all()
    return [{"name": stock.name, "code": stock.code, "price": stock.price} for stock in stocks]

# 가격 기록 조회
@app.get("/stocks/history")
def get_stock_price_history(
    code: str = Query(..., description="종목 코드"),
    limit: int = Query(100, description="조회할 최대 기록 개수"),
    db: Session = Depends(get_db)
):
    records = (
        db.query(models.StockPriceHistory)
        .filter(models.StockPriceHistory.code == code)
        .order_by(desc(models.StockPriceHistory.timestamp))
        .limit(limit)
        .all()
    )
    return [{"code": r.code, "price": r.price, "timestamp": r.timestamp.isoformat()} for r in records]

# 내 자산 조회 (최신 가격 기준)
@app.get("/me/asset")
def get_my_total_asset(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    username = verify_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    wallet = db.query(models.UserWallet).filter(models.UserWallet.user_id == user.id).first()
    cash = wallet.money if wallet else Decimal("0.0")

    ownerships = db.query(models.StockOwnership).filter(models.StockOwnership.user_id == user.id).all()
    stock_value = Decimal("0.0")
    for o in ownerships:
        latest_price_record = db.query(models.StockPriceHistory)\
            .filter(models.StockPriceHistory.code == o.stock.code)\
            .order_by(desc(models.StockPriceHistory.timestamp))\
            .first()
        if latest_price_record:
            stock_value += Decimal(latest_price_record.price) * o.quantity

    total_asset = cash + stock_value
    return {"username": username, "cash": float(cash), "stock_value": float(stock_value), "total_asset": float(total_asset)}

@app.get("/me/cash")
def get_my_cash(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    username = verify_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(models.User).filter(models.User.username == username).first()
    wallet = db.query(models.UserWallet).filter(models.UserWallet.user_id == user.id).first()
    return {"username": username, "cash": float(wallet.money) if wallet else 0.0}

# 주식 구매
@app.post("/stocks/buy")
def buy_stock(stock_code: str = Query(...), quantity: int = Query(..., gt=0),
              token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    username = verify_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(models.User).filter(models.User.username == username).first()

    latest_price_record = db.query(StockPriceHistory)\
        .filter(StockPriceHistory.code == stock_code)\
        .order_by(desc(StockPriceHistory.timestamp))\
        .first()
    if not latest_price_record:
        raise HTTPException(status_code=404, detail="Stock price not found")

    total_price = Decimal(latest_price_record.price) * Decimal(quantity)
    wallet = db.query(models.UserWallet).filter(models.UserWallet.user_id == user.id).first()
    if not wallet or wallet.money < total_price:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    wallet.money -= total_price

    stock = db.query(models.Stock).filter(models.Stock.code == stock_code).first()
    ownership = db.query(models.StockOwnership)\
        .filter(models.StockOwnership.user_id == user.id, models.StockOwnership.stock_id == stock.id)\
        .first()
    if ownership:
        ownership.quantity += quantity
    else:
        ownership = models.StockOwnership(user_id=user.id, stock_id=stock.id,
                                          price_at_time=latest_price_record.price, quantity=quantity)
        db.add(ownership)
    db.commit()
    return {"msg": f"Bought {quantity} shares of {stock_code} at {latest_price_record.price} 원"}

# 주식 판매
@app.post("/stocks/sell")
def sell_stock(stock_code: str = Query(...), quantity: int = Query(..., gt=0),
               token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    username = verify_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(models.User).filter(models.User.username == username).first()

    stock = db.query(models.Stock).filter(models.Stock.code == stock_code).first()
    ownership = db.query(models.StockOwnership)\
        .filter(models.StockOwnership.user_id == user.id, models.StockOwnership.stock_id == stock.id)\
        .first()
    if not ownership or ownership.quantity < quantity:
        raise HTTPException(status_code=400, detail="Not enough stock to sell")

    latest_price_record = db.query(StockPriceHistory)\
        .filter(StockPriceHistory.code == stock_code)\
        .order_by(desc(StockPriceHistory.timestamp))\
        .first()
    if not latest_price_record:
        raise HTTPException(status_code=404, detail="Stock price not found")

    total_price = Decimal(latest_price_record.price) * Decimal(quantity)
    ownership.quantity -= quantity

    wallet = db.query(models.UserWallet).filter(models.UserWallet.user_id == user.id).first()
    wallet.money += total_price
    db.commit()
    return {"msg": f"Sold {quantity} shares of {stock_code} at {latest_price_record.price} 원"}


@app.get("/me/ownerships")
def get_my_stock_ownerships(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    username = verify_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ownerships = db.query(models.StockOwnership).filter(models.StockOwnership.user_id == user.id).all()
    result = []
    for o in ownerships:
        latest_price_record = db.query(StockPriceHistory)\
            .filter(StockPriceHistory.code == o.stock.code)\
            .order_by(desc(StockPriceHistory.timestamp))\
            .first()
        if latest_price_record:
            result.append({
                "stock_name": o.stock.name,
                "stock_code": o.stock.code,
                "quantity": o.quantity,
                "latest_price": float(latest_price_record.price),
                "total_value": float(latest_price_record.price) * o.quantity
            })

    return {"username": username, "stocks": result}



# 현금 입금
@app.post("/me/deposit")
def deposit_money(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    username = verify_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    wallet = db.query(models.UserWallet).filter(models.UserWallet.user_id == user.id).first()
    if not wallet:
        wallet = models.UserWallet(user_id=user.id, money=Decimal("10000.0"))
        db.add(wallet)
    else:
        wallet.money += Decimal("10000.0")
    db.commit()
    return {"username": username, "msg": "10,000원 입금 완료", "current_cash": float(wallet.money)}

# 스케줄러
scheduler.add_job(fetch_and_save_all_stock_prices, 'interval', minutes=60)
scheduler.start()


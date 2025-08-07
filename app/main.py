from fastapi import FastAPI, Depends, HTTPException,Query
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

# 테이블 생성
models.Base.metadata.create_all(bind=engine)
app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
scheduler = BackgroundScheduler()
# 종목 코드 매핑
STOCK_CODES = {
    "삼성전자": "005930",
    "화일전자": "061250",
    "LG전자": "066570",
    "GS리테일": "007070",
    "GS": "078930",
    "POSCO홀딩스": "005490",
    "SK하이닉스": "000660",
    "NAVER": "035420",
    "카카오": "035720",
    "현대차": "005380",
}



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 도메인 허용
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용 (GET, POST 등)
    allow_headers=["*"],  # 모든 헤더 허용
)
# DB 세션
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_stock_price(code: str):
    """
    Naver 금융에서 주가 가져오기
    """
    url = f"https://finance.naver.com/item/main.nhn?code={code}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    price_tag = soup.select_one("p.no_today span.blind")
    if price_tag:
        return price_tag.text.replace(",", "")
    return None

def fetch_and_save_all_stock_prices():
    db = SessionLocal()
    try:
        for name, code in STOCK_CODES.items():
            price_str = get_stock_price(code)
            if price_str:
                price = int(price_str)
                save_stock_price_history(db, code, price)
    finally:
        db.close()

def save_stock_to_db(db: Session, name: str, code: str, price: int):
    stock = db.query(models.Stock).filter(models.Stock.code == code).first()
    if stock:
        stock.price = price  # 기존 값 업데이트
    else:
        stock = models.Stock(name=name, code=code, price=price)
        db.add(stock)
    db.commit()

def save_stock_price_history(db: Session, code: str, price: int):
    from datetime import datetime
    history = StockPriceHistory(code=code, price=price, timestamp=datetime.utcnow())
    db.add(history)
    db.commit()


# 회원가입 json
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

# 로그인 form
@app.post("/signin", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token(data={"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

#이름 조회 curl
@app.get("/me")
def get_me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    username = verify_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user = db.query(models.User).filter(models.User.username == username).first()
    return {"username": user.username}



@app.get("/hi")
def get_hi(db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    result = [{"id": user.id, "username": user.username} for user in users]
    return {"msg": result}

def get_samsung_stock_price():
    url = "https://finance.naver.com/item/main.nhn?code=005930"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    price_tag = soup.select_one("p.no_today span.blind")
    if price_tag:
        return price_tag.text.replace(",", "")
    return None

@app.get("/samsung/price")
def read_stock_price():
    price = get_samsung_stock_price()
    if price:
        return {"ticker": "삼성전자", "price": int(price)}
    else:
        return {"error": "가격을 불러오지 못했습니다."}


@app.get("/stocks")
def read_multiple_stock_prices(db: Session = Depends(get_db)):
    results = []
    for name, code in STOCK_CODES.items():
        price = get_stock_price(code)
        if price:
            price_int = int(price)
            results.append({"name": name, "code": code, "price": price_int})
            save_stock_to_db(db, name, code, price_int)  # DB 저장
        else:
            results.append({"name": name, "code": code, "error": "가격을 불러오지 못했습니다."})
    return results


@app.get("/stocks/db")
def get_stocks_from_db(db: Session = Depends(get_db)):
    stocks = db.query(models.Stock).all()
    return [{"name": stock.name, "code": stock.code, "price": stock.price} for stock in stocks]


@app.get("/stocks/history")
def get_stock_price_history(
    code: str = Query(..., description="종목 코드"),
    limit: int = Query(100, description="조회할 최대 기록 개수"),
    db: Session = Depends(get_db)
):
    """
    특정 종목 코드의 가격 기록을 최신순으로 조회합니다.
    """
    records = (
        db.query(models.StockPriceHistory)
        .filter(models.StockPriceHistory.code == code)
        .order_by(models.StockPriceHistory.timestamp.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "code": record.code,
            "price": record.price,
            "timestamp": record.timestamp.isoformat()
        }
        for record in records
    ]


scheduler.add_job(fetch_and_save_all_stock_prices, 'interval', minutes=5)
scheduler.start()
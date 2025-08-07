from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from fastapi.middleware.cors import CORSMiddleware
from . import models, schemas
from .database import engine, SessionLocal
from .auth import create_access_token, verify_token
import requests
from bs4 import BeautifulSoup
# 테이블 생성
models.Base.metadata.create_all(bind=engine)
app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 종목 코드 매핑
STOCK_CODES = {
    "삼성전자": "005930",
    "화일전자": "061250",
    "LG전자": "066570",
    "GS리테일": "007070",
    "GS": "078930",
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
def read_multiple_stock_prices():
    results = []
    for name, code in STOCK_CODES.items():
        price = get_stock_price(code)
        if price:
            results.append({"ticker": name, "price": int(price)})
        else:
            results.append({"ticker": name, "error": "가격을 불러오지 못했습니다."})
    return results


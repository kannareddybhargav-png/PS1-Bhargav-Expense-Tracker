from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
import os
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Database Setup ----------
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./expenses.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ---------- Database Models ----------
class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    expenses = relationship("ExpenseDB", back_populates="owner")

class ExpenseDB(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True, index=True)
    description = Column(String)
    amount = Column(Float)
    category = Column(String)
    date = Column(String)
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("UserDB", back_populates="expenses")

Base.metadata.create_all(bind=engine)

# ---------- Auth Setup ----------
SECRET_KEY = os.environ.get("SECRET_KEY", "supersecretkey123")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ---------- Pydantic Models ----------
class UserCreate(BaseModel):
    email: str
    password: str

class Expense(BaseModel):
    description: str
    amount: float
    category: str
    date: str

class Token(BaseModel):
    access_token: str
    token_type: str

# ---------- Helpers ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def create_token(data: dict, expires_days: int = ACCESS_TOKEN_EXPIRE_DAYS):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=expires_days)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(UserDB).filter(UserDB.email == email).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# ---------- Auth Routes ----------
@app.post("/api/auth/signup", status_code=201)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(UserDB).filter(UserDB.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    new_user = UserDB(
        email=user.email,
        hashed_password=hash_password(user.password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    token = create_token({"sub": new_user.email})
    return {"access_token": token, "token_type": "bearer", "email": new_user.email}

@app.post("/api/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token({"sub": user.email})
    return {"access_token": token, "token_type": "bearer", "email": user.email}

# ---------- Expense Routes ----------
@app.get("/api/expenses")
def get_expenses(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    return db.query(ExpenseDB).filter(ExpenseDB.owner_id == current_user.id).all()

@app.post("/api/expenses", status_code=201)
def add_expense(expense: Expense, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    db_expense = ExpenseDB(**expense.dict(), owner_id=current_user.id)
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense

@app.get("/api/expenses/summary")
def summary(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    expenses = db.query(ExpenseDB).filter(ExpenseDB.owner_id == current_user.id).all()
    totals = {}
    for e in expenses:
        if e.category not in totals:
            totals[e.category] = {"total": 0, "count": 0}
        totals[e.category]["total"] += e.amount
        totals[e.category]["count"] += 1
    return totals

@app.get("/api/expenses/total")
def total(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    expenses = db.query(ExpenseDB).filter(ExpenseDB.owner_id == current_user.id).all()
    return {"total": sum(e.amount for e in expenses)}


@app.put("/api/expenses/{id}")
def update_expense(id: int, expense: Expense, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    db_expense = db.query(ExpenseDB).filter(ExpenseDB.id == id, ExpenseDB.owner_id == current_user.id).first()
    if not db_expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    for key, value in expense.dict().items():
        setattr(db_expense, key, value)
    db.commit()
    db.refresh(db_expense)
    return {"message": f"Updated expense #{id}", "expense": db_expense}

@app.delete("/api/expenses/{id}")
def delete_expense(id: int, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    db_expense = db.query(ExpenseDB).filter(ExpenseDB.id == id, ExpenseDB.owner_id == current_user.id).first()
    if not db_expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(db_expense)
    db.commit()
    return {"message": f"Deleted expense #{id}"}

@app.get("/health")
def health():
    return {"status": "ok"}

# ---------- Monthly Log Model ----------
class MonthlyLogDB(Base):
    __tablename__ = "monthly_logs"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    month_label = Column(String)
    snapshot = Column(String)
    total = Column(Float)
    created_at = Column(String)

Base.metadata.create_all(bind=engine)

@app.post("/api/logs/save")
def save_monthly_log(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    import json
    from datetime import datetime

    expenses = db.query(ExpenseDB).filter(
        ExpenseDB.owner_id == current_user.id
    ).all()

    if not expenses:
        raise HTTPException(status_code=400, detail="No expenses to log")

    snapshot = [
        {
            "description": e.description,
            "amount": e.amount,
            "category": e.category,
            "date": e.date
        }
        for e in expenses
    ]

    total = sum(e.amount for e in expenses)
    now = datetime.utcnow()
    month_label = now.strftime("%B %Y")

    log = MonthlyLogDB(
        owner_id=current_user.id,
        month_label=month_label,
        snapshot=json.dumps(snapshot),
        total=total,
        created_at=now.strftime("%Y-%m-%d %H:%M:%S")
    )
    db.add(log)

    for e in expenses:
        db.delete(e)

    db.commit()
    db.refresh(log)
    return {"message": f"Logged {len(snapshot)} expenses for {month_label}", "total": total}

@app.get("/api/logs")
def get_logs(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    import json
    logs = db.query(MonthlyLogDB).filter(
        MonthlyLogDB.owner_id == current_user.id
    ).order_by(MonthlyLogDB.id.desc()).all()

    return [
        {
            "id": log.id,
            "month_label": log.month_label,
            "total": log.total,
            "created_at": log.created_at,
            "snapshot": json.loads(log.snapshot)
        }
        for log in logs
    ]

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)

from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timedelta
from models import UserRegister, UserLogin, Token
from database import users_collection, sessions_collection
from security import hash_password, verify_password, create_access_token, verify_token
from config import SESSION_EXPIRE_HOURS

router = APIRouter(prefix="/api", tags=["auth"])

@router.post("/register", response_model=Token)
async def register(user: UserRegister):
    if users_collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_data = {
        "name": user.name,
        "email": user.email,
        "password": hash_password(user.password),
        "role": user.role,
        "created_at": datetime.utcnow()
    }
    users_collection.insert_one(user_data)
    
    token = create_access_token({"sub": user.email})
    expires_at = datetime.utcnow() + timedelta(hours=SESSION_EXPIRE_HOURS)
    
    sessions_collection.insert_one({
        "email": user.email,
        "token": token,
        "created_at": datetime.utcnow(),
        "expires_at": expires_at
    })
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"name": user.name, "email": user.email, "role": user.role}
    }

@router.post("/login", response_model=Token)
async def login(user: UserLogin):
    db_user = users_collection.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({"sub": user.email})
    expires_at = datetime.utcnow() + timedelta(hours=SESSION_EXPIRE_HOURS)
    
    sessions_collection.delete_many({"email": user.email})
    sessions_collection.insert_one({
        "email": user.email,
        "token": token,
        "created_at": datetime.utcnow(),
        "expires_at": expires_at
    })
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"name": db_user["name"], "email": db_user["email"], "role": db_user.get("role", "Creator")}
    }

@router.post("/logout")
async def logout(email: str = Depends(verify_token)):
    sessions_collection.delete_many({"email": email})
    return {"message": "Logged out successfully"}

@router.get("/verify")
async def verify_session(email: str = Depends(verify_token)):
    return {"valid": True, "email": email}

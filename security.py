from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from config import SECRET_KEY, ALGORITHM, SESSION_EXPIRE_HOURS
from database import sessions_collection, users_collection

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=SESSION_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        session = sessions_collection.find_one({"email": email, "token": token})
        if not session or datetime.utcnow() > session["expires_at"]:
            raise HTTPException(status_code=401, detail="Session expired")
        
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def verify_admin(email: str = Depends(verify_token)):
    user = users_collection.find_one({"email": email})
    if not user or user.get("role") != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return email

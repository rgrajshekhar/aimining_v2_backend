from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from pymongo import MongoClient
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, List
import os
from dotenv import load_dotenv
import uuid
import boto3
from botocore.exceptions import ClientError
import razorpay
import hmac
import hashlib

load_dotenv()

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["creatornexus"]
users_collection = db["users"]
sessions_collection = db["sessions"]
minerals_collection = db["minerals"]
star_ratings_collection = db["star_ratings"]
ebooks_collection = db["ebooks"]
purchases_collection = db["purchases"]
monthly_returns_collection = db["monthly_returns"]

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
SESSION_EXPIRE_HOURS = 2

# Razorpay
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)) if RAZORPAY_KEY_ID else None

# AWS S3
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME", "creatornexus-ebooks")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
) if AWS_ACCESS_KEY else None

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Models
class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict

class MineDetail(BaseModel):
    mineName: str
    mineralsGranted: str
    leaseAreaHectares: Optional[float] = None
    leaseLocation: str
    leasePeriodFrom: Optional[str] = None
    leasePeriodTo: Optional[str] = None
    miningMethod: Optional[str] = None
    quarryCategory: Optional[str] = None
    captiveType: Optional[str] = None
    mdlNo: Optional[str] = None
    mdlDate: Optional[str] = None
    mdlValidity: Optional[str] = None
    productionMT: Optional[float] = None
    surfaceFeature: Optional[str] = None

class UserProfile(BaseModel):
    name: str
    email: EmailStr
    role: str
    bio: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    lesseeId: Optional[str] = None
    firmName: Optional[str] = None
    managingDirector: Optional[str] = None
    lesseeAddress: Optional[str] = None
    aadharNo: Optional[str] = None
    panCardNo: Optional[str] = None
    mobileNo: Optional[str] = None
    additionalInfo: Optional[str] = None
    mines: Optional[List[MineDetail]] = []
    subscriptionPlan: Optional[str] = "Free"

class RoyaltyInput(BaseModel):
    royaltyRate: float
    quantity: float
    area: float

class Mineral(BaseModel):
    name: str
    quality: str
    royaltyRate: float
    salesPrice: float
    unit: str

class MineralUpdate(BaseModel):
    quality: str
    royaltyRate: float
    salesPrice: float
    unit: str

class StarRatingData(BaseModel):
    year: int
    leaseDetails: dict
    landUse: dict
    royalty: dict
    statutory: dict
    moduleI: dict
    moduleII: dict
    moduleIII: dict
    moduleIV: dict

class Ebook(BaseModel):
    title: str
    category: str
    description: str
    author: str
    fileUrl: str
    coverUrl: Optional[str] = None
    requiresSubscription: bool = False
    requiredPlan: str = "Free"

class EbookUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    fileUrl: Optional[str] = None
    coverUrl: Optional[str] = None
    requiresSubscription: Optional[bool] = None
    requiredPlan: Optional[str] = None

class MonthlyReturn(BaseModel):
    month: str
    mineralName: str
    quality: str
    storedStart: float
    minedProduction: float
    domesticUse: float
    dispatchTrain1: float
    dispatchTrain2: float
    dispatchTrain3: float
    royaltyRate: float
    challanIssued: int
    total: float
    totalDispatched: float
    royaltyAmount: float
    mineralLeft: float

class ContactForm(BaseModel):
    name: str
    email: EmailStr
    message: str

class PaymentOrder(BaseModel):
    amount: int
    email: EmailStr
    name: str
    role: str

class PaymentVerification(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    email: EmailStr
    name: str
    password: str
    role: str

# Helper functions
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
        
        # Check session in MongoDB
        session = sessions_collection.find_one({"email": email, "token": token})
        if not session or datetime.utcnow() > session["expires_at"]:
            raise HTTPException(status_code=401, detail="Session expired")
        
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Routes
@app.post("/api/register", response_model=Token)
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

@app.post("/api/login", response_model=Token)
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

@app.post("/api/logout")
async def logout(email: str = Depends(verify_token)):
    sessions_collection.delete_many({"email": email})
    return {"message": "Logged out successfully"}

@app.get("/api/profile")
async def get_profile(email: str = Depends(verify_token)):
    user = users_collection.find_one({"email": email}, {"password": 0, "_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.put("/api/profile")
async def update_profile(profile: UserProfile, email: str = Depends(verify_token)):
    print(f"Updating profile for: {email}")
    print(f"Received data: {profile.dict()}")
    
    # Check if email is being changed and if new email already exists
    if profile.email != email:
        existing = users_collection.find_one({"email": profile.email})
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
    
    # Update profile
    update_data = {
        "name": profile.name,
        "email": profile.email,
        "role": profile.role,
        "updated_at": datetime.utcnow()
    }
    if profile.bio is not None:
        update_data["bio"] = profile.bio
    if profile.location is not None:
        update_data["location"] = profile.location
    if profile.website is not None:
        update_data["website"] = profile.website
    if profile.lesseeId is not None:
        update_data["lesseeId"] = profile.lesseeId
    if profile.firmName is not None:
        update_data["firmName"] = profile.firmName
    if profile.managingDirector is not None:
        update_data["managingDirector"] = profile.managingDirector
    if profile.lesseeAddress is not None:
        update_data["lesseeAddress"] = profile.lesseeAddress
    if profile.aadharNo is not None:
        update_data["aadharNo"] = profile.aadharNo
    if profile.panCardNo is not None:
        update_data["panCardNo"] = profile.panCardNo
    if profile.mobileNo is not None:
        update_data["mobileNo"] = profile.mobileNo
    if profile.additionalInfo is not None:
        update_data["additionalInfo"] = profile.additionalInfo
    if profile.mines is not None:
        update_data["mines"] = [mine.dict() for mine in profile.mines]
    if profile.subscriptionPlan is not None:
        update_data["subscriptionPlan"] = profile.subscriptionPlan
    
    print(f"Update data: {update_data}")
    
    result = users_collection.update_one(
        {"email": email},
        {"$set": update_data}
    )
    
    print(f"Update result - matched: {result.matched_count}, modified: {result.modified_count}")
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    # If email changed, update sessions
    if profile.email != email:
        sessions_collection.update_many(
            {"email": email},
            {"$set": {"email": profile.email}}
        )
    
    # Return updated user
    updated_user = users_collection.find_one({"email": profile.email}, {"password": 0, "_id": 0})
    print(f"Updated user: {updated_user}")
    return updated_user

@app.get("/api/verify")
async def verify_session(email: str = Depends(verify_token)):
    return {"valid": True, "email": email}

@app.post("/api/calculate-royalty")
async def calculate_royalty(inputs: RoyaltyInput):
    royalty = inputs.royaltyRate * inputs.quantity
    deadRent = (inputs.area * 30000) / 12
    if (royalty > deadRent): base_amount = royalty
    else: base_amount = deadRent
    
    dmft = base_amount * 0.30
    interest = base_amount * 0.24 / 12
    nmet = base_amount * 0.02
    itCess = base_amount * 0.02
    managementFee = inputs.quantity * 1
    environmentCess = base_amount * 0.02
    totalDemand = base_amount + dmft + interest + nmet + itCess + managementFee + environmentCess
    
    return {
        "royalty": royalty,
        "deadRent": deadRent,
        "dmft": dmft,
        "interest": interest,
        "nmet": nmet,
        "itCess": itCess,
        "managementFee": managementFee,
        "environmentCess": environmentCess,
        "totalDemand": totalDemand
    }

# Admin endpoints
def verify_admin(email: str = Depends(verify_token)):
    user = users_collection.find_one({"email": email})
    if not user or user.get("role") != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return email

@app.get("/api/admin/users")
async def get_all_users(email: str = Depends(verify_admin)):
    users = list(users_collection.find({}, {"password": 0, "_id": 0}))
    return users

@app.delete("/api/admin/users/{user_email}")
async def delete_user(user_email: str, email: str = Depends(verify_admin)):
    result = users_collection.delete_one({"email": user_email})
    sessions_collection.delete_many({"email": user_email})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted"}

@app.get("/api/admin/stats")
async def get_stats(email: str = Depends(verify_admin)):
    total_users = users_collection.count_documents({})
    active_sessions = sessions_collection.count_documents({"expires_at": {"$gt": datetime.utcnow()}})
    users_by_role = list(users_collection.aggregate([
        {"$group": {"_id": "$role", "count": {"$sum": 1}}}
    ]))
    return {
        "totalUsers": total_users,
        "activeSessions": active_sessions,
        "usersByRole": {item["_id"]: item["count"] for item in users_by_role}
    }

# Minerals endpoints
@app.get("/api/minerals")
async def get_minerals():
    minerals = list(minerals_collection.find({}))
    for mineral in minerals:
        mineral["_id"] = str(mineral["_id"])
    return minerals

@app.post("/api/admin/minerals")
async def create_mineral(mineral: Mineral, email: str = Depends(verify_admin)):
    if minerals_collection.find_one({"name": mineral.name}):
        raise HTTPException(status_code=400, detail="Mineral already exists")
    minerals_collection.insert_one(mineral.dict())
    return mineral

@app.put("/api/admin/minerals/{mineral_name}")
async def update_mineral(mineral_name: str, update: MineralUpdate, email: str = Depends(verify_admin)):
    result = minerals_collection.update_one({"name": mineral_name}, {"$set": {"quality": update.quality, "royaltyRate": update.royaltyRate, "salesPrice": update.salesPrice, "unit": update.unit}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Mineral not found")
    return {"name": mineral_name, "quality": update.quality, "royaltyRate": update.royaltyRate, "salesPrice": update.salesPrice, "unit": update.unit}

@app.delete("/api/admin/minerals/{mineral_name}")
async def delete_mineral(mineral_name: str, email: str = Depends(verify_admin)):
    result = minerals_collection.delete_one({"name": mineral_name})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Mineral not found")
    return {"message": "Mineral deleted"}

# Star Rating endpoints
@app.post("/api/star-rating")
async def save_star_rating(data: StarRatingData, email: str = Depends(verify_token)):
    rating_data = data.dict()
    rating_data["email"] = email
    rating_data["created_at"] = datetime.utcnow()
    rating_data["updated_at"] = datetime.utcnow()
    
    # Check if rating exists for this year and user
    existing = star_ratings_collection.find_one({"email": email, "year": data.year})
    if existing:
        star_ratings_collection.update_one(
            {"email": email, "year": data.year},
            {"$set": {**rating_data, "updated_at": datetime.utcnow()}}
        )
        return {"message": "Star rating updated", "id": str(existing["_id"])}
    else:
        result = star_ratings_collection.insert_one(rating_data)
        return {"message": "Star rating saved", "id": str(result.inserted_id)}

@app.get("/api/star-rating/{year}")
async def get_star_rating(year: int, email: str = Depends(verify_token)):
    rating = star_ratings_collection.find_one({"email": email, "year": year}, {"_id": 0})
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    return rating

@app.get("/api/star-ratings")
async def get_all_star_ratings(email: str = Depends(verify_token)):
    ratings = list(star_ratings_collection.find({"email": email}, {"_id": 0}).sort("year", -1))
    return ratings

# Ebook endpoints
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), email: str = Depends(verify_token)):
    if not s3_client:
        raise HTTPException(status_code=500, detail="AWS S3 not configured")
    
    try:
        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        # Upload to S3
        s3_client.upload_fileobj(
            file.file,
            AWS_BUCKET_NAME,
            unique_filename,
            ExtraArgs={'ContentType': file.content_type}
        )
        
        # Generate URL
        file_url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{unique_filename}"
        
        return {"url": file_url}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/api/ebooks")
async def get_ebooks(category: Optional[str] = None, email: str = Depends(verify_token)):
    query = {}
    if category and category != "All":
        query["category"] = category
    ebooks = list(ebooks_collection.find(query, {"_id": 0}).sort("createdAt", -1))
    
    # Get user subscription plan
    user = users_collection.find_one({"email": email})
    user_plan = user.get("subscriptionPlan", "Free")
    
    plan_hierarchy = {"Free": 0, "Basic": 1, "Premium": 2}
    
    for ebook in ebooks:
        required_plan = ebook.get("requiredPlan", "Free")
        ebook["hasAccess"] = plan_hierarchy.get(user_plan, 0) >= plan_hierarchy.get(required_plan, 0)
    
    return ebooks

@app.get("/api/ebooks/{ebook_id}")
async def get_ebook(ebook_id: str, email: str = Depends(verify_token)):
    ebook = ebooks_collection.find_one({"id": ebook_id}, {"_id": 0})
    if not ebook:
        raise HTTPException(status_code=404, detail="Ebook not found")
    
    user = users_collection.find_one({"email": email})
    user_plan = user.get("subscriptionPlan", "Free")
    required_plan = ebook.get("requiredPlan", "Free")
    
    plan_hierarchy = {"Free": 0, "Basic": 1, "Premium": 2}
    ebook["hasAccess"] = plan_hierarchy.get(user_plan, 0) >= plan_hierarchy.get(required_plan, 0)
    
    return ebook

@app.post("/api/admin/ebooks")
async def create_ebook(ebook: Ebook, email: str = Depends(verify_admin)):
    import uuid
    ebook_data = ebook.dict()
    ebook_data["id"] = str(uuid.uuid4())
    ebook_data["createdAt"] = datetime.utcnow()
    ebook_data["updatedAt"] = datetime.utcnow()
    ebooks_collection.insert_one(ebook_data)
    return ebook_data

@app.put("/api/admin/ebooks/{ebook_id}")
async def update_ebook(ebook_id: str, update: EbookUpdate, email: str = Depends(verify_admin)):
    update_data = {k: v for k, v in update.dict().items() if v is not None}
    update_data["updatedAt"] = datetime.utcnow()
    
    result = ebooks_collection.update_one({"id": ebook_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Ebook not found")
    
    updated = ebooks_collection.find_one({"id": ebook_id}, {"_id": 0})
    return updated

@app.delete("/api/admin/ebooks/{ebook_id}")
async def delete_ebook(ebook_id: str, email: str = Depends(verify_admin)):
    result = ebooks_collection.delete_one({"id": ebook_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Ebook not found")
    purchases_collection.delete_many({"ebookId": ebook_id})
    return {"message": "Ebook deleted"}

@app.get("/api/my-library")
async def get_my_library(email: str = Depends(verify_token)):
    user = users_collection.find_one({"email": email})
    user_plan = user.get("subscriptionPlan", "Free")
    
    plan_hierarchy = {"Free": 0, "Basic": 1, "Premium": 2}
    user_level = plan_hierarchy.get(user_plan, 0)
    
    ebooks = list(ebooks_collection.find({}, {"_id": 0}))
    accessible_ebooks = []
    
    for ebook in ebooks:
        required_plan = ebook.get("requiredPlan", "Free")
        if user_level >= plan_hierarchy.get(required_plan, 0):
            ebook["hasAccess"] = True
            accessible_ebooks.append(ebook)
    
    return accessible_ebooks

@app.put("/api/profile/subscription")
async def update_subscription(plan: str, email: str = Depends(verify_token)):
    if plan not in ["Free", "Basic", "Premium"]:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    users_collection.update_one({"email": email}, {"$set": {"subscriptionPlan": plan}})
    return {"message": "Subscription updated", "plan": plan}

@app.post("/api/monthly-returns")
async def create_monthly_return(data: MonthlyReturn, email: str = Depends(verify_token)):
    return_data = data.dict()
    return_data["email"] = email
    return_data["id"] = str(uuid.uuid4())
    return_data["createdAt"] = datetime.utcnow()
    monthly_returns_collection.insert_one(return_data)
    return {"message": "Monthly return saved", "id": return_data["id"]}

@app.get("/api/monthly-returns")
async def get_monthly_returns(email: str = Depends(verify_token)):
    returns = list(monthly_returns_collection.find({"email": email}, {"_id": 0}).sort("createdAt", -1))
    return returns

@app.post("/api/contact")
async def submit_contact(contact: ContactForm):
    contact_data = contact.dict()
    contact_data["createdAt"] = datetime.utcnow()
    contact_data["id"] = str(uuid.uuid4())
    db["contacts"].insert_one(contact_data)
    return {"message": "Contact form submitted successfully", "id": contact_data["id"]}

@app.post("/api/create-order")
async def create_order(order: PaymentOrder):
    if not razorpay_client:
        raise HTTPException(status_code=500, detail="Razorpay not configured")
    
    try:
        razorpay_order = razorpay_client.order.create({
            "amount": order.amount * 100,
            "currency": "INR",
            "payment_capture": 1
        })
        
        return {
            "order_id": razorpay_order["id"],
            "amount": razorpay_order["amount"],
            "currency": razorpay_order["currency"],
            "razorpay_key": RAZORPAY_KEY_ID
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/verify-payment")
async def verify_payment(verification: PaymentVerification):
    if not razorpay_client:
        raise HTTPException(status_code=500, detail="Razorpay not configured")
    
    try:
        # Verify signature
        generated_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode(),
            f"{verification.razorpay_order_id}|{verification.razorpay_payment_id}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        if generated_signature != verification.razorpay_signature:
            raise HTTPException(status_code=400, detail="Invalid payment signature")
        
        # Check if user already exists
        if users_collection.find_one({"email": verification.email}):
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Create user
        user_data = {
            "name": verification.name,
            "email": verification.email,
            "password": hash_password(verification.password),
            "role": verification.role,
            "paymentStatus": "paid",
            "paymentId": verification.razorpay_payment_id,
            "orderId": verification.razorpay_order_id,
            "created_at": datetime.utcnow()
        }
        users_collection.insert_one(user_data)
        
        # Store payment record
        db["payments"].insert_one({
            "email": verification.email,
            "orderId": verification.razorpay_order_id,
            "paymentId": verification.razorpay_payment_id,
            "amount": verification.amount if hasattr(verification, 'amount') else 0,
            "role": verification.role,
            "status": "success",
            "createdAt": datetime.utcnow()
        })
        
        return {"success": True, "message": "Payment verified and account created"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

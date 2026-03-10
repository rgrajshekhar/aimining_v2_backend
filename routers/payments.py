from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
import uuid
import hmac
import hashlib
import razorpay
from models import ContactForm, PaymentOrder, PaymentVerification
from database import contacts_collection, payments_collection, users_collection
from security import hash_password, verify_token
from config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET

router = APIRouter(prefix="/api", tags=["payments"])

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)) if RAZORPAY_KEY_ID else None

@router.post("/contact")
async def submit_contact(contact: ContactForm):
    contact_data = contact.dict()
    contact_data["createdAt"] = datetime.utcnow()
    contact_data["id"] = str(uuid.uuid4())
    contacts_collection.insert_one(contact_data)
    return {"message": "Contact form submitted successfully", "id": contact_data["id"]}

@router.post("/create-order")
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

@router.post("/verify-payment")
async def verify_payment(verification: PaymentVerification):
    if not razorpay_client:
        raise HTTPException(status_code=500, detail="Razorpay not configured")
    
    try:
        generated_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode(),
            f"{verification.razorpay_order_id}|{verification.razorpay_payment_id}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        if generated_signature != verification.razorpay_signature:
            raise HTTPException(status_code=400, detail="Invalid payment signature")
        
        if users_collection.find_one({"email": verification.email}):
            raise HTTPException(status_code=400, detail="Email already registered")
        
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
        
        payments_collection.insert_one({
            "email": verification.email,
            "orderId": verification.razorpay_order_id,
            "paymentId": verification.razorpay_payment_id,
            "role": verification.role,
            "status": "success",
            "createdAt": datetime.utcnow()
        })
        
        return {"success": True, "message": "Payment verified and account created"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

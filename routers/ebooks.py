from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from datetime import datetime
from typing import Optional
import uuid
import os
import boto3
from botocore.exceptions import ClientError
from models import Ebook, EbookUpdate
from database import ebooks_collection, users_collection, purchases_collection
from security import verify_token, verify_admin
from config import AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_BUCKET_NAME, AWS_REGION

router = APIRouter(prefix="/api", tags=["ebooks"])

s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
) if AWS_ACCESS_KEY else None

PLAN_HIERARCHY = {"Free": 0, "Basic": 1, "Premium": 2}

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), email: str = Depends(verify_token)):
    if not s3_client:
        raise HTTPException(status_code=500, detail="AWS S3 not configured")
    
    try:
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        s3_client.upload_fileobj(
            file.file,
            AWS_BUCKET_NAME,
            unique_filename,
            ExtraArgs={'ContentType': file.content_type}
        )
        
        file_url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{unique_filename}"
        return {"url": file_url}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/ebooks")
async def get_ebooks(category: Optional[str] = None, email: str = Depends(verify_token)):
    query = {} if not category or category == "All" else {"category": category}
    ebooks = list(ebooks_collection.find(query, {"_id": 0}).sort("createdAt", -1))
    
    user = users_collection.find_one({"email": email})
    user_plan = user.get("subscriptionPlan", "Free")
    user_level = PLAN_HIERARCHY.get(user_plan, 0)
    
    for ebook in ebooks:
        required_plan = ebook.get("requiredPlan", "Free")
        ebook["hasAccess"] = user_level >= PLAN_HIERARCHY.get(required_plan, 0)
    
    return ebooks

@router.get("/ebooks/{ebook_id}")
async def get_ebook(ebook_id: str, email: str = Depends(verify_token)):
    ebook = ebooks_collection.find_one({"id": ebook_id}, {"_id": 0})
    if not ebook:
        raise HTTPException(status_code=404, detail="Ebook not found")
    
    user = users_collection.find_one({"email": email})
    user_plan = user.get("subscriptionPlan", "Free")
    required_plan = ebook.get("requiredPlan", "Free")
    
    ebook["hasAccess"] = PLAN_HIERARCHY.get(user_plan, 0) >= PLAN_HIERARCHY.get(required_plan, 0)
    return ebook

@router.post("/admin/ebooks")
async def create_ebook(ebook: Ebook, email: str = Depends(verify_admin)):
    ebook_data = ebook.dict()
    ebook_data["id"] = str(uuid.uuid4())
    ebook_data["createdAt"] = datetime.utcnow()
    ebook_data["updatedAt"] = datetime.utcnow()
    ebooks_collection.insert_one(ebook_data)
    return ebook_data

@router.put("/admin/ebooks/{ebook_id}")
async def update_ebook(ebook_id: str, update: EbookUpdate, email: str = Depends(verify_admin)):
    update_data = {k: v for k, v in update.dict().items() if v is not None}
    update_data["updatedAt"] = datetime.utcnow()
    
    result = ebooks_collection.update_one({"id": ebook_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Ebook not found")
    
    updated = ebooks_collection.find_one({"id": ebook_id}, {"_id": 0})
    return updated

@router.delete("/admin/ebooks/{ebook_id}")
async def delete_ebook(ebook_id: str, email: str = Depends(verify_admin)):
    result = ebooks_collection.delete_one({"id": ebook_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Ebook not found")
    purchases_collection.delete_many({"ebookId": ebook_id})
    return {"message": "Ebook deleted"}

@router.get("/my-library")
async def get_my_library(email: str = Depends(verify_token)):
    user = users_collection.find_one({"email": email})
    user_plan = user.get("subscriptionPlan", "Free")
    user_level = PLAN_HIERARCHY.get(user_plan, 0)
    
    ebooks = list(ebooks_collection.find({}, {"_id": 0}))
    accessible_ebooks = []
    
    for ebook in ebooks:
        required_plan = ebook.get("requiredPlan", "Free")
        if user_level >= PLAN_HIERARCHY.get(required_plan, 0):
            ebook["hasAccess"] = True
            accessible_ebooks.append(ebook)
    
    return accessible_ebooks

from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from models import UserProfile
from database import users_collection, sessions_collection
from security import verify_token, verify_admin

router = APIRouter(prefix="/api", tags=["users"])

@router.get("/profile")
async def get_profile(email: str = Depends(verify_token)):
    user = users_collection.find_one({"email": email}, {"password": 0, "_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/profile")
async def update_profile(profile: UserProfile, email: str = Depends(verify_token)):
    if profile.email != email:
        existing = users_collection.find_one({"email": profile.email})
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
    
    update_data = {
        "name": profile.name,
        "email": profile.email,
        "role": profile.role,
        "updated_at": datetime.utcnow()
    }
    
    optional_fields = ["bio", "location", "website", "lesseeId", "firmName", 
                      "managingDirector", "lesseeAddress", "aadharNo", "panCardNo", 
                      "mobileNo", "additionalInfo", "subscriptionPlan"]
    
    for field in optional_fields:
        value = getattr(profile, field, None)
        if value is not None:
            update_data[field] = value
    
    if profile.mines is not None:
        update_data["mines"] = [mine.dict() for mine in profile.mines]
    
    result = users_collection.update_one({"email": email}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    if profile.email != email:
        sessions_collection.update_many({"email": email}, {"$set": {"email": profile.email}})
    
    updated_user = users_collection.find_one({"email": profile.email}, {"password": 0, "_id": 0})
    return updated_user

@router.put("/profile/subscription")
async def update_subscription(plan: str, email: str = Depends(verify_token)):
    if plan not in ["Free", "Basic", "Premium"]:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    users_collection.update_one({"email": email}, {"$set": {"subscriptionPlan": plan}})
    return {"message": "Subscription updated", "plan": plan}

@router.get("/admin/users")
async def get_all_users(email: str = Depends(verify_admin)):
    users = list(users_collection.find({}, {"password": 0, "_id": 0}))
    return users

@router.delete("/admin/users/{user_email}")
async def delete_user(user_email: str, email: str = Depends(verify_admin)):
    result = users_collection.delete_one({"email": user_email})
    sessions_collection.delete_many({"email": user_email})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted"}

@router.get("/admin/stats")
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

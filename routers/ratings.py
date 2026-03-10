from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from models import StarRatingData
from database import star_ratings_collection
from security import verify_token

router = APIRouter(prefix="/api", tags=["ratings"])

@router.post("/star-rating")
async def save_star_rating(data: StarRatingData, email: str = Depends(verify_token)):
    rating_data = data.dict()
    rating_data["email"] = email
    rating_data["created_at"] = datetime.utcnow()
    rating_data["updated_at"] = datetime.utcnow()
    
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

@router.get("/star-rating/{year}")
async def get_star_rating(year: int, email: str = Depends(verify_token)):
    rating = star_ratings_collection.find_one({"email": email, "year": year}, {"_id": 0})
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    return rating

@router.get("/star-ratings")
async def get_all_star_ratings(email: str = Depends(verify_token)):
    ratings = list(star_ratings_collection.find({"email": email}, {"_id": 0}).sort("year", -1))
    return ratings

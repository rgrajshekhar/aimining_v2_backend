from fastapi import APIRouter, Depends
from datetime import datetime
import uuid
from models import MonthlyReturn
from database import monthly_returns_collection
from security import verify_token

router = APIRouter(prefix="/api", tags=["returns"])

@router.post("/monthly-returns")
async def create_monthly_return(data: MonthlyReturn, email: str = Depends(verify_token)):
    return_data = data.dict()
    return_data["email"] = email
    return_data["id"] = str(uuid.uuid4())
    return_data["createdAt"] = datetime.utcnow()
    monthly_returns_collection.insert_one(return_data)
    return {"message": "Monthly return saved", "id": return_data["id"]}

@router.get("/monthly-returns")
async def get_monthly_returns(email: str = Depends(verify_token)):
    returns = list(monthly_returns_collection.find({"email": email}, {"_id": 0}).sort("createdAt", -1))
    return returns

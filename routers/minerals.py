from fastapi import APIRouter, HTTPException, Depends
from models import Mineral, MineralUpdate, RoyaltyInput
from database import minerals_collection
from security import verify_admin

router = APIRouter(prefix="/api", tags=["minerals"])

@router.get("/minerals")
async def get_minerals():
    minerals = list(minerals_collection.find({}))
    for mineral in minerals:
        mineral["_id"] = str(mineral["_id"])
    return minerals

@router.post("/admin/minerals")
async def create_mineral(mineral: Mineral, email: str = Depends(verify_admin)):
    if minerals_collection.find_one({"name": mineral.name}):
        raise HTTPException(status_code=400, detail="Mineral already exists")
    minerals_collection.insert_one(mineral.dict())
    return mineral

@router.put("/admin/minerals/{mineral_name}")
async def update_mineral(mineral_name: str, update: MineralUpdate, email: str = Depends(verify_admin)):
    result = minerals_collection.update_one(
        {"name": mineral_name}, 
        {"$set": update.dict()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Mineral not found")
    return {"name": mineral_name, **update.dict()}

@router.delete("/admin/minerals/{mineral_name}")
async def delete_mineral(mineral_name: str, email: str = Depends(verify_admin)):
    result = minerals_collection.delete_one({"name": mineral_name})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Mineral not found")
    return {"message": "Mineral deleted"}

@router.post("/calculate-royalty")
async def calculate_royalty(inputs: RoyaltyInput):
    royalty = inputs.royaltyRate * inputs.quantity
    deadRent = (inputs.area * 30000) / 12
    base_amount = royalty if royalty > deadRent else deadRent
    
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

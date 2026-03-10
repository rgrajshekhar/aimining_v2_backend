from pydantic import BaseModel, EmailStr
from typing import Optional, List

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

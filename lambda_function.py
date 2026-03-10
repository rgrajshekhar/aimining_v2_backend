from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import CORS_ORIGINS
from routers import auth, users, minerals, ebooks, ratings, returns, payments
from mangum import Mangum
app = FastAPI(title="CreatorNexus API", version="1.0.0")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(minerals.router)
app.include_router(ebooks.router)
app.include_router(ratings.router)
app.include_router(returns.router)
app.include_router(payments.router)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

handler = Mangum(app)   


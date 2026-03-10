from pymongo import MongoClient
from config import MONGO_URI, DB_NAME

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# Collections
users_collection = db["users"]
sessions_collection = db["sessions"]
minerals_collection = db["minerals"]
star_ratings_collection = db["star_ratings"]
ebooks_collection = db["ebooks"]
purchases_collection = db["purchases"]
monthly_returns_collection = db["monthly_returns"]
contacts_collection = db["contacts"]
payments_collection = db["payments"]

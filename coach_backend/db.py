import os
import certifi
from pymongo import MongoClient
from dotenv import load_dotenv
from pathlib import Path

# Load from backend/.env (sibling directory)
env_path = Path(__file__).resolve().parent.parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path)

MONGO_URL = os.getenv("MONGO_URL")

if not MONGO_URL:
    raise ValueError("No MONGO_URL found in environment variables")

# Use certifi for SSL certificate verification (fixes common Mac SSL errors)
client = MongoClient(MONGO_URL, tlsCAFile=certifi.where())
db = client.get_database("totem_coach_db")

totems_collection = db.get_collection("totems")
users_collection = db.get_collection("users")
goals_collection = db.get_collection("goals")

# Indexes
totems_collection.create_index("nfc_id", unique=True)
users_collection.create_index("user_id", unique=True)
goals_collection.create_index("user_id")
coaches_collection = db.get_collection("coaches")

# Ensure unique index on nfc_id
coaches_collection.create_index("nfc_id", unique=True)

# Test connection
try:
    client.admin.command('ping')
    print("Successfully connected to MongoDB!")
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")

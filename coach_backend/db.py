import os
import certifi
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")

if not MONGO_URL:
    raise ValueError("No MONGO_URL found in environment variables")

# Use certifi for SSL certificate verification (fixes common Mac SSL errors)
client = MongoClient(MONGO_URL, tlsCAFile=certifi.where())
db = client.get_database("totem_coach_db")
coaches_collection = db.get_collection("coaches")

# Ensure unique index on nfc_id
coaches_collection.create_index("nfc_id", unique=True)

# Test connection
try:
    client.admin.command('ping')
    print("Successfully connected to MongoDB!")
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")

import sys
import json
from datetime import datetime
from coach_manager import get_or_create_user_by_nfc, get_user_goals
from rag_stub import get_rag_context

def load_session(nfc_id: str) -> dict:
    """
    Orchestrates the loading of a user session.
    1. Identifies user via MongoDB (Identity).
    2. Retrieves goals via MongoDB (Profile).
    3. Retrieves context via RAG (Wisdom).
    4. Bundles into a single JSON payload.
    """
    
    # 1. Identity (MongoDB)
    # This function already handles looking up the Totem and getting/creating the User
    user_data = get_or_create_user_by_nfc(nfc_id)
    
    # If the user is brand new (e.g. no user_id yet or just created), 
    # nfc_id might be the only robust identifier we have initially if creation failed,
    # but get_or_create should return a valid user dict.
    
    user_id = user_data.get("user_id")
    
    # Convert any datetime fields in user_data to ISO format strings
    # Also convert ObjectId if present in top level
    for k, v in user_data.items():
         if isinstance(v, datetime):
             user_data[k] = v.isoformat()
         # Check for ObjectId by string repr if types not available, or just convert all non-serializable
         if str(type(v)) == "<class 'bson.objectid.ObjectId'>":
             user_data[k] = str(v)
             
    # Recursively clean user_data just in case
    user_data = json.loads(json.dumps(user_data, default=str))

    # 2. Profile/Goals (MongoDB)
    goals = []
    if user_id:
        # Cursor to list
        goals = list(get_user_goals(user_id))
        # Convert ObjectIds to strings if necessary (usually happens in to_dict methods or manual processing)
        # Assuming goals are dicts
        for g in goals:
            if "_id" in g:
                g["_id"] = str(g["_id"])
            # Handle timestamps (created_at fields etc)
            for k, v in g.items():
                if isinstance(v, datetime):
                    g[k] = v.isoformat()

    # 3. Wisdom (RAG)
    # Only fetch RAG context if it's an existing user likely to have history
    rag_context = []
    if user_id:
       rag_context = get_rag_context(user_id, query="Current Context")

    # Logic to set welcome message based on onboarding status
    user_status = user_data.get("coach_type", "unset")
    
    # 4. Bundle Payload (Prepare the message for frontend)
    welcome_msg = ""
    if user_status == "unset":
        # Onboarding Trigger
        welcome_msg = "New totem detected. I am your Coach. Are you looking for Personal growth or Corporate leadership?"
    else:
        # Standard Welcome
        user_name = user_data.get("name", "User")
        welcome_msg = f"Welcome back, {user_name}. Your {user_status} session is ready."

    payload = {
        "type": "session_start",
        "nfc_id": nfc_id,
        "user": user_data,   
        "goals": goals,
        "context": rag_context,
        "welcome_message": welcome_msg, # Explicitly sending this to frontend
        "timestamp": "now"
    }
    
    return payload

if __name__ == "__main__":
    # Test
    print(json.dumps(load_session("TEST_TAG_123"), indent=2))

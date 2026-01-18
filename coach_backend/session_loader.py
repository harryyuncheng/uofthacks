import sys
import json
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

    # 3. Wisdom (RAG)
    # Only fetch RAG context if it's an existing user likely to have history
    rag_context = []
    if user_id:
        rag_context = get_rag_context(user_id, query="Current Context")

    # 4. Bundle Payload
    payload = {
        "type": "session_start",
        "nfc_id": nfc_id,
        "user": user_data,   # Includes name, coach_type, etc.
        "goals": goals,
        "context": rag_context,
        "timestamp": "now" # In real app use datetime.now().isoformat()
    }
    
    return payload

if __name__ == "__main__":
    # Test
    print(json.dumps(load_session("TEST_TAG_123"), indent=2))

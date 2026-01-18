from datetime import datetime
from models import CoachProfile
from db import coaches_collection

def get_or_create_coach(nfc_id: str) -> dict:
    """
    Retrieves an existing coach profile by NFC ID or creates a new one
    if it doesn't exist.
    """
    
    # Try to find existing coach
    existing_coach = coaches_collection.find_one({"nfc_id": nfc_id})
    
    if existing_coach:
        # Update last accessed time
        coaches_collection.update_one(
            {"nfc_id": nfc_id},
            {"$set": {"last_accessed": datetime.now()}}
        )
        print(f"Found existing coach for NFC ID: {nfc_id}")
        return existing_coach

    # Create new coach profile
    print(f"Creating new coach for NFC ID: {nfc_id}")
    new_coach = CoachProfile(nfc_id=nfc_id)
    
    # Default context is already set in the model ("You are a coach...")
    
    # Insert into DB
    result = coaches_collection.insert_one(new_coach.to_dict())
    
    # Return existence confirmed created object (or query it back)
    return coaches_collection.find_one({"_id": result.inserted_id})

def update_learned_context(nfc_id: str, new_info: str):
    """
    Appends new learned information to the user's context.
    """
    # In a real app, this would append to a string or update a vector DB
    # For now, we just append to the string field
    coach = coaches_collection.find_one({"nfc_id": nfc_id})
    if coach:
        current_context = coach.get("learned_context", "")
        updated_context = current_context + "\n" + new_info
        
        coaches_collection.update_one(
            {"nfc_id": nfc_id},
            {"$set": {"learned_context": updated_context}}
        )

def set_coach_type(nfc_id: str, type_str: str):
    """
    Sets the coach type (personal/corporate) and updates the system instruction.
    type_str should be 'personal' or 'corporate'.
    """
    if type_str.lower() not in ["personal", "corporate"]:
        return False
        
    s_prompt = ""
    if type_str.lower() == "personal":
        s_prompt = "You are a Personal Life Coach. Focus on health, well-being, and personal goals."
    else:
        s_prompt = "You are a Corporate Executive Coach. Focus on career growth, leadership, and productivity."

    coaches_collection.update_one(
        {"nfc_id": nfc_id},
        {"$set": {
            "coach_type": type_str.lower(),
            "onboarding_completed": True,
            "system_instruction": s_prompt
        }}
    )
    return True

def add_goal(nfc_id: str, title: str, description: str = ""):
    from models import Goal
    goal = Goal(title=title, description=description)
    
    coaches_collection.update_one(
        {"nfc_id": nfc_id},
        {"$push": {"goals": goal.dict()}}
    )

if __name__ == "__main__":
    # Test simulation
    test_nfc_id = "0415A2C3" # Example hex UID from Arduino
    
    coach = get_or_create_coach(test_nfc_id)
    print("Coach Profile:", coach)

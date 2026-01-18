from datetime import datetime
from models import User, Totem, Goal, CoachType
from db import users_collection, totems_collection, goals_collection

def get_or_create_user_by_nfc(nfc_id: str) -> dict:
    """
    1. Looks up Totem by NFC ID.
    2. If found, returns the linked User.
    3. If not found, creates a new User and a new Totem link.
    Returns: User dict (with nfc_id injected for convenience)
    """
    
    # 1. Check Totem
    totem = totems_collection.find_one({"nfc_id": nfc_id})
    
    if totem:
        user_id = totem["user_id"]
        user = users_collection.find_one({"user_id": user_id})
        if user:
            print(f"Found existing user {user.get('name')} for NFC {nfc_id}")
            user["nfc_id"] = nfc_id # Inject for convenience
            return user
        else:
            # Edge case: Totem exists but user deleted? Re-create user? 
            # For now, treat as new.
            pass

    # 2. Create New
    print(f"Creating new user for NFC ID: {nfc_id}")
    
    new_user = User() # Generates user_id auto
    new_totem = Totem(nfc_id=nfc_id, user_id=new_user.user_id)
    
    users_collection.insert_one(new_user.to_dict())
    totems_collection.insert_one(new_totem.to_dict())
    
    result_user = new_user.to_dict()
    result_user["nfc_id"] = nfc_id
    return result_user

def update_user_background(user_id: str, new_info: str):
    """
    Appends new learned information to the user's background.
    """
    user = users_collection.find_one({"user_id": user_id})
    if user:
        current_bg = user.get("background", "")
        updated_bg = current_bg + "\n" + new_info if current_bg else new_info
        
        users_collection.update_one(
            {"user_id": user_id},
            {"": {"background": updated_bg}}
        )

def set_coach_type(user_id: str, type_str: str):
    """
    Sets the coach type (personal/corporate) and updates the system instruction.
    """
    if type_str.lower() not in ["personal", "corporate"]:
        return False
        
    s_prompt = ""
    if type_str.lower() == "personal":
        s_prompt = "You are a Personal Life Coach. Focus on health, well-being, and personal goals."
    else:
        s_prompt = "You are a Corporate Executive Coach. Focus on career growth, leadership, and productivity."

    users_collection.update_one(
        {"user_id": user_id},
        {"": {
            "coach_type": type_str.lower(),
            "onboarding_completed": True,
            "system_instruction": s_prompt
        }}
    )
    return True

def create_goal(user_id: str, title: str, description: str = "", deadline: datetime = None):
    goal = Goal(
        user_id=user_id, 
        title=title, 
        description=description, 
        deadline=deadline
    )
    goals_collection.insert_one(goal.to_dict())
    
    # Link goal to user
    users_collection.update_one(
        {"user_id": user_id},
        {"$push": {"goal_ids": goal.goal_id}}
    )
    return goal

def get_user_goals(user_id: str):
    return list(goals_collection.find({"user_id": user_id}))

if __name__ == "__main__":
    # Test simulation
    test_nfc = "DEBUG_NFC_01"
    
    user = get_or_create_user_by_nfc(test_nfc)
    print("User:", user)
    
    add_goal = create_goal(user["user_id"], "Learn React", "Build a dashboard")
    print("Goal Created:", add_goal)

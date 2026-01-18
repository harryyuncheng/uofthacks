from datetime import datetimefrom datetime import datetime

from models import User, Totem, Goal, CoachTypefrom models import CoachProfile

from db import users_collection, totems_collection, goals_collectionfrom db import coaches_collection



def get_or_create_user_by_nfc(nfc_id: str) -> dict:def get_or_create_coach(nfc_id: str) -> dict:

    """    """

    1. Looks up Totem by NFC ID.    Retrieves an existing coach profile by NFC ID or creates a new one

    2. If found, returns the linked User.    if it doesn't exist.

    3. If not found, creates a new User and a new Totem link.    """

    Returns: User dict (with nfc_id injected for convenience)    

    """    # Try to find existing coach

        existing_coach = coaches_collection.find_one({"nfc_id": nfc_id})

    # 1. Check Totem    

    totem = totems_collection.find_one({"nfc_id": nfc_id})    if existing_coach:

            # Update last accessed time

    if totem:        coaches_collection.update_one(

        user_id = totem["user_id"]            {"nfc_id": nfc_id},

        user = users_collection.find_one({"user_id": user_id})            {"$set": {"last_accessed": datetime.now()}}

        if user:        )

            print(f"Found existing user {user.get('name')} for NFC {nfc_id}")        print(f"Found existing coach for NFC ID: {nfc_id}")

            user["nfc_id"] = nfc_id # Inject for convenience        return existing_coach

            return user

        else:    # Create new coach profile

            # Edge case: Totem exists but user deleted? Re-create user?     print(f"Creating new coach for NFC ID: {nfc_id}")

            # For now, treat as new.    new_coach = CoachProfile(nfc_id=nfc_id)

            pass    

    # Default context is already set in the model ("You are a coach...")

    # 2. Create New    

    print(f"Creating new user for NFC ID: {nfc_id}")    # Insert into DB

        result = coaches_collection.insert_one(new_coach.to_dict())

    new_user = User() # Generates user_id auto    

    new_totem = Totem(nfc_id=nfc_id, user_id=new_user.user_id)    # Return existence confirmed created object (or query it back)

        return coaches_collection.find_one({"_id": result.inserted_id})

    users_collection.insert_one(new_user.to_dict())

    totems_collection.insert_one(new_totem.to_dict())def update_learned_context(nfc_id: str, new_info: str):

        """

    result_user = new_user.to_dict()    Appends new learned information to the user's context.

    result_user["nfc_id"] = nfc_id    """

    return result_user    # In a real app, this would append to a string or update a vector DB

    # For now, we just append to the string field

def update_user_background(user_id: str, new_info: str):    coach = coaches_collection.find_one({"nfc_id": nfc_id})

    """    if coach:

    Appends new learned information to the user's background.        current_context = coach.get("learned_context", "")

    """        updated_context = current_context + "\n" + new_info

    user = users_collection.find_one({"user_id": user_id})        

    if user:        coaches_collection.update_one(

        current_bg = user.get("background", "")            {"nfc_id": nfc_id},

        updated_bg = current_bg + "\n" + new_info if current_bg else new_info            {"$set": {"learned_context": updated_context}}

                )

        users_collection.update_one(

            {"user_id": user_id},def set_coach_type(nfc_id: str, type_str: str):

            {"$set": {"background": updated_bg}}    """

        )    Sets the coach type (personal/corporate) and updates the system instruction.

    type_str should be 'personal' or 'corporate'.

def set_coach_type(user_id: str, type_str: str):    """

    """    if type_str.lower() not in ["personal", "corporate"]:

    Sets the coach type (personal/corporate) and updates the system instruction.        return False

    """        

    if type_str.lower() not in ["personal", "corporate"]:    s_prompt = ""

        return False    if type_str.lower() == "personal":

                s_prompt = "You are a Personal Life Coach. Focus on health, well-being, and personal goals."

    s_prompt = ""    else:

    if type_str.lower() == "personal":        s_prompt = "You are a Corporate Executive Coach. Focus on career growth, leadership, and productivity."

        s_prompt = "You are a Personal Life Coach. Focus on health, well-being, and personal goals."

    else:    coaches_collection.update_one(

        s_prompt = "You are a Corporate Executive Coach. Focus on career growth, leadership, and productivity."        {"nfc_id": nfc_id},

        {"$set": {

    users_collection.update_one(            "coach_type": type_str.lower(),

        {"user_id": user_id},            "onboarding_completed": True,

        {"$set": {            "system_instruction": s_prompt

            "coach_type": type_str.lower(),        }}

            "onboarding_completed": True,    )

            "system_instruction": s_prompt    return True

        }}

    )def add_goal(nfc_id: str, title: str, description: str = ""):

    return True    from models import Goal

    goal = Goal(title=title, description=description)

def create_goal(user_id: str, title: str, description: str = "", deadline: datetime = None):    

    goal = Goal(    coaches_collection.update_one(

        user_id=user_id,         {"nfc_id": nfc_id},

        title=title,         {"$push": {"goals": goal.dict()}}

        description=description,     )

        deadline=deadline

    )if __name__ == "__main__":

    goals_collection.insert_one(goal.to_dict())    # Test simulation

    return goal    test_nfc_id = "0415A2C3" # Example hex UID from Arduino

    

def get_user_goals(user_id: str):    coach = get_or_create_coach(test_nfc_id)

    return list(goals_collection.find({"user_id": user_id}))    print("Coach Profile:", coach)


if __name__ == "__main__":
    # Test simulation
    test_nfc = "DEBUG_NFC_01"
    
    user = get_or_create_user_by_nfc(test_nfc)
    print("User:", user)
    
    add_goal = create_goal(user["user_id"], "Learn React", "Build a dashboard")
    print("Goal Created:", add_goal)

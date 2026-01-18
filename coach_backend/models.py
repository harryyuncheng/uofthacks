from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum
import uuid

def generate_id():
    return str(uuid.uuid4())

# --- Enums ---

class GoalStatus(str, Enum):
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class CoachType(str, Enum):
    UNSET = "unset"
    PERSONAL = "personal"
    CORPORATE = "corporate"

# --- Models ---

class Totem(BaseModel):
    nfc_id: str
    user_id: str
    created_at: datetime = Field(default_factory=datetime.now)

    def to_dict(self):
        return self.dict()

class User(BaseModel):
    user_id: str = Field(default_factory=generate_id)
    name: str = "New User"
    
    # Coach Configuration
    personality: str = "Motivational, direct, friendly"
    coach_type: CoachType = CoachType.UNSET
    
    # RAG / Context
    background: str = "" # "High school student..."
    system_instruction: str = "You are a coach. Your first task is to ask the user if they want coaching for personal or business/corporate reasons."
    onboarding_completed: bool = False
    
    created_at: datetime = Field(default_factory=datetime.now)

    def to_dict(self):
        return self.dict()

class Goal(BaseModel):
    goal_id: str = Field(default_factory=generate_id)
    user_id: str
    title: str
    description: str = ""
    progress: int = 0
    deadline: Optional[datetime] = None
    status: GoalStatus = GoalStatus.IN_PROGRESS
    subgoals: List[str] = [] 
    created_at: datetime = Field(default_factory=datetime.now)

    def to_dict(self):
        return self.dict()

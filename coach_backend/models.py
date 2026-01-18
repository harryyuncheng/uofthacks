from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class Goal(BaseModel):
    title: str
    description: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    completed: bool = False
    completed_at: Optional[datetime] = None

class CoachType(str, Enum):
    UNSET = "unset"
    PERSONAL = "personal"
    CORPORATE = "corporate"

class CoachProfile(BaseModel):
    nfc_id: str
    name: str = "New User"
    
    # State and Type
    coach_type: CoachType = CoachType.UNSET
    onboarding_completed: bool = False
    
    # AI Context
    system_instruction: str = "You are a coach. Your first task is to ask the user if they want coaching for personal or business/corporate reasons."
    learned_context: str = "" # Accumulated background info about the mentee
    
    goals: List[Goal] = []
    goals_achieved: List[Goal] = []
    
    created_at: datetime = Field(default_factory=datetime.now)
    last_accessed: datetime = Field(default_factory=datetime.now)

    def to_dict(self):
        return self.dict()

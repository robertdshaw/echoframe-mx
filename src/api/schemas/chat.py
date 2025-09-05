from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class ChatMessage(BaseModel):
    content: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    sources: List[Dict[str, Any]] = []
    alerts: List[Dict[str, Any]] = []
    timestamp: datetime = datetime.utcnow()

class ChatSession(BaseModel):
    session_id: str
    user_id: Optional[str] = None
    messages: List[Dict[str, Any]] = []
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()

class ChatFeedback(BaseModel):
    message_id: str
    rating: int  # 1-5
    feedback: Optional[str] = None
    user_id: Optional[str] = None
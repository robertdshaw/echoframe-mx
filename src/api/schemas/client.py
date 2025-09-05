from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime
from ...models import SectorType

class ClientBase(BaseModel):
    name: str
    email: EmailStr
    company: Optional[str] = None
    sectors: List[SectorType] = []
    states: List[str] = []
    notification_frequency: str = "daily"
    metadata: Dict[str, Any] = {}

class ClientCreate(ClientBase):
    pass

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    company: Optional[str] = None
    sectors: Optional[List[SectorType]] = None
    states: Optional[List[str]] = None
    notification_frequency: Optional[str] = None
    is_active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None

class ClientResponse(ClientBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class EmailReportBase(BaseModel):
    subject: str
    content: str
    alert_ids: List[int] = []
    metadata: Dict[str, Any] = {}

class EmailReportCreate(EmailReportBase):
    client_id: int

class EmailReportResponse(EmailReportBase):
    id: int
    client_id: int
    sent_at: Optional[datetime] = None
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True
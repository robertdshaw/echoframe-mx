from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from ...models import RiskLevel, SectorType

class RiskAlertBase(BaseModel):
    risk_score: float
    risk_level: RiskLevel
    sector: SectorType
    summary: str
    details: Dict[str, Any] = {}

class RiskAlertCreate(RiskAlertBase):
    article_id: int
    risk_pattern_id: int

class RiskAlertResponse(RiskAlertBase):
    id: int
    article_id: int
    risk_pattern_id: int
    is_sent: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class RiskPatternBase(BaseModel):
    name: str
    sector: SectorType
    pattern_type: str
    keywords: List[str] = []
    risk_level: RiskLevel
    description: Optional[str] = None
    template: Dict[str, Any] = {}

class RiskPatternCreate(RiskPatternBase):
    pass

class RiskPatternResponse(RiskPatternBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any, List
from datetime import datetime
from ...models import ContentType, SourceType

class ArticleBase(BaseModel):
    title: str
    content: Optional[str] = None
    summary: Optional[str] = None
    url: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    language: str = "es"
    metadata: Dict[str, Any] = {}

class ArticleCreate(ArticleBase):
    source_id: int

class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    url: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    language: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ArticleResponse(ArticleBase):
    id: int
    source_id: int
    scraped_at: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True

class SourceBase(BaseModel):
    name: str
    url: Optional[str] = None
    source_type: SourceType
    content_type: ContentType
    country: str = "MEX"
    state: Optional[str] = None
    city: Optional[str] = None
    metadata: Dict[str, Any] = {}

class SourceCreate(SourceBase):
    pass

class SourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    source_type: Optional[SourceType] = None
    content_type: Optional[ContentType] = None
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    is_active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None

class SourceResponse(SourceBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
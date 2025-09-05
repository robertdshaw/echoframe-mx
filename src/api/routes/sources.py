from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import get_db
from ...models import Source, SourceType, ContentType
from ..schemas.article import SourceResponse, SourceCreate, SourceUpdate

router = APIRouter()

@router.get("/", response_model=List[SourceResponse])
async def get_sources(
    skip: int = 0,
    limit: int = 100,
    source_type: Optional[SourceType] = None,
    content_type: Optional[ContentType] = None,
    country: str = "MEX",
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db)
):
    query = db.query(Source).filter(Source.country == country)
    
    if source_type:
        query = query.filter(Source.source_type == source_type)
    if content_type:
        query = query.filter(Source.content_type == content_type)
    if is_active is not None:
        query = query.filter(Source.is_active == is_active)
    
    sources = query.offset(skip).limit(limit).all()
    return sources

@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source

@router.post("/", response_model=SourceResponse)
async def create_source(source: SourceCreate, db: Session = Depends(get_db)):
    db_source = Source(**source.dict())
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    return db_source

@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: int,
    source_update: SourceUpdate,
    db: Session = Depends(get_db)
):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    for field, value in source_update.dict(exclude_unset=True).items():
        setattr(source, field, value)
    
    db.commit()
    db.refresh(source)
    return source

@router.delete("/{source_id}")
async def delete_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    db.delete(source)
    db.commit()
    return {"message": "Source deleted successfully"}

@router.get("/{source_id}/articles")
async def get_source_articles(
    source_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    articles = db.query(Article).filter(Article.source_id == source_id).offset(skip).limit(limit).all()
    return articles
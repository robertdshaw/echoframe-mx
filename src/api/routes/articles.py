from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from typing import List, Optional
from datetime import datetime, timedelta
from ...database import get_db
from ...models import Article, Source, Entity, RiskAlert, SectorType, RiskLevel
from ..schemas.article import ArticleResponse, ArticleCreate, ArticleUpdate

router = APIRouter()

@router.get("/", response_model=List[ArticleResponse])
async def get_articles(
    skip: int = 0,
    limit: int = 100,
    source_id: Optional[int] = None,
    sector: Optional[SectorType] = None,
    risk_level: Optional[RiskLevel] = None,
    days_back: Optional[int] = 7,
    db: Session = Depends(get_db)
):
    query = db.query(Article)
    
    if source_id:
        query = query.filter(Article.source_id == source_id)
    
    if days_back:
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        query = query.filter(Article.published_at >= cutoff_date)
    
    if sector or risk_level:
        query = query.join(RiskAlert)
        if sector:
            query = query.filter(RiskAlert.sector == sector)
        if risk_level:
            query = query.filter(RiskAlert.risk_level == risk_level)
    
    articles = query.order_by(desc(Article.published_at)).offset(skip).limit(limit).all()
    return articles

@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: int, db: Session = Depends(get_db)):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article

@router.get("/{article_id}/entities")
async def get_article_entities(article_id: int, db: Session = Depends(get_db)):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    entities = db.query(Entity).filter(Entity.article_id == article_id).all()
    return entities

@router.get("/{article_id}/alerts")
async def get_article_alerts(article_id: int, db: Session = Depends(get_db)):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    alerts = db.query(RiskAlert).filter(RiskAlert.article_id == article_id).all()
    return alerts

@router.post("/", response_model=ArticleResponse)
async def create_article(article: ArticleCreate, db: Session = Depends(get_db)):
    db_article = Article(**article.dict())
    db.add(db_article)
    db.commit()
    db.refresh(db_article)
    return db_article

@router.put("/{article_id}", response_model=ArticleResponse)
async def update_article(
    article_id: int, 
    article_update: ArticleUpdate, 
    db: Session = Depends(get_db)
):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    for field, value in article_update.dict(exclude_unset=True).items():
        setattr(article, field, value)
    
    db.commit()
    db.refresh(article)
    return article

@router.delete("/{article_id}")
async def delete_article(article_id: int, db: Session = Depends(get_db)):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    db.delete(article)
    db.commit()
    return {"message": "Article deleted successfully"}

@router.get("/search/by-content")
async def search_articles(
    q: str = Query(..., min_length=3),
    limit: int = 50,
    db: Session = Depends(get_db)
):
    articles = db.query(Article).filter(
        Article.content.ilike(f"%{q}%") |
        Article.title.ilike(f"%{q}%") |
        Article.summary.ilike(f"%{q}%")
    ).limit(limit).all()
    
    return articles
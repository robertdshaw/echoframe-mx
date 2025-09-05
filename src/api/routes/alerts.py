from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from typing import List, Optional
from datetime import datetime, timedelta
from ...database import get_db
from ...models import RiskAlert, RiskLevel, SectorType, Article
from ..schemas.alert import RiskAlertResponse, RiskAlertCreate

router = APIRouter()

@router.get("/", response_model=List[RiskAlertResponse])
async def get_alerts(
    skip: int = 0,
    limit: int = 100,
    sector: Optional[SectorType] = None,
    risk_level: Optional[RiskLevel] = None,
    days_back: int = 7,
    min_score: Optional[float] = None,
    db: Session = Depends(get_db)
):
    query = db.query(RiskAlert)
    
    cutoff_date = datetime.utcnow() - timedelta(days=days_back)
    query = query.filter(RiskAlert.created_at >= cutoff_date)
    
    if sector:
        query = query.filter(RiskAlert.sector == sector)
    if risk_level:
        query = query.filter(RiskAlert.risk_level == risk_level)
    if min_score:
        query = query.filter(RiskAlert.risk_score >= min_score)
    
    alerts = query.order_by(desc(RiskAlert.risk_score), desc(RiskAlert.created_at)).offset(skip).limit(limit).all()
    return alerts

@router.get("/critical", response_model=List[RiskAlertResponse])
async def get_critical_alerts(
    hours_back: int = 24,
    db: Session = Depends(get_db)
):
    cutoff_date = datetime.utcnow() - timedelta(hours=hours_back)
    alerts = db.query(RiskAlert).filter(
        and_(
            RiskAlert.risk_level == RiskLevel.CRITICAL,
            RiskAlert.created_at >= cutoff_date
        )
    ).order_by(desc(RiskAlert.created_at)).all()
    
    return alerts

@router.get("/dashboard")
async def get_dashboard_stats(
    days_back: int = 7,
    db: Session = Depends(get_db)
):
    cutoff_date = datetime.utcnow() - timedelta(days=days_back)
    
    total_alerts = db.query(RiskAlert).filter(RiskAlert.created_at >= cutoff_date).count()
    critical_alerts = db.query(RiskAlert).filter(
        and_(
            RiskAlert.risk_level == RiskLevel.CRITICAL,
            RiskAlert.created_at >= cutoff_date
        )
    ).count()
    high_alerts = db.query(RiskAlert).filter(
        and_(
            RiskAlert.risk_level == RiskLevel.HIGH,
            RiskAlert.created_at >= cutoff_date
        )
    ).count()
    
    sector_breakdown = db.query(
        RiskAlert.sector,
        db.func.count(RiskAlert.id).label('count')
    ).filter(RiskAlert.created_at >= cutoff_date).group_by(RiskAlert.sector).all()
    
    return {
        "total_alerts": total_alerts,
        "critical_alerts": critical_alerts,
        "high_alerts": high_alerts,
        "sector_breakdown": [{"sector": s.sector, "count": s.count} for s in sector_breakdown]
    }

@router.get("/{alert_id}", response_model=RiskAlertResponse)
async def get_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert

@router.post("/", response_model=RiskAlertResponse)
async def create_alert(alert: RiskAlertCreate, db: Session = Depends(get_db)):
    db_alert = RiskAlert(**alert.dict())
    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)
    return db_alert

@router.put("/{alert_id}/mark-sent")
async def mark_alert_sent(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.is_sent = True
    db.commit()
    return {"message": "Alert marked as sent"}

@router.get("/by-sector/{sector}")
async def get_alerts_by_sector(
    sector: SectorType,
    days_back: int = 30,
    db: Session = Depends(get_db)
):
    cutoff_date = datetime.utcnow() - timedelta(days=days_back)
    alerts = db.query(RiskAlert).filter(
        and_(
            RiskAlert.sector == sector,
            RiskAlert.created_at >= cutoff_date
        )
    ).order_by(desc(RiskAlert.risk_score)).all()
    
    return alerts
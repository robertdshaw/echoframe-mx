from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import get_db
from ...models import Client, SectorType
from ..schemas.client import ClientResponse, ClientCreate, ClientUpdate

router = APIRouter()

@router.get("/", response_model=List[ClientResponse])
async def get_clients(
    skip: int = 0,
    limit: int = 100,
    sector: Optional[SectorType] = None,
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db)
):
    query = db.query(Client)
    
    if is_active is not None:
        query = query.filter(Client.is_active == is_active)
    if sector:
        query = query.filter(Client.sectors.contains([sector]))
    
    clients = query.offset(skip).limit(limit).all()
    return clients

@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: int, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@router.post("/", response_model=ClientResponse)
async def create_client(client: ClientCreate, db: Session = Depends(get_db)):
    # Check if email already exists
    existing = db.query(Client).filter(Client.email == client.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    db_client = Client(**client.dict())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    client_update: ClientUpdate,
    db: Session = Depends(get_db)
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Check email uniqueness if being updated
    if client_update.email and client_update.email != client.email:
        existing = db.query(Client).filter(Client.email == client_update.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
    
    for field, value in client_update.dict(exclude_unset=True).items():
        setattr(client, field, value)
    
    db.commit()
    db.refresh(client)
    return client

@router.delete("/{client_id}")
async def delete_client(client_id: int, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Soft delete - just deactivate
    client.is_active = False
    db.commit()
    return {"message": "Client deactivated successfully"}

@router.get("/{client_id}/reports")
async def get_client_reports(
    client_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    reports = db.query(EmailReport).filter(
        EmailReport.client_id == client_id
    ).order_by(desc(EmailReport.created_at)).offset(skip).limit(limit).all()
    
    return reports
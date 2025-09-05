from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from ..database import get_db, engine
from ..models import Base
from .routes import articles, sources, alerts, clients, chat
import uvicorn

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EchoFrame MX",
    description="Intelligent Risk Monitoring for Mexico",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(articles.router, prefix="/api/v1/articles", tags=["articles"])
app.include_router(sources.router, prefix="/api/v1/sources", tags=["sources"])
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["alerts"])
app.include_router(clients.router, prefix="/api/v1/clients", tags=["clients"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])

@app.get("/")
async def root():
    return {"message": "EchoFrame MX API", "version": "1.0.0"}

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
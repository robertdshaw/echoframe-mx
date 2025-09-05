from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import asyncio
from ...database import get_db
from ...chat.chat_handler import ChatHandler
from ..schemas.chat import ChatMessage, ChatResponse

router = APIRouter()
chat_handler = ChatHandler()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def send_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

manager = ConnectionManager()

@router.post("/message", response_model=ChatResponse)
async def send_message(message: ChatMessage, db: Session = Depends(get_db)):
    try:
        response = await chat_handler.process_message(message.content, db)
        return ChatResponse(
            response=response["text"],
            sources=response.get("sources", []),
            alerts=response.get("alerts", [])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Process message
            response = await chat_handler.process_message(message_data["content"], db)
            
            # Send response
            await manager.send_message(json.dumps({
                "response": response["text"],
                "sources": response.get("sources", []),
                "alerts": response.get("alerts", [])
            }), websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        await manager.send_message(json.dumps({
            "error": f"Chat error: {str(e)}"
        }), websocket)

@router.get("/history")
async def get_chat_history(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    # Implementation would depend on chat history storage
    return {"message": "Chat history endpoint - implementation needed"}

@router.post("/feedback")
async def submit_feedback(
    message_id: str,
    rating: int,
    feedback: Optional[str] = None,
    db: Session = Depends(get_db)
):
    # Store feedback for improving responses
    return {"message": "Feedback received"}

@router.get("/suggestions")
async def get_chat_suggestions(db: Session = Depends(get_db)):
    # Return suggested queries based on recent alerts
    suggestions = [
        "¿Cuáles son los últimos riesgos críticos en el sector energético?",
        "Muéstrame alertas recientes en Jalisco",
        "¿Qué patrones de riesgo están activos para farmacéuticas?",
        "Resumen de alertas de la última semana"
    ]
    return {"suggestions": suggestions}
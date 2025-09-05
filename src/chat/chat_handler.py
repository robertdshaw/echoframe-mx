import asyncio
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc
from ..models import Article, RiskAlert, Source, RiskLevel, SectorType
from ..rag.vector_store import VectorStore
from ..config import settings
import openai

logger = logging.getLogger(__name__)

class ChatHandler:
    def __init__(self):
        self.vector_store = VectorStore()
        self.openai_client = None
        if settings.openai_api_key:
            self.openai_client = openai.OpenAI(api_key=settings.openai_api_key)
    
    async def process_message(self, user_message: str, db: Session) -> Dict:
        """Process user chat message and return response"""
        try:
            # Classify the user's intent
            intent = await self.classify_intent(user_message)
            
            response = await self.handle_intent(intent, user_message, db)
            return response
            
        except Exception as e:
            logger.error(f"Error processing chat message: {str(e)}")
            return {
                "text": "Lo siento, hubo un error procesando tu consulta. Por favor intenta de nuevo.",
                "sources": [],
                "alerts": []
            }
    
    async def classify_intent(self, message: str) -> Dict:
        """Classify user intent using AI"""
        if not self.openai_client:
            return self.fallback_intent_classification(message)
        
        try:
            system_prompt = """Analiza el siguiente mensaje del usuario y clasifica su intención.
            
            Responde ÚNICAMENTE con un JSON válido en este formato:
            {
                "intent": "search|alerts|stats|trends|help",
                "entities": {
                    "sector": "energy|pharma|mining|finance|manufacturing|infrastructure",
                    "location": "estado o ciudad mencionada",
                    "time_period": "recent|week|month|specific_date",
                    "risk_level": "critical|high|medium|low",
                    "keywords": ["palabra1", "palabra2"]
                }
            }
            
            Intenciones posibles:
            - search: buscar información específica
            - alerts: consultar alertas de riesgo
            - stats: estadísticas y métricas
            - trends: tendencias y análisis temporal
            - help: ayuda o información general"""
            
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                max_tokens=200,
                temperature=0.1
            )
            
            intent_json = response.choices[0].message.content.strip()
            return json.loads(intent_json)
            
        except Exception as e:
            logger.error(f"Error classifying intent: {str(e)}")
            return self.fallback_intent_classification(message)
    
    def fallback_intent_classification(self, message: str) -> Dict:
        """Fallback intent classification using keywords"""
        message_lower = message.lower()
        
        intent = "help"  # default
        entities = {"keywords": []}
        
        # Intent classification
        if any(word in message_lower for word in ['buscar', 'encontrar', 'información', 'qué es', 'dónde']):
            intent = "search"
        elif any(word in message_lower for word in ['alerta', 'riesgo', 'crítico', 'peligro']):
            intent = "alerts"
        elif any(word in message_lower for word in ['estadística', 'cuánto', 'número', 'cantidad']):
            intent = "stats"
        elif any(word in message_lower for word in ['tendencia', 'últimos', 'reciente', 'cambio']):
            intent = "trends"
        
        # Extract sectors
        sector_keywords = {
            'energy': ['energía', 'pemex', 'cfe', 'petróleo', 'electricidad', 'renovable'],
            'pharma': ['farmacéutico', 'medicina', 'cofepris', 'laboratorio', 'medicamento'],
            'mining': ['minería', 'mina', 'extracción', 'mineral'],
            'finance': ['financiero', 'banco', 'crédito', 'inversión'],
            'manufacturing': ['manufactura', 'fábrica', 'producción', 'industrial']
        }
        
        for sector, keywords in sector_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                entities["sector"] = sector
                break
        
        # Extract risk levels
        if any(word in message_lower for word in ['crítico', 'grave', 'severo']):
            entities["risk_level"] = "critical"
        elif any(word in message_lower for word in ['alto', 'importante']):
            entities["risk_level"] = "high"
        
        # Extract time periods
        if any(word in message_lower for word in ['hoy', 'actual', 'reciente']):
            entities["time_period"] = "recent"
        elif any(word in message_lower for word in ['semana', 'semanal']):
            entities["time_period"] = "week"
        elif any(word in message_lower for word in ['mes', 'mensual']):
            entities["time_period"] = "month"
        
        return {"intent": intent, "entities": entities}
    
    async def handle_intent(self, intent: Dict, user_message: str, db: Session) -> Dict:
        """Handle different user intents"""
        intent_type = intent.get("intent", "help")
        entities = intent.get("entities", {})
        
        if intent_type == "search":
            return await self.handle_search(user_message, entities, db)
        elif intent_type == "alerts":
            return await self.handle_alerts_query(entities, db)
        elif intent_type == "stats":
            return await self.handle_stats_query(entities, db)
        elif intent_type == "trends":
            return await self.handle_trends_query(entities, db)
        else:
            return await self.handle_help()
    
    async def handle_search(self, query: str, entities: Dict, db: Session) -> Dict:
        """Handle search queries using RAG"""
        try:
            # Perform semantic search
            similar_articles = await self.vector_store.similarity_search(
                query, 
                limit=10,
                sector_filter=entities.get("sector"),
                days_back=self.get_days_back(entities.get("time_period"))
            )
            
            if not similar_articles:
                return {
                    "text": "No encontré información relevante sobre tu consulta. ¿Podrías ser más específico?",
                    "sources": [],
                    "alerts": []
                }
            
            # Generate AI response
            response_text = await self.generate_search_response(query, similar_articles)
            
            # Get related alerts
            related_alerts = []
            for article in similar_articles[:3]:
                alerts = await self.get_article_alerts(article['id'], db)
                related_alerts.extend(alerts)
            
            return {
                "text": response_text,
                "sources": similar_articles[:5],
                "alerts": related_alerts[:3]
            }
            
        except Exception as e:
            logger.error(f"Error handling search: {str(e)}")
            return {
                "text": "Hubo un error procesando tu búsqueda. Por favor intenta de nuevo.",
                "sources": [],
                "alerts": []
            }
    
    async def handle_alerts_query(self, entities: Dict, db: Session) -> Dict:
        """Handle alerts-related queries"""
        try:
            # Build query filters
            filters = [RiskAlert.created_at >= datetime.now() - timedelta(days=7)]
            
            if entities.get("sector"):
                try:
                    sector = SectorType(entities["sector"])
                    filters.append(RiskAlert.sector == sector)
                except ValueError:
                    pass
            
            if entities.get("risk_level"):
                try:
                    risk_level = RiskLevel(entities["risk_level"])
                    filters.append(RiskAlert.risk_level == risk_level)
                except ValueError:
                    pass
            
            # Query alerts
            result = db.execute(
                select(RiskAlert).where(and_(*filters))
                .order_by(desc(RiskAlert.risk_score))
                .limit(10)
            )
            alerts = result.scalars().all()
            
            # Generate response
            response_text = await self.generate_alerts_response(alerts, entities)
            
            alert_data = [
                {
                    "id": alert.id,
                    "summary": alert.summary,
                    "risk_level": alert.risk_level.value,
                    "sector": alert.sector.value,
                    "risk_score": alert.risk_score,
                    "created_at": alert.created_at.isoformat()
                }
                for alert in alerts[:5]
            ]
            
            return {
                "text": response_text,
                "sources": [],
                "alerts": alert_data
            }
            
        except Exception as e:
            logger.error(f"Error handling alerts query: {str(e)}")
            return {
                "text": "Hubo un error consultando las alertas. Por favor intenta de nuevo.",
                "sources": [],
                "alerts": []
            }
    
    async def handle_stats_query(self, entities: Dict, db: Session) -> Dict:
        """Handle statistics queries"""
        try:
            days_back = self.get_days_back(entities.get("time_period", "week"))
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            # Get basic stats
            total_alerts = db.execute(
                select(db.func.count(RiskAlert.id)).where(RiskAlert.created_at >= cutoff_date)
            ).scalar()
            
            critical_alerts = db.execute(
                select(db.func.count(RiskAlert.id)).where(
                    and_(
                        RiskAlert.created_at >= cutoff_date,
                        RiskAlert.risk_level == RiskLevel.CRITICAL
                    )
                )
            ).scalar()
            
            # Sector breakdown
            sector_stats = db.execute(
                select(RiskAlert.sector, db.func.count(RiskAlert.id).label('count'))
                .where(RiskAlert.created_at >= cutoff_date)
                .group_by(RiskAlert.sector)
            ).all()
            
            response_text = f"""📊 **Estadísticas de los últimos {days_back} días:**

🚨 **Total de alertas:** {total_alerts}
⚠️ **Alertas críticas:** {critical_alerts}

**Por sector:**"""
            
            for sector, count in sector_stats:
                response_text += f"\n• {sector.value.title()}: {count} alertas"
            
            return {
                "text": response_text,
                "sources": [],
                "alerts": []
            }
            
        except Exception as e:
            logger.error(f"Error handling stats query: {str(e)}")
            return {
                "text": "Hubo un error generando las estadísticas.",
                "sources": [],
                "alerts": []
            }
    
    async def handle_trends_query(self, entities: Dict, db: Session) -> Dict:
        """Handle trends analysis queries"""
        try:
            trending_topics = await self.vector_store.get_trending_topics(
                days_back=self.get_days_back(entities.get("time_period", "week"))
            )
            
            if not trending_topics:
                return {
                    "text": "No hay tendencias significativas en el período consultado.",
                    "sources": [],
                    "alerts": []
                }
            
            response_text = "📈 **Tendencias identificadas:**\n\n"
            for i, trend in enumerate(trending_topics[:5], 1):
                response_text += f"{i}. **{trend['topic']}**\n"
                response_text += f"   • {trend['article_count']} artículos relacionados\n"
                response_text += f"   • Puntuación de tendencia: {trend['trend_score']:.2f}\n\n"
            
            return {
                "text": response_text,
                "sources": [],
                "alerts": []
            }
            
        except Exception as e:
            logger.error(f"Error handling trends query: {str(e)}")
            return {
                "text": "Hubo un error analizando las tendencias.",
                "sources": [],
                "alerts": []
            }
    
    async def handle_help(self) -> Dict:
        """Handle help queries"""
        help_text = """👋 **¡Hola! Soy el asistente de EchoFrame MX.**

Puedo ayudarte con:

🔍 **Búsquedas:** "Busca información sobre Pemex en Veracruz"
🚨 **Alertas:** "Muéstrame alertas críticas de esta semana"
📊 **Estadísticas:** "¿Cuántas alertas hay en el sector energético?"
📈 **Tendencias:** "¿Cuáles son las tendencias recientes?"

**Ejemplos de consultas:**
• "¿Qué riesgos hay en el sector farmacéutico?"
• "Alertas críticas de los últimos 3 días"
• "Estadísticas de riesgo en Jalisco"
• "Tendencias en el sector energético"

¿En qué puedo ayudarte?"""
        
        return {
            "text": help_text,
            "sources": [],
            "alerts": []
        }
    
    def get_days_back(self, time_period: Optional[str]) -> int:
        """Convert time period to days"""
        period_map = {
            "recent": 3,
            "week": 7,
            "month": 30
        }
        return period_map.get(time_period, 7)
    
    async def get_article_alerts(self, article_id: int, db: Session) -> List[Dict]:
        """Get alerts for a specific article"""
        try:
            result = db.execute(
                select(RiskAlert).where(RiskAlert.article_id == article_id)
                .limit(3)
            )
            alerts = result.scalars().all()
            
            return [
                {
                    "id": alert.id,
                    "summary": alert.summary,
                    "risk_level": alert.risk_level.value,
                    "sector": alert.sector.value,
                    "risk_score": alert.risk_score
                }
                for alert in alerts
            ]
            
        except Exception as e:
            logger.error(f"Error getting article alerts: {str(e)}")
            return []
    
    async def generate_search_response(self, query: str, articles: List[Dict]) -> str:
        """Generate AI response for search results"""
        if not self.openai_client:
            return f"Encontré {len(articles)} artículos relacionados con tu consulta."
        
        try:
            articles_text = "\n\n".join([
                f"Título: {article['title']}\nContenido: {article['content'][:200]}..."
                for article in articles[:3]
            ])
            
            system_prompt = """Eres un analista de riesgo especializado en México. 
            Analiza los artículos proporcionados y responde la consulta del usuario en español.
            Sé conciso, informativo y enfócate en los riesgos más relevantes.
            Máximo 200 palabras."""
            
            user_prompt = f"""
            Consulta del usuario: {query}
            
            Artículos encontrados:
            {articles_text}
            
            Por favor proporciona un resumen analítico de los riesgos identificados.
            """
            
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=250,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating search response: {str(e)}")
            return f"Encontré {len(articles)} artículos relacionados con tu consulta sobre riesgos en México."
    
    async def generate_alerts_response(self, alerts: List, entities: Dict) -> str:
        """Generate response for alerts queries"""
        if not alerts:
            return "No encontré alertas que coincidan con tus criterios de búsqueda."
        
        critical_count = len([a for a in alerts if a.risk_level == RiskLevel.CRITICAL])
        high_count = len([a for a in alerts if a.risk_level == RiskLevel.HIGH])
        
        response = f"📊 **Encontré {len(alerts)} alertas:**\n\n"
        
        if critical_count > 0:
            response += f"🚨 **{critical_count} alertas críticas**\n"
        if high_count > 0:
            response += f"⚠️ **{high_count} alertas de alto riesgo**\n\n"
        
        # Add top alerts
        for i, alert in enumerate(alerts[:3], 1):
            risk_emoji = "🚨" if alert.risk_level == RiskLevel.CRITICAL else "⚠️" if alert.risk_level == RiskLevel.HIGH else "📊"
            response += f"{risk_emoji} **{alert.summary[:100]}...**\n"
        
        return response
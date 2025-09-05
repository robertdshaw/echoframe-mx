import json
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import logging
from ..models import Article, RiskPattern, RiskAlert, SectorType, RiskLevel
from ..database import AsyncSessionLocal
from ..config import settings
from sqlalchemy import select, and_, or_
import openai
import asyncio

logger = logging.getLogger(__name__)

class RiskAnalyzer:
    def __init__(self):
        self.risk_patterns = self._load_risk_patterns()
        self.openai_client = None
        if settings.openai_api_key:
            self.openai_client = openai.OpenAI(api_key=settings.openai_api_key)
    
    def _load_risk_patterns(self) -> Dict:
        """Load risk patterns from configuration"""
        try:
            with open('config/risk_patterns.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load risk patterns: {str(e)}")
            return {}
    
    def calculate_risk_score(self, article: Article, pattern: Dict) -> float:
        """Calculate risk score for article against pattern"""
        score = 0.0
        text = f"{article.title} {article.content}".lower()
        
        # Keyword matching score
        keyword_matches = 0
        for keyword in pattern.get('keywords', []):
            if keyword.lower() in text:
                keyword_matches += 1
        
        if pattern.get('keywords'):
            keyword_score = min(keyword_matches / len(pattern['keywords']), 1.0)
            score += keyword_score * 0.4  # 40% weight for keyword matching
        
        # Trigger phrase matching score
        template = pattern.get('template', {})
        triggers = template.get('triggers', [])
        trigger_matches = 0
        
        for trigger in triggers:
            if trigger.lower() in text:
                trigger_matches += 1
                score += 0.3  # Additional score for trigger phrases
        
        # Risk factors scoring
        risk_factors = template.get('risk_factors', {})
        for factor_key, factor_weight in risk_factors.items():
            # Convert factor key to search terms
            search_terms = self._factor_to_search_terms(factor_key)
            for term in search_terms:
                if term in text:
                    score += factor_weight * 0.1  # Additional scoring for risk factors
                    break
        
        # Location relevance (boost for hyperlocal news)
        if article.source and article.source.source_type == 'synthetic':
            score += 0.1  # Boost for hyperlocal sources
        
        # Recency boost (more recent = higher risk)
        if article.published_at:
            days_old = (datetime.now() - article.published_at.replace(tzinfo=None)).days
            if days_old <= 7:
                score += 0.1
            elif days_old <= 30:
                score += 0.05
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _factor_to_search_terms(self, factor_key: str) -> List[str]:
        """Convert risk factor key to search terms"""
        factor_mapping = {
            'permit_suspension': ['suspensión', 'permiso'],
            'license_revocation': ['revocación', 'licencia'],
            'regulatory_investigation': ['investigación', 'regulatoria'],
            'compliance_violation': ['violación', 'cumplimiento'],
            'explosion': ['explosión'],
            'oil_spill': ['derrame', 'petróleo'],
            'facility_fire': ['incendio', 'instalaciones'],
            'infrastructure_failure': ['falla', 'infraestructura'],
            'community_protest': ['protesta', 'comunidad'],
            'access_blockade': ['bloqueo', 'acceso'],
            'indigenous_opposition': ['indígena', 'oposición'],
            'consultation_issues': ['consulta'],
            'major_losses': ['pérdidas', 'millones'],
            'regulatory_fines': ['multa', 'sanción'],
            'financing_issues': ['financiamiento', 'crédito'],
            'cost_overruns': ['sobrecosto', 'presupuesto'],
            'cofepris_suspension': ['cofepris', 'suspensión'],
            'registration_revocation': ['registro', 'revocación'],
            'sanitary_investigation': ['sanitaria', 'investigación'],
            'drug_recall': ['retiro', 'medicamento'],
            'adverse_effects': ['efectos adversos'],
            'contamination': ['contaminación'],
            'counterfeit_drugs': ['falsificación'],
            'drug_shortage': ['escasez', 'medicamentos'],
            'hospital_shortage': ['desabasto', 'hospitalario'],
            'supply_interruption': ['interrupción', 'suministro'],
            'import_issues': ['importación', 'problemas']
        }
        
        return factor_mapping.get(factor_key, [factor_key])
    
    def determine_risk_level(self, score: float) -> RiskLevel:
        """Determine risk level based on score"""
        if score >= settings.risk_threshold_high:
            return RiskLevel.CRITICAL
        elif score >= settings.risk_threshold_medium:
            return RiskLevel.HIGH
        elif score >= settings.risk_threshold_low:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    async def generate_risk_summary(self, article: Article, pattern: Dict, score: float) -> str:
        """Generate AI-powered risk summary"""
        if not self.openai_client:
            # Fallback summary
            return f"Riesgo {pattern['risk_level']} detectado en {pattern['pattern_type']} para sector {pattern['sector']}"
        
        try:
            system_prompt = """Eres un analista de riesgo especializado en México. 
            Analiza el siguiente artículo de noticias y genera un resumen conciso del riesgo identificado.
            Enfócate en:
            1. El tipo específico de riesgo
            2. Las entidades o empresas afectadas
            3. La ubicación geográfica
            4. El impacto potencial
            5. Recomendaciones de monitoreo
            
            Mantén el resumen en máximo 150 palabras y usa un tono profesional."""
            
            user_prompt = f"""
            Artículo: {article.title}
            
            Contenido: {article.content[:2000]}
            
            Patrón de riesgo detectado: {pattern['name']}
            Sector: {pattern['sector']}
            Tipo: {pattern['pattern_type']}
            Nivel de riesgo calculado: {score:.2f}
            """
            
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=200,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Failed to generate AI summary: {str(e)}")
            return f"Riesgo {pattern['risk_level']} detectado: {article.title[:100]}..."
    
    async def analyze_article(self, article: Article) -> List[Dict]:
        """Analyze single article for all risk patterns"""
        alerts = []
        
        # Check all pattern categories
        for category in ['energy_patterns', 'pharma_patterns', 'general_patterns']:
            patterns = self.risk_patterns.get(category, [])
            
            for pattern in patterns:
                score = self.calculate_risk_score(article, pattern)
                
                # Only create alert if score exceeds threshold
                if score >= settings.risk_threshold_low:
                    risk_level = self.determine_risk_level(score)
                    summary = await self.generate_risk_summary(article, pattern, score)
                    
                    alert_data = {
                        'article_id': article.id,
                        'pattern_name': pattern['name'],
                        'risk_score': score,
                        'risk_level': risk_level,
                        'sector': SectorType(pattern['sector']) if pattern['sector'] != 'general' else SectorType.ENERGY,  # Default fallback
                        'summary': summary,
                        'details': {
                            'pattern_type': pattern['pattern_type'],
                            'keywords_matched': [kw for kw in pattern.get('keywords', []) if kw.lower() in f"{article.title} {article.content}".lower()],
                            'location': {
                                'state': article.source.state if article.source else None,
                                'city': article.source.city if article.source else None
                            },
                            'source_info': {
                                'name': article.source.name if article.source else None,
                                'type': article.source.source_type.value if article.source else None
                            }
                        }
                    }
                    
                    alerts.append(alert_data)
        
        return alerts
    
    async def store_risk_alerts(self, alerts_data: List[Dict]) -> int:
        """Store risk alerts in database"""
        stored_count = 0
        
        async with AsyncSessionLocal() as db:
            for alert_data in alerts_data:
                # Check if alert already exists for this article and pattern
                existing = await db.execute(
                    select(RiskAlert).where(
                        and_(
                            RiskAlert.article_id == alert_data['article_id'],
                            RiskAlert.summary == alert_data['summary']
                        )
                    )
                )
                
                if existing.scalar_one_or_none():
                    continue
                
                # Create risk pattern if it doesn't exist
                pattern_result = await db.execute(
                    select(RiskPattern).where(RiskPattern.name == alert_data['pattern_name'])
                )
                risk_pattern = pattern_result.scalar_one_or_none()
                
                if not risk_pattern:
                    # Find pattern definition
                    pattern_def = None
                    for category in self.risk_patterns.values():
                        if isinstance(category, list):
                            for p in category:
                                if p['name'] == alert_data['pattern_name']:
                                    pattern_def = p
                                    break
                    
                    if pattern_def:
                        risk_pattern = RiskPattern(
                            name=pattern_def['name'],
                            sector=SectorType(pattern_def['sector']) if pattern_def['sector'] != 'general' else SectorType.ENERGY,
                            pattern_type=pattern_def['pattern_type'],
                            keywords=pattern_def.get('keywords', []),
                            risk_level=RiskLevel(pattern_def['risk_level']),
                            description=pattern_def.get('description', ''),
                            template=pattern_def.get('template', {})
                        )
                        db.add(risk_pattern)
                        await db.flush()
                
                if risk_pattern:
                    alert = RiskAlert(
                        article_id=alert_data['article_id'],
                        risk_pattern_id=risk_pattern.id,
                        risk_score=alert_data['risk_score'],
                        risk_level=alert_data['risk_level'],
                        sector=alert_data['sector'],
                        summary=alert_data['summary'],
                        details=alert_data['details']
                    )
                    db.add(alert)
                    stored_count += 1
            
            await db.commit()
        
        return stored_count
    
    async def analyze_recent_articles(self, days: int = 1) -> int:
        """Analyze recent articles for risk patterns"""
        cutoff_date = datetime.now() - timedelta(days=days)
        total_alerts = 0
        
        async with AsyncSessionLocal() as db:
            # Get recent articles that haven't been analyzed yet
            result = await db.execute(
                select(Article)
                .where(
                    and_(
                        Article.created_at >= cutoff_date,
                        Article.content.isnot(None),
                        Article.embedding.isnot(None)
                    )
                )
                .limit(100)  # Process in batches
            )
            
            articles = result.scalars().all()
            
            for article in articles:
                try:
                    alerts_data = await self.analyze_article(article)
                    if alerts_data:
                        stored = await self.store_risk_alerts(alerts_data)
                        total_alerts += stored
                        logger.info(f"Created {stored} alerts for article {article.id}")
                        
                except Exception as e:
                    logger.error(f"Error analyzing article {article.id}: {str(e)}")
                    continue
        
        logger.info(f"Total risk alerts created: {total_alerts}")
        return total_alerts
    
    async def get_high_risk_alerts(self, sector: Optional[SectorType] = None, 
                                  state: Optional[str] = None, 
                                  days: int = 7) -> List[RiskAlert]:
        """Get high-risk alerts for reporting"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        async with AsyncSessionLocal() as db:
            query = select(RiskAlert).where(
                and_(
                    RiskAlert.created_at >= cutoff_date,
                    RiskAlert.risk_level.in_([RiskLevel.HIGH, RiskLevel.CRITICAL])
                )
            )
            
            if sector:
                query = query.where(RiskAlert.sector == sector)
            
            result = await db.execute(query.order_by(RiskAlert.risk_score.desc()))
            return result.scalars().all()
import spacy
import re
from sentence_transformers import SentenceTransformer
import openai
from typing import List, Dict, Optional, Tuple
import logging
from ..config import settings
from ..models import Article, Entity
from ..database import AsyncSessionLocal
from sqlalchemy import select, update
import asyncio
import numpy as np

logger = logging.getLogger(__name__)

class NLPPipeline:
    def __init__(self):
        self.nlp = None
        self.embedding_model = None
        self.openai_client = None
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize NLP models"""
        try:
            # Load Spanish spaCy model
            self.nlp = spacy.load(settings.ner_model)
            logger.info(f"Loaded spaCy model: {settings.ner_model}")
        except OSError:
            logger.warning(f"spaCy model {settings.ner_model} not found. Install with: python -m spacy download {settings.ner_model}")
            # Fallback to basic processing
            self.nlp = None
        
        try:
            # Load embedding model
            self.embedding_model = SentenceTransformer(settings.embedding_model)
            logger.info(f"Loaded embedding model: {settings.embedding_model}")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {str(e)}")
        
        # Initialize OpenAI client
        if settings.openai_api_key:
            self.openai_client = openai.OpenAI(api_key=settings.openai_api_key)
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove special characters but keep Spanish accents
        text = re.sub(r'[^\w\s\.\,\;\:\!\?\-\(\)\"\'áéíóúüñÁÉÍÓÚÜÑ]', '', text)
        
        return text
    
    def extract_entities(self, text: str) -> List[Dict]:
        """Extract named entities from text"""
        if not self.nlp or not text:
            return []
        
        entities = []
        doc = self.nlp(text)
        
        for ent in doc.ents:
            entities.append({
                'entity_type': ent.label_,
                'entity_text': ent.text,
                'start_pos': ent.start_char,
                'end_pos': ent.end_char,
                'confidence': getattr(ent, 'confidence', 0.9),  # Default confidence
                'metadata': {
                    'lemma': ent.lemma_ if hasattr(ent, 'lemma_') else '',
                    'description': spacy.explain(ent.label_) if spacy.explain(ent.label_) else ''
                }
            })
        
        return entities
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text"""
        if not self.embedding_model or not text:
            return None
        
        try:
            # Clean and truncate text if too long
            clean_text = self.clean_text(text)
            if len(clean_text) > 8192:  # Model limit
                clean_text = clean_text[:8192]
            
            embedding = self.embedding_model.encode(clean_text)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            return None
    
    async def generate_summary(self, text: str, max_length: int = 200) -> Optional[str]:
        """Generate summary using OpenAI"""
        if not self.openai_client or not text:
            return None
        
        try:
            # Truncate text if too long
            if len(text) > 12000:
                text = text[:12000] + "..."
            
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un asistente que resume noticias en español. Crea un resumen conciso y objetivo del artículo, destacando los puntos principales y cualquier riesgo político o económico mencionado."
                    },
                    {
                        "role": "user",
                        "content": f"Resume este artículo de noticias en máximo {max_length} palabras:\n\n{text}"
                    }
                ],
                max_tokens=int(max_length * 1.5),  # Allow some buffer
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Failed to generate summary: {str(e)}")
            return None
    
    def extract_risk_keywords(self, text: str) -> List[str]:
        """Extract risk-related keywords from text"""
        risk_keywords = [
            # Political risks
            'protesta', 'manifestación', 'huelga', 'conflicto', 'tensión', 'crisis',
            'elecciones', 'gobierno', 'política', 'regulación', 'ley', 'decreto',
            'suspensión', 'cancelación', 'investigación', 'corrupción', 'escándalo',
            
            # Economic risks
            'inflación', 'devaluación', 'recesión', 'crisis económica', 'quiebra',
            'insolvencia', 'bancarrota', 'multa', 'sanción', 'impuesto', 'aranceles',
            'pérdidas', 'déficit', 'deuda', 'morosidad',
            
            # Operational risks
            'accidente', 'falla', 'interrupción', 'suspensión', 'cierre', 'evacuación',
            'emergencia', 'desastre', 'incendio', 'explosión', 'derrame', 'contaminación',
            'seguridad', 'violencia', 'crimen', 'narcotráfico', 'secuestro',
            
            # Regulatory risks
            'cofepris', 'sener', 'cfe', 'pemex', 'cnh', 'cre', 'cnbv', 'condusef',
            'licencia', 'permiso', 'autorización', 'violación', 'incumplimiento',
            'revocación', 'clausura', 'audit', 'inspección'
        ]
        
        found_keywords = []
        text_lower = text.lower()
        
        for keyword in risk_keywords:
            if keyword in text_lower:
                found_keywords.append(keyword)
        
        return list(set(found_keywords))  # Remove duplicates
    
    async def process_article(self, article_id: int) -> bool:
        """Process single article through NLP pipeline"""
        try:
            async with AsyncSessionLocal() as db:
                # Get article
                result = await db.execute(
                    select(Article).where(Article.id == article_id)
                )
                article = result.scalar_one_or_none()
                
                if not article or not article.content:
                    return False
                
                # Clean text
                clean_content = self.clean_text(article.content)
                clean_title = self.clean_text(article.title)
                
                # Generate embedding for title + content
                full_text = f"{clean_title}\n\n{clean_content}"
                embedding = self.generate_embedding(full_text)
                
                # Generate summary
                summary = await self.generate_summary(clean_content)
                
                # Extract entities
                entities = self.extract_entities(clean_content)
                
                # Extract risk keywords
                risk_keywords = self.extract_risk_keywords(clean_content)
                
                # Update article with processed data
                update_data = {
                    'summary': summary,
                    'embedding': embedding
                }
                
                # Add risk keywords to metadata
                if article.metadata:
                    article.metadata['risk_keywords'] = risk_keywords
                    article.metadata['processed'] = True
                    update_data['metadata'] = article.metadata
                else:
                    update_data['metadata'] = {
                        'risk_keywords': risk_keywords,
                        'processed': True
                    }
                
                await db.execute(
                    update(Article)
                    .where(Article.id == article_id)
                    .values(**update_data)
                )
                
                # Store entities
                for entity_data in entities:
                    entity = Entity(
                        article_id=article_id,
                        **entity_data
                    )
                    db.add(entity)
                
                await db.commit()
                logger.info(f"Processed article {article_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error processing article {article_id}: {str(e)}")
            return False
    
    async def process_unprocessed_articles(self, batch_size: int = 10) -> int:
        """Process articles that haven't been processed yet"""
        processed_count = 0
        
        async with AsyncSessionLocal() as db:
            # Get unprocessed articles
            result = await db.execute(
                select(Article.id)
                .where(
                    Article.content.isnot(None),
                    Article.embedding.is_(None)
                )
                .limit(batch_size)
            )
            
            article_ids = [row[0] for row in result.fetchall()]
            
            for article_id in article_ids:
                if await self.process_article(article_id):
                    processed_count += 1
        
        return processed_count
    
    async def reprocess_all_articles(self) -> int:
        """Reprocess all articles (for model updates)"""
        processed_count = 0
        
        async with AsyncSessionLocal() as db:
            # Get all articles with content
            result = await db.execute(
                select(Article.id)
                .where(Article.content.isnot(None))
            )
            
            article_ids = [row[0] for row in result.fetchall()]
            
            for article_id in article_ids:
                if await self.process_article(article_id):
                    processed_count += 1
        
        return processed_count
import numpy as np
from typing import List, Dict, Optional, Tuple
import asyncio
import logging
from sqlalchemy import select, and_, or_, text
from sqlalchemy.orm import selectinload
from pgvector.sqlalchemy import Vector
from ..models import Article, Source, RiskAlert, Entity
from ..database import AsyncSessionLocal
from ..config import settings
import openai
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self):
        self.openai_client = None
        if settings.openai_api_key:
            self.openai_client = openai.OpenAI(api_key=settings.openai_api_key)
    
    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text using OpenAI"""
        try:
            if not self.openai_client:
                logger.warning("OpenAI client not initialized")
                return None
            
            response = await asyncio.to_thread(
                self.openai_client.embeddings.create,
                model="text-embedding-ada-002",
                input=text[:8000]  # Truncate to avoid token limits
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            return None
    
    async def store_article_embedding(self, article: Article) -> bool:
        """Generate and store embedding for an article"""
        try:
            # Combine title and content for embedding
            text_content = f"{article.title}\n\n{article.content or ''}"
            
            embedding = await self.generate_embedding(text_content)
            if not embedding:
                return False
            
            # Store embedding in database
            async with AsyncSessionLocal() as db:
                article.embedding = embedding
                db.add(article)
                await db.commit()
                
            logger.info(f"Stored embedding for article {article.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing embedding for article {article.id}: {str(e)}")
            return False
    
    async def process_unembedded_articles(self, limit: int = 50) -> int:
        """Process articles without embeddings"""
        processed_count = 0
        
        async with AsyncSessionLocal() as db:
            # Get articles without embeddings
            result = await db.execute(
                select(Article).where(
                    and_(
                        Article.embedding.is_(None),
                        Article.content.isnot(None),
                        Article.content != ""
                    )
                ).limit(limit)
            )
            articles = result.scalars().all()
            
            for article in articles:
                try:
                    success = await self.store_article_embedding(article)
                    if success:
                        processed_count += 1
                        
                except Exception as e:
                    logger.error(f"Error processing article {article.id}: {str(e)}")
                    continue
        
        logger.info(f"Processed {processed_count} articles for embeddings")
        return processed_count
    
    async def similarity_search(self, query: str, limit: int = 10, 
                               sector_filter: Optional[str] = None,
                               days_back: Optional[int] = None) -> List[Dict]:
        """Perform semantic similarity search"""
        try:
            query_embedding = await self.generate_embedding(query)
            if not query_embedding:
                return []
            
            async with AsyncSessionLocal() as db:
                # Build base query
                sql = """
                SELECT 
                    a.id, a.title, a.content, a.url, a.published_at,
                    s.name as source_name, s.state, s.city,
                    (a.embedding <=> %s::vector) as distance
                FROM articles a 
                JOIN sources s ON a.source_id = s.id 
                WHERE a.embedding IS NOT NULL
                """
                params = [query_embedding]
                
                # Add filters
                if days_back:
                    cutoff_date = datetime.now() - timedelta(days=days_back)
                    sql += " AND a.published_at >= %s"
                    params.append(cutoff_date)
                
                if sector_filter:
                    sql += """ AND a.id IN (
                        SELECT ra.article_id FROM risk_alerts ra 
                        WHERE ra.sector = %s
                    )"""
                    params.append(sector_filter)
                
                sql += " ORDER BY distance ASC LIMIT %s"
                params.append(limit)
                
                result = await db.execute(text(sql), params)
                rows = result.fetchall()
                
                articles = []
                for row in rows:
                    articles.append({
                        'id': row.id,
                        'title': row.title,
                        'content': row.content[:500] + "..." if len(row.content or '') > 500 else row.content,
                        'url': row.url,
                        'published_at': row.published_at.isoformat() if row.published_at else None,
                        'source': {
                            'name': row.source_name,
                            'location': f"{row.city}, {row.state}" if row.city and row.state else None
                        },
                        'similarity_score': 1 - row.distance,  # Convert distance to similarity
                        'distance': row.distance
                    })
                
                return articles
                
        except Exception as e:
            logger.error(f"Error in similarity search: {str(e)}")
            return []
    
    async def get_related_alerts(self, article_id: int, limit: int = 5) -> List[Dict]:
        """Get alerts related to a specific article using semantic similarity"""
        async with AsyncSessionLocal() as db:
            # Get the source article
            result = await db.execute(
                select(Article).where(Article.id == article_id)
            )
            source_article = result.scalar_one_or_none()
            
            if not source_article or not source_article.embedding:
                return []
            
            # Find similar articles with risk alerts
            sql = """
            SELECT DISTINCT
                a.id, a.title, a.content, a.published_at,
                s.name as source_name, s.state, s.city,
                ra.id as alert_id, ra.risk_level, ra.sector, ra.summary, ra.risk_score,
                (a.embedding <=> %s::vector) as distance
            FROM articles a 
            JOIN sources s ON a.source_id = s.id 
            JOIN risk_alerts ra ON a.id = ra.article_id
            WHERE a.embedding IS NOT NULL 
            AND a.id != %s
            AND (a.embedding <=> %s::vector) < 0.3
            ORDER BY distance ASC 
            LIMIT %s
            """
            
            result = await db.execute(
                text(sql), 
                [source_article.embedding, article_id, source_article.embedding, limit]
            )
            rows = result.fetchall()
            
            related_alerts = []
            for row in rows:
                related_alerts.append({
                    'article_id': row.id,
                    'article_title': row.title,
                    'alert_id': row.alert_id,
                    'risk_level': row.risk_level,
                    'sector': row.sector,
                    'summary': row.summary,
                    'risk_score': row.risk_score,
                    'similarity_score': 1 - row.distance,
                    'source': {
                        'name': row.source_name,
                        'location': f"{row.city}, {row.state}" if row.city and row.state else None
                    },
                    'published_at': row.published_at.isoformat() if row.published_at else None
                })
            
            return related_alerts
    
    async def find_similar_patterns(self, risk_pattern: str, limit: int = 20) -> List[Dict]:
        """Find articles with similar risk patterns"""
        try:
            pattern_embedding = await self.generate_embedding(risk_pattern)
            if not pattern_embedding:
                return []
            
            async with AsyncSessionLocal() as db:
                sql = """
                SELECT 
                    a.id, a.title, a.content, a.published_at,
                    s.name as source_name, s.state, s.city,
                    ra.risk_level, ra.sector, ra.summary, ra.risk_score,
                    (a.embedding <=> %s::vector) as distance
                FROM articles a 
                JOIN sources s ON a.source_id = s.id 
                LEFT JOIN risk_alerts ra ON a.id = ra.article_id
                WHERE a.embedding IS NOT NULL
                ORDER BY distance ASC 
                LIMIT %s
                """
                
                result = await db.execute(text(sql), [pattern_embedding, limit])
                rows = result.fetchall()
                
                similar_articles = []
                for row in rows:
                    similar_articles.append({
                        'id': row.id,
                        'title': row.title,
                        'content': row.content[:300] + "..." if len(row.content or '') > 300 else row.content,
                        'published_at': row.published_at.isoformat() if row.published_at else None,
                        'source': {
                            'name': row.source_name,
                            'location': f"{row.city}, {row.state}" if row.city and row.state else None
                        },
                        'risk_alert': {
                            'level': row.risk_level,
                            'sector': row.sector,
                            'summary': row.summary,
                            'score': row.risk_score
                        } if row.risk_level else None,
                        'similarity_score': 1 - row.distance
                    })
                
                return similar_articles
                
        except Exception as e:
            logger.error(f"Error finding similar patterns: {str(e)}")
            return []
    
    async def cluster_articles_by_topic(self, min_cluster_size: int = 5) -> List[Dict]:
        """Simple clustering of articles by semantic similarity"""
        try:
            async with AsyncSessionLocal() as db:
                # Get recent articles with embeddings
                result = await db.execute(
                    select(Article).options(selectinload(Article.source)).where(
                        and_(
                            Article.embedding.isnot(None),
                            Article.published_at >= datetime.now() - timedelta(days=30)
                        )
                    ).limit(100)
                )
                articles = result.scalars().all()
                
                if len(articles) < min_cluster_size:
                    return []
                
                # Simple clustering using similarity threshold
                clusters = []
                processed_ids = set()
                
                for article in articles:
                    if article.id in processed_ids:
                        continue
                    
                    # Find similar articles
                    similar_articles = await self.similarity_search(
                        f"{article.title} {article.content[:200]}", 
                        limit=20
                    )
                    
                    cluster_articles = [a for a in similar_articles if a['similarity_score'] > 0.7]
                    
                    if len(cluster_articles) >= min_cluster_size:
                        cluster = {
                            'cluster_id': len(clusters),
                            'topic': article.title[:100],
                            'articles': cluster_articles,
                            'size': len(cluster_articles),
                            'avg_similarity': np.mean([a['similarity_score'] for a in cluster_articles])
                        }
                        clusters.append(cluster)
                        
                        # Mark articles as processed
                        for cluster_article in cluster_articles:
                            processed_ids.add(cluster_article['id'])
                
                return clusters
                
        except Exception as e:
            logger.error(f"Error clustering articles: {str(e)}")
            return []
    
    async def get_trending_topics(self, days_back: int = 7, min_articles: int = 3) -> List[Dict]:
        """Identify trending topics using semantic clustering"""
        try:
            # Get recent articles with high similarity
            recent_clusters = await self.cluster_articles_by_topic(min_cluster_size=min_articles)
            
            # Sort by cluster size and average similarity
            trending_topics = []
            for cluster in recent_clusters:
                # Calculate trend score based on recency and volume
                recent_articles = [
                    a for a in cluster['articles'] 
                    if a.get('published_at') and 
                    datetime.fromisoformat(a['published_at'].replace('Z', '+00:00')) >= 
                    datetime.now().replace(tzinfo=None) - timedelta(days=days_back)
                ]
                
                if len(recent_articles) >= min_articles:
                    trend_score = len(recent_articles) * cluster['avg_similarity']
                    
                    trending_topics.append({
                        'topic': cluster['topic'],
                        'article_count': len(recent_articles),
                        'trend_score': trend_score,
                        'avg_similarity': cluster['avg_similarity'],
                        'sample_articles': recent_articles[:3]
                    })
            
            # Sort by trend score
            trending_topics.sort(key=lambda x: x['trend_score'], reverse=True)
            return trending_topics[:10]
            
        except Exception as e:
            logger.error(f"Error identifying trending topics: {str(e)}")
            return []
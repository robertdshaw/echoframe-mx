import asyncio
import logging
from typing import Dict, List
from datetime import datetime, timedelta
from .rss_fetcher import RSSFetcher, initialize_rss_sources
from .synthetic_data import SyntheticDataGenerator
from ..processing.nlp_pipeline import NLPPipeline
from ..processing.risk_analyzer import RiskAnalyzer
from ..models import Article
from ..database import AsyncSessionLocal
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)

class IngestionCoordinator:
    def __init__(self):
        self.nlp_pipeline = NLPPipeline()
        self.risk_analyzer = RiskAnalyzer()
        self.synthetic_generator = SyntheticDataGenerator()
    
    async def run_full_ingestion_cycle(self) -> Dict[str, int]:
        """Run complete ingestion cycle: RSS -> Synthetic -> NLP -> Risk Analysis"""
        results = {
            "rss_articles": 0,
            "synthetic_articles": 0,
            "processed_articles": 0,
            "risk_alerts": 0,
            "errors": 0
        }
        
        try:
            logger.info("Starting full ingestion cycle")
            
            # Step 1: Initialize sources
            await initialize_rss_sources()
            await self.synthetic_generator.create_synthetic_sources()
            
            # Step 2: Fetch RSS articles
            async with RSSFetcher() as rss_fetcher:
                rss_results = await rss_fetcher.fetch_all_rss_sources()
                results["rss_articles"] = sum(rss_results.values())
                logger.info(f"Fetched {results['rss_articles']} RSS articles")
            
            # Step 3: Generate synthetic articles (only if needed)
            async with AsyncSessionLocal() as db:
                recent_articles = await db.execute(
                    select(Article).where(
                        Article.created_at >= datetime.now() - timedelta(days=1)
                    )
                )
                recent_count = len(recent_articles.scalars().all())
                
                if recent_count < 50:  # Generate synthetic if low content
                    synthetic_count = await self.synthetic_generator.generate_synthetic_articles(100)
                    results["synthetic_articles"] = synthetic_count
                    logger.info(f"Generated {synthetic_count} synthetic articles")
            
            # Step 4: Process articles with NLP
            unprocessed_articles = await self.get_unprocessed_articles()
            for article in unprocessed_articles:
                try:
                    await self.nlp_pipeline.process_article(article)
                    results["processed_articles"] += 1
                except Exception as e:
                    logger.error(f"Error processing article {article.id}: {str(e)}")
                    results["errors"] += 1
            
            # Step 5: Run risk analysis
            risk_alerts = await self.risk_analyzer.analyze_recent_articles(days=1)
            results["risk_alerts"] = risk_alerts
            
            logger.info(f"Ingestion cycle completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error in ingestion cycle: {str(e)}")
            results["errors"] += 1
            return results
    
    async def get_unprocessed_articles(self, limit: int = 100) -> List[Article]:
        """Get articles that haven't been processed yet"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Article).where(
                    and_(
                        Article.embedding.is_(None),
                        Article.content.isnot(None),
                        Article.content != ""
                    )
                ).limit(limit)
            )
            return result.scalars().all()
    
    async def run_rss_only_cycle(self) -> Dict[str, int]:
        """Run RSS-only ingestion cycle"""
        results = {"rss_articles": 0, "errors": 0}
        
        try:
            await initialize_rss_sources()
            
            async with RSSFetcher() as rss_fetcher:
                rss_results = await rss_fetcher.fetch_all_rss_sources()
                results["rss_articles"] = sum(rss_results.values())
                
            logger.info(f"RSS cycle completed: {results['rss_articles']} articles")
            return results
            
        except Exception as e:
            logger.error(f"Error in RSS cycle: {str(e)}")
            results["errors"] += 1
            return results
    
    async def run_processing_cycle(self) -> Dict[str, int]:
        """Run processing cycle for unprocessed articles"""
        results = {"processed_articles": 0, "risk_alerts": 0, "errors": 0}
        
        try:
            # Process articles with NLP
            unprocessed_articles = await self.get_unprocessed_articles()
            for article in unprocessed_articles:
                try:
                    await self.nlp_pipeline.process_article(article)
                    results["processed_articles"] += 1
                except Exception as e:
                    logger.error(f"Error processing article {article.id}: {str(e)}")
                    results["errors"] += 1
            
            # Run risk analysis
            risk_alerts = await self.risk_analyzer.analyze_recent_articles(days=1)
            results["risk_alerts"] = risk_alerts
            
            logger.info(f"Processing cycle completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error in processing cycle: {str(e)}")
            results["errors"] += 1
            return results
    
    async def health_check(self) -> Dict[str, any]:
        """Check ingestion system health"""
        health_status = {
            "status": "healthy",
            "rss_sources_active": 0,
            "synthetic_sources_active": 0,
            "recent_articles": 0,
            "pending_processing": 0,
            "recent_alerts": 0,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            async with AsyncSessionLocal() as db:
                # Count active sources
                from ..models import Source, SourceType, RiskAlert
                
                rss_sources = await db.execute(
                    select(Source).where(
                        and_(
                            Source.source_type == SourceType.RSS,
                            Source.is_active == True
                        )
                    )
                )
                health_status["rss_sources_active"] = len(rss_sources.scalars().all())
                
                synthetic_sources = await db.execute(
                    select(Source).where(Source.source_type == SourceType.SYNTHETIC)
                )
                health_status["synthetic_sources_active"] = len(synthetic_sources.scalars().all())
                
                # Count recent articles
                recent_articles = await db.execute(
                    select(Article).where(
                        Article.created_at >= datetime.now() - timedelta(hours=24)
                    )
                )
                health_status["recent_articles"] = len(recent_articles.scalars().all())
                
                # Count pending processing
                unprocessed = await db.execute(
                    select(Article).where(Article.embedding.is_(None))
                )
                health_status["pending_processing"] = len(unprocessed.scalars().all())
                
                # Count recent alerts
                recent_alerts = await db.execute(
                    select(RiskAlert).where(
                        RiskAlert.created_at >= datetime.now() - timedelta(hours=24)
                    )
                )
                health_status["recent_alerts"] = len(recent_alerts.scalars().all())
                
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status
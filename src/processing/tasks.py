from celery import Celery
import asyncio
from typing import Dict, List
import logging
from ..config import settings
from ..ingestion.rss_fetcher import RSSFetcher, initialize_rss_sources
from ..ingestion.synthetic_data import SyntheticDataGenerator
from .nlp_pipeline import NLPPipeline
from .risk_analyzer import RiskAnalyzer
from ..email.email_service import EmailService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Celery
celery_app = Celery(
    'echoframe',
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=['src.processing.tasks']
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_routes={
        'src.processing.tasks.fetch_rss_feeds': {'queue': 'ingestion'},
        'src.processing.tasks.process_articles': {'queue': 'processing'},
        'src.processing.tasks.analyze_risks': {'queue': 'analysis'},
        'src.processing.tasks.send_email_reports': {'queue': 'notifications'},
    }
)

# Periodic tasks configuration
celery_app.conf.beat_schedule = {
    'fetch-rss-feeds': {
        'task': 'src.processing.tasks.fetch_rss_feeds',
        'schedule': settings.rss_update_interval * 60.0,  # Convert minutes to seconds
    },
    'process-articles': {
        'task': 'src.processing.tasks.process_articles',
        'schedule': 300.0,  # Every 5 minutes
    },
    'analyze-risks': {
        'task': 'src.processing.tasks.analyze_risks',
        'schedule': settings.risk_analysis_interval * 60.0,
    },
    'send-email-reports': {
        'task': 'src.processing.tasks.send_email_reports',
        'schedule': settings.email_report_interval * 60.0,
    },
}

@celery_app.task
def fetch_rss_feeds():
    """Periodic task to fetch RSS feeds"""
    async def _fetch():
        try:
            # Initialize RSS sources if needed
            await initialize_rss_sources()
            
            # Fetch from all RSS sources
            async with RSSFetcher() as fetcher:
                results = await fetcher.fetch_all_rss_sources()
                
            total_articles = sum(results.values())
            logger.info(f"RSS fetch completed. Total new articles: {total_articles}")
            
            # Trigger article processing
            if total_articles > 0:
                process_articles.delay()
            
            return {
                'status': 'success',
                'total_articles': total_articles,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"RSS fetch failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    return asyncio.run(_fetch())

@celery_app.task
def process_articles(batch_size: int = 20):
    """Process unprocessed articles through NLP pipeline"""
    async def _process():
        try:
            nlp_pipeline = NLPPipeline()
            processed_count = await nlp_pipeline.process_unprocessed_articles(batch_size)
            
            logger.info(f"Processed {processed_count} articles")
            
            # Trigger risk analysis if articles were processed
            if processed_count > 0:
                analyze_risks.delay()
            
            return {
                'status': 'success',
                'processed_count': processed_count
            }
            
        except Exception as e:
            logger.error(f"Article processing failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    return asyncio.run(_process())

@celery_app.task
def analyze_risks():
    """Analyze articles for risk patterns"""
    async def _analyze():
        try:
            risk_analyzer = RiskAnalyzer()
            alerts_created = await risk_analyzer.analyze_recent_articles()
            
            logger.info(f"Created {alerts_created} risk alerts")
            
            return {
                'status': 'success',
                'alerts_created': alerts_created
            }
            
        except Exception as e:
            logger.error(f"Risk analysis failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    return asyncio.run(_analyze())

@celery_app.task
def send_email_reports():
    """Send email reports to clients"""
    async def _send():
        try:
            email_service = EmailService()
            reports_sent = await email_service.send_daily_reports()
            
            logger.info(f"Sent {reports_sent} email reports")
            
            return {
                'status': 'success',
                'reports_sent': reports_sent
            }
            
        except Exception as e:
            logger.error(f"Email reports failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    return asyncio.run(_send())

@celery_app.task
def generate_synthetic_data(count: int = 100):
    """Generate synthetic hyperlocal news data"""
    async def _generate():
        try:
            generator = SyntheticDataGenerator()
            articles_created = await generator.generate_synthetic_articles(count)
            
            logger.info(f"Generated {articles_created} synthetic articles")
            
            # Trigger processing of new articles
            process_articles.delay()
            
            return {
                'status': 'success',
                'articles_created': articles_created
            }
            
        except Exception as e:
            logger.error(f"Synthetic data generation failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    return asyncio.run(_generate())

@celery_app.task
def initialize_system():
    """Initialize the system with default data"""
    async def _init():
        try:
            results = {}
            
            # Initialize RSS sources
            await initialize_rss_sources()
            results['rss_sources'] = 'initialized'
            
            # Generate synthetic data
            generator = SyntheticDataGenerator()
            articles_created = await generator.generate_synthetic_articles(500)
            results['synthetic_articles'] = articles_created
            
            # Process articles
            nlp_pipeline = NLPPipeline()
            processed_count = await nlp_pipeline.process_unprocessed_articles(100)
            results['processed_articles'] = processed_count
            
            # Analyze risks
            risk_analyzer = RiskAnalyzer()
            alerts_created = await risk_analyzer.analyze_recent_articles()
            results['risk_alerts'] = alerts_created
            
            logger.info(f"System initialization completed: {results}")
            
            return {
                'status': 'success',
                'results': results
            }
            
        except Exception as e:
            logger.error(f"System initialization failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    return asyncio.run(_init())

# Health check task
@celery_app.task
def health_check():
    """Health check for the worker"""
    return {
        'status': 'healthy',
        'worker': 'running',
        'timestamp': asyncio.run(_get_timestamp())
    }

async def _get_timestamp():
    from datetime import datetime
    return datetime.utcnow().isoformat()
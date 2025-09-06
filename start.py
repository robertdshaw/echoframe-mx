#!/usr/bin/env python3
"""
EchoFrame MX Startup Script
This script initializes the system and starts all services
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.database import engine, AsyncSessionLocal
from src.models import Base
from src.ingestion.rss_fetcher import initialize_rss_sources
from src.ingestion.synthetic_data import SyntheticDataGenerator
from src.processing.nlp_pipeline import NLPPipeline
from src.rag.vector_store import VectorStore
from src.database import async_engine, AsyncSessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def initialize_system():
    """Initialize EchoFrame MX system"""
    logger.info("🚀 Starting EchoFrame MX initialization...")

    try:
        # 1. Create database tables
        logger.info("📊 Creating database tables...")
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables created")

        # 2. Initialize RSS sources
        logger.info("📰 Initializing RSS sources...")
        await initialize_rss_sources()
        logger.info("✅ RSS sources initialized")

        # 3. Create synthetic news sources
        logger.info("🏗️ Creating synthetic news sources...")
        generator = SyntheticDataGenerator()
        await generator.create_synthetic_sources()
        logger.info("✅ Synthetic sources created")

        # 4. Generate some initial synthetic data
        logger.info("📝 Generating initial synthetic articles...")
        articles_created = await generator.generate_synthetic_articles(100)
        logger.info(f"✅ Created {articles_created} synthetic articles")

        # 5. Process embeddings for initial articles
        logger.info("🔍 Processing embeddings...")
        vector_store = VectorStore()
        processed = await vector_store.process_unembedded_articles(50)
        logger.info(f"✅ Processed {processed} article embeddings")

        # 6. Run initial NLP processing
        logger.info("🤖 Running initial NLP processing...")
        nlp_pipeline = NLPPipeline()
        # This would process recent articles for entities
        logger.info("✅ NLP processing initialized")

        logger.info("🎉 EchoFrame MX system initialization complete!")
        logger.info("🌐 API Server ready at http://localhost:8000")
        logger.info("📚 API Documentation at http://localhost:8000/docs")

        return True

    except Exception as e:
        logger.error(f"❌ System initialization failed: {str(e)}")
        return False


async def health_check():
    """Perform system health check"""
    logger.info("🔍 Performing system health check...")

    try:
        async with AsyncSessionLocal() as db:
            # Test database connection
            await db.execute("SELECT 1")
            logger.info("✅ Database connection: OK")

        # Add more health checks as needed
        return True

    except Exception as e:
        logger.error(f"❌ Health check failed: {str(e)}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="EchoFrame MX System Manager")
    parser.add_argument("--init", action="store_true", help="Initialize the system")
    parser.add_argument("--health", action="store_true", help="Run health check")
    parser.add_argument("--start", action="store_true", help="Start the API server")

    args = parser.parse_args()

    if args.init:
        success = asyncio.run(initialize_system())
        sys.exit(0 if success else 1)
    elif args.health:
        success = asyncio.run(health_check())
        sys.exit(0 if success else 1)
    elif args.start:
        logger.info("🚀 Starting EchoFrame MX API Server...")
        import uvicorn
        from src.api.main import app

        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    else:
        print("EchoFrame MX - Intelligent Risk Monitoring for Mexico")
        print("Usage:")
        print("  python start.py --init    # Initialize the system")
        print("  python start.py --health  # Run health check")
        print("  python start.py --start   # Start API server")
        print("  docker-compose up         # Start all services")

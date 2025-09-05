import feedparser
import asyncio
import aiohttp
from datetime import datetime, timezone
from typing import List, Dict, Optional
import logging
from bs4 import BeautifulSoup
import re
from ..models import Source, Article, SourceType
from ..database import AsyncSessionLocal
from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

class RSSFetcher:
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'EchoFrame/1.0 (Risk Intelligence Platform)'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_rss_feed(self, url: str) -> Optional[Dict]:
        """Fetch and parse RSS feed"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    feed = feedparser.parse(content)
                    return feed
                else:
                    logger.error(f"Failed to fetch RSS feed {url}: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching RSS feed {url}: {str(e)}")
            return None
    
    def clean_html_content(self, html_content: str) -> str:
        """Clean HTML content and extract text"""
        if not html_content:
            return ""
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text and clean it
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text
    
    def parse_feed_entry(self, entry, source: Source) -> Dict:
        """Parse individual RSS feed entry"""
        # Get published date
        published_at = None
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            published_at = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        
        # Clean content
        content = ""
        if hasattr(entry, 'content') and entry.content:
            content = self.clean_html_content(entry.content[0].value)
        elif hasattr(entry, 'description'):
            content = self.clean_html_content(entry.description)
        elif hasattr(entry, 'summary'):
            content = self.clean_html_content(entry.summary)
        
        # Extract author
        author = getattr(entry, 'author', '')
        
        return {
            'title': getattr(entry, 'title', ''),
            'content': content,
            'url': getattr(entry, 'link', ''),
            'author': author,
            'published_at': published_at,
            'language': 'es',
            'metadata': {
                'tags': getattr(entry, 'tags', []),
                'categories': getattr(entry, 'categories', []),
                'source_metadata': {
                    'feed_title': getattr(entry, 'feed', {}).get('title', ''),
                    'feed_description': getattr(entry, 'feed', {}).get('description', '')
                }
            }
        }
    
    async def fetch_and_store_articles(self, source: Source) -> int:
        """Fetch articles from RSS source and store in database"""
        try:
            feed = await self.fetch_rss_feed(source.url)
            if not feed:
                return 0
            
            articles_stored = 0
            async with AsyncSessionLocal() as db:
                for entry in feed.entries:
                    article_data = self.parse_feed_entry(entry, source)
                    
                    # Check if article already exists
                    existing = await db.execute(
                        select(Article).where(
                            Article.url == article_data['url'],
                            Article.source_id == source.id
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue
                    
                    # Create new article
                    article = Article(
                        source_id=source.id,
                        **article_data
                    )
                    db.add(article)
                    articles_stored += 1
                
                await db.commit()
                logger.info(f"Stored {articles_stored} new articles from {source.name}")
                return articles_stored
                
        except Exception as e:
            logger.error(f"Error processing RSS source {source.name}: {str(e)}")
            return 0
    
    async def fetch_all_rss_sources(self) -> Dict[str, int]:
        """Fetch articles from all active RSS sources"""
        results = {}
        
        async with AsyncSessionLocal() as db:
            # Get all active RSS sources
            result = await db.execute(
                select(Source).where(
                    Source.source_type == SourceType.RSS,
                    Source.is_active == True
                )
            )
            sources = result.scalars().all()
            
            for source in sources:
                count = await self.fetch_and_store_articles(source)
                results[source.name] = count
        
        return results

# Mexican news sources configuration
MEXICAN_RSS_SOURCES = [
    {
        'name': 'El Universal',
        'url': 'https://www.eluniversal.com.mx/rss.xml',
        'state': 'CDMX',
        'city': 'Mexico City'
    },
    {
        'name': 'La Jornada',
        'url': 'https://www.jornada.com.mx/rss/edicion.xml',
        'state': 'CDMX',
        'city': 'Mexico City'
    },
    {
        'name': 'Milenio',
        'url': 'https://www.milenio.com/rss',
        'state': 'CDMX',
        'city': 'Mexico City'
    },
    {
        'name': 'El Financiero',
        'url': 'https://www.elfinanciero.com.mx/rss',
        'state': 'CDMX',
        'city': 'Mexico City'
    },
    {
        'name': 'Animal Político',
        'url': 'https://www.animalpolitico.com/feed/',
        'state': 'CDMX',
        'city': 'Mexico City'
    }
]

async def initialize_rss_sources():
    """Initialize RSS sources in database"""
    async with AsyncSessionLocal() as db:
        for source_data in MEXICAN_RSS_SOURCES:
            # Check if source exists
            existing = await db.execute(
                select(Source).where(Source.name == source_data['name'])
            )
            if existing.scalar_one_or_none():
                continue
            
            # Create new source
            source = Source(
                name=source_data['name'],
                url=source_data['url'],
                source_type=SourceType.RSS,
                content_type='news',
                country='MEX',
                state=source_data['state'],
                city=source_data['city']
            )
            db.add(source)
        
        await db.commit()
        logger.info("RSS sources initialized")
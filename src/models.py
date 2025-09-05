from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    Float,
    ForeignKey,
    ARRAY,
    Enum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from .database import Base
import enum
import uuid


class SourceType(str, enum.Enum):
    RSS = "rss"
    API = "api"
    SCRAPER = "scraper"
    SYNTHETIC = "synthetic"


class ContentType(str, enum.Enum):
    NEWS = "news"
    GOVERNMENT = "government"
    NGO = "ngo"
    INDUSTRY = "industry"
    INTERGOVERNMENTAL = "intergovernmental"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SectorType(str, enum.Enum):
    ENERGY = "energy"
    PHARMA = "pharma"
    MINING = "mining"
    MANUFACTURING = "manufacturing"
    FINANCE = "finance"
    INFRASTRUCTURE = "infrastructure"


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    url = Column(Text)
    source_type = Column(Enum(SourceType), nullable=False)
    content_type = Column(Enum(ContentType), nullable=False)
    country = Column(String(3), default="MEX")
    state = Column(String(100))
    city = Column(String(100))
    is_active = Column(Boolean, default=True)
    meta_data = Column(JSONB, default={})
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    articles = relationship("Article", back_populates="source")


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"))
    title = Column(Text, nullable=False)
    content = Column(Text)
    summary = Column(Text)
    url = Column(Text)
    author = Column(String(255))
    published_at = Column(DateTime)
    scraped_at = Column(DateTime, server_default=func.now())
    language = Column(String(5), default="es")
    meta_data = Column(JSONB, default={})
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    source = relationship("Source", back_populates="articles")
    entities = relationship("Entity", back_populates="article")
    risk_alerts = relationship("RiskAlert", back_populates="article")


class Entity(Base):
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"))
    entity_type = Column(String(50), nullable=False)
    entity_text = Column(String(500), nullable=False)
    confidence = Column(Float)
    start_pos = Column(Integer)
    end_pos = Column(Integer)
    meta_data = Column(JSONB, default={})

    # Relationships
    article = relationship("Article", back_populates="entities")


class RiskPattern(Base):
    __tablename__ = "risk_patterns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    sector = Column(Enum(SectorType), nullable=False)
    pattern_type = Column(String(50), nullable=False)
    keywords = Column(ARRAY(Text))
    risk_level = Column(Enum(RiskLevel), nullable=False)
    description = Column(Text)
    template = Column(JSONB, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    risk_alerts = relationship("RiskAlert", back_populates="risk_pattern")


class RiskAlert(Base):
    __tablename__ = "risk_alerts"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"))
    risk_pattern_id = Column(Integer, ForeignKey("risk_patterns.id"))
    risk_score = Column(Float, nullable=False)
    risk_level = Column(Enum(RiskLevel), nullable=False)
    sector = Column(Enum(SectorType), nullable=False)
    summary = Column(Text)
    details = Column(JSONB, default={})
    is_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    article = relationship("Article", back_populates="risk_alerts")
    risk_pattern = relationship("RiskPattern", back_populates="risk_alerts")


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    company = Column(String(255))
    sectors = Column(ARRAY(Enum(SectorType)), default=[])
    states = Column(ARRAY(String(100)), default=[])
    notification_frequency = Column(String(20), default="daily")
    is_active = Column(Boolean, default=True)
    meta_data = Column(JSONB, default={})
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    email_reports = relationship("EmailReport", back_populates="client")


class EmailReport(Base):
    __tablename__ = "email_reports"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    subject = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    alert_ids = Column(ARRAY(Integer), default=[])
    sent_at = Column(DateTime)
    status = Column(String(20), default="pending")
    meta_data = Column(JSONB, default={})
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    client = relationship("Client", back_populates="email_reports")

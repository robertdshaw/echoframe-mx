# EchoFrame MX 🇲🇽

**Intelligent Risk Monitoring Platform for Mexico**

EchoFrame MX is an AI-powered risk intelligence system designed to monitor, analyze, and alert on business risks across Mexico. The platform combines RSS news ingestion, synthetic data generation, advanced NLP processing, and sophisticated risk pattern matching to provide real-time insights for businesses operating in Mexico.

## 🚀 Features

### Core Capabilities
- **🔍 Multi-Source Data Ingestion**: RSS feeds + synthetic hyperlocal news
- **🤖 AI-Powered Risk Analysis**: Pattern matching with OpenAI integration
- **📊 Real-time Risk Scoring**: Dynamic risk assessment across sectors
- **📧 Intelligent Notifications**: Automated email alerts and reports
- **💬 Interactive AI Chat**: Query risks using natural language
- **🎯 Sector-Specific Monitoring**: Energy, pharmaceutical, and general risk patterns

### Technical Architecture
- **FastAPI**: Modern async API framework
- **PostgreSQL + pgvector**: Vector embeddings for semantic search
- **Redis + Celery**: Background task processing
- **Docker**: Containerized deployment
- **RAG System**: Retrieval-augmented generation for intelligent responses

## 📋 Prerequisites

- Docker & Docker Compose
- Python 3.11+
- PostgreSQL with pgvector extension
- OpenAI API key (optional, for AI features)

## 🛠️ Quick Start

### 1. Clone and Setup
```bash
git clone <repository-url>
cd echoframe-mx
cp .env.example .env
# Edit .env with your configuration
```

### 2. Start with Docker (Recommended)
```bash
# Start all services
docker-compose up -d

# Initialize the system
docker-compose exec app python start.py --init

# Check system health
docker-compose exec app python start.py --health
```

### 3. Manual Setup (Development)
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://user:pass@localhost:5432/echoframe"
export REDIS_URL="redis://localhost:6379"
export OPENAI_API_KEY="your-api-key"

# Initialize database
python start.py --init

# Start API server
python start.py --start
```

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Sources  │    │   Processing    │    │    Outputs      │
│                 │    │                 │    │                 │
│ • RSS Feeds     │───▶│ • NLP Pipeline  │───▶│ • Risk Alerts   │
│ • Synthetic     │    │ • Risk Analyzer │    │ • Email Reports │
│   News          │    │ • RAG System    │    │ • API Responses │
│ • Manual Input  │    │ • Embeddings    │    │ • Dashboard     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📊 Data Flow

1. **Ingestion**: RSS feeds + synthetic Mexican news generation
2. **Processing**: NLP entity extraction + embedding generation
3. **Analysis**: Risk pattern matching with configurable rules
4. **Alerting**: Email notifications + real-time API alerts
5. **Intelligence**: AI chat interface with RAG capabilities

## 🎯 Risk Patterns

### Energy Sector
- Regulatory actions (SENER, ASEA permits)
- Operational incidents (explosions, spills)
- Social conflicts (community protests)
- Financial impacts (losses, fines)

### Pharmaceutical Sector
- COFEPRIS regulatory actions
- Drug safety issues and recalls
- Supply chain disruptions
- Market competition risks

### General Patterns
- Political changes affecting business
- Economic indicators and trends
- Security incidents

## 🔧 Configuration

### Environment Variables (.env)
```bash
# Database
DATABASE_URL=postgresql://echoframe_user:echoframe_pass@postgres:5432/echoframe

# Redis
REDIS_URL=redis://redis:6379

# OpenAI (optional)
OPENAI_API_KEY=your-api-key-here

# Email (optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
FROM_EMAIL=noreply@echoframe.mx

# Risk Thresholds
RISK_THRESHOLD_LOW=0.3
RISK_THRESHOLD_MEDIUM=0.5
RISK_THRESHOLD_HIGH=0.7

# Frontend URL
FRONTEND_URL=http://localhost:3000
```

### Risk Patterns (config/risk_patterns.json)
Customize risk detection patterns for different sectors and risk types.

## 📡 API Endpoints

### Core Endpoints
- `GET /` - System status
- `GET /health` - Health check
- `GET /docs` - Interactive API documentation

### Articles & Sources
- `GET /api/v1/articles` - List articles with filters
- `GET /api/v1/articles/{id}` - Get specific article
- `GET /api/v1/sources` - List news sources
- `POST /api/v1/sources` - Add new source

### Risk Management
- `GET /api/v1/alerts` - List risk alerts
- `GET /api/v1/alerts/critical` - Critical alerts only
- `GET /api/v1/alerts/dashboard` - Dashboard statistics
- `POST /api/v1/alerts` - Create manual alert

### Client Management
- `GET /api/v1/clients` - List clients
- `POST /api/v1/clients` - Register new client
- `PUT /api/v1/clients/{id}` - Update client preferences

### AI Chat Interface
- `POST /api/v1/chat/message` - Send chat message
- `WebSocket /api/v1/chat/ws` - Real-time chat
- `GET /api/v1/chat/suggestions` - Get query suggestions

## 🤖 AI Chat Interface

The AI chat system supports natural language queries:

```
User: "¿Qué riesgos hay en el sector energético en Veracruz?"
AI: "Encontré 5 alertas en el sector energético de Veracruz:
    🚨 2 alertas críticas sobre suspensión de permisos
    ⚠️ 3 alertas altas sobre incidentes operacionales..."

User: "Muéstrame las tendencias de la última semana"
AI: "📈 Tendencias identificadas:
    1. Suspensiones COFEPRIS (8 artículos)
    2. Protestas energéticas (12 artículos)..."
```

## 📧 Email Notifications

### Daily Reports
- Risk summary by sector
- Critical and high alerts
- Statistical dashboard
- Customizable by client preferences

### Immediate Critical Alerts
- Real-time notifications for critical risks
- Detailed risk analysis
- Recommended actions
- Source attribution

## 🔍 Monitoring & Maintenance

### System Health
```bash
# Check overall system health
curl http://localhost:8000/health

# View logs
docker-compose logs app

# Monitor background tasks
docker-compose logs worker
```

### Data Processing
```bash
# Process new RSS feeds
docker-compose exec app python -c "
from src.ingestion.coordinator import IngestionCoordinator
import asyncio
coordinator = IngestionCoordinator()
asyncio.run(coordinator.run_rss_only_cycle())
"

# Generate embeddings
docker-compose exec app python -c "
from src.rag.vector_store import VectorStore
import asyncio
vs = VectorStore()
asyncio.run(vs.process_unembedded_articles())
"
```

## 🚀 Deployment

### Production Deployment
1. **Environment Setup**: Configure production environment variables
2. **Database**: Use managed PostgreSQL with pgvector
3. **Redis**: Use managed Redis service
4. **Containers**: Deploy with Docker Swarm or Kubernetes
5. **Monitoring**: Add application monitoring (Prometheus, Grafana)
6. **SSL**: Configure HTTPS with reverse proxy (nginx)

### Scaling Considerations
- **Database**: Read replicas for heavy query loads
- **Worker Nodes**: Scale Celery workers for data processing
- **Caching**: Redis caching for frequent API queries
- **CDN**: Static asset delivery optimization

## 🔒 Security

- **API Authentication**: JWT tokens (implement as needed)
- **Database**: Connection encryption and credential management
- **Email**: Secure SMTP with app passwords
- **Environment**: Secrets management for API keys

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue in this repository
- Check the API documentation at `/docs`
- Review system logs for troubleshooting

---

**EchoFrame MX** - Powering intelligent risk management for businesses in Mexico 🇲🇽
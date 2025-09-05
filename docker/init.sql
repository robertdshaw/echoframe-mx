-- Create the vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create enum types
CREATE TYPE source_type AS ENUM ('rss', 'api', 'scraper', 'synthetic');
CREATE TYPE content_type AS ENUM ('news', 'government', 'ngo', 'industry', 'intergovernmental');
CREATE TYPE risk_level AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE sector_type AS ENUM ('energy', 'pharma', 'mining', 'manufacturing', 'finance', 'infrastructure');

-- Create sources table
CREATE TABLE sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    url TEXT,
    source_type source_type NOT NULL,
    content_type content_type NOT NULL,
    country VARCHAR(3) DEFAULT 'MEX',
    state VARCHAR(100),
    city VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create articles table
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES sources(id),
    title TEXT NOT NULL,
    content TEXT,
    summary TEXT,
    url TEXT,
    author VARCHAR(255),
    published_at TIMESTAMP,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    language VARCHAR(5) DEFAULT 'es',
    metadata JSONB DEFAULT '{}',
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create entities table (for NER results)
CREATE TABLE entities (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id),
    entity_type VARCHAR(50) NOT NULL,
    entity_text VARCHAR(500) NOT NULL,
    confidence FLOAT,
    start_pos INTEGER,
    end_pos INTEGER,
    metadata JSONB DEFAULT '{}'
);

-- Create risk_patterns table
CREATE TABLE risk_patterns (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    sector sector_type NOT NULL,
    pattern_type VARCHAR(50) NOT NULL,
    keywords TEXT[],
    risk_level risk_level NOT NULL,
    description TEXT,
    template JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create risk_alerts table
CREATE TABLE risk_alerts (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id),
    risk_pattern_id INTEGER REFERENCES risk_patterns(id),
    risk_score FLOAT NOT NULL,
    risk_level risk_level NOT NULL,
    sector sector_type NOT NULL,
    summary TEXT,
    details JSONB DEFAULT '{}',
    is_sent BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create clients table
CREATE TABLE clients (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    company VARCHAR(255),
    sectors sector_type[] DEFAULT '{}',
    states VARCHAR(100)[] DEFAULT '{}',
    notification_frequency VARCHAR(20) DEFAULT 'daily',
    is_active BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create email_reports table
CREATE TABLE email_reports (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id),
    subject VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    alert_ids INTEGER[] DEFAULT '{}',
    sent_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX idx_articles_published_at ON articles(published_at);
CREATE INDEX idx_articles_source_id ON articles(source_id);
CREATE INDEX idx_articles_embedding ON articles USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_entities_article_id ON entities(article_id);
CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_risk_alerts_created_at ON risk_alerts(created_at);
CREATE INDEX idx_risk_alerts_risk_level ON risk_alerts(risk_level);
CREATE INDEX idx_risk_alerts_sector ON risk_alerts(sector);

-- Insert default Mexican news sources
INSERT INTO sources (name, url, source_type, content_type, state, city) VALUES
('El Universal', 'https://www.eluniversal.com.mx/rss.xml', 'rss', 'news', 'CDMX', 'Mexico City'),
('La Jornada', 'https://www.jornada.com.mx/rss/edicion.xml', 'rss', 'news', 'CDMX', 'Mexico City'),
('Milenio', 'https://www.milenio.com/rss', 'rss', 'news', 'CDMX', 'Mexico City'),
('Reforma', 'https://www.reforma.com/rss/', 'rss', 'news', 'CDMX', 'Mexico City'),
('El Norte (Monterrey)', 'https://www.elnorte.com/rss/', 'rss', 'news', 'Nuevo León', 'Monterrey'),
('El Informador (Guadalajara)', 'https://www.informador.mx/rss/', 'rss', 'news', 'Jalisco', 'Guadalajara'),
('Noroeste (Sinaloa)', 'https://www.noroeste.com.mx/rss/', 'rss', 'news', 'Sinaloa', 'Culiacán'),
('Synthetic Hyperlocal News', null, 'synthetic', 'news', 'Various', 'Various');

-- Insert default client (CMM law firm)
INSERT INTO clients (name, email, company, sectors, states) VALUES
('CMM Law Firm', 'admin@cmmsc.com.mx', 'CMM SC', '{energy,pharma}', '{CDMX,Nuevo León,Jalisco,Veracruz,Tabasco}');

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_sources_updated_at BEFORE UPDATE ON sources FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_risk_patterns_updated_at BEFORE UPDATE ON risk_patterns FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_clients_updated_at BEFORE UPDATE ON clients FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
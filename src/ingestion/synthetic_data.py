import random
from datetime import datetime, timedelta
from typing import List, Dict
import asyncio
from ..models import Source, Article, SourceType, ContentType
from ..database import AsyncSessionLocal
from sqlalchemy import select

# Mexican states and cities for hyperlocal news
MEXICAN_LOCATIONS = {
    "Veracruz": ["Veracruz", "Xalapa", "Coatzacoalcos", "Poza Rica", "Córdoba"],
    "Tabasco": ["Villahermosa", "Cárdenas", "Comalcalco", "Huimanguillo", "Macuspana"],
    "Nuevo León": ["Monterrey", "Guadalupe", "San Nicolás", "Apodaca", "Santa Catarina"],
    "Jalisco": ["Guadalajara", "Zapopan", "Tlaquepaque", "Tonalá", "Puerto Vallarta"],
    "Chihuahua": ["Chihuahua", "Ciudad Juárez", "Delicias", "Parral", "Camargo"],
    "Sonora": ["Hermosillo", "Ciudad Obregón", "Nogales", "Navojoa", "Guaymas"],
    "Tamaulipas": ["Tampico", "Reynosa", "Matamoros", "Nuevo Laredo", "Ciudad Victoria"],
    "Coahuila": ["Saltillo", "Torreón", "Monclova", "Piedras Negras", "Acuña"],
    "Puebla": ["Puebla", "Tehuacán", "Atlixco", "San Martín", "Cholula"],
    "CDMX": ["Mexico City"]
}

# Energy sector news templates
ENERGY_NEWS_TEMPLATES = [
    {
        "title_templates": [
            "CFE anuncia nueva inversión de {amount} millones en {location}",
            "Pemex planea expansion de refinería en {location}",
            "Proyecto de energía renovable genera {amount} empleos en {location}",
            "Regulación energética afecta a empresas en {location}",
            "Nueva ley de hidrocarburos impacta sector en {location}"
        ],
        "content_templates": [
            "La Comisión Federal de Electricidad (CFE) anunció una inversión de {amount} millones de pesos para modernizar la infraestructura eléctrica en {location}. El proyecto incluye la construcción de nuevas subestaciones y líneas de transmisión que beneficiarán a más de {beneficiaries} familias. Las obras comenzarán en {timeline} y se espera que generen {jobs} empleos directos.",
            "Pemex presentó su plan de expansión para la refinería ubicada en {location}, con una inversión estimada de {amount} millones de pesos. El proyecto contempla aumentar la capacidad de refinación en {capacity}% y crear {jobs} nuevos empleos. Sin embargo, organizaciones ambientales expresaron preocupación por el impacto ecológico de la expansión.",
            "Un nuevo parque de energía renovable en {location} comenzó operaciones esta semana, generando {capacity} megawatts de energía limpia. La inversión de {amount} millones de pesos creó {jobs} empleos permanentes y reducirá las emisiones de CO2 en la región. El proyecto cuenta con el respaldo de inversionistas nacionales e internacionales."
        ],
        "risk_indicators": ["regulación", "impuesto", "protesta", "suspensión", "multa", "investigación"]
    },
    {
        "title_templates": [
            "Suspenden temporalmente operaciones de {company} en {location}",
            "SENER revisa permisos de exploración en {location}",
            "Comunidades indígenas protestan contra proyecto energético en {location}",
            "Nuevo impuesto afecta sector energético en {location}",
            "Falla en infraestructura eléctrica deja sin luz a {location}"
        ],
        "content_templates": [
            "La Secretaría de Energía (SENER) ordenó la suspensión temporal de las operaciones de {company} en {location} debido a irregularidades en los permisos ambientales. La medida afecta a {workers} trabajadores y podría extenderse por {timeline}. La empresa anunció que presentará los recursos legales correspondientes para revertir la decisión.",
            "Un grupo de {protesters} manifestantes de comunidades indígenas bloqueó el acceso al proyecto energético en {location}, exigiendo mayor consulta y beneficios para la región. Los manifestantes denuncian que no fueron consultados adecuadamente antes del inicio del proyecto. Las autoridades estatales iniciaron mesas de diálogo para resolver el conflicto."
        ]
    }
]

# Pharmaceutical sector news templates
PHARMA_NEWS_TEMPLATES = [
    {
        "title_templates": [
            "COFEPRIS aprueba nuevo medicamento para {condition} en México",
            "Laboratorio farmacéutico invierte {amount} millones en planta de {location}",
            "Escasez de medicamentos para {condition} afecta hospitales en {location}",
            "Nueva regulación farmacéutica genera controversia en {location}",
            "Cofepris suspende licencia de laboratorio en {location}"
        ],
        "content_templates": [
            "La Comisión Federal para la Protección contra Riesgos Sanitarios (COFEPRIS) aprobó un nuevo medicamento para el tratamiento de {condition}, desarrollado por el laboratorio {company}. El fármaco estará disponible en farmacias de {location} a partir de {timeline} y beneficiará a aproximadamente {patients} pacientes en la región.",
            "El laboratorio farmacéutico {company} anunció una inversión de {amount} millones de pesos para construir una nueva planta de producción en {location}. La facility generará {jobs} empleos directos y aumentará la capacidad de producción de medicamentos genéricos en {capacity}%. Las obras iniciarán en {timeline}.",
            "Los hospitales públicos de {location} reportan escasez crítica de medicamentos para {condition}, afectando a más de {patients} pacientes. La Secretaría de Salud estatal informó que está trabajando con proveedores alternativos para resolver la situación. Mientras tanto, familiares de pacientes organizan protestas exigiendo soluciones inmediatas."
        ],
        "risk_indicators": ["suspensión", "multa", "investigación", "escasez", "recalls", "efectos adversos"]
    }
]

class SyntheticDataGenerator:
    def __init__(self):
        self.companies = {
            "energy": ["Pemex", "CFE", "Iberdrola México", "Enel Green Power", "Acciona Energía", "Renovalia"],
            "pharma": ["Laboratorios Pisa", "Grupo Probiomed", "Chinoin", "Landsteiner Scientific", "Silanes", "Rimsa"]
        }
        
    def generate_amount(self):
        """Generate realistic investment amounts"""
        return random.choice([50, 75, 100, 150, 200, 250, 300, 500, 750, 1000, 1500, 2000])
    
    def generate_jobs(self):
        """Generate realistic job numbers"""
        return random.choice([50, 100, 150, 200, 300, 500, 750, 1000, 1500])
    
    def generate_timeline(self):
        """Generate realistic timelines"""
        return random.choice([
            "el próximo mes", "los próximos 3 meses", "el segundo semestre",
            "el próximo año", "los próximos 2 años", "el primer trimestre de 2026"
        ])
    
    def generate_location(self):
        """Generate random Mexican location"""
        state = random.choice(list(MEXICAN_LOCATIONS.keys()))
        city = random.choice(MEXICAN_LOCATIONS[state])
        return state, city
    
    def generate_energy_article(self) -> Dict:
        """Generate synthetic energy sector article"""
        template_group = random.choice(ENERGY_NEWS_TEMPLATES)
        title_template = random.choice(template_group["title_templates"])
        content_template = random.choice(template_group["content_templates"])
        
        state, city = self.generate_location()
        company = random.choice(self.companies["energy"])
        
        # Generate variables
        variables = {
            "location": f"{city}, {state}",
            "company": company,
            "amount": self.generate_amount(),
            "jobs": self.generate_jobs(),
            "timeline": self.generate_timeline(),
            "beneficiaries": random.randint(1000, 50000),
            "capacity": random.randint(10, 50),
            "workers": random.randint(50, 500),
            "protesters": random.randint(20, 200)
        }
        
        title = title_template.format(**variables)
        content = content_template.format(**variables)
        
        # Generate publication date (last 2 years)
        days_ago = random.randint(1, 730)
        published_at = datetime.now() - timedelta(days=days_ago)
        
        return {
            "title": title,
            "content": content,
            "published_at": published_at,
            "state": state,
            "city": city,
            "sector": "energy",
            "metadata": {
                "synthetic": True,
                "template_group": "energy",
                "risk_indicators": template_group.get("risk_indicators", [])
            }
        }
    
    def generate_pharma_article(self) -> Dict:
        """Generate synthetic pharmaceutical sector article"""
        template_group = random.choice(PHARMA_NEWS_TEMPLATES)
        title_template = random.choice(template_group["title_templates"])
        content_template = random.choice(template_group["content_templates"])
        
        state, city = self.generate_location()
        company = random.choice(self.companies["pharma"])
        
        conditions = ["diabetes", "hipertensión", "cáncer", "artritis", "migraña", "epilepsia", "asma"]
        
        variables = {
            "location": f"{city}, {state}",
            "company": company,
            "amount": self.generate_amount(),
            "jobs": self.generate_jobs(),
            "timeline": self.generate_timeline(),
            "condition": random.choice(conditions),
            "patients": random.randint(1000, 10000),
            "capacity": random.randint(15, 40)
        }
        
        title = title_template.format(**variables)
        content = content_template.format(**variables)
        
        # Generate publication date (last 2 years)
        days_ago = random.randint(1, 730)
        published_at = datetime.now() - timedelta(days=days_ago)
        
        return {
            "title": title,
            "content": content,
            "published_at": published_at,
            "state": state,
            "city": city,
            "sector": "pharma",
            "metadata": {
                "synthetic": True,
                "template_group": "pharma",
                "risk_indicators": template_group.get("risk_indicators", [])
            }
        }
    
    async def create_synthetic_sources(self):
        """Create synthetic hyperlocal news sources"""
        async with AsyncSessionLocal() as db:
            for state, cities in MEXICAN_LOCATIONS.items():
                for city in cities:
                    source_name = f"Noticias {city}"
                    
                    # Check if source exists
                    existing = await db.execute(
                        select(Source).where(Source.name == source_name)
                    )
                    if existing.scalar_one_or_none():
                        continue
                    
                    source = Source(
                        name=source_name,
                        url=None,  # Synthetic sources don't have URLs
                        source_type=SourceType.SYNTHETIC,
                        content_type=ContentType.NEWS,
                        country="MEX",
                        state=state,
                        city=city,
                        metadata={"type": "hyperlocal", "synthetic": True}
                    )
                    db.add(source)
            
            await db.commit()
    
    async def generate_synthetic_articles(self, count: int = 500):
        """Generate synthetic articles and store in database"""
        async with AsyncSessionLocal() as db:
            # Get synthetic sources
            result = await db.execute(
                select(Source).where(Source.source_type == SourceType.SYNTHETIC)
            )
            sources = result.scalars().all()
            
            if not sources:
                await self.create_synthetic_sources()
                result = await db.execute(
                    select(Source).where(Source.source_type == SourceType.SYNTHETIC)
                )
                sources = result.scalars().all()
            
            articles_created = 0
            
            for i in range(count):
                # Choose sector (60% energy, 40% pharma)
                sector = "energy" if random.random() < 0.6 else "pharma"
                
                if sector == "energy":
                    article_data = self.generate_energy_article()
                else:
                    article_data = self.generate_pharma_article()
                
                # Find matching source
                matching_sources = [
                    s for s in sources 
                    if s.state == article_data["state"] and s.city == article_data["city"]
                ]
                
                if not matching_sources:
                    continue
                
                source = random.choice(matching_sources)
                
                article = Article(
                    source_id=source.id,
                    title=article_data["title"],
                    content=article_data["content"],
                    published_at=article_data["published_at"],
                    language="es",
                    metadata=article_data["metadata"],
                    url=f"https://{source.name.lower().replace(' ', '')}.com.mx/noticia/{i+1}",
                    author=random.choice(["Redacción", "Corresponsal", "Agencias"])
                )
                
                db.add(article)
                articles_created += 1
            
            await db.commit()
            return articles_created
"""
Configuración general del sistema de scraping.
Carga variables de entorno desde .env y define constantes globales.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Ruta base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# Cargar variables de entorno
load_dotenv(BASE_DIR / ".env")


# --- Base de Datos ---
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'surf_scraper.db'}")

# --- Google APIs ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")

# --- Email SMTP ---
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Carving Mates")
EMAIL_FROM_ADDRESS = os.getenv("EMAIL_FROM_ADDRESS", "")

# --- SendGrid ---
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")

# --- Twilio / WhatsApp ---
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")

# --- Scraping ---
MAX_REQUESTS_PER_MINUTE = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "30"))
DEFAULT_DELAY_SECONDS = float(os.getenv("DEFAULT_DELAY_SECONDS", "2"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

# Deportes soportados (extensible sin cambiar código)
DEPORTES_SOPORTADOS = [
    "surf", "bodyboard", "snowboard", "ski",
    "kitesurf", "windsurf", "wakeboard",
    "paddlesurf", "kayak", "yoga", "skate",
]

# Tipos de negocio soportados
TIPOS_NEGOCIO = [
    "escuela", "alquiler", "retreat", "trip", "camp", "shop",
]

# Directorios de datos
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EXPORTS_DIR = DATA_DIR / "exports"
LOGS_DIR = BASE_DIR / "logs"

# Crear directorios si no existen
for directorio in [RAW_DIR, PROCESSED_DIR, EXPORTS_DIR, LOGS_DIR]:
    directorio.mkdir(parents=True, exist_ok=True)

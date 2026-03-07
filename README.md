# Surf Scraper System

Sistema modular de scraping y contacto automatizado para [Carving Mates](https://www.carvingmates.com) — una app que conecta escuelas de surf, retreats y experiencias deportivas con viajeros de todo el mundo.

## Que hace

El sistema tiene dos bloques independientes:

### Bloque 1: Recoleccion de datos
Busca negocios en internet (escuelas de surf, yoga retreats, surf camps, tiendas de alquiler, etc.), visita sus webs y extrae informacion de contacto. Todo se almacena en una base de datos SQLite local (`data/surf_scraper.db`).

```
WebScraper    -> busca negocios en DuckDuckGo / Google API / directorios
EmailScraper  -> visita cada web y extrae emails (mailto:, footer, /contact)
PhoneScraper  -> extrae telefonos y normaliza a formato internacional E.164
SocialScraper -> extrae links de Instagram, Facebook, TikTok, YouTube, etc.
TripsScraper  -> busqueda especializada de trips y retreats
```

### Bloque 2: Contacto automatizado
Toma los negocios de la base de datos y les envia emails personalizados o mensajes de WhatsApp invitandolos a registrarse en la plataforma.

### Como funciona la base de datos

La base de datos **se acumula**: cada busqueda nueva anade negocios. Si un negocio ya existe (mismo dominio web o mismo nombre+pais), se actualiza con datos nuevos sin borrar los anteriores. Puedes buscar "surf Bali", luego "surf Portugal", luego "yoga Bali", y la DB va creciendo con todos los resultados.

---

## Instalacion

```bash
# Clonar el repositorio
git clone https://github.com/Alejandro440/2-SCRAPING-CARVING-MATES.git
cd surf-scraper-system

# Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus API keys (ver seccion Configuracion)
```

## Ejecucion

```bash
python main.py
```

El servidor arranca en `http://localhost:5001`. Comprueba que funciona:

```bash
curl http://localhost:5001/
# {"service":"Surf Scraper API","status":"ok"}
```

> **Nota:** En Mac el puerto 5000 esta ocupado por AirPlay Receiver, por eso usamos 5001.

## Ejecucion con Docker

```bash
# Construir la imagen
docker build -t surf-scraper .

# Ejecutar
docker run -p 5001:5001 --env-file .env surf-scraper
```

---

## API Reference

El sistema expone una API REST en `http://localhost:5001`. Todas las peticiones se hacen con `curl`, Postman, o cualquier cliente HTTP.

Necesitas **dos terminales**:
1. **Terminal 1**: ejecuta `python main.py` (deja el servidor corriendo)
2. **Terminal 2**: desde aqui lanzas los comandos curl

Si `API_KEY_ENABLED=true` en `.env`, todas las peticiones necesitan el header `X-API-KEY: tu_clave`.

---

### `GET /`

Health check. Sin body.

```bash
curl http://localhost:5001/
```

**Respuesta:**
```json
{"status": "ok", "service": "Surf Scraper API"}
```

---

### `GET /api/stats`

Estadisticas de la base de datos. Sin body.

```bash
curl http://localhost:5001/api/stats
```

**Respuesta:**
```json
{
  "status": "success",
  "stats": {
    "total_negocios": 57,
    "con_email": 28,
    "con_telefono": 18,
    "contactados": 0,
    "por_deporte": {"surf": 57},
    "por_tipo": {"escuela": 30, "camp": 16, "alquiler": 8, "retreat": 3}
  },
  "ultimas_ejecuciones": [...]
}
```

---

### `POST /api/scraping/search`

Ejecuta el pipeline completo de scraping (web + email + phone + social). Tarda ~2 minutos.

**Body JSON:**
```json
{
  "deporte": "surf",           // obligatorio - "surf", "yoga", "kitesurf", etc.
  "locacion": "Bali",          // obligatorio - "Bali", "Costa Rica", "Portugal", etc.
  "tipo_negocio": "escuela",   // opcional (default null) - "escuela", "camp", "retreat", "shop"
  "max_resultados": 50,        // opcional (default 50) - entre 1 y 200
  "idioma": "en"               // opcional (default "en") - idioma de busqueda
}
```

**Ejemplo:**
```bash
curl -X POST http://localhost:5001/api/scraping/search \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali"}'
```

**Respuesta:**
```json
{
  "status": "success",
  "message": "Scraping completado correctamente",
  "input": {"deporte": "surf", "locacion": "Bali", ...},
  "summary": {
    "total_resultados": 57,
    "negocios_encontrados_web": 50,
    "fuentes_utilizadas": ["google", "duckduckgo", "directorios"],
    "errores": []
  },
  "resultados": [
    {
      "nombre": "Odysseys Surf School",
      "tipo_negocio": "escuela",
      "deporte": "surf",
      "pais": "Indonesia",
      "website": "https://odysseysurfschool.com",
      "emails": ["info@odysseysurfschool.com"],
      "telefonos": ["+6281234567890"],
      "redes_sociales": {"instagram": "https://instagram.com/odysseysurfschool"},
      ...
    },
    ...
  ]
}
```

---

### `POST /api/scraping/trips`

Busqueda especializada de trips y retreats.

**Body JSON:**
```json
{
  "deporte": "yoga",           // obligatorio
  "locacion": "Costa Rica",    // obligatorio
  "max_resultados": 30         // opcional (default 30)
}
```

**Ejemplo:**
```bash
curl -X POST http://localhost:5001/api/scraping/trips \
  -H "Content-Type: application/json" \
  -d '{"deporte": "yoga", "locacion": "Costa Rica"}'
```

---

### `POST /api/scraping/export`

Exporta negocios de la base de datos. Los datos se devuelven en la respuesta HTTP. Para guardarlos en un archivo, usa `-o nombre.json`.

**Body JSON:**
```json
{
  "deporte": "surf",      // opcional - sin filtro = exporta todo
  "locacion": "Bali",     // opcional
  "formato": "json"       // opcional (default "json") - "json" o "csv"
}
```

**Ejemplos:**
```bash
# Ver en pantalla
curl -X POST http://localhost:5001/api/scraping/export \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali"}'

# Guardar como JSON
curl -X POST http://localhost:5001/api/scraping/export \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali"}' \
  -o export_surf_bali.json

# Guardar como CSV (abrir con Excel/Google Sheets)
curl -X POST http://localhost:5001/api/scraping/export \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali", "formato": "csv"}' \
  -o export_surf_bali.csv

# Exportar TODA la base de datos
curl -X POST http://localhost:5001/api/scraping/export \
  -H "Content-Type: application/json" \
  -d '{}' -o export_todo.json
```

> **Nota:** El archivo se guarda en el directorio desde donde ejecutas el curl. Usa `-o ~/Desktop/export.json` para guardarlo en el escritorio.

---

### `POST /api/contact/email`

Envia emails a negocios pendientes. Requiere configurar SMTP o SendGrid en `.env`.

**Body JSON:**
```json
{
  "deporte": "surf",                // opcional
  "locacion": "Bali",              // opcional
  "template": "escuela_inicial",   // opcional (default "escuela_inicial")
  "max_envios": 50,                // opcional (default 50)
  "dry_run": true                  // opcional (default true) - true = simula sin enviar
}
```

**Ejemplos:**
```bash
# Simulacion (ver que haria sin enviar)
curl -X POST http://localhost:5001/api/contact/email \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali", "dry_run": true}'

# Envio real
curl -X POST http://localhost:5001/api/contact/email \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali", "dry_run": false, "template": "escuela_inicial"}'
```

---

## Ejemplo de uso completo

```bash
# Terminal 1: arrancar el servidor
python main.py

# Terminal 2: buscar escuelas de surf en Bali
curl -X POST http://localhost:5001/api/scraping/search \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali"}'
# (esperar ~2 min)

# Buscar tambien en Portugal
curl -X POST http://localhost:5001/api/scraping/search \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Portugal"}'

# Ver cuantos negocios tenemos en total
curl http://localhost:5001/api/stats

# Exportar todo a CSV
curl -X POST http://localhost:5001/api/scraping/export \
  -H "Content-Type: application/json" \
  -d '{"formato": "csv"}' -o todos_los_negocios.csv

# Exportar solo Bali a JSON
curl -X POST http://localhost:5001/api/scraping/export \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali"}' -o bali.json
```

---

## Configuracion (.env)

```bash
# Base de datos
DATABASE_URL=sqlite:///data/surf_scraper.db

# Google Custom Search API (opcional, DuckDuckGo funciona sin esto)
GOOGLE_API_KEY=tu_api_key
GOOGLE_SEARCH_ENGINE_ID=tu_search_engine_id

# Email - SMTP (Gmail)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu_email@gmail.com
SMTP_PASSWORD=tu_app_password

# Email - SendGrid (alternativa)
SENDGRID_API_KEY=tu_sendgrid_key

# WhatsApp (Twilio, opcional)
TWILIO_ACCOUNT_SID=tu_sid
TWILIO_AUTH_TOKEN=tu_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

# API
API_KEY_ENABLED=false
API_KEY=tu_api_key_secreta

# Scraping
MAX_REQUESTS_PER_MINUTE=30
DEFAULT_DELAY_SECONDS=2
MAX_RETRIES=3
REQUEST_TIMEOUT=30
```

**Sin Google API, el sistema funciona perfectamente con DuckDuckGo como motor de busqueda.**

---

## Estructura del proyecto

```
surf-scraper-system/
├── main.py                          # Entry point (Flask server, puerto 5001)
├── Dockerfile
├── requirements.txt
├── .env.example
├── app/
│   ├── __init__.py                  # Flask app factory
│   ├── api/
│   │   └── routes.py               # Endpoints REST
│   └── services/
│       └── scraping_service.py      # Capa de servicio (orquesta scrapers)
├── config/
│   ├── settings.py                  # Configuracion desde .env
│   └── sources.py                   # Fuentes de scraping, templates de busqueda
├── database/
│   ├── connection.py                # SQLAlchemy engine + sesiones
│   └── models.py                    # Modelos: Negocio, LogScraping, LogContacto
├── scrapers/
│   ├── base_scraper.py              # Clase base (fetch, retry, rate limiting, dedup)
│   ├── web_scraper.py               # Pipeline 1: busqueda de negocios
│   ├── email_scraper.py             # Pipeline 2: extraccion de emails
│   ├── phone_scraper.py             # Pipeline 3: extraccion de telefonos
│   ├── social_scraper.py            # Pipeline 4: redes sociales
│   └── trips_scraper.py             # Pipeline 5: trips y retreats
├── automation/
│   ├── email_sender.py              # Envio de emails (SMTP / SendGrid)
│   ├── whatsapp_sender.py           # Envio de WhatsApp (Twilio)
│   └── templates/                   # Templates HTML personalizables
├── utils/
│   ├── logger.py                    # Logging a consola + archivo
│   ├── validators.py                # Validacion de emails, telefonos, URLs
│   ├── rate_limiter.py              # Rate limiting por dominio
│   └── helpers.py                   # User-Agent rotation, utilidades
├── tests/                           # 52 tests
├── data/
│   ├── surf_scraper.db              # Base de datos SQLite (se crea automaticamente)
│   ├── raw/
│   ├── processed/
│   └── exports/
└── logs/
```

## Deportes soportados

surf, bodyboard, snowboard, ski, kitesurf, windsurf, wakeboard, paddlesurf, kayak, yoga, skate

Agregar un nuevo deporte no requiere cambiar codigo — es solo un parametro en el JSON.

## Tests

```bash
python -m pytest tests/ -v
```

---

Built for [Carving Mates](https://www.carvingmates.com)

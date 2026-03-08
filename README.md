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
git clone https://github.com/Alejandro440/2-SCRAPING-CARVING-MATES.git
cd surf-scraper-system

python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

pip install -r requirements.txt

cp .env.example .env
# Editar .env con tus API keys (ver seccion Configuracion)
```

## Ejecucion

```bash
python main.py
```

El servidor arranca en `http://localhost:5001`.

> **Nota:** En Mac el puerto 5000 esta ocupado por AirPlay Receiver, por eso usamos 5001.

## Ejecucion con Docker

```bash
docker build -t surf-scraper .
docker run -p 5001:5001 --env-file .env surf-scraper
```

---

## API Reference

**Base URL:** `http://localhost:5001`

**Headers requeridos en todos los POST:**
```
Content-Type: application/json
```

**Header opcional (si `API_KEY_ENABLED=true` en `.env`):**
```
X-API-KEY: tu_clave
```

Necesitas **dos terminales**: una ejecutando `python main.py` y otra para lanzar las peticiones.

---

### `GET /`

Health check. Sin body.

**Request:**
```
GET http://localhost:5001/
```

**Response 200:**
```json
{
  "status": "ok",
  "service": "Surf Scraper API"
}
```

---

### `POST /api/scraping/search`

Ejecuta el pipeline completo de scraping (web + email + phone + social). Tarda ~2 minutos.

**Headers:**
```
Content-Type: application/json
```

**Body JSON:**

| Campo | Tipo | Obligatorio | Default | Valores posibles |
|---|---|---|---|---|
| `deporte` | string | si | — | `"surf"`, `"yoga"`, `"kitesurf"`, `"snowboard"`, `"bodyboard"`, `"ski"`, `"windsurf"`, `"wakeboard"`, `"paddlesurf"`, `"kayak"`, `"skate"` |
| `locacion` | string | si | — | `"Bali"`, `"Portugal"`, `"Costa Rica"`, etc. |
| `tipo_negocio` | string | no | `null` | `"escuela"`, `"alquiler"`, `"retreat"`, `"trip"`, `"camp"`, `"shop"` |
| `max_resultados` | int | no | `50` | `1` a `200` |
| `idioma` | string | no | `"en"` | `"en"`, `"es"`, etc. |

**Ejemplo Postman / curl:**
```bash
curl -X POST http://localhost:5001/api/scraping/search \
  -H "Content-Type: application/json" \
  -d '{
    "deporte": "surf",
    "locacion": "Bali"
  }'
```

**Response 200:**
```json
{
  "status": "success",
  "message": "Scraping completado correctamente",
  "input": {
    "deporte": "surf",
    "locacion": "Bali",
    "tipo_negocio": null,
    "max_resultados": 50,
    "idioma": "en"
  },
  "summary": {
    "total_resultados": 57,
    "negocios_encontrados_web": 50,
    "fuentes_utilizadas": ["google", "duckduckgo", "directorios"],
    "errores": []
  },
  "resultados": [
    {
      "id": "a1b2c3d4-...",
      "nombre": "Odysseys Surf School",
      "tipo_negocio": "escuela",
      "deporte": "surf",
      "deportes_secundarios": [],
      "descripcion": null,
      "pais": "Indonesia",
      "region": "Bali",
      "ciudad": "Kuta",
      "direccion": null,
      "latitud": null,
      "longitud": null,
      "telefonos": ["+6281234567890"],
      "emails": ["info@odysseysurfschool.com"],
      "website": "https://odysseysurfschool.com",
      "redes_sociales": {"instagram": "https://instagram.com/odysseysurf"},
      "precio_referencia": null,
      "rating": null,
      "reviews_count": null,
      "fuente": "duckduckgo",
      "fecha_scraping": "2026-03-07",
      "contactado": false,
      "fecha_contacto": null,
      "metodo_contacto": null,
      "respuesta": null
    }
  ]
}
```

---

### `POST /api/scraping/trips`

Busqueda especializada de trips y retreats.

**Headers:**
```
Content-Type: application/json
```

**Body JSON:**

| Campo | Tipo | Obligatorio | Default |
|---|---|---|---|
| `deporte` | string | si | — |
| `locacion` | string | si | — |
| `max_resultados` | int | no | `30` |

**Ejemplo:**
```bash
curl -X POST http://localhost:5001/api/scraping/trips \
  -H "Content-Type: application/json" \
  -d '{
    "deporte": "yoga",
    "locacion": "Costa Rica"
  }'
```

**Response 200:**
```json
{
  "status": "success",
  "message": "Busqueda de trips completada",
  "input": {
    "deporte": "yoga",
    "locacion": "Costa Rica",
    "max_resultados": 30
  },
  "summary": {
    "total_resultados": 15,
    "errores": []
  },
  "resultados": [ ... ]
}
```

> **Nota:** El `summary` de trips NO incluye `negocios_encontrados_web` ni `fuentes_utilizadas` (solo `total_resultados` y `errores`).

---

### `GET /api/stats`

Estadisticas de la base de datos. Sin body.

**Request:**
```
GET http://localhost:5001/api/stats
```

**Response 200:**
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
  "ultimas_ejecuciones": [
    {
      "pipeline": "web",
      "deporte": "surf",
      "locacion": "Bali",
      "resultados_nuevos": 45,
      "errores": 1,
      "fecha": "2026-03-07 03:23:08.111939"
    }
  ]
}
```

---

### `POST /api/scraping/export`

Exporta negocios de la base de datos. Los datos se devuelven en la respuesta HTTP. Para guardarlos en un archivo, usa `-o nombre.json` en curl o "Save Response" en Postman.

**Headers:**
```
Content-Type: application/json
```

**Body JSON:**

| Campo | Tipo | Obligatorio | Default |
|---|---|---|---|
| `deporte` | string | no | `null` (exporta todo) |
| `locacion` | string | no | `null` (exporta todo) |
| `formato` | string | no | `"json"` |

Valores de `formato`: `"json"` o `"csv"`.

**Ejemplo — JSON en pantalla:**
```bash
curl -X POST http://localhost:5001/api/scraping/export \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali"}'
```

**Ejemplo — guardar como archivo:**
```bash
curl -X POST http://localhost:5001/api/scraping/export \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali"}' \
  -o export_surf_bali.json
```

**Ejemplo — CSV:**
```bash
curl -X POST http://localhost:5001/api/scraping/export \
  -H "Content-Type: application/json" \
  -d '{"formato": "csv"}' \
  -o export_todo.csv
```

> **Nota:** El archivo se guarda en el directorio desde donde ejecutas curl.

**Response 200 (formato json):**
```json
{
  "status": "success",
  "total": 57,
  "resultados": [
    {
      "nombre": "Odysseys Surf School",
      "tipo_negocio": "escuela",
      "deporte": "surf",
      "pais": "Indonesia",
      "region": "Bali",
      "ciudad": "Kuta",
      "website": "https://odysseysurfschool.com",
      "emails": "info@odysseysurfschool.com",
      "telefonos": "+6281234567890",
      "instagram": "https://instagram.com/odysseysurf",
      "facebook": "",
      "rating": null,
      "reviews_count": null,
      "precio_referencia": null,
      "fuente": "duckduckgo",
      "contactado": false,
      "respuesta": null
    }
  ]
}
```

> **Nota:** El formato de export es diferente al de search. En export, `emails` y `telefonos` son strings separados por coma (no arrays), y `redes_sociales` se aplana a campos individuales (`instagram`, `facebook`).

**Response 200 (formato csv):** Descarga directa del archivo `.csv` con los mismos campos.

---

### `POST /api/contact/email`

Envia emails a negocios pendientes. Requiere configurar SMTP o SendGrid en `.env`.

**Headers:**
```
Content-Type: application/json
```

**Body JSON:**

| Campo | Tipo | Obligatorio | Default |
|---|---|---|---|
| `deporte` | string | no | `null` |
| `locacion` | string | no | `null` |
| `template` | string | no | `"escuela_inicial"` |
| `max_envios` | int | no | `50` |
| `dry_run` | bool | no | `true` |

Templates disponibles: `"escuela_inicial"`, `"retreat_inicial"`, `"followup"`.

**Ejemplo — simulacion (no envia):**
```bash
curl -X POST http://localhost:5001/api/contact/email \
  -H "Content-Type: application/json" \
  -d '{
    "deporte": "surf",
    "locacion": "Bali",
    "dry_run": true
  }'
```

**Ejemplo — envio real:**
```bash
curl -X POST http://localhost:5001/api/contact/email \
  -H "Content-Type: application/json" \
  -d '{
    "deporte": "surf",
    "locacion": "Bali",
    "dry_run": false,
    "template": "escuela_inicial"
  }'
```

**Response 200:**
```json
{
  "status": "success",
  "message": "Contacto completado (dry run)",
  "resultado": { ... }
}
```

---

## Codigos de error

Todas las respuestas de error siguen el mismo formato:

```json
{
  "status": "error",
  "message": "Descripcion del error"
}
```

| Codigo | Cuando ocurre |
|---|---|
| `400` | Body no es JSON valido |
| `400` | Falta campo obligatorio `deporte` o `locacion` |
| `400` | `max_resultados` no es entero o esta fuera de rango (1-200) |
| `400` | `formato` no es `"json"` ni `"csv"` |
| `401` | `API_KEY_ENABLED=true` y falta header `X-API-KEY` o el valor es incorrecto |
| `500` | Error interno (fallo de scraper, error de base de datos, etc.) |

**Ejemplos de mensajes de error reales:**

```json
{"status": "error", "message": "El body debe ser JSON valido"}
{"status": "error", "message": "El campo 'deporte' es obligatorio"}
{"status": "error", "message": "El campo 'locacion' es obligatorio"}
{"status": "error", "message": "max_resultados debe ser un entero entre 1 y 200"}
{"status": "error", "message": "max_resultados debe ser un entero valido"}
{"status": "error", "message": "formato debe ser 'json' o 'csv'"}
{"status": "error", "message": "API key invalida o faltante. Envia el header X-API-KEY."}
{"status": "error", "message": "Error interno: ..."}
```

---

## Ejemplo de uso completo

```bash
# Terminal 1: arrancar el servidor
python main.py

# Terminal 2:

# 1. Buscar escuelas de surf en Bali (~2 min)
curl -X POST http://localhost:5001/api/scraping/search \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali"}'

# 2. Buscar tambien en Portugal
curl -X POST http://localhost:5001/api/scraping/search \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Portugal"}'

# 3. Ver cuantos negocios hay en la DB
curl http://localhost:5001/api/stats

# 4. Exportar todo a CSV
curl -X POST http://localhost:5001/api/scraping/export \
  -H "Content-Type: application/json" \
  -d '{"formato": "csv"}' -o todos_los_negocios.csv

# 5. Exportar solo Bali a JSON
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

## Tests

```bash
python -m pytest tests/ -v
```

---

Built for [Carving Mates](https://www.carvingmates.com)

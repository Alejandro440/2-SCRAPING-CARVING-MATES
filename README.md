# Surf Scraper System

API open source de scraping por `deporte` + `locacion` para [Carving Mates](https://www.carvingmates.com). Busca negocios (escuelas de surf, yoga retreats, camps, shops) combinando multiples fuentes publicas. No depende de Google ni de ninguna API propietaria.

## Endpoints

**Base URL:** `http://localhost:5001`

| Metodo | Ruta | Tiempo | Descripcion |
|--------|------|--------|-------------|
| `GET` | `/` | instant | Health check |
| `POST` | `/api/scraping/search` | ~30s | **Busqueda principal** (DuckDuckGo + directorios) |
| `POST` | `/api/scraping/enrich` | ~2min | Enriquecer con emails, telefonos, redes sociales |
| `POST` | `/api/scraping/trips` | ~30s | Buscar trips y retreats |
| `GET` | `/api/stats` | instant | Estadisticas de la base de datos |
| `POST` | `/api/scraping/export` | instant | Exportar datos (JSON o CSV) |
| `POST` | `/api/contact/email` | variable | Enviar emails a negocios |

### Endpoint principal

```
POST http://localhost:5001/api/scraping/search
Content-Type: application/json

{"deporte": "surf", "locacion": "Bali"}
```

```json
{
  "status": "success",
  "message": "Busqueda completada correctamente",
  "input": {"deporte": "surf", "locacion": "Bali"},
  "summary": {
    "total_resultados": 40,
    "fuentes_utilizadas": ["duckduckgo", "directorios"],
    "errores": []
  },
  "resultados": [
    {
      "nombre": "Odysseys Surf School",
      "tipo_negocio": "escuela",
      "deporte": "surf",
      "locacion": "Bali",
      "website": "https://odysseysurfschool.com",
      "emails": [],
      "telefonos": [],
      "redes_sociales": {},
      "fuente": "duckduckgo"
    }
  ]
}
```

---

## Quick Start

```bash
git clone https://github.com/Alejandro440/2-SCRAPING-CARVING-MATES.git
cd surf-scraper-system
pip install -r requirements.txt
cp .env.example .env
python main.py
```

En otra terminal:

```bash
# Health check
curl http://localhost:5001/

# Buscar negocios (~30s)
curl -X POST http://localhost:5001/api/scraping/search \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali"}'
```

No necesitas API keys para buscar. El sistema usa fuentes publicas abiertas.

---

## Arquitectura

```
POST /api/scraping/search  {"deporte": "surf", "locacion": "Bali"}
         |
         v
   app/api/routes.py            Valida input, enruta al servicio
         |
         v
   app/services/scraping_service.py    Orquesta el pipeline
         |
         v
   scrapers/web_scraper.py      Busca en DuckDuckGo + directorios
         |                       Si una fuente falla, sigue con las demas
         v
   database/models.py           Guarda en SQLite (dedup por dominio o nombre+pais)
         |
         v
   Response JSON                Devuelve resultados simplificados
```

**Principios:**
- **Open source:** No depende de Google API ni de ninguna API propietaria. Solo fuentes publicas.
- **Multi-fuente:** DuckDuckGo HTML + directorios especializados. Si una fuente falla, las demas siguen.
- **Busqueda separada de enriquecimiento:** `/search` responde rapido (~30s). `/enrich` anade emails/phones/social (opcional, ~2min).
- **Sin reintentos en 403:** Si un dominio bloquea, se sigue adelante inmediatamente.
- **JSON simplificado:** Solo campos utiles (nombre, tipo, deporte, locacion, website, contacto, fuente).

| Capa | Archivos | Responsabilidad |
|---|---|---|
| Entry point | `main.py` | Arranca Flask en puerto 5001 |
| Routing | `app/api/routes.py` | 7 endpoints, validacion, autenticacion |
| Servicio | `app/services/scraping_service.py` | Orquesta pipelines, lee resultados de DB |
| Scrapers | `scrapers/*.py` | 5 pipelines independientes |
| Modelos | `database/models.py` | `Negocio`, `LogScraping`, `LogContacto` |
| Config | `config/settings.py` | Carga `.env`, constantes |
| Utilidades | `utils/*.py` | Logger, validadores, rate limiter |
| Contacto | `automation/*.py` | Email (SMTP/SendGrid) y WhatsApp (Twilio) |

---

## API Reference

Todos los POST requieren `Content-Type: application/json`. Si `API_KEY_ENABLED=true` en `.env`, todas las peticiones necesitan `X-API-KEY: tu_clave`.

---

### `POST /api/scraping/search`

Busqueda principal. Combina DuckDuckGo + directorios. Responde en ~30s.

**Body JSON:**

| Campo | Tipo | Obligatorio | Default |
|---|---|---|---|
| `deporte` | string | si | — |
| `locacion` | string | si | — |
| `tipo_negocio` | string | no | `null` |
| `max_resultados` | int | no | `50` |
| `idioma` | string | no | `"en"` |

Deportes: `"surf"`, `"yoga"`, `"kitesurf"`, `"snowboard"`, `"bodyboard"`, `"ski"`, `"windsurf"`, `"wakeboard"`, `"paddlesurf"`, `"kayak"`, `"skate"`.

Tipos de negocio: `"escuela"`, `"alquiler"`, `"retreat"`, `"trip"`, `"camp"`, `"shop"`.

**curl:**
```bash
curl -X POST http://localhost:5001/api/scraping/search \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali"}'
```

**Postman:** POST → `http://localhost:5001/api/scraping/search` → Body raw JSON → `{"deporte": "surf", "locacion": "Bali"}`

**Response 200:**
```json
{
  "status": "success",
  "message": "Busqueda completada correctamente",
  "input": {
    "deporte": "surf",
    "locacion": "Bali"
  },
  "summary": {
    "total_resultados": 40,
    "negocios_encontrados_web": 50,
    "fuentes_utilizadas": ["duckduckgo", "directorios"],
    "errores": []
  },
  "resultados": [
    {
      "nombre": "Odysseys Surf School",
      "tipo_negocio": "escuela",
      "deporte": "surf",
      "locacion": "Bali",
      "website": "https://odysseysurfschool.com",
      "emails": [],
      "telefonos": [],
      "redes_sociales": {},
      "fuente": "duckduckgo"
    }
  ]
}
```

---

### `POST /api/scraping/enrich`

Enriquece negocios ya encontrados con emails, telefonos y redes sociales. Llamar despues de `/search`. Tarda ~1-2 min.

**Body JSON:**

| Campo | Tipo | Obligatorio | Default |
|---|---|---|---|
| `deporte` | string | si | — |
| `locacion` | string | si | — |
| `max_resultados` | int | no | `50` |

**curl:**
```bash
curl -X POST http://localhost:5001/api/scraping/enrich \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali"}'
```

**Response 200:**
```json
{
  "status": "success",
  "message": "Enriquecimiento completado",
  "summary": {
    "total_resultados": 40,
    "pipelines_ejecutados": ["email", "phone", "social"],
    "errores": []
  },
  "resultados": [
    {
      "nombre": "Odysseys Surf School",
      "tipo_negocio": "escuela",
      "deporte": "surf",
      "locacion": "Bali",
      "website": "https://odysseysurfschool.com",
      "emails": ["info@odysseysurfschool.com"],
      "telefonos": ["+6281234567890"],
      "redes_sociales": {"instagram": "https://instagram.com/odysseysurf"},
      "fuente": "duckduckgo"
    }
  ]
}
```

---

### `POST /api/scraping/trips`

Busqueda especializada de trips y retreats.

**Body JSON:**

| Campo | Tipo | Obligatorio | Default |
|---|---|---|---|
| `deporte` | string | si | — |
| `locacion` | string | si | — |
| `max_resultados` | int | no | `30` |

**curl:**
```bash
curl -X POST http://localhost:5001/api/scraping/trips \
  -H "Content-Type: application/json" \
  -d '{"deporte": "yoga", "locacion": "Costa Rica"}'
```

---

### `GET /api/stats`

Estadisticas de la base de datos. Sin body.

```bash
curl http://localhost:5001/api/stats
```

---

### `POST /api/scraping/export`

Exporta negocios de la DB. Usar `-o` en curl para guardar a archivo.

**Body JSON:**

| Campo | Tipo | Obligatorio | Default |
|---|---|---|---|
| `deporte` | string | no | `null` (todo) |
| `locacion` | string | no | `null` (todo) |
| `formato` | string | no | `"json"` |

```bash
curl -X POST http://localhost:5001/api/scraping/export \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali"}' -o bali.json
```

---

### `POST /api/contact/email`

Envia emails a negocios. Requiere SMTP o SendGrid en `.env`.

**Body JSON:**

| Campo | Tipo | Obligatorio | Default |
|---|---|---|---|
| `deporte` | string | no | `null` |
| `locacion` | string | no | `null` |
| `template` | string | no | `"escuela_inicial"` |
| `max_envios` | int | no | `50` |
| `dry_run` | bool | no | `true` |

```bash
curl -X POST http://localhost:5001/api/contact/email \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali", "dry_run": true}'
```

---

## Codigos de error

```json
{"status": "error", "message": "Descripcion del error"}
```

| Codigo | Cuando |
|---|---|
| `400` | Falta `deporte` o `locacion`, body invalido, `max_resultados` fuera de rango |
| `401` | `API_KEY_ENABLED=true` y falta `X-API-KEY` |
| `500` | Error interno |

---

## Flujo de uso tipico

```bash
# 1. Buscar negocios (~30s)
curl -X POST http://localhost:5001/api/scraping/search \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali"}'

# 2. Enriquecer con datos de contacto (~2min, opcional)
curl -X POST http://localhost:5001/api/scraping/enrich \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali"}'

# 3. Ver estadisticas
curl http://localhost:5001/api/stats

# 4. Exportar
curl -X POST http://localhost:5001/api/scraping/export \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali"}' -o bali.json
```

La base de datos se acumula: cada busqueda anade negocios sin borrar los anteriores.

---

## Configuracion (.env)

```bash
DATABASE_URL=sqlite:///data/surf_scraper.db

# Email SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu_email@gmail.com
SMTP_PASSWORD=tu_app_password

# SendGrid (alternativa)
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

No se necesitan API keys para buscar. El sistema usa fuentes publicas abiertas (DuckDuckGo + directorios).

## Ejecucion con Docker

```bash
docker build -t surf-scraper .
docker run -p 5001:5001 --env-file .env surf-scraper
```

## Tests

```bash
python -m pytest tests/ -v
```

---

Built for [Carving Mates](https://www.carvingmates.com)

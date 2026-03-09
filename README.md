# Surf Scraper System

API global de scraping por `deporte` + `locacion` para [Carving Mates](https://www.carvingmates.com). Busca negocios (escuelas de surf, yoga retreats, camps, shops) combinando multiples fuentes de forma automatica. No depende de una sola web ni de un solo directorio.

## Endpoints

**Base URL:** `http://localhost:5001`

| Metodo | Ruta | Tiempo | Descripcion |
|--------|------|--------|-------------|
| `GET` | `/` | instant | Health check |
| `POST` | `/api/scraping/search` | ~30s | **Busqueda principal** (Google + DuckDuckGo + directorios) |
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
  "input": {"deporte": "surf", "locacion": "Bali", "tipo_negocio": null, "max_resultados": 50, "idioma": "en"},
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
      "emails": [],
      "telefonos": [],
      "redes_sociales": {}
    }
  ]
}
```

> **Busqueda y enriquecimiento estan separados.** El endpoint `/search` solo busca negocios (~30s). Para obtener emails, telefonos y redes sociales, llamar despues a `/enrich`.

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
# 1. Health check
curl http://localhost:5001/

# 2. Buscar negocios (~30s)
curl -X POST http://localhost:5001/api/scraping/search \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali"}'

# 3. Enriquecer con emails/telefonos/redes (~2min)
curl -X POST http://localhost:5001/api/scraping/enrich \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali"}'

# 4. Exportar resultados
curl -X POST http://localhost:5001/api/scraping/export \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali"}' -o bali.json
```

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
   scrapers/web_scraper.py      Busca en Google + DuckDuckGo + directorios
         |                       Si Google da 403, sigue con DuckDuckGo (no reintenta)
         |                       Si un directorio falla, sigue con los demas
         v
   database/models.py           Guarda en SQLite (dedup por dominio o nombre+pais)
         |
         v
   Response JSON                Devuelve resultados unificados
```

**Principios:**
- **Multi-fuente:** Google Custom Search API + DuckDuckGo HTML + directorios especializados. Si una fuente falla, las demas siguen funcionando.
- **Busqueda separada de enriquecimiento:** `/search` responde rapido (~30s). `/enrich` es opcional y lento (~2min).
- **Sin reintentos en 403:** Si un dominio bloquea, se registra y se sigue adelante. No hay retries que cuelguen la respuesta.
- **Deduplicacion:** Mismo dominio web o mismo nombre+pais = un solo registro. Los datos se acumulan entre busquedas.

| Capa | Archivos | Responsabilidad |
|---|---|---|
| Entry point | `main.py` | Arranca Flask en puerto 5001 |
| Routing | `app/api/routes.py` | 7 endpoints, validacion, autenticacion |
| Servicio | `app/services/scraping_service.py` | Orquesta pipelines, lee resultados de DB |
| Scrapers | `scrapers/*.py` | 5 pipelines independientes, cada uno escribe en DB |
| Modelos | `database/models.py` | `Negocio`, `LogScraping`, `LogContacto` (SQLAlchemy/SQLite) |
| Config | `config/settings.py` | Carga `.env`, define constantes |
| Utilidades | `utils/*.py` | Logger, validadores, rate limiter, User-Agent rotation |
| Contacto | `automation/*.py` | Email (SMTP/SendGrid) y WhatsApp (Twilio) |

---

## API Reference

Todos los POST requieren `Content-Type: application/json`. Si `API_KEY_ENABLED=true` en `.env`, todas las peticiones necesitan `X-API-KEY: tu_clave`.

---

### `POST /api/scraping/search`

Busqueda principal. Combina Google + DuckDuckGo + directorios. Responde en ~30s.

**Body JSON:**

| Campo | Tipo | Obligatorio | Default | Valores |
|---|---|---|---|---|
| `deporte` | string | si | — | `"surf"`, `"yoga"`, `"kitesurf"`, `"snowboard"`, `"bodyboard"`, `"ski"`, `"windsurf"`, `"wakeboard"`, `"paddlesurf"`, `"kayak"`, `"skate"` |
| `locacion` | string | si | — | `"Bali"`, `"Portugal"`, `"Costa Rica"`, etc. |
| `tipo_negocio` | string | no | `null` | `"escuela"`, `"alquiler"`, `"retreat"`, `"trip"`, `"camp"`, `"shop"` |
| `max_resultados` | int | no | `50` | `1` a `200` |
| `idioma` | string | no | `"en"` | `"en"`, `"es"`, etc. |

**curl:**
```bash
curl -X POST http://localhost:5001/api/scraping/search \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali"}'
```

**Postman:**
- Method: `POST`
- URL: `http://localhost:5001/api/scraping/search`
- Body: raw JSON → `{"deporte": "surf", "locacion": "Bali"}`

**Response 200:**
```json
{
  "status": "success",
  "message": "Busqueda completada correctamente",
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
      "telefonos": [],
      "emails": [],
      "website": "https://odysseysurfschool.com",
      "redes_sociales": {},
      "precio_referencia": null,
      "rating": null,
      "reviews_count": null,
      "fuente": "duckduckgo",
      "fecha_scraping": "2026-03-09",
      "contactado": false,
      "fecha_contacto": null,
      "metodo_contacto": null,
      "respuesta": null
    }
  ]
}
```

---

### `POST /api/scraping/enrich`

Enriquece negocios ya encontrados con emails, telefonos y redes sociales. Visita cada web de la DB y extrae informacion de contacto. Llamar despues de `/search`. Tarda ~1-2 minutos.

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
  "input": {
    "deporte": "surf",
    "locacion": "Bali",
    "max_resultados": 50
  },
  "summary": {
    "total_resultados": 57,
    "pipelines_ejecutados": ["email", "phone", "social"],
    "errores": []
  },
  "resultados": [
    {
      "nombre": "Odysseys Surf School",
      "emails": ["info@odysseysurfschool.com"],
      "telefonos": ["+6281234567890"],
      "redes_sociales": {"instagram": "https://instagram.com/odysseysurf"}
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

**Response 200:**
```json
{
  "status": "success",
  "message": "Busqueda de trips completada",
  "input": {"deporte": "yoga", "locacion": "Costa Rica", "max_resultados": 30},
  "summary": {"total_resultados": 15, "errores": []},
  "resultados": [ ... ]
}
```

---

### `GET /api/stats`

Estadisticas de la base de datos. Sin body.

**curl:**
```bash
curl http://localhost:5001/api/stats
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
      "fecha": "2026-03-09 11:53:00.000000"
    }
  ]
}
```

---

### `POST /api/scraping/export`

Exporta negocios de la DB. Los datos se devuelven en la respuesta. Usar `-o` en curl para guardar a archivo.

**Body JSON:**

| Campo | Tipo | Obligatorio | Default |
|---|---|---|---|
| `deporte` | string | no | `null` (todo) |
| `locacion` | string | no | `null` (todo) |
| `formato` | string | no | `"json"` |

Valores de `formato`: `"json"` o `"csv"`.

**curl:**
```bash
# JSON
curl -X POST http://localhost:5001/api/scraping/export \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali"}' -o bali.json

# CSV
curl -X POST http://localhost:5001/api/scraping/export \
  -H "Content-Type: application/json" \
  -d '{"formato": "csv"}' -o export.csv
```

> En export, `emails` y `telefonos` son strings separados por coma (no arrays), y `redes_sociales` se aplana a `instagram`, `facebook`.

---

### `POST /api/contact/email`

Envia emails a negocios. Requiere SMTP o SendGrid configurado en `.env`.

**Body JSON:**

| Campo | Tipo | Obligatorio | Default |
|---|---|---|---|
| `deporte` | string | no | `null` |
| `locacion` | string | no | `null` |
| `template` | string | no | `"escuela_inicial"` |
| `max_envios` | int | no | `50` |
| `dry_run` | bool | no | `true` |

Templates: `"escuela_inicial"`, `"retreat_inicial"`, `"followup"`.

**curl:**
```bash
curl -X POST http://localhost:5001/api/contact/email \
  -H "Content-Type: application/json" \
  -d '{"deporte": "surf", "locacion": "Bali", "dry_run": true}'
```

---

## Codigos de error

Formato homogeneo en todos los endpoints:

```json
{"status": "error", "message": "Descripcion del error"}
```

| Codigo | Cuando |
|---|---|
| `400` | Body no es JSON, falta `deporte` o `locacion`, `max_resultados` fuera de rango, `formato` invalido |
| `401` | `API_KEY_ENABLED=true` y falta `X-API-KEY` o es incorrecta |
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

La base de datos se acumula: cada busqueda nueva anade negocios sin borrar los anteriores.

---

## Configuracion (.env)

```bash
DATABASE_URL=sqlite:///data/surf_scraper.db

# Google Custom Search API (opcional — DuckDuckGo funciona sin esto)
GOOGLE_API_KEY=tu_api_key
GOOGLE_SEARCH_ENGINE_ID=tu_search_engine_id

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

# Surf Scraper System

Sistema modular de scraping y contacto automatizado para [Carving Mates](https://www.carvingmates.com) — una app que conecta escuelas de surf, retreats y experiencias deportivas con viajeros de todo el mundo.

## Qué hace

El sistema tiene dos bloques independientes:

### Bloque 1: Recolección de datos
Busca negocios en internet (escuelas de surf, yoga retreats, surf camps, tiendas de alquiler, etc.), visita sus webs y extrae información de contacto. Todo se almacena en una base de datos SQLite.

```
WebScraper → busca negocios en DuckDuckGo / Google API / directorios
EmailScraper → visita cada web y extrae emails (mailto:, footer, /contact)
PhoneScraper → extrae teléfonos y normaliza a formato internacional E.164
SocialScraper → extrae links de Instagram, Facebook, TikTok, YouTube, etc.
TripsScraper → búsqueda especializada de trips y retreats
```

### Bloque 2: Contacto automatizado
Toma los negocios de la base de datos y les envía emails personalizados o mensajes de WhatsApp invitándolos a registrarse en la plataforma.

---

## Instalación

```bash
# Clonar el repositorio
git clone https://github.com/tu-usuario/surf-scraper-system.git
cd surf-scraper-system

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus API keys (ver sección Configuración)

# Inicializar la base de datos
python main.py stats
```

## Uso

### Recolección de datos

```bash
# Búsqueda completa: busca negocios + extrae emails, teléfonos y redes
python main.py buscar surf Bali
python main.py buscar yoga "Costa Rica"
python main.py buscar kitesurf Tarifa

# Filtrar por tipo de negocio
python main.py buscar surf Bali --tipo escuela
python main.py buscar surf Bali --tipo camp

# Buscar solo trips/retreats
python main.py trips yoga Bali
python main.py trips surf Portugal

# Ejecutar pipelines individuales (sobre negocios ya en la DB)
python main.py emails surf Bali        # Solo extraer emails
python main.py telefonos surf Bali     # Solo extraer teléfonos
python main.py redes surf Bali         # Solo extraer redes sociales
```

### Contacto automatizado

```bash
# Simular envío (no envía realmente, muestra qué haría)
python main.py contactar surf Bali --dry

# Enviar emails a negocios pendientes
python main.py contactar surf Bali
python main.py contactar surf Bali --template retreat_inicial

# Follow-up automático (negocios sin respuesta después de 7 días)
python main.py followup
python main.py followup --dry

# WhatsApp (requiere Twilio configurado)
python main.py whatsapp surf Bali --dry
python main.py whatsapp surf Bali

# Marcar respuesta de un negocio
python main.py respuesta <negocio_id> interesado
python main.py respuesta <negocio_id> no_interesado
```

### Utilidades

```bash
# Ver estadísticas de la base de datos
python main.py stats

# Exportar a CSV
python main.py exportar                  # Todos los negocios
python main.py exportar surf Bali        # Filtrado

# Scheduler: ejecución periódica automática
python scheduler.py                      # Inicia cron (ver tareas en scheduler.py)
python scheduler.py --once               # Ejecuta todas las tareas una vez
```

## Configuración (.env)

```bash
# Google Custom Search API (opcional, DuckDuckGo funciona sin esto)
GOOGLE_API_KEY=tu_api_key
GOOGLE_SEARCH_ENGINE_ID=tu_search_engine_id

# Email - opción 1: SMTP (Gmail)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu_email@gmail.com
SMTP_PASSWORD=tu_app_password          # App Password, no la contraseña normal

# Email - opción 2: SendGrid
SENDGRID_API_KEY=tu_sendgrid_key

# WhatsApp (opcional)
TWILIO_ACCOUNT_SID=tu_sid
TWILIO_AUTH_TOKEN=tu_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
```

### Google Custom Search API (opcional)

1. Ir a [Google Cloud Console](https://console.cloud.google.com/)
2. Crear un proyecto (o usar uno existente)
3. Habilitar "Custom Search API" en APIs & Services
4. Crear una API Key en Credentials
5. Ir a [Programmable Search Engine](https://programmablesearchengine.google.com/) y crear un motor de búsqueda
6. Copiar el Search Engine ID

**Sin Google API, el sistema funciona con DuckDuckGo como motor de búsqueda.**

### Gmail App Password

Para enviar emails con Gmail necesitás un App Password:
1. Ir a [Google Account Security](https://myaccount.google.com/security)
2. Habilitar 2-Step Verification
3. Ir a App Passwords → generar una para "Mail"
4. Usar esa contraseña en `SMTP_PASSWORD`

## Estructura del proyecto

```
surf-scraper-system/
├── main.py                          # CLI principal
├── scheduler.py                     # Ejecución periódica (cron)
├── config/
│   ├── settings.py                  # Configuración desde .env
│   └── sources.py                   # Fuentes de scraping, templates de búsqueda
├── database/
│   ├── connection.py                # SQLAlchemy engine + sesiones
│   └── models.py                    # Modelos: Negocio, LogScraping, LogContacto
├── scrapers/
│   ├── base_scraper.py              # Clase base (fetch, retry, rate limiting, dedup)
│   ├── web_scraper.py               # Pipeline 1: búsqueda de negocios
│   ├── email_scraper.py             # Pipeline 2: extracción de emails
│   ├── phone_scraper.py             # Pipeline 3: extracción de teléfonos
│   ├── social_scraper.py            # Pipeline 4: redes sociales
│   └── trips_scraper.py             # Pipeline 5: trips y retreats
├── automation/
│   ├── email_sender.py              # Envío de emails (SMTP / SendGrid)
│   ├── whatsapp_sender.py           # Envío de WhatsApp (Twilio)
│   └── templates/                   # Templates HTML personalizables
│       ├── escuela_inicial.html
│       ├── retreat_inicial.html
│       └── followup.html
├── utils/
│   ├── logger.py                    # Logging a consola + archivo
│   ├── validators.py                # Validación de emails, teléfonos, URLs
│   ├── rate_limiter.py              # Rate limiting por dominio
│   └── helpers.py                   # User-Agent rotation, utilidades
├── tests/                           # 52 tests
├── data/
│   ├── raw/                         # Datos crudos
│   ├── processed/                   # Datos procesados
│   └── exports/                     # CSVs exportados
└── logs/                            # Logs por módulo
```

## Modelo de datos

Cada negocio almacenado tiene:

| Campo | Descripción |
|-------|-------------|
| nombre | Nombre del negocio |
| tipo_negocio | escuela, camp, retreat, trip, alquiler, shop |
| deporte | surf, yoga, kitesurf, snowboard, etc. |
| pais, region, ciudad | Ubicación |
| website | URL del negocio |
| emails | Lista de emails extraídos |
| telefonos | Lista de teléfonos (formato E.164) |
| redes_sociales | Instagram, Facebook, TikTok, YouTube, Twitter, LinkedIn |
| rating, reviews_count | Rating y cantidad de reviews |
| contactado | Si ya fue contactado |
| respuesta | interesado, no_interesado, sin_respuesta |

## Deportes soportados

surf, bodyboard, snowboard, ski, kitesurf, windsurf, wakeboard, paddlesurf, kayak, yoga, skate

Agregar un nuevo deporte no requiere cambiar código — es solo un parámetro:
```bash
python main.py buscar wakeboard "Lake Tahoe"
```

## Tests

```bash
python -m pytest tests/ -v
```

## Personalización

### Agregar templates de email
Copiar un template existente en `automation/templates/` y editarlo. La primera línea debe ser:
```html
<!-- SUBJECT: Tu asunto aquí - {{nombre_negocio}} -->
```
Variables disponibles: `{{nombre_negocio}}`, `{{deporte}}`, `{{tipo_negocio}}`, `{{pais}}`, `{{ciudad}}`, `{{website}}`

### Agregar fuentes de scraping
Editar `config/sources.py` → `DIRECTORIOS` para agregar nuevos directorios especializados.

### Programar búsquedas automáticas
Editar `scheduler.py` → `TAREAS_PROGRAMADAS` para definir qué buscar y con qué frecuencia.

---

Built for [Carving Mates](https://www.carvingmates.com)

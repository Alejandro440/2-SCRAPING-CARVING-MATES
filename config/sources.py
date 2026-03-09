"""
Fuentes de scraping organizadas por tipo.
Cada fuente tiene un nombre, URL base, y los deportes/tipos que soporta.
Facilmente extensible: solo agregar nuevas entradas al diccionario.
"""

# Directorios especializados por deporte
DIRECTORIOS = {
    "surf": [
        {
            "nombre": "BookSurfCamps",
            "url_base": "https://www.booksurfcamps.com",
            "url_busqueda": "https://www.booksurfcamps.com/all/s/{locacion}",
            "tipos": ["escuela", "camp", "retreat"],
        },
        {
            "nombre": "Surfline",
            "url_base": "https://www.surfline.com",
            "url_busqueda": None,
            "tipos": ["escuela"],
        },
    ],
    "yoga": [
        {
            "nombre": "BookYogaRetreats",
            "url_base": "https://www.bookyogaretreats.com",
            "url_busqueda": "https://www.bookyogaretreats.com/all/d/{locacion}",
            "tipos": ["retreat", "camp"],
        },
        {
            "nombre": "BookRetreats",
            "url_base": "https://www.bookretreats.com",
            "url_busqueda": "https://www.bookretreats.com/all/s/{locacion}",
            "tipos": ["retreat"],
        },
    ],
    "kitesurf": [
        {
            "nombre": "BookKitesurfCamps",
            "url_base": "https://www.booksurfcamps.com/kitesurf",
            "url_busqueda": "https://www.booksurfcamps.com/kitesurf/s/{locacion}",
            "tipos": ["escuela", "camp"],
        },
    ],
}

# Sub-localizaciones conocidas para busquedas mas granulares
# Permite buscar por ciudades/regiones/spots ademas de por pais
SUB_LOCACIONES = {
    "portugal": ["Ericeira", "Peniche", "Cascais", "Algarve", "Nazare", "Porto", "Sagres"],
    "spain": ["Cantabria", "Asturias", "Pais Vasco", "Galicia", "Cadiz", "Canarias", "Tenerife", "Fuerteventura", "Lanzarote"],
    "españa": ["Cantabria", "Asturias", "Pais Vasco", "Galicia", "Cadiz", "Canarias", "Tenerife", "Fuerteventura", "Lanzarote"],
    "costa rica": ["Tamarindo", "Santa Teresa", "Nosara", "Jaco", "Dominical", "Pavones"],
    "indonesia": ["Bali", "Lombok", "Mentawai", "Sumatra", "Sumbawa"],
    "bali": ["Canggu", "Kuta", "Seminyak", "Uluwatu", "Sanur", "Medewi"],
    "australia": ["Gold Coast", "Byron Bay", "Sydney", "Torquay", "Margaret River", "Noosa"],
    "france": ["Biarritz", "Hossegor", "Lacanau", "Capbreton", "Anglet"],
    "francia": ["Biarritz", "Hossegor", "Lacanau", "Capbreton", "Anglet"],
    "morocco": ["Taghazout", "Essaouira", "Imsouane", "Tamraght", "Agadir"],
    "marruecos": ["Taghazout", "Essaouira", "Imsouane", "Tamraght", "Agadir"],
    "mexico": ["Puerto Escondido", "Sayulita", "Punta de Mita", "Todos Santos", "Baja California"],
    "méxico": ["Puerto Escondido", "Sayulita", "Punta de Mita", "Todos Santos", "Baja California"],
    "sri lanka": ["Arugam Bay", "Weligama", "Mirissa", "Hikkaduwa", "Ahangama"],
    "south africa": ["Jeffreys Bay", "Muizenberg", "Durban", "Cape Town"],
    "brazil": ["Florianopolis", "Itacare", "Fernando de Noronha", "Ubatuba"],
    "brasil": ["Florianopolis", "Itacare", "Fernando de Noronha", "Ubatuba"],
    "hawaii": ["Oahu", "Maui", "North Shore", "Waikiki"],
    "california": ["San Diego", "Santa Cruz", "Malibu", "Huntington Beach", "San Francisco"],
    "uk": ["Cornwall", "Devon", "Pembrokeshire", "Newquay", "Croyde"],
    "italy": ["Sardinia", "Sicily", "Levanto", "Cagliari"],
    "italia": ["Sardinia", "Sicily", "Levanto", "Cagliari"],
}

# Dominios editoriales que NO son negocios reales
# Usados para filtrar resultados de busqueda
DOMINIOS_EDITORIALES = [
    # Medios de viaje
    "lonelyplanet.com", "tripadvisor.com", "timeout.com",
    "travelandleisure.com", "cntraveler.com", "theculturetrip.com",
    "nomadicmatt.com", "theworldbucketlist.com", "thesmartlocal.com",
    "matadornetwork.com", "roughguides.com", "fodors.com",
    "wanderlust.co.uk", "nationalgeographic.com",
    # Booking / OTAs
    "booking.com", "expedia.com", "hostelworld.com", "hotels.com",
    "airbnb.com", "kayak.com", "skyscanner.com",
    # Surf media / editorial
    "surfline.com", "magicseaweed.com", "surfertoday.com",
    "theinertia.com", "surfersvillage.com", "wannasurf.com",
    "secretseaweed.com", "thesurfatlas.com", "stabmag.com",
    "surfermag.com", "surfer.com", "boardriders.com",
    # Social / plataformas
    "wikipedia.org", "wikivoyage.org", "reddit.com", "quora.com",
    "medium.com", "youtube.com", "facebook.com", "instagram.com",
    "twitter.com", "x.com", "tiktok.com", "linkedin.com",
    "pinterest.com",
    # E-commerce / marketplaces
    "amazon.com", "ebay.com", "etsy.com",
    # Listas / reviews
    "yelp.com", "trustpilot.com", "glassdoor.com",
]

# Patrones en titulo/URL que indican contenido editorial, no negocio
PATRONES_EDITORIAL = [
    "best ", "top ", "guide ", " guide", "ultimate guide",
    "things to do", "bucket list", "where to ",
    "review of", "comparison", "vs ", " vs.",
    "magazine", "blog", "news", "article",
    "how to choose", "tips for", "what to know",
    "travel guide", "complete guide", "insider guide",
]

# Paginas internas donde buscar datos de contacto
CONTACT_PATHS = [
    "/contact",
    "/contacto",
    "/contact-us",
    "/about",
    "/about-us",
    "/sobre-nosotros",
    "/impressum",
    "/kontakt",
    "/book",
    "/booking",
    "/book-now",
    "/reservar",
    "/surf-lessons",
    "/lessons",
    "/courses",
    "/rentals",
    "/camp",
    "/retreat",
    "/faq",
]

# User-Agents rotativos (se complementan con fake-useragent)
FALLBACK_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

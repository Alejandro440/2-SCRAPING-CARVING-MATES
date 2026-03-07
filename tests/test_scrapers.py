"""
Tests para los scrapers.
Valida la lógica de parsing sin hacer requests reales.
Ejecutar con: pytest tests/test_scrapers.py -v
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bs4 import BeautifulSoup
from scrapers.web_scraper import WebScraper
from scrapers.email_scraper import EmailScraper
from scrapers.social_scraper import SocialScraper


# === Tests de WebScraper ===

class TestWebScraper:
    def setup_method(self):
        self.scraper = WebScraper()

    def test_inferir_tipo_escuela(self):
        assert self.scraper._inferir_tipo_negocio("Bali Surf School") == "escuela"
        assert self.scraper._inferir_tipo_negocio("Learn to surf academy") == "escuela"

    def test_inferir_tipo_retreat(self):
        assert self.scraper._inferir_tipo_negocio("Yoga Retreat Bali") == "retreat"

    def test_inferir_tipo_camp(self):
        assert self.scraper._inferir_tipo_negocio("Surf Camp Portugal") == "camp"

    def test_inferir_tipo_trip(self):
        assert self.scraper._inferir_tipo_negocio("Adventure Trip Costa Rica") == "trip"

    def test_inferir_tipo_alquiler(self):
        assert self.scraper._inferir_tipo_negocio("Board Rental Shop") == "alquiler"

    def test_inferir_tipo_default(self):
        assert self.scraper._inferir_tipo_negocio("Random Business Name") == "escuela"

    def test_extraer_locacion_snippet(self):
        resultado = self.scraper._extraer_locacion_snippet(
            "Best surf lessons in Canggu, Indonesia with professional instructors"
        )
        assert resultado is not None
        assert resultado["ciudad"] == "Canggu"
        assert resultado["pais"] == "Indonesia"

    def test_extraer_locacion_snippet_sin_match(self):
        resultado = self.scraper._extraer_locacion_snippet("No location info here")
        assert resultado is None

    def test_parsear_booksurfcamps(self):
        html = """
        <div class="camp-card">
            <h3 class="title">Epic Surf Camp</h3>
            <a href="/surf-camp/epic-bali">Link</a>
            <span class="location">Canggu, Indonesia</span>
            <span class="price">USD 450</span>
            <span class="rating">4.8</span>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        resultados = self.scraper._parsear_booksurfcamps(soup, "surf", "booksurfcamps")
        assert len(resultados) == 1
        assert resultados[0]["nombre"] == "Epic Surf Camp"
        assert resultados[0]["ciudad"] == "Canggu"
        assert resultados[0]["pais"] == "Indonesia"

    def test_parsear_generico(self):
        html = """
        <article>
            <h3 class="title">Beach Surf School</h3>
            <a href="https://beachsurf.com">Visit</a>
            <p class="description">Professional surf lessons on the beach</p>
        </article>
        <article>
            <h3 class="title">Wave Riders Academy</h3>
            <a href="https://waveriders.com">Visit</a>
            <p class="description">Learn to surf with us</p>
        </article>
        <article>
            <h3 class="title">Ocean Surf Camp</h3>
            <a href="https://oceancamp.com">Visit</a>
            <p class="description">Surf and yoga retreat</p>
        </article>
        """
        soup = BeautifulSoup(html, "lxml")
        resultados = self.scraper._parsear_generico(soup, "surf", "test_source")
        assert len(resultados) == 3
        assert resultados[0]["nombre"] == "Beach Surf School"


# === Tests de EmailScraper ===

class TestEmailScraper:
    def setup_method(self):
        self.scraper = EmailScraper()

    def test_extraer_emails_de_html_mailto(self):
        html = """
        <html><body>
            <a href="mailto:info@surfschool.com">Contact us</a>
            <a href="mailto:bookings@surfschool.com?subject=Inquiry">Book</a>
            <p>Or email us at hello@surfschool.com</p>
        </body></html>
        """
        # Simular response
        mock_response = MagicMock()
        mock_response.text = html

        with patch.object(self.scraper, 'fetch', return_value=mock_response):
            emails = self.scraper._extraer_emails_de_url("https://surfschool.com")

        assert "info@surfschool.com" in emails
        assert "bookings@surfschool.com" in emails
        assert "hello@surfschool.com" in emails

    def test_extraer_emails_de_footer(self):
        html = """
        <html><body>
            <main><p>Welcome to our school</p></main>
            <footer>
                <p>Contact: reservas@escuela.com | Tel: +34 612 345 678</p>
            </footer>
        </body></html>
        """
        mock_response = MagicMock()
        mock_response.text = html

        with patch.object(self.scraper, 'fetch', return_value=mock_response):
            emails = self.scraper._extraer_emails_de_url("https://escuela.com")

        assert "reservas@escuela.com" in emails


# === Tests de SocialScraper ===

class TestSocialScraper:
    def setup_method(self):
        self.scraper = SocialScraper()

    def test_extraer_redes_de_html(self):
        html = """
        <html><body>
            <a href="https://www.instagram.com/surfschool">Instagram</a>
            <a href="https://www.facebook.com/surfschool">Facebook</a>
            <a href="https://tiktok.com/@surfschool">TikTok</a>
            <a href="https://www.youtube.com/@surfschool">YouTube</a>
            <a href="https://x.com/surfschool">Twitter</a>
        </body></html>
        """
        mock_response = MagicMock()
        mock_response.text = html

        with patch.object(self.scraper, 'fetch', return_value=mock_response):
            redes = self.scraper._extraer_redes_de_web("https://surfschool.com")

        assert "instagram.com/surfschool" in redes["instagram"]
        assert "facebook.com/surfschool" in redes["facebook"]
        assert "tiktok.com/@surfschool" in redes["tiktok"]
        assert "youtube.com/@surfschool" in redes["youtube"]
        assert redes["twitter"] is not None

    def test_filtrar_share_buttons(self):
        html = """
        <html><body>
            <a href="https://www.facebook.com/sharer/sharer.php?u=example">Share</a>
            <a href="https://twitter.com/intent/tweet?text=hello">Tweet</a>
            <a href="https://www.instagram.com/mysurfcamp">Follow us</a>
        </body></html>
        """
        mock_response = MagicMock()
        mock_response.text = html

        with patch.object(self.scraper, 'fetch', return_value=mock_response):
            redes = self.scraper._extraer_redes_de_web("https://surfschool.com")

        # Share buttons deben ser filtrados
        assert redes["facebook"] is None
        assert redes["twitter"] is None
        # Perfil real debe ser detectado
        assert redes["instagram"] is not None

    def test_extraer_username_ig(self):
        assert self.scraper._extraer_username_ig("https://instagram.com/surfschool") == "surfschool"
        assert self.scraper._extraer_username_ig("https://instagram.com/p/ABC123") == "p"

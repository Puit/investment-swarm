import requests
from bs4 import BeautifulSoup
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
from datetime import datetime, timezone
import yfinance as yf


class NewsInput(BaseModel):
    ticker: str = Field(description="Símbolo del ticker para buscar noticias")


class NewsScraperTool(BaseTool):
    name: str = "news_scraper"
    description: str = (
        "Obtiene titulares de noticias recientes (últimas 72h) sobre una empresa. "
        "Llama esta herramienta PRIMERO antes de generar cualquier análisis de sentimiento."
    )
    args_schema: Type[BaseModel] = NewsInput

    def _run(self, ticker: str) -> str:
        # Fuente 1: yfinance news API (fiable, sin scraping)
        result = self._yfinance_news(ticker)
        if result:
            return result

        # Fuente 2: Finviz scraping (fallback)
        result = self._finviz_news(ticker)
        if result:
            return result

        return f"Sin noticias disponibles para {ticker} en este momento."

    def _yfinance_news(self, ticker: str) -> str:
        try:
            stock = yf.Ticker(ticker)
            news = stock.news
            if not news:
                return ""

            lines = []
            now = datetime.now(timezone.utc)
            for item in news[:8]:
                title = item.get("title", "")
                publisher = item.get("publisher", "")
                ts = item.get("providerPublishTime")
                if not title:
                    continue

                if ts:
                    pub_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                    hours_ago = (now - pub_dt).total_seconds() / 3600
                    time_str = (
                        f"hace {int(hours_ago)}h"
                        if hours_ago < 48
                        else pub_dt.strftime("%Y-%m-%d")
                    )
                else:
                    time_str = "reciente"

                lines.append(f"[{time_str}] ({publisher}) {title}")

            return "\n".join(lines) if lines else ""
        except Exception:
            return ""

    def _finviz_news(self, ticker: str) -> str:
        try:
            url = f"https://finviz.com/quote.ashx?t={ticker}"
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            news_table = soup.find(id="news-table")
            if not news_table:
                return ""

            lines = []
            for row in news_table.findAll("tr")[:6]:
                try:
                    cols = row.findAll("td")
                    if len(cols) >= 2:
                        fecha = cols[0].text.strip()
                        titulo = cols[1].a.text.strip() if cols[1].a else ""
                        if titulo:
                            lines.append(f"[{fecha}] {titulo}")
                except Exception:
                    continue

            return "\n".join(lines) if lines else ""
        except Exception:
            return ""

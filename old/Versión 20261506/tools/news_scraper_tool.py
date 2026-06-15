import requests
from bs4 import BeautifulSoup
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
import time

class NewsInput(BaseModel):
    ticker: str = Field(description="Símbolo del ticker para buscar noticias")

class NewsScraperTool(BaseTool):
    name: str = "news_scraper"
    description: str = "Obtiene titulares de noticias recientes sobre una empresa"
    args_schema: Type[BaseModel] = NewsInput

    def _run(self, ticker: str) -> str:
        try:
            url = f"https://finviz.com/quote.ashx?t={ticker}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            news_table = soup.find(id="news-table")
            if not news_table:
                return f"Sin noticias disponibles para {ticker}"

            noticias = []
            for row in news_table.findAll("tr")[:5]:
                try:
                    cols = row.findAll("td")
                    if len(cols) >= 2:
                        fecha = cols[0].text.strip()
                        titulo = cols[1].a.text.strip() if cols[1].a else ""
                        if titulo:
                            noticias.append(f"[{fecha}] {titulo}")
                except:
                    continue

            return "\n".join(noticias) if noticias else f"Sin noticias recientes para {ticker}"
        except requests.Timeout:
            return f"Timeout obteniendo noticias de {ticker}. Reintentando..."
        except Exception as e:
            return f"Noticias no disponibles para {ticker}: {str(e)}"
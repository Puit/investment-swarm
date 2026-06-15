import yfinance as yf
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
import json

class YFinanceInput(BaseModel):
    ticker: str = Field(description="Símbolo del ticker, ej: AAPL")

class YFinanceTool(BaseTool):
    name: str = "financial_data"
    description: str = "Obtiene datos financieros fundamentales y técnicos de un ticker"
    args_schema: Type[BaseModel] = YFinanceInput

    def _run(self, ticker: str) -> str:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            hist = stock.history(period="3mo")

            # Datos fundamentales
            fundamental = {
                "ticker": ticker,
                "nombre": info.get("longName", "N/A"),
                "sector": info.get("sector", "N/A"),
                "precio_actual": info.get("currentPrice", "N/A"),
                "pe_ratio": info.get("trailingPE", "N/A"),
                "forward_pe": info.get("forwardPE", "N/A"),
                "eps": info.get("trailingEps", "N/A"),
                "revenue_growth": info.get("revenueGrowth", "N/A"),
                "profit_margins": info.get("profitMargins", "N/A"),
                "debt_to_equity": info.get("debtToEquity", "N/A"),
                "roe": info.get("returnOnEquity", "N/A"),
                "market_cap": info.get("marketCap", "N/A"),
                "52w_high": info.get("fiftyTwoWeekHigh", "N/A"),
                "52w_low": info.get("fiftyTwoWeekLow", "N/A"),
                "analyst_target": info.get("targetMeanPrice", "N/A"),
                "recommendation": info.get("recommendationKey", "N/A"),
            }

            # Datos técnicos básicos desde histórico
            if not hist.empty:
                closes = hist["Close"]
                sma20 = closes.rolling(20).mean().iloc[-1]
                sma50 = closes.rolling(50).mean().iloc[-1]
                precio = closes.iloc[-1]
                max_3m = closes.max()
                min_3m = closes.min()

                # RSI simplificado
                delta = closes.diff()
                gain = delta.clip(lower=0).rolling(14).mean()
                loss = (-delta.clip(upper=0)).rolling(14).mean()
                rs = gain / loss
                rsi = (100 - (100 / (1 + rs))).iloc[-1]

                tecnico = {
                    "precio": round(float(precio), 2),
                    "sma20": round(float(sma20), 2),
                    "sma50": round(float(sma50), 2),
                    "rsi_14": round(float(rsi), 2),
                    "max_3m": round(float(max_3m), 2),
                    "min_3m": round(float(min_3m), 2),
                    "tendencia": "alcista" if precio > sma20 > sma50 else "bajista" if precio < sma20 < sma50 else "lateral",
                }
                fundamental["tecnico"] = tecnico

            return json.dumps(fundamental, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"Error obteniendo datos de {ticker}: {str(e)}"
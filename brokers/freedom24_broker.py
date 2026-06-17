"""
FREEDOM24 BROKER - Live Trading Connector
==========================================

Integración con API de Freedom24 para trading en vivo.
"""

import os
import logging
from typing import Optional, Dict, List
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Freedom24Broker:
    """Conector para Freedom24 - Trading en vivo"""

    def __init__(self):
        """Inicializa conexión con Freedom24"""
        self.api_key = os.getenv("FREEDOM24_API_KEY")
        self.api_secret = os.getenv("FREEDOM24_API_SECRET")
        self.account_id = os.getenv("FREEDOM24_ACCOUNT_ID")
        self.base_url = os.getenv("FREEDOM24_BASE_URL", "https://api.freedom24.com/api/v1")

        self.connected = False
        self.session = None

        logger.info("Freedom24Broker inicializado")

    def connect(self) -> bool:
        """Conecta con Freedom24"""
        try:
            if not all([self.api_key, self.api_secret, self.account_id]):
                logger.warning("Credenciales de Freedom24 no configuradas")
                return False

            self.session = requests.Session()
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            })

            # Verificar conexión
            response = self.session.get(f"{self.base_url}/accounts/{self.account_id}")

            if response.status_code == 200:
                self.connected = True
                logger.info("✓ Conectado a Freedom24")
                return True
            else:
                logger.error(f"Error conectando a Freedom24: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error en conexión Freedom24: {e}")
            return False

    def disconnect(self) -> None:
        """Desconecta de Freedom24"""
        if self.session:
            self.session.close()
        self.connected = False
        logger.info("Desconectado de Freedom24")

    def get_portfolio_summary(self) -> Dict:
        """Obtiene resumen de cartera"""
        try:
            if not self.connected:
                return {
                    "cash": 0.0,
                    "positions_value": 0.0,
                    "total_value": 0.0,
                    "initial_capital": 0.0,
                    "return_pct": 0.0,
                    "positions": [],
                    "error": "No conectado"
                }

            # Obtener saldo de cuenta
            response = self.session.get(f"{self.base_url}/accounts/{self.account_id}/balance")

            if response.status_code != 200:
                logger.error(f"Error obteniendo balance: {response.status_code}")
                return {"cash": 0.0, "total_value": 0.0, "positions": [], "error": "API Error"}

            account_data = response.json()
            cash = float(account_data.get("cash", 0.0))
            total_value = float(account_data.get("equity", cash))

            # Obtener posiciones
            positions = self._get_positions()

            positions_value = sum([p.get("value", 0) for p in positions])

            return {
                "cash": cash,
                "positions_value": positions_value,
                "total_value": total_value,
                "initial_capital": total_value,
                "return_pct": 0.0,
                "positions": positions,
                "connected": True
            }

        except Exception as e:
            logger.error(f"Error en portfolio summary: {e}")
            return {"cash": 0.0, "total_value": 0.0, "positions": [], "error": str(e)}

    def _get_positions(self) -> List[Dict]:
        """Obtiene posiciones abiertas"""
        try:
            response = self.session.get(f"{self.base_url}/accounts/{self.account_id}/positions")

            if response.status_code != 200:
                return []

            positions_data = response.json()
            positions = []

            for pos in positions_data.get("positions", []):
                positions.append({
                    "ticker": pos.get("symbol"),
                    "qty": float(pos.get("quantity", 0)),
                    "entry_price": float(pos.get("avg_price", 0)),
                    "current_price": float(pos.get("current_price", 0)),
                    "value": float(pos.get("market_value", 0)),
                    "pnl": float(pos.get("unrealized_pnl", 0)),
                    "pnl_pct": float(pos.get("unrealized_pnl_percent", 0))
                })

            return positions

        except Exception as e:
            logger.error(f"Error obteniendo posiciones: {e}")
            return []

    def buy(self, ticker: str, quantity: int, order_type: str = "MARKET") -> Optional[Dict]:
        """Compra acciones"""
        try:
            if not self.connected:
                logger.error("No conectado a Freedom24")
                return None

            payload = {
                "symbol": ticker,
                "quantity": quantity,
                "type": order_type,
                "side": "BUY"
            }

            response = self.session.post(
                f"{self.base_url}/accounts/{self.account_id}/orders",
                json=payload
            )

            if response.status_code in [200, 201]:
                order_data = response.json()
                logger.info(f"✓ Orden de compra: {ticker} x{quantity}")
                return {
                    "order_id": order_data.get("order_id"),
                    "ticker": ticker,
                    "qty": quantity,
                    "status": "FILLED"
                }
            else:
                logger.error(f"Error en orden: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error en compra: {e}")
            return None

    def sell(self, ticker: str, quantity: int, order_type: str = "MARKET") -> Optional[Dict]:
        """Vende acciones"""
        try:
            if not self.connected:
                logger.error("No conectado a Freedom24")
                return None

            payload = {
                "symbol": ticker,
                "quantity": quantity,
                "type": order_type,
                "side": "SELL"
            }

            response = self.session.post(
                f"{self.base_url}/accounts/{self.account_id}/orders",
                json=payload
            )

            if response.status_code in [200, 201]:
                order_data = response.json()
                logger.info(f"✓ Orden de venta: {ticker} x{quantity}")
                return {
                    "order_id": order_data.get("order_id"),
                    "ticker": ticker,
                    "qty": quantity,
                    "status": "FILLED"
                }
            else:
                logger.error(f"Error en orden: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error en venta: {e}")
            return None

    def get_current_price(self, ticker: str) -> Optional[float]:
        """Obtiene precio actual de una acción"""
        try:
            response = self.session.get(f"{self.base_url}/quotes/{ticker}")

            if response.status_code == 200:
                data = response.json()
                return float(data.get("price", 0))
            return None

        except Exception as e:
            logger.error(f"Error obteniendo precio de {ticker}: {e}")
            return None

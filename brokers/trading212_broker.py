"""
TRADING 212 BROKER
==================
Integración con la API v0 de Trading 212.

Cómo obtener las credenciales en T212:
  Settings → API (beta) → Create key
  → Te da dos valores:
      · ID de clave API  = un identificador visual (solo para referencia en el panel)
      · Clave secreta    = el token real que va en el header Authorization

  ¡La clave secreta solo se muestra UNA VEZ al crearla. Guárdala en el .env!

Variables de entorno (.env):
  T212_API_KEY_ID_PAPER_TRADING  — ID visible en el panel (cuenta demo)
  T212_API_SECRET_PAPER_TRADING  — Token de autenticación (cuenta demo)
  T212_API_KEY_ID_LIVE_TRADING   — ID visible en el panel (cuenta real)
  T212_API_SECRET_LIVE_TRADING   — Token de autenticación (cuenta real)

Pasar account_type="paper" carga las credenciales PAPER_TRADING y usa la URL demo.
Pasar account_type="live"  carga las credenciales LIVE_TRADING  y usa la URL live.
"""

import os
import base64
import logging
import time
from typing import Optional, Dict, List
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class Trading212Broker:
    """Conector para Trading 212 (demo/paper y live)."""

    _BASE_LIVE = "https://live.trading212.com/api/v0"
    _BASE_DEMO = "https://demo.trading212.com/api/v0"

    def __init__(
        self,
        account_type: str = "paper",
        max_buy_amount: Optional[float] = None,
    ):
        """
        Args:
            account_type:   "paper" → cuenta demo T212  |  "live" → cuenta real T212
            max_buy_amount: Importe máximo por orden de compra (None = sin límite).
        """
        self.mode = account_type.lower()

        if self.mode == "live":
            self.api_secret = (
                os.getenv("T212_API_SECRET_LIVE_TRADING")
                or os.getenv("T212_API_SECRET", "")
            )
            self.api_key_id = (
                os.getenv("T212_API_KEY_ID_LIVE_TRADING")
                or os.getenv("T212_API_KEY_ID", "")
            )
            self.base_url = self._BASE_LIVE
        else:
            # "paper" (demo/practice) — T212 Invest usa live.trading212.com
            # para AMBOS tipos de cuenta (práctica y real).
            # La diferencia la gestiona T212 internamente según la API key.
            self.api_secret = (
                os.getenv("T212_API_SECRET_PAPER_TRADING")
                or os.getenv("T212_API_SECRET", "")
            )
            self.api_key_id = (
                os.getenv("T212_API_KEY_ID_PAPER_TRADING")
                or os.getenv("T212_API_KEY_ID", "")
            )
            # T212 Invest: cuenta práctica → demo.trading212.com
            self.base_url = self._BASE_DEMO
            self.mode     = "paper"

        self.max_buy_amount = max_buy_amount

        self.connected  = False
        self.session: Optional[requests.Session] = None

        # Caché de instrumentos: symbol → t212_ticker (ej. "AAPL" → "AAPL_US_EQ")
        self._instruments: Dict[str, str] = {}
        self._instruments_loaded = False

    def _build_auth_header(self) -> str:
        """
        T212 usa HTTP Basic Auth: Authorization: Basic base64(key_id:secret)
        """
        token = base64.b64encode(
            f"{self.api_key_id}:{self.api_secret}".encode()
        ).decode()
        return f"Basic {token}"

    @property
    def api_key(self) -> str:
        """Alias de compatibilidad — devuelve el secret."""
        return self.api_secret

    # ── Conexión ──────────────────────────────────────────────

    def connect(self) -> bool:
        """Valida la clave secreta y precarga el catálogo de instrumentos."""
        if not self.api_secret:
            logger.warning("T212_API_SECRET no configurada en el .env")
            return False

        self.session = requests.Session()
        self.session.headers.update({
            # T212 usa HTTP Basic Auth: Basic base64(key_id:secret)
            "Authorization": self._build_auth_header(),
            "Content-Type":  "application/json",
        })
        logger.info(f"T212 auth: Basic base64({self.api_key_id[:8]}...:<secret>)")

        try:
            r = self.session.get(f"{self.base_url}/equity/account/info", timeout=10)
            if r.status_code == 200:
                self.connected = True
                logger.info(f"✓ Trading 212 conectado ({self.mode})")
                self._load_instruments()
                return True
            else:
                logger.error(f"T212 auth error: {r.status_code} — {r.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"Error conectando T212: {e}")
            return False

    def disconnect(self) -> None:
        if self.session:
            self.session.close()
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected

    # ── Catálogo de instrumentos ──────────────────────────────

    def _load_instruments(self) -> None:
        """Descarga el catálogo completo de T212 y construye symbol→ticker map."""
        if self._instruments_loaded:
            return
        try:
            r = self.session.get(
                f"{self.base_url}/equity/metadata/instruments", timeout=30
            )
            if r.status_code != 200:
                logger.warning(f"No se pudo cargar catálogo T212: {r.status_code}")
                return

            for inst in r.json():
                # "ticker" es el ID de T212 (ej. AAPL_US_EQ)
                # "shortName" o el tramo antes de "_" suele ser el símbolo bursátil
                t212_ticker = inst.get("ticker", "")
                symbol = inst.get("shortName", "").upper()
                if not symbol:
                    # Fallback: primer segmento del ticker T212
                    symbol = t212_ticker.split("_")[0].upper()
                # Guardamos el primero que aparece (evita colisiones multi-mercado)
                if symbol and symbol not in self._instruments:
                    self._instruments[symbol] = t212_ticker

            self._instruments_loaded = True
            logger.info(f"✓ Catálogo T212 cargado: {len(self._instruments)} instrumentos")
        except Exception as e:
            logger.error(f"Error cargando catálogo T212: {e}")

    def resolve_ticker(self, symbol: str) -> Optional[str]:
        """Convierte un símbolo estándar (AAPL) al ticker de T212 (AAPL_US_EQ)."""
        if not self._instruments_loaded:
            self._load_instruments()
        return self._instruments.get(symbol.upper())

    def search_ticker(self, symbol: str) -> List[Dict]:
        """Devuelve coincidencias del catálogo para un símbolo parcial."""
        sym = symbol.upper()
        return [
            {"symbol": s, "t212_ticker": t}
            for s, t in self._instruments.items()
            if sym in s
        ][:10]

    # ── Cuenta ────────────────────────────────────────────────

    def get_cash(self) -> Dict:
        """
        Devuelve el estado de la cuenta en efectivo.
        Campos clave: free (disponible para operar), total, invested, ppl (P&L no realizado).
        """
        try:
            r = self._get("/equity/account/cash")
            return r or {}
        except Exception as e:
            logger.error(f"T212 get_cash error: {e}")
            return {}

    def get_account_info(self) -> Dict:
        """Información de la cuenta (currencyCode, id, etc.)."""
        try:
            return self._get("/equity/account/info") or {}
        except Exception as e:
            logger.error(f"T212 get_account_info error: {e}")
            return {}

    def get_portfolio_summary(self) -> Dict:
        """
        Resumen de cartera en el mismo formato que PaperTradingEngine,
        para que el dashboard pueda usarlo de forma uniforme.
        """
        try:
            cash_data = self.get_cash()
            positions = self.get_positions()

            free        = float(cash_data.get("free",     0.0))
            invested    = float(cash_data.get("invested", 0.0))
            total       = float(cash_data.get("total",    free + invested))
            ppl         = float(cash_data.get("ppl",      0.0))

            mode_label = "paper/demo" if self.mode == "paper" else "live"
            return {
                "cash":             free,
                "positions_value":  invested,
                "total_value":      total,
                "unrealized_pnl":   ppl,
                "return_pct":       (ppl / (total - ppl) * 100) if (total - ppl) > 0 else 0.0,
                "positions":        positions,
                "connected":        True,
                "mode":             mode_label,
            }
        except Exception as e:
            logger.error(f"T212 portfolio_summary error: {e}")
            return {
                "cash": 0.0, "positions_value": 0.0, "total_value": 0.0,
                "positions": [], "connected": False, "error": str(e),
            }

    # ── Posiciones ────────────────────────────────────────────

    def get_positions(self) -> List[Dict]:
        """
        Devuelve las posiciones abiertas normalizadas al formato del dashboard.
        """
        try:
            data = self._get("/equity/account/portfolio")
            if not data:
                return []

            positions = []
            for pos in data:
                t212_ticker = pos.get("ticker", "")
                # Recuperar símbolo limpio desde la caché inversa
                symbol = self._t212_to_symbol(t212_ticker) or t212_ticker

                qty          = float(pos.get("quantity",         0))
                avg_price    = float(pos.get("averagePrice",     0))
                current_price = float(pos.get("currentPrice",   0))
                ppl          = float(pos.get("ppl",              0))
                cost         = qty * avg_price
                pnl_pct      = (ppl / cost * 100) if cost > 0 else 0.0

                positions.append({
                    "ticker":        symbol,
                    "t212_ticker":   t212_ticker,
                    "qty":           qty,
                    "entry_price":   avg_price,
                    "current_price": current_price,
                    "value":         qty * current_price,
                    "pnl":           ppl,
                    "pnl_pct":       pnl_pct,
                })
            return positions
        except Exception as e:
            logger.error(f"T212 get_positions error: {e}")
            return []

    def _t212_to_symbol(self, t212_ticker: str) -> Optional[str]:
        """Búsqueda inversa: AAPL_US_EQ → AAPL."""
        for sym, t in self._instruments.items():
            if t == t212_ticker:
                return sym
        return None

    # ── Órdenes ───────────────────────────────────────────────

    def buy(
        self,
        symbol: str,
        quantity: float,
        max_amount: Optional[float] = None,
    ) -> Dict:
        """
        Lanza una orden de mercado de compra.

        Args:
            symbol:     Símbolo estándar (AAPL, MSFT…)
            quantity:   Número de acciones (puede ser fraccionario en T212)
            max_amount: Límite de importe para esta orden específica.
                        Si no se pasa usa self.max_buy_amount. None = sin límite.

        Returns:
            {"success": bool, "order_id": str|None, "message": str, ...}
        """
        return self._place_order(symbol, quantity, "BUY", max_amount)

    def sell(self, symbol: str, quantity: float) -> Dict:
        """Lanza una orden de mercado de venta."""
        return self._place_order(symbol, quantity, "SELL")

    def _place_order(
        self,
        symbol: str,
        quantity: float,
        side: str,
        max_amount: Optional[float] = None,
    ) -> Dict:
        if not self.connected:
            return {"success": False, "message": "No conectado a Trading 212"}

        t212_ticker = self.resolve_ticker(symbol)
        if not t212_ticker:
            return {
                "success": False,
                "message": f"Instrumento '{symbol}' no encontrado en T212. "
                           f"Usa search_ticker() para verificar el símbolo.",
            }

        # Límite de importe (si aplica)
        limit = max_amount or self.max_buy_amount
        if side == "BUY" and limit is not None:
            cash_data = self.get_cash()
            free = float(cash_data.get("free", 0))
            if free < limit:
                limit = free  # No gastar más de lo disponible
            # Ajustar cantidad si supera el límite
            price = self._estimate_price(t212_ticker)
            if price and price > 0:
                max_qty = limit / price
                if quantity > max_qty:
                    quantity = round(max_qty, 4)
                    logger.info(f"Cantidad ajustada a {quantity} por límite ${limit:.2f}")

        payload = {
            "ticker":       t212_ticker,
            "quantity":     quantity,
            "timeValidity": "DAY",
        }

        try:
            r = self.session.post(
                f"{self.base_url}/equity/orders/market",
                json=payload,
                timeout=15,
            )

            if r.status_code in (200, 201):
                data = r.json()
                order_id = data.get("id") or data.get("orderId")
                logger.info(f"✓ T212 {side}: {quantity} {symbol} ({t212_ticker}) → order {order_id}")
                return {
                    "success":     True,
                    "order_id":    str(order_id),
                    "ticker":      symbol,
                    "t212_ticker": t212_ticker,
                    "quantity":    quantity,
                    "side":        side,
                    "status":      data.get("status", "SUBMITTED"),
                    "message":     f"✅ Orden {side} enviada: {quantity} {symbol}",
                }
            else:
                msg = r.json().get("message", r.text[:300]) if r.content else r.text
                logger.error(f"T212 order error {r.status_code}: {msg}")
                return {"success": False, "message": f"T212 error {r.status_code}: {msg}"}

        except Exception as e:
            logger.error(f"T212 _place_order exception: {e}")
            return {"success": False, "message": str(e)}

    def _estimate_price(self, t212_ticker: str) -> Optional[float]:
        """Intenta obtener el precio de mercado actual del instrumento."""
        try:
            positions = self._get("/equity/account/portfolio") or []
            for p in positions:
                if p.get("ticker") == t212_ticker:
                    return float(p.get("currentPrice", 0))
        except Exception:
            pass
        return None

    # ── Historial de órdenes ──────────────────────────────────

    def get_order_history(self, limit: int = 50) -> List[Dict]:
        """Devuelve el historial de órdenes ejecutadas."""
        try:
            r = self.session.get(
                f"{self.base_url}/equity/history/orders",
                params={"limit": limit},
                timeout=15,
            )
            if r.status_code == 200:
                items = r.json().get("items", r.json() if isinstance(r.json(), list) else [])
                return items
            return []
        except Exception as e:
            logger.error(f"T212 order_history error: {e}")
            return []

    def get_open_orders(self) -> List[Dict]:
        """Devuelve las órdenes abiertas/pendientes."""
        try:
            return self._get("/equity/orders") or []
        except Exception as e:
            logger.error(f"T212 open_orders error: {e}")
            return []

    def cancel_order(self, order_id: str) -> bool:
        """Cancela una orden abierta."""
        try:
            r = self.session.delete(
                f"{self.base_url}/equity/orders/{order_id}", timeout=10
            )
            return r.status_code in (200, 204)
        except Exception as e:
            logger.error(f"T212 cancel_order error: {e}")
            return False

    # ── Utilidades internas ───────────────────────────────────

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Optional[any]:
        """GET con manejo básico de errores y rate-limit."""
        try:
            r = self.session.get(
                f"{self.base_url}{endpoint}", params=params, timeout=15
            )
            if r.status_code == 429:
                retry = int(r.headers.get("Retry-After", 5))
                logger.warning(f"T212 rate-limit, esperando {retry}s")
                time.sleep(retry)
                r = self.session.get(
                    f"{self.base_url}{endpoint}", params=params, timeout=15
                )
            if r.status_code == 200:
                return r.json()
            logger.error(f"T212 GET {endpoint}: {r.status_code}")
            return None
        except Exception as e:
            logger.error(f"T212 GET {endpoint} exception: {e}")
            return None

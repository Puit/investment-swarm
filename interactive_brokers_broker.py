"""
INTERACTIVE BROKERS BROKER
==========================

Adaptador para conectar con Interactive Brokers (cuenta real).
Replica la interfaz de PaperTradingEngine pero con conexión a IB Gateway.

Requisitos:
- TWS (Trader Workstation) o IB Gateway corriendo
- Puerto 4002 (IB Gateway) o 7497 (TWS)
- Credenciales IB configuradas

Uso:
    broker = InteractiveBrokersBroker(
        host="127.0.0.1",
        port=4002,
        client_id=1
    )
    broker.connect()
    broker.place_order(ticker="MSFT", action="BUY", quantity=10)
    
Documentación:
    https://ib-insync.readthedocs.io/
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import json

import ib_insync
from ib_insync import IB, Stock, MarketOrder, LimitOrder

logger = logging.getLogger(__name__)

# Estados de orden
ORDER_STATUS_SUBMITTED = "Submitted"
ORDER_STATUS_FILLED = "Filled"
ORDER_STATUS_CANCELLED = "Cancelled"


class InteractiveBrokersBroker:
    """
    Broker para Interactive Brokers con dinero real.
    
    Interfaz compatible con PaperTradingEngine pero conectando a IB.
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4002,
        client_id: int = 1,
        state_file: str = "data/live_trading_state.json"
    ):
        """
        Inicializa el broker de IB.
        
        Args:
            host: Host de IB Gateway (default: localhost)
            port: Puerto de IB Gateway (default: 4002)
            client_id: Client ID para IB (debe ser único)
            state_file: Archivo para guardar estado local
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.state_file = Path(state_file)
        
        self.ib = IB()
        self.connected = False
        
        # Estado local (para compatibilidad)
        self.state = {
            "cash": 0.0,
            "positions": {},
            "watchlist": [],
            "trade_history": [],
            "last_sync": None,
        }
        
        # Cargar estado si existe
        self.load_state()
        
        logger.info(f"InteractiveBrokersBroker inicializado para {host}:{port}")
    
    def connect(self) -> bool:
        """Conecta con IB Gateway."""
        try:
            logger.info(f"Conectando a {self.host}:{self.port}...")
            self.ib.connect(
                host=self.host,
                port=self.port,
                clientId=self.client_id
            )
            self.connected = True
            logger.info("✓ Conectado a Interactive Brokers")
            
            # Obtener datos iniciales
            self._sync_account_data()
            return True
            
        except Exception as e:
            logger.error(f"Error conectando a IB: {e}")
            self.connected = False
            return False
    
    def disconnect(self) -> None:
        """Desconecta de IB Gateway."""
        if self.connected:
            self.ib.disconnect()
            self.connected = False
            logger.info("Desconectado de Interactive Brokers")
    
    def _sync_account_data(self) -> None:
        """Sincroniza datos de la cuenta con IB."""
        try:
            # Obtener cuenta
            account = self.ib.managedAccounts()[0]
            
            # Obtener valores
            account_values = self.ib.accountValues(account=account)
            
            # Cash disponible
            for av in account_values:
                if av.tag == "AvailableFunds" and av.currency == "USD":
                    self.state["cash"] = float(av.value)
                    break
            
            # Posiciones abiertas
            portfolio = self.ib.portfolio(account=account)
            self.state["positions"] = {}
            
            for position in portfolio:
                ticker = position.contract.symbol
                qty = position.position
                market_price = position.marketPrice
                
                if ticker not in self.state["positions"]:
                    self.state["positions"][ticker] = []
                
                self.state["positions"][ticker].append({
                    "qty": qty,
                    "current_price": market_price,
                    "market_value": qty * market_price,
                })
            
            self.state["last_sync"] = datetime.now().isoformat()
            logger.info(f"✓ Datos sincronizados. Cash: ${self.state['cash']:.2f}")
            
        except Exception as e:
            logger.error(f"Error sincronizando datos: {e}")
    
    def place_order(
        self,
        ticker: str,
        action: str,
        quantity: int,
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Coloca una orden en Interactive Brokers.
        
        Args:
            ticker: Símbolo del ticker
            action: "BUY" o "SELL"
            quantity: Cantidad de acciones
            order_type: "MARKET" o "LIMIT"
            limit_price: Precio límite (si order_type="LIMIT")
        
        Returns:
            Dict con resultado de la orden
        """
        if not self.connected:
            return {
                "success": False,
                "message": "No conectado a Interactive Brokers"
            }
        
        try:
            # Crear contrato
            contract = Stock(ticker, "SMART", "USD")
            
            # Crear orden
            if order_type == "MARKET":
                order = MarketOrder(action, quantity)
            elif order_type == "LIMIT":
                if limit_price is None:
                    return {
                        "success": False,
                        "message": "Precio límite requerido para orden LIMIT"
                    }
                order = LimitOrder(action, quantity, limit_price)
            else:
                return {
                    "success": False,
                    "message": f"Tipo de orden desconocido: {order_type}"
                }
            
            logger.info(f"Colocando orden: {action} {quantity} {ticker}")
            
            # Colocar orden
            trade = self.ib.placeOrder(contract, order)
            
            # Esperar confirmación
            self.ib.sleep(1)
            
            # Obtener detalles
            if trade.orderStatus.status == ORDER_STATUS_FILLED:
                # Registrar en histórico
                self.state["trade_history"].append({
                    "date": datetime.now().isoformat(),
                    "ticker": ticker,
                    "action": action,
                    "quantity": quantity,
                    "price": trade.fills[0].execution.price if trade.fills else 0,
                    "amount": trade.fills[0].execution.shares * trade.fills[0].execution.price if trade.fills else 0,
                    "fee": 0,  # IB calcula comisiones internamente
                    "origin": "LIVE_TRADING",
                    "bot_opinion": "N/A",  # Será actualizado por scheduler
                })
                
                self.save_state()
                
                return {
                    "success": True,
                    "message": f"Orden ejecutada: {action} {quantity} {ticker} @ ${trade.fills[0].execution.price:.2f}"
                }
            else:
                return {
                    "success": False,
                    "message": f"Orden no ejecutada: {trade.orderStatus.status}"
                }
        
        except Exception as e:
            logger.error(f"Error en orden: {e}")
            return {
                "success": False,
                "message": f"Error al colocar orden: {str(e)}"
            }
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Obtiene resumen de la cartera."""
        try:
            self._sync_account_data()
            
            positions_value = sum(
                sum(lot["market_value"] for lot in lots)
                for lots in self.state["positions"].values()
            )
            
            total_value = self.state["cash"] + positions_value
            return_pct = 0.0  # Calcular si necesario
            
            return {
                "cash": self.state["cash"],
                "positions_value": positions_value,
                "total_value": total_value,
                "return_pct": return_pct,
                "positions": self._format_positions(),
                "last_sync": self.state["last_sync"],
            }
        
        except Exception as e:
            logger.error(f"Error obteniendo portfolio: {e}")
            return {
                "cash": 0.0,
                "positions_value": 0.0,
                "total_value": 0.0,
                "return_pct": 0.0,
                "positions": [],
            }
    
    def _format_positions(self) -> List[Dict[str, Any]]:
        """Formatea posiciones para output."""
        positions = []
        for ticker, lots in self.state["positions"].items():
            total_qty = sum(lot["qty"] for lot in lots)
            avg_price = sum(lot["qty"] * lot["current_price"] for lot in lots) / total_qty if total_qty > 0 else 0
            current_price = lots[0]["current_price"] if lots else 0
            
            positions.append({
                "ticker": ticker,
                "qty": total_qty,
                "entry_price": avg_price,
                "current_price": current_price,
                "pnl": (current_price - avg_price) * total_qty,
                "pnl_pct": ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0,
            })
        
        return positions
    
    def get_current_price(self, ticker: str) -> Optional[float]:
        """Obtiene precio actual de un ticker."""
        if not self.connected:
            return None
        
        try:
            contract = Stock(ticker, "SMART", "USD")
            ticker_data = self.ib.reqMktData(contract, "", False, False)
            self.ib.sleep(0.5)
            return ticker_data.last
        
        except Exception as e:
            logger.error(f"Error obteniendo precio de {ticker}: {e}")
            return None
    
    def save_state(self) -> None:
        """Guarda estado local."""
        try:
            self.state_file.parent.mkdir(exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando estado: {e}")
    
    def load_state(self) -> None:
        """Carga estado previo si existe."""
        try:
            if self.state_file.exists():
                with open(self.state_file) as f:
                    self.state = json.load(f)
        except Exception as e:
            logger.error(f"Error cargando estado: {e}")
    
    def add_ticker(self, ticker: str) -> None:
        """Agrega ticker a watchlist."""
        if ticker not in self.state["watchlist"]:
            self.state["watchlist"].append(ticker)
            self.save_state()
    
    def remove_ticker(self, ticker: str) -> None:
        """Remueve ticker de watchlist."""
        if ticker in self.state["watchlist"]:
            self.state["watchlist"].remove(ticker)
            self.save_state()
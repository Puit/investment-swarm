import os
from ib_insync import IB, Stock, MarketOrder, Order
from datetime import datetime
import json
import logging
from pathlib import Path
from config import IB_ACCOUNT, IB_USE_PAPER, IB_HOST, IB_PORT, SIMULATION_MODE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BrokerManager")


class BrokerManager:
    """Gestiona conexión con Interactive Brokers y ejecución de órdenes"""

    def __init__(self):
        self.ib = None
        self.connected = False
        self.simulation_file = Path("simulation_trades.json")
        self.simulation_trades = self._load_simulation_trades()

    def connect(self):
        """Conecta con Interactive Brokers"""
        if SIMULATION_MODE:
            logger.info("🔄 Modo SIMULACIÓN activado — no se ejecutarán órdenes reales")
            self.connected = True
            return True

        try:
            self.ib = IB()
            self.ib.connect(IB_HOST, IB_PORT, clientId=1)
            self.connected = True
            logger.info(f"✅ Conectado a Interactive Brokers ({IB_ACCOUNT})")
            return True
        except Exception as e:
            logger.error(f"❌ Error conectando a IB: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Desconecta de IB"""
        if self.ib:
            self.ib.disconnect()
            self.connected = False
            logger.info("Desconectado de Interactive Brokers")

    def get_available_capital(self) -> float:
        """Obtiene capital disponible en la cuenta"""
        if SIMULATION_MODE:
            return self.simulation_trades.get("available_capital", 5000.0)

        try:
            account_summary = self.ib.accountSummary(IB_ACCOUNT)
            for item in account_summary:
                if item.tag == "AvailableFunds":
                    capital = float(item.value)
                    logger.info(f"💰 Capital disponible: ${capital:.2f}")
                    return capital
            return 0.0
        except Exception as e:
            logger.error(f"Error obteniendo capital: {e}")
            return 0.0

    def get_open_positions(self) -> dict:
        """Obtiene posiciones abiertas"""
        if SIMULATION_MODE:
            return self.simulation_trades.get("positions", {})

        try:
            positions = {}
            for position in self.ib.positions():
                ticker = position.contract.symbol
                positions[ticker] = {
                    "quantity": position.position,
                    "avg_cost": position.avgCost,
                    "market_price": position.marketPrice if hasattr(position, 'marketPrice') else 0,
                    "pnl": position.unrealizedPNL if hasattr(position, 'unrealizedPNL') else 0,
                }
            return positions
        except Exception as e:
            logger.error(f"Error obteniendo posiciones: {e}")
            return {}

    def buy_stock(self, ticker: str, amount_usd: float, conviction: str) -> bool:
        """
        Compra un stock con cantidad en USD
        
        Args:
            ticker: Símbolo del stock (ej: "AAPL")
            amount_usd: Cantidad en dólares a invertir
            conviction: "VERY_HIGH", "HIGH", "MEDIUM"
        
        Returns:
            True si la compra fue exitosa (o simulada)
        """
        if SIMULATION_MODE:
            return self._simulate_buy(ticker, amount_usd, conviction)

        try:
            # Obtener precio actual
            stock = Stock(ticker, "SMART", "USD")
            self.ib.qualifyContracts(stock)
            ticker_data = self.ib.reqMktData(stock)
            price = ticker_data.last

            if not price or price <= 0:
                logger.error(f"No se pudo obtener precio para {ticker}")
                return False

            # Calcular cantidad de acciones
            quantity = int(amount_usd / price)

            if quantity <= 0:
                logger.error(f"Cantidad insuficiente para {ticker}")
                return False

            # Crear orden de mercado
            order = MarketOrder("BUY", quantity)
            trade = self.ib.placeOrder(stock, order)

            logger.info(f"✅ Orden COMPRA enviada: {quantity} {ticker} @ ${price:.2f}")
            return True

        except Exception as e:
            logger.error(f"Error comprando {ticker}: {e}")
            return False

    def sell_stock(self, ticker: str, quantity: int, reason: str) -> bool:
        """Vende un stock"""
        if SIMULATION_MODE:
            return self._simulate_sell(ticker, quantity, reason)

        try:
            stock = Stock(ticker, "SMART", "USD")
            self.ib.qualifyContracts(stock)
            order = MarketOrder("SELL", quantity)
            trade = self.ib.placeOrder(stock, order)

            logger.info(f"✅ Orden VENTA enviada: {quantity} {ticker} ({reason})")
            return True

        except Exception as e:
            logger.error(f"Error vendiendo {ticker}: {e}")
            return False

    # ── SIMULACIÓN ──

    def _load_simulation_trades(self) -> dict:
        """Carga el archivo de simulación"""
        if self.simulation_file.exists():
            with open(self.simulation_file) as f:
                return json.load(f)
        return {
            "available_capital": 5000.0,
            "positions": {},
            "trades_history": [],
        }

    def _simulate_buy(self, ticker: str, amount_usd: float, conviction: str) -> bool:
        """Simula una compra"""
        try:
            import yfinance as yf

            stock_data = yf.Ticker(ticker)
            price = stock_data.info.get("currentPrice", 0)

            if not price or price <= 0:
                logger.error(f"No se pudo obtener precio para {ticker}")
                return False

            quantity = int(amount_usd / price)
            capital = self.simulation_trades["available_capital"]

            if amount_usd > capital:
                logger.error(f"Capital insuficiente: ${capital:.2f} < ${amount_usd:.2f}")
                return False

            # Registrar compra
            self.simulation_trades["available_capital"] -= amount_usd
            if ticker not in self.simulation_trades["positions"]:
                self.simulation_trades["positions"][ticker] = {
                    "quantity": 0,
                    "avg_cost": 0,
                    "pnl": 0,
                }

            self.simulation_trades["positions"][ticker]["quantity"] += quantity
            self.simulation_trades["positions"][ticker]["avg_cost"] = price

            self.simulation_trades["trades_history"].append({
                "type": "BUY",
                "ticker": ticker,
                "quantity": quantity,
                "price": price,
                "amount": amount_usd,
                "conviction": conviction,
                "timestamp": datetime.now().isoformat(),
            })

            self._save_simulation_trades()
            logger.info(
                f"📊 SIMULACIÓN: Comprados {quantity} {ticker} @ ${price:.2f} (${amount_usd:.2f})"
            )
            return True

        except Exception as e:
            logger.error(f"Error en simulación de compra: {e}")
            return False

    def _simulate_sell(self, ticker: str, quantity: int, reason: str) -> bool:
        """Simula una venta"""
        try:
            if ticker not in self.simulation_trades["positions"]:
                logger.error(f"No hay posición abierta de {ticker}")
                return False

            position = self.simulation_trades["positions"][ticker]
            if position["quantity"] < quantity:
                logger.error(f"Cantidad insuficiente: {position['quantity']} < {quantity}")
                return False

            import yfinance as yf

            stock_data = yf.Ticker(ticker)
            price = stock_data.info.get("currentPrice", 0)

            amount = quantity * price
            self.simulation_trades["available_capital"] += amount
            position["quantity"] -= quantity

            if position["quantity"] == 0:
                del self.simulation_trades["positions"][ticker]

            self.simulation_trades["trades_history"].append({
                "type": "SELL",
                "ticker": ticker,
                "quantity": quantity,
                "price": price,
                "amount": amount,
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
            })

            self._save_simulation_trades()
            logger.info(f"📊 SIMULACIÓN: Vendidos {quantity} {ticker} @ ${price:.2f} ({reason})")
            return True

        except Exception as e:
            logger.error(f"Error en simulación de venta: {e}")
            return False

    def _save_simulation_trades(self):
        """Guarda el archivo de simulación"""
        with open(self.simulation_file, "w") as f:
            json.dump(self.simulation_trades, f, indent=2)

    def get_portfolio_value(self) -> dict:
        """Retorna el valor total del portfolio"""
        positions = self.get_open_positions()
        capital = self.get_available_capital()
        portfolio_value = capital
        total_pnl = 0

        for ticker, pos in positions.items():
            position_value = pos["quantity"] * pos.get("market_price", pos["avg_cost"])
            portfolio_value += position_value
            total_pnl += pos.get("pnl", 0)

        return {
            "total_value": portfolio_value,
            "available_capital": capital,
            "positions_value": portfolio_value - capital,
            "total_pnl": total_pnl,
            "num_positions": len(positions),
        }
"""
SISTEMA DE ÓRDENES PROGRAMADAS
===============================

Gestiona órdenes de compra/venta programadas por el usuario.
Las órdenes se persisten en JSON y el scheduler las monitorea.

Estados:
- waiting_for_price: Esperando que baje el precio
- waiting_for_signal: Esperando que mejoren los análisis
- executed: Orden ejecutada
- cancelled: Orden cancelada por el usuario
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

PROGRAMMED_ORDERS_FILE = Path("data/programmed_orders.json")


class ProgrammedOrdersManager:
    """Gestor de órdenes programadas"""

    def __init__(self):
        """Inicializa el gestor"""
        PROGRAMMED_ORDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.orders = self._load_orders()

    def _load_orders(self) -> List[Dict]:
        """Carga órdenes del archivo"""
        if not PROGRAMMED_ORDERS_FILE.exists():
            return []
        try:
            with open(PROGRAMMED_ORDERS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error cargando órdenes: {e}")
            return []

    def _save_orders(self) -> None:
        """Guarda órdenes al archivo"""
        try:
            with open(PROGRAMMED_ORDERS_FILE, 'w') as f:
                json.dump(self.orders, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error guardando órdenes: {e}")

    def add_order(self, ticker: str, action: str, quantity: int,
                  current_price: float, status: str, analyses: Dict) -> None:
        """Agrega una nueva orden programada"""
        order = {
            "id": f"{ticker}_{action}_{datetime.now().timestamp()}",
            "ticker": ticker,
            "action": action,  # BUY o SELL
            "quantity": quantity,
            "max_price": current_price * 1.05,  # 5% de margen
            "created_at": datetime.now().isoformat(),
            "last_check": datetime.now().isoformat(),
            "status": status,  # waiting_for_price, waiting_for_signal, executed, cancelled
            "analyses": analyses,
            "attempts": 0,
        }
        self.orders.append(order)
        self._save_orders()
        logger.info(f"✓ Orden programada: {action} {quantity} x {ticker}")

    def get_active_orders(self) -> List[Dict]:
        """Obtiene órdenes activas (no ejecutadas ni canceladas)"""
        return [o for o in self.orders if o["status"] not in ["executed", "cancelled"]]

    def update_order_status(self, order_id: str, status: str, data: Dict = None) -> None:
        """Actualiza el estado de una orden"""
        for order in self.orders:
            if order["id"] == order_id:
                order["status"] = status
                order["last_check"] = datetime.now().isoformat()
                if data:
                    order.update(data)
                self._save_orders()
                logger.info(f"✓ Orden actualizada: {order_id} -> {status}")
                return
        logger.warning(f"⚠️ Orden no encontrada: {order_id}")

    def cancel_order(self, order_id: str) -> None:
        """Cancela una orden"""
        self.update_order_status(order_id, "cancelled")

    def execute_order(self, order_id: str) -> None:
        """Marca una orden como ejecutada"""
        self.update_order_status(order_id, "executed", {
            "executed_at": datetime.now().isoformat()
        })

    def remove_old_orders(self, days: int = 30) -> None:
        """Elimina órdenes ejecutadas/canceladas más antiguas que N días"""
        cutoff = datetime.now().timestamp() - (days * 86400)
        initial_count = len(self.orders)

        self.orders = [
            o for o in self.orders
            if not (
                o["status"] in ["executed", "cancelled"] and
                datetime.fromisoformat(o["created_at"]).timestamp() < cutoff
            )
        ]

        if len(self.orders) < initial_count:
            self._save_orders()
            logger.info(f"🗑️ Eliminadas {initial_count - len(self.orders)} órdenes antiguas")


# Instancia global
orders_manager = ProgrammedOrdersManager()

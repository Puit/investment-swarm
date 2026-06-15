import json
import os
from datetime import datetime
from pathlib import Path

class AnalysisStorage:
    def __init__(self, cache_dir="analysis_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.positions_file = self.cache_dir / "positions.json"
        self.fundamentals_file = self.cache_dir / "fundamentals.json"

    def save_fundamental(self, ticker: str, analysis: dict):
        """Guarda análisis fundamental con timestamp"""
        data = self.load_fundamentals()
        data[ticker] = {
            "analysis": analysis,
            "timestamp": datetime.now().isoformat(),
        }
        with open(self.fundamentals_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_fundamental(self, ticker: str):
        """Retorna análisis fundamental si existe"""
        data = self.load_fundamentals()
        return data.get(ticker, {}).get("analysis")

    def load_fundamentals(self) -> dict:
        """Carga todos los análisis guardados"""
        if self.fundamentals_file.exists():
            with open(self.fundamentals_file) as f:
                return json.load(f)
        return {}

    def add_position(self, ticker: str, entry_price: float, quantity: int, notes: str = ""):
        """Añade una posición a la cartera"""
        positions = self.load_positions()
        positions[ticker] = {
            "entry_price": entry_price,
            "quantity": quantity,
            "entry_date": datetime.now().isoformat(),
            "notes": notes,
            "pnl": 0,
            "status": "OPEN"
        }
        with open(self.positions_file, "w") as f:
            json.dump(positions, f, indent=2, ensure_ascii=False)

    def update_position_pnl(self, ticker: str, current_price: float):
        """Actualiza P&L de una posición"""
        positions = self.load_positions()
        if ticker in positions:
            entry = positions[ticker]["entry_price"]
            qty = positions[ticker]["quantity"]
            positions[ticker]["pnl"] = (current_price - entry) * qty
            positions[ticker]["current_price"] = current_price
            with open(self.positions_file, "w") as f:
                json.dump(positions, f, indent=2, ensure_ascii=False)

    def close_position(self, ticker: str, exit_price: float):
        """Cierra una posición"""
        positions = self.load_positions()
        if ticker in positions:
            positions[ticker]["status"] = "CLOSED"
            positions[ticker]["exit_price"] = exit_price
            positions[ticker]["exit_date"] = datetime.now().isoformat()
            with open(self.positions_file, "w") as f:
                json.dump(positions, f, indent=2, ensure_ascii=False)

    def load_positions(self) -> dict:
        """Carga todas las posiciones"""
        if self.positions_file.exists():
            with open(self.positions_file) as f:
                return json.load(f)
        return {}
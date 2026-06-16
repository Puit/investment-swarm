"""
Sistema de almacenamiento de análisis para sincronizar Telegram Bot y Dashboard
"""

import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

ANALYSIS_FILE = Path(__file__).parent.parent / "data" / "analyses.json"
ANALYSIS_FILE.parent.mkdir(exist_ok=True)


class AnalysisStorage:
    """Almacena y recupera análisis para sincronización entre bot y dashboard"""

    @staticmethod
    def save_analysis(ticker: str, analysis_type: str, data: dict) -> None:
        """Guarda un análisis (fundamental, sentiment, technical)"""
        try:
            # Leer análisis existentes
            if ANALYSIS_FILE.exists():
                with open(ANALYSIS_FILE, 'r') as f:
                    all_analyses = json.load(f)
            else:
                all_analyses = {}

            # Crear entrada para el ticker si no existe
            if ticker not in all_analyses:
                all_analyses[ticker] = {}

            # Guardar análisis con timestamp
            all_analyses[ticker][analysis_type] = {
                "data": data,
                "timestamp": datetime.now().isoformat(),
                "type": analysis_type
            }

            # Escribir de vuelta
            with open(ANALYSIS_FILE, 'w') as f:
                json.dump(all_analyses, f, indent=2)

            logger.info(f"✓ Análisis guardado: {ticker} - {analysis_type}")

        except Exception as e:
            logger.error(f"Error guardando análisis: {e}")

    @staticmethod
    def get_analysis(ticker: str, analysis_type: str = None) -> dict:
        """Lee un análisis específico o todos los análisis de un ticker"""
        try:
            if not ANALYSIS_FILE.exists():
                return {}

            with open(ANALYSIS_FILE, 'r') as f:
                all_analyses = json.load(f)

            ticker_data = all_analyses.get(ticker, {})

            if analysis_type:
                return ticker_data.get(analysis_type, {})
            else:
                return ticker_data

        except Exception as e:
            logger.error(f"Error leyendo análisis: {e}")
            return {}

    @staticmethod
    def get_all_analyses() -> dict:
        """Lee todos los análisis guardados"""
        try:
            if not ANALYSIS_FILE.exists():
                return {}

            with open(ANALYSIS_FILE, 'r') as f:
                return json.load(f)

        except Exception as e:
            logger.error(f"Error leyendo análisis: {e}")
            return {}

    @staticmethod
    def clear_ticker(ticker: str) -> None:
        """Borra todos los análisis de un ticker"""
        try:
            if ANALYSIS_FILE.exists():
                with open(ANALYSIS_FILE, 'r') as f:
                    all_analyses = json.load(f)

                if ticker in all_analyses:
                    del all_analyses[ticker]

                with open(ANALYSIS_FILE, 'w') as f:
                    json.dump(all_analyses, f, indent=2)

                logger.info(f"✓ Análisis borrado para {ticker}")

        except Exception as e:
            logger.error(f"Error borrando análisis: {e}")

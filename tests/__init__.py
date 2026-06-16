"""
Tests package para Investment Swarm.

Contiene:
- test_suite.py: Suite completa de tests
- diagnose_telegram.py: Diagnóstico del bot de Telegram
- conftest.py: Configuración compartida de tests

Uso:
    python -m pytest tests/              # Ejecutar con pytest
    python run_tests.py                 # Ejecutar script personalizado
    python tests/diagnose_telegram.py   # Diagnóstico directo
"""

__version__ = "1.0.0"
__all__ = ["test_suite", "diagnose_telegram"]
"""
DIAGNÓSTICO COMPLETO - Investment Swarm
========================================

Verifica todos los componentes y dependencias.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

print("=" * 70)
print("🔍 DIAGNÓSTICO COMPLETO - INVESTMENT SWARM")
print("=" * 70)

# ─────────────────────────────────────────────────────────────────
# 1. VARIABLES DE ENTORNO
# ─────────────────────────────────────────────────────────────────

print("\n1️⃣ VARIABLES DE ENTORNO")
print("-" * 70)

token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

if token:
    print(f"  ✓ TELEGRAM_BOT_TOKEN: {token[:30]}...")
else:
    print("  ✗ TELEGRAM_BOT_TOKEN no configurado")

if chat_id:
    print(f"  ✓ TELEGRAM_CHAT_ID: {chat_id}")
else:
    print("  ✗ TELEGRAM_CHAT_ID no configurado")

if not (token and chat_id):
    print("\n⚠️ Edita .env y agrega credenciales de Telegram")

# ─────────────────────────────────────────────────────────────────
# 2. DEPENDENCIAS PYTHON
# ─────────────────────────────────────────────────────────────────

print("\n2️⃣ DEPENDENCIAS PYTHON")
print("-" * 70)

deps = {
    "streamlit": "streamlit",
    "telegram": "python-telegram-bot",
    "pandas": "pandas",
    "yfinance": "yfinance",
    "crewai": "crewai",
    "ib_insync": "ib-insync",
    "dotenv": "python-dotenv",
}

missing = []
for module, pip_name in deps.items():
    try:
        __import__(module)
        print(f"  ✓ {pip_name}")
    except ImportError:
        print(f"  ✗ {pip_name}")
        missing.append(pip_name)

if missing:
    print(f"\n❌ Instala paquetes faltantes:")
    print(f"   pip install {' '.join(missing)}")

# ─────────────────────────────────────────────────────────────────
# 3. ARCHIVOS LOCALES
# ─────────────────────────────────────────────────────────────────

print("\n3️⃣ ARCHIVOS LOCALES")
print("-" * 70)

files = [
    "paper_trading_engine.py",
    "telegram_bot.py",
    "telegram_bot_main.py",
    "interactive_brokers_broker.py",
    "scheduler.py",
    "dashboard.py",
    "run.py",
    "requirements.txt",
    ".env",
]

for f in files:
    exists = Path(f).exists()
    status = "✓" if exists else "✗"
    print(f"  {status} {f}")

# ─────────────────────────────────────────────────────────────────
# 4. IMPORTS DE MÓDULOS LOCALES
# ─────────────────────────────────────────────────────────────────

print("\n4️⃣ IMPORTS DE MÓDULOS LOCALES")
print("-" * 70)

modules = [
    ("PaperTradingEngine", "paper_trading_engine"),
    ("TelegramTradingBotV2", "telegram_bot"),
    ("InteractiveBrokersBroker", "interactive_brokers_broker"),
    ("InvestmentSchedulerV2", "scheduler"),
]

for class_name, module_name in modules:
    try:
        mod = __import__(module_name)
        if hasattr(mod, class_name):
            print(f"  ✓ {class_name} from {module_name}")
        else:
            print(f"  ✗ {class_name} not found in {module_name}")
    except Exception as e:
        print(f"  ✗ {class_name}: {str(e)[:50]}")

# ─────────────────────────────────────────────────────────────────
# 5. DIRECTORIO DATA
# ─────────────────────────────────────────────────────────────────

print("\n5️⃣ DIRECTORIO DATA")
print("-" * 70)

data_dir = Path("data")
if data_dir.exists():
    print(f"  ✓ data/ existe")
    
    state_file = data_dir / "paper_trading_state.json"
    if state_file.exists():
        size = state_file.stat().st_size
        print(f"  ✓ paper_trading_state.json ({size} bytes)")
    else:
        print(f"  ⚠️ paper_trading_state.json (será creado)")
else:
    print(f"  ⚠️ data/ no existe (será creado al ejecutar)")

# ─────────────────────────────────────────────────────────────────
# 6. RESUMEN
# ─────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("📊 RESUMEN")
print("=" * 70)

issues = []

if not token or not chat_id:
    issues.append("⚠️ Credenciales de Telegram no configuradas")

if missing:
    issues.append(f"❌ {len(missing)} paquetes faltantes")

if not Path(".env").exists():
    issues.append("❌ Archivo .env no existe")

if issues:
    print("\n❌ PROBLEMAS ENCONTRADOS:\n")
    for issue in issues:
        print(f"   {issue}")
    print("\n📝 ACCIONES REQUERIDAS:")
    print("   1. Edita .env y agrega TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID")
    print("   2. Ejecuta: pip install -r requirements.txt")
    print("   3. Abre IB Gateway si quieres live trading")
    print("   4. Ejecuta: python test_telegram_bot.py")
else:
    print("\n✅ TODO PARECE OK")
    print("\nPróximos pasos:")
    print("   1. Ejecuta: python test_telegram_bot.py")
    print("   2. Si OK, ejecuta: python run.py")
    print("   3. Dashboard: http://localhost:8501")

print("\n" + "=" * 70 + "\n")
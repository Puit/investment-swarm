"""
Script para probar telegram_bot_main.py directamente y ver errores.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

print("=" * 60)
print("🧪 TEST: Telegram Bot v2")
print("=" * 60)

# Test 1: Variables de entorno
print("\n1️⃣ Verificando variables de entorno...")
if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
    print(f"  ✓ TOKEN: {TELEGRAM_BOT_TOKEN[:20]}...")
    print(f"  ✓ CHAT_ID: {TELEGRAM_CHAT_ID}")
else:
    print("  ✗ Variables no configuradas")
    sys.exit(1)

# Test 2: Imports
print("\n2️⃣ Verificando imports...")
try:
    from trading.paper_trading_engine import PaperTradingEngine
    print("  ✓ PaperTradingEngine")
except Exception as e:
    print(f"  ✗ PaperTradingEngine: {e}")
    sys.exit(1)

try:
    from bot.telegram_bot import TelegramTradingBotV2
    print("  ✓ TelegramTradingBotV2")
except Exception as e:
    print(f"  ✗ TelegramTradingBotV2: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    from brokers.interactive_brokers_broker import InteractiveBrokersBroker
    print("  ✓ InteractiveBrokersBroker")
except Exception as e:
    print(f"  ⚠️ InteractiveBrokersBroker (opcional): {e}")

# Test 3: Crear engine
print("\n3️⃣ Creando Paper Trading Engine...")
try:
    engine = PaperTradingEngine(initial_capital=5000.0)
    print("  ✓ Engine creado")
except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Crear bot
print("\n4️⃣ Creando Telegram Bot v2...")
try:
    bot = TelegramTradingBotV2(
        paper_engine=engine,
        live_broker=None,
        chat_id=TELEGRAM_CHAT_ID
    )
    print("  ✓ Bot creado")
except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Setup bot
print("\n5️⃣ Setup del bot...")
import asyncio

async def test_setup():
    try:
        await bot.setup(token=TELEGRAM_BOT_TOKEN)
        print("  ✓ Bot setup completo")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

success = asyncio.run(test_setup())

if success:
    print("\n" + "=" * 60)
    print("✅ TODO OK - Bot debería funcionar")
    print("=" * 60)
else:
    print("\n" + "=" * 60)
    print("❌ HAY PROBLEMAS - Ver errores arriba")
    print("=" * 60)
    sys.exit(1)
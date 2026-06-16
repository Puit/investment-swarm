"""
TELEGRAM BOT MAIN - Entry point
================================

Script ejecutable que instancia y ejecuta TelegramTradingBotV2.

Uso:
    python telegram_bot_main.py
"""

import os
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Imports locales
from paper_trading_engine import PaperTradingEngine
from telegram_bot import TelegramTradingBotV2
from interactive_brokers_broker import InteractiveBrokersBroker

# Credenciales
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


async def main():
    """Función principal."""
    
    logger.info("=" * 60)
    logger.info("🤖 TELEGRAM BOT v2 - Iniciando")
    logger.info("=" * 60)
    
    # 1. Verificar credenciales
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("❌ Credenciales no configuradas en .env")
        logger.error("Necesitas: TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID")
        return
    
    logger.info("✓ Credenciales cargadas")
    
    # 2. Inicializar Paper Trading Engine
    logger.info("Inicializando Paper Trading Engine...")
    engine = PaperTradingEngine(initial_capital=5000.0)
    logger.info("✓ Engine listo")
    
    # 3. Inicializar Interactive Brokers (opcional)
    logger.info("Intentando conectar con Interactive Brokers...")
    broker = InteractiveBrokersBroker()
    broker_connected = False
    
    try:
        if broker.connect():
            broker_connected = True
            logger.info("✓ Broker conectado (Live Trading disponible)")
        else:
            logger.warning("⚠ Broker no disponible (Paper Trading only)")
    except Exception as e:
        logger.warning(f"⚠ Error conectando broker: {e}")
        logger.warning("  Continuando con Paper Trading only")
    
    # 4. Inicializar Bot Telegram v2
    logger.info("Inicializando Telegram Bot v2...")
    bot = TelegramTradingBotV2(
        paper_engine=engine,
        live_broker=broker if broker_connected else None,
        chat_id=TELEGRAM_CHAT_ID
    )
    
    # Setup bot
    await bot.setup(token=TELEGRAM_BOT_TOKEN)
    logger.info("✓ Bot configurado")
    
    # 5. Iniciar bot
    logger.info("=" * 60)
    logger.info("🟢 BOT TELEGRAM RUNNING")
    logger.info(f"📞 Chat ID: {TELEGRAM_CHAT_ID}")
    logger.info(f"📚 Paper Trading: Activo")
    
    if broker_connected:
        logger.info(f"🔴 Live Trading: Activo")
    else:
        logger.info(f"🔴 Live Trading: No disponible")
    
    logger.info("=" * 60)
    logger.info("Esperando comandos en Telegram...")
    logger.info("=" * 60 + "\n")
    
    try:
        # Iniciar polling
        await bot.app.initialize()
        await bot.app.start()
        await bot.app.updater.start_polling(
            allowed_updates=['message', 'callback_query']
        )
        
        # Mantener corriendo
        await bot.app.updater.idle()
    
    except KeyboardInterrupt:
        logger.info("\n\n⏹ Bot detenido por usuario")
    
    except Exception as e:
        logger.error(f"Error: {e}")
    
    finally:
        # Cleanup
        logger.info("Limpiando...")
        if broker_connected:
            broker.disconnect()
            logger.info("✓ Broker desconectado")
        
        await bot.app.stop()
        logger.info("✓ Bot detenido")
        logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
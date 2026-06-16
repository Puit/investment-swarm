"""
DIAGNÓSTICO DEL BOT DE TELEGRAM
================================

Verifica cada componente del bot y encuentra el problema.

Uso:
    python diagnose_telegram.py
"""

import os
import sys
from pathlib import Path

# Agregar carpeta raíz al path (IMPORTANTE para imports)
root_path = str(Path(__file__).parent.parent)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from dotenv import load_dotenv

# Colores
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_test(name, passed, message=""):
    """Imprime resultado de test."""
    status = f"{Colors.GREEN}✓ PASS{Colors.ENDC}" if passed else f"{Colors.RED}✗ FAIL{Colors.ENDC}"
    print(f"  {status} {name}")
    if message:
        print(f"       {Colors.YELLOW}{message}{Colors.ENDC}")

def diagnose():
    """Ejecuta diagnóstico completo."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}🔍 DIAGNÓSTICO BOT TELEGRAM{Colors.ENDC}\n")
    
    # Test 1: .env existe
    print(f"{Colors.BOLD}1. Verificando configuración...{Colors.ENDC}")
    env_exists = Path(".env").exists()
    print_test(".env existe", env_exists, 
               "Crea .env si no existe" if not env_exists else "")
    
    if not env_exists:
        return False
    
    # Cargar .env
    load_dotenv()
    
    # Test 2: Variables de entorno
    print(f"\n{Colors.BOLD}2. Variables de entorno...{Colors.ENDC}")
    
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    
    token_ok = token and len(token) > 20
    chat_id_ok = chat_id and chat_id.startswith("-") or chat_id.isdigit()
    
    print_test("TELEGRAM_BOT_TOKEN configurado", token_ok,
               f"Token: {token[:20]}..." if token_ok else "Falta en .env")
    print_test("TELEGRAM_CHAT_ID configurado", chat_id_ok,
               f"Chat ID: {chat_id}" if chat_id_ok else "Falta en .env")
    
    if not (token_ok and chat_id_ok):
        print(f"\n{Colors.RED}❌ Faltan credenciales. Completa .env:{Colors.ENDC}")
        print(f"TELEGRAM_BOT_TOKEN=tu_token_aqui")
        print(f"TELEGRAM_CHAT_ID=tu_chat_id_aqui")
        return False
    
    # Test 3: Módulos requeridos
    print(f"\n{Colors.BOLD}3. Módulos Python...{Colors.ENDC}")
    
    modules_ok = True
    required_modules = [
        ("telegram", "python-telegram-bot"),
        ("paper_trading_engine", "paper_trading_engine.py"),
        ("dotenv", "python-dotenv"),
    ]
    
    for module, package in required_modules:
        try:
            __import__(module)
            print_test(f"{module} importable", True)
        except ImportError as e:
            print_test(f"{module} importable", False, f"Instala: pip install {package}")
            modules_ok = False
    
    if not modules_ok:
        return False
    
    # Test 4: Conexión a Telegram API
    print(f"\n{Colors.BOLD}4. Conexión a Telegram API...{Colors.ENDC}")
    
    try:
        from telegram import Bot
        import asyncio
        
        async def test_connection():
            try:
                bot = Bot(token=token)
                # Prueba simple: obtener información del bot
                me = await bot.get_me()
                return True, f"Bot conectado: @{me.username}"
            except Exception as e:
                return False, str(e)
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        success, message = loop.run_until_complete(test_connection())
        print_test("Conexión a API Telegram", success, message)
        
        if not success:
            print(f"\n{Colors.RED}❌ Error de conexión:{Colors.ENDC}")
            print(f"   Posibles causas:")
            print(f"   1. Token inválido o expirado")
            print(f"   2. Sin conexión a internet")
            print(f"   3. Telegram API no accesible")
            return False
            
    except Exception as e:
        print_test("Conexión a API Telegram", False, str(e))
        return False
    
    # Test 5: Chat ID válido
    print(f"\n{Colors.BOLD}5. Validación Chat ID...{Colors.ENDC}")
    
    try:
        from telegram import Bot
        import asyncio
        
        async def test_chat():
            try:
                bot = Bot(token=token)
                # Intenta enviar mensaje de prueba
                await bot.send_message(
                    chat_id=chat_id,
                    text="🤖 Prueba de diagnóstico - si ves esto, ¡el bot funciona!"
                )
                return True, "Mensaje enviado correctamente"
            except Exception as e:
                return False, str(e)
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        success, message = loop.run_until_complete(test_chat())
        print_test("Chat ID válido y bot puede enviar", success, message)
        
        if not success:
            print(f"\n{Colors.RED}❌ Error con Chat ID:{Colors.ENDC}")
            print(f"   1. Chat ID incorrecto")
            print(f"   2. Bot no es admin en el chat")
            print(f"   3. Chat bloqueado")
            print(f"\n   {Colors.YELLOW}Cómo obtener Chat ID correcto:{Colors.ENDC}")
            print(f"   1. Manda mensaje al bot")
            print(f"   2. Ve a: https://api.telegram.org/bot{token[:10]}XXX/getUpdates")
            print(f"   3. Busca 'chat' -> 'id' (número negativo o positivo)")
            return False
            
    except Exception as e:
        print_test("Chat ID válido", False, str(e))
        return False
    
    # Test 6: Paper Trading Engine
    print(f"\n{Colors.BOLD}6. Paper Trading Engine...{Colors.ENDC}")
    
    try:
        from trading.paper_trading_engine import PaperTradingEngine
        engine = PaperTradingEngine(initial_capital=5000.0)
        print_test("PaperTradingEngine inicializa", True)
        print_test("Estado cargado", len(engine.state) > 0, f"Keys: {len(engine.state)}")
    except Exception as e:
        print_test("PaperTradingEngine inicializa", False, str(e))
        return False
    
    # Test 7: Telegram Bot
    print(f"\n{Colors.BOLD}7. Telegram Trading Bot...{Colors.ENDC}")
    
    try:
        from bot.telegram_bot import TelegramTradingBot
        bot = TelegramTradingBot(engine, chat_id=chat_id)
        print_test("TelegramTradingBot inicializa", True)
        print_test("Tiene handlers registrados", bot.app is not None, "Listo para handlers")
    except Exception as e:
        print_test("TelegramTradingBot inicializa", False, str(e))
        return False
    
    # Resumen
    print(f"\n{Colors.BOLD}{Colors.GREEN}✓ TODOS LOS TESTS PASARON{Colors.ENDC}")
    print(f"\n{Colors.YELLOW}Si el bot aún no responde:{Colors.ENDC}")
    print(f"1. Envía un mensaje al bot primero")
    print(f"2. Ejecuta: python run.py")
    print(f"3. Envía comandos en Telegram")
    print(f"\n{Colors.BOLD}Comandos disponibles:{Colors.ENDC}")
    print(f"/start - Iniciar bot")
    print(f"/positions - Ver posiciones")
    print(f"/portfolio - Ver cartera")
    print(f"/buy TICKER QTY - Comprar")
    print(f"/sell TICKER QTY - Vender")
    print(f"/help - Ayuda")
    
    return True

if __name__ == "__main__":
    try:
        success = diagnose()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Diagnóstico cancelado{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Error inesperado: {e}{Colors.ENDC}")
        sys.exit(1)
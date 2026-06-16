"""
SETUP - Investment Swarm
========================

Configura el proyecto automáticamente:
1. Verifica que estén todos los archivos necesarios
2. Instala dependencias
3. Valida la configuración

Uso:
    python setup.py
"""

import os
import sys
from pathlib import Path
import subprocess

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(title):
    """Imprime header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.ENDC}\n")

def print_ok(msg):
    """Imprime OK."""
    print(f"{Colors.GREEN}✓{Colors.ENDC} {msg}")

def print_error(msg):
    """Imprime error."""
    print(f"{Colors.RED}✗{Colors.ENDC} {msg}")

def print_warning(msg):
    """Imprime advertencia."""
    print(f"{Colors.YELLOW}⚠{Colors.ENDC} {msg}")

def check_files():
    """Verifica que existan todos los archivos necesarios."""
    print_header("1️⃣ Verificando archivos")
    
    required_files = [
        "trading/paper_trading_engine.py",
        "bot/telegram_bot.py",
        "trading/scheduler.py",
        "dashboard/dashboard.py",
        "core/investment_decision_engine.py",
        "config_improved.py",
        "requirements.txt",
        ".env.example",
        "run.py",
        "run_tests.py",
        "conftest.py",
    ]
    
    required_dirs = [
        "tests",
        "data",
    ]
    
    missing_files = []
    missing_dirs = []
    
    for file in required_files:
        if Path(file).exists():
            print_ok(f"{file}")
        else:
            print_error(f"{file} - FALTA")
            missing_files.append(file)
    
    for dir in required_dirs:
        if Path(dir).exists():
            print_ok(f"📁 {dir}/")
        else:
            print_warning(f"📁 {dir}/ - CREANDO")
            Path(dir).mkdir(exist_ok=True)
    
    return len(missing_files) == 0

def check_dependencies():
    """Verifica que estén instaladas las dependencias."""
    print_header("2️⃣ Verificando dependencias")
    
    packages = {
        "streamlit": "streamlit",
        "telegram": "python-telegram-bot",
        "pandas": "pandas",
        "yfinance": "yfinance",
        "crewai": "crewai",
        "dotenv": "python-dotenv",
    }
    
    missing = []
    for module, pip_name in packages.items():
        try:
            __import__(module)
            print_ok(f"{pip_name}")
        except ImportError:
            print_error(f"{pip_name} - FALTA")
            missing.append(pip_name)
    
    if missing:
        print(f"\n{Colors.YELLOW}Instala los paquetes faltantes:{Colors.ENDC}")
        print(f"pip install {' '.join(missing)}")
        return False
    
    return True

def check_env():
    """Verifica configuración .env."""
    print_header("3️⃣ Verificando .env")
    
    if not Path(".env").exists():
        print_error(".env no existe")
        print(f"\n{Colors.YELLOW}Crea .env con:{Colors.ENDC}")
        
        env_example = Path(".env.example")
        if env_example.exists():
            print(f"Copia {env_example} → .env")
            print("\nO manually:")
            print("TELEGRAM_BOT_TOKEN=your_token_here")
            print("TELEGRAM_CHAT_ID=your_chat_id_here")
        
        return False
    
    print_ok(".env existe")
    
    # Verificar que tiene valores
    with open(".env") as f:
        env_content = f.read()
    
    if "TELEGRAM_BOT_TOKEN=" in env_content:
        if "your_token" not in env_content.lower():
            print_ok("TELEGRAM_BOT_TOKEN configurado")
        else:
            print_error("TELEGRAM_BOT_TOKEN no configurado (aún tiene placeholder)")
            return False
    else:
        print_error("TELEGRAM_BOT_TOKEN no encontrado en .env")
        return False
    
    if "TELEGRAM_CHAT_ID=" in env_content:
        if "your_chat" not in env_content.lower():
            print_ok("TELEGRAM_CHAT_ID configurado")
        else:
            print_error("TELEGRAM_CHAT_ID no configurado (aún tiene placeholder)")
            return False
    else:
        print_error("TELEGRAM_CHAT_ID no encontrado en .env")
        return False
    
    return True

def check_python_version():
    """Verifica versión de Python."""
    print_header("4️⃣ Verificando Python")
    
    version = sys.version_info
    print_ok(f"Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print_warning("Se recomienda Python 3.10+")
        return False
    
    return True

def test_imports():
    """Prueba importar módulos principales."""
    print_header("5️⃣ Probando imports")
    
    modules = [
        "trading.paper_trading_engine",
        "bot.telegram_bot",
        "trading.scheduler",
        "core.investment_decision_engine",
    ]

    all_ok = True
    for module in modules:
        try:
            __import__(module)
            print_ok(f"from {module} import ...")
        except ImportError as e:
            print_error(f"from {module} import ... - {e}")
            all_ok = False
    
    return all_ok

def main():
    """Función principal."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                                                            ║")
    print("║           🚀 SETUP - INVESTMENT SWARM 🚀                  ║")
    print("║                                                            ║")
    print("║  Configuración automática del proyecto                    ║")
    print("║                                                            ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}")
    
    results = {}
    
    # Ejecutar checks
    results["files"] = check_files()
    results["deps"] = check_dependencies()
    results["env"] = check_env()
    results["python"] = check_python_version()
    results["imports"] = test_imports()
    
    # Resumen
    print_header("📊 RESUMEN")
    
    for check, passed in results.items():
        status = f"{Colors.GREEN}✓ OK{Colors.ENDC}" if passed else f"{Colors.RED}✗ FALLA{Colors.ENDC}"
        print(f"  {check:15} {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ TODO ESTÁ CONFIGURADO CORRECTAMENTE{Colors.ENDC}")
        print(f"\n{Colors.BOLD}Próximo paso:{Colors.ENDC}")
        print(f"  python run_tests.py")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}✗ HAY PROBLEMAS QUE RESOLVER{Colors.ENDC}")
        print(f"\n{Colors.BOLD}Sigue las indicaciones arriba y ejecuta setup.py de nuevo.{Colors.ENDC}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
"""
INVESTMENT SWARM - UNIFIED LAUNCHER
====================================

Ejecuta TODO desde un único comando:
- Telegram Bot
- Scheduler
- Dashboard Streamlit

Uso:
    python run.py                    # Inicia todos los servicios
    python run.py --scheduler-time 10:00  # Análisis a las 10:00

Ctrl+C para detener todo
"""

import subprocess
import sys
import time
import os
import signal
from pathlib import Path
import argparse

# Intentar importar psutil, si no está disponible usar fallback
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# Colores para output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header():
    """Muestra header del launcher."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║        🚀 INVESTMENT SWARM - UNIFIED LAUNCHER 🚀           ║
║                                                            ║
║  Iniciando: Telegram Bot + Scheduler + Dashboard          ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
{Colors.ENDC}
""")

def print_service_starting(service_name, command):
    """Imprime que un servicio está iniciando."""
    print(f"{Colors.BLUE}[{service_name}]{Colors.ENDC} Iniciando...")
    print(f"{Colors.BLUE}[{service_name}]{Colors.ENDC} Comando: {command}")

def print_service_ready(service_name, info):
    """Imprime que un servicio está listo."""
    print(f"{Colors.GREEN}[✓ {service_name}]{Colors.ENDC} {info}")

def print_error(service_name, error):
    """Imprime error de un servicio."""
    print(f"{Colors.RED}[✗ {service_name}]{Colors.ENDC} Error: {error}")

def check_env_file():
    """Verifica que existe .env con credenciales."""
    if not Path(".env").exists():
        print(f"{Colors.RED}❌ ERROR: Archivo .env no encontrado{Colors.ENDC}")
        print(f"{Colors.YELLOW}Crea un archivo .env con:{Colors.ENDC}")
        print("""
TELEGRAM_BOT_TOKEN=tu_token
TELEGRAM_CHAT_ID=tu_chat_id
""")
        sys.exit(1)

def check_dependencies():
    """Verifica que todas las dependencias estén instaladas."""
    print(f"\n{Colors.YELLOW}Verificando dependencias...{Colors.ENDC}")
    
    # Mapeo de nombres de paquetes pip a nombres de módulos
    packages_to_check = {
        "streamlit": "streamlit",
        "python-telegram-bot": "telegram",  # El módulo se llama 'telegram'
        "pandas": "pandas",
        "yfinance": "yfinance",
        "crewai": "crewai",
        "ib-insync": "ib_insync",  # Para Interactive Brokers
    }
    
    missing = []
    for pip_name, module_name in packages_to_check.items():
        try:
            __import__(module_name)
            print(f"{Colors.GREEN}✓{Colors.ENDC} {pip_name}")
        except ImportError:
            print(f"{Colors.RED}✗{Colors.ENDC} {pip_name}")
            missing.append(pip_name)
    
    if missing:
        print(f"\n{Colors.RED}Instala los paquetes faltantes:{Colors.ENDC}")
        print(f"pip install {' '.join(missing)}")
        sys.exit(1)
    
    print(f"{Colors.GREEN}✓ Todas las dependencias están OK{Colors.ENDC}\n")

class UnifiedLauncher:
    """Lanzador unificado de todos los servicios."""

    def __init__(self, scheduler_time="09:30"):
        self.processes = {}
        self.scheduler_time = scheduler_time
        self.running = True

        # Matar procesos previos del bot
        self._kill_previous_bot_instances()
    
    def _kill_previous_bot_instances(self):
        """Mata cualquier instancia anterior del bot de Telegram."""
        try:
            if HAS_PSUTIL:
                # Usar psutil si está disponible
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        cmdline = proc.info['cmdline']
                        if cmdline and 'telegram_bot_main.py' in ' '.join(cmdline):
                            print(f"{Colors.YELLOW}⚠️  Matando bot anterior (PID: {proc.info['pid']})...{Colors.ENDC}")
                            proc.kill()
                            time.sleep(0.5)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            else:
                # Fallback: usar taskkill en Windows
                if sys.platform == 'win32':
                    try:
                        # Buscar y matar procesos que ejecuten telegram_bot_main.py
                        result = subprocess.run(
                            ['taskkill', '/F', '/IM', 'python.exe', '/V'],
                            capture_output=True,
                            timeout=5
                        )
                        # Solo matar si encontramos procesos
                        if 'telegram' in result.stdout.decode(errors='ignore').lower():
                            print(f"{Colors.YELLOW}⚠️  Se terminaron instancias previas del bot...{Colors.ENDC}")
                    except:
                        pass
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️  No se pudo limpiar procesos previos: {e}{Colors.ENDC}")

    def start_telegram_bot(self):
        """Inicia Telegram Bot."""
        print_service_starting("TELEGRAM BOT", "python bot/telegram_bot_main.py")

        try:
            process = subprocess.Popen(
                [sys.executable, "bot/telegram_bot_main.py"],
                stdout=None,  # Mostrar logs en tiempo real
                stderr=None,  # Mostrar errores en tiempo real
                text=True,
                bufsize=1,
            )
            self.processes["telegram_bot"] = process
            time.sleep(3)

            if process.poll() is None:
                print_service_ready("TELEGRAM BOT", "Escuchando comandos (Paper + Live)")
            else:
                print_error("TELEGRAM BOT", "Proceso terminó inesperadamente")
                return False
        except Exception as e:
            print_error("TELEGRAM BOT", str(e))
            return False
        
        return True
    
    def start_scheduler(self):
        """Inicia Scheduler."""
        cmd = [sys.executable, "trading/scheduler.py", "--time", self.scheduler_time]
        print_service_starting("SCHEDULER", " ".join(cmd))

        try:
            process = subprocess.Popen(
                cmd,
                stdout=None,  # Mostrar logs en tiempo real
                stderr=None,  # Mostrar errores en tiempo real
                text=True,
                bufsize=1,
            )
            self.processes["scheduler"] = process
            time.sleep(3)

            if process.poll() is None:
                print_service_ready(
                    "SCHEDULER",
                    f"Análisis programados para {self.scheduler_time} CET"
                )
            else:
                print_error("SCHEDULER", "Proceso terminó inesperadamente")
                return False
        except Exception as e:
            print_error("SCHEDULER", str(e))
            return False
        
        return True
    
    def start_dashboard(self):
        """Inicia Dashboard Streamlit."""
        cmd = [sys.executable, "-m", "streamlit", "run", "dashboard/dashboard.py"]
        print_service_starting("DASHBOARD", " ".join(cmd))

        try:
            process = subprocess.Popen(
                cmd,
                stdout=None,  # Mostrar logs en tiempo real
                stderr=None,  # Mostrar errores en tiempo real
                text=True,
                bufsize=1,
            )
            self.processes["dashboard"] = process
            time.sleep(4)

            if process.poll() is None:
                print_service_ready("DASHBOARD", "http://localhost:8501")
            else:
                print_error("DASHBOARD", "Proceso terminó inesperadamente")
                return False
        except Exception as e:
            print_error("DASHBOARD", str(e))
            return False
        
        return True
    
    def print_status(self):
        """Imprime estado de todos los servicios."""
        print(f"\n{Colors.BOLD}{Colors.CYAN}📊 Estado de servicios:{Colors.ENDC}")
        
        for name, process in self.processes.items():
            status = "🟢 RUNNING" if process.poll() is None else "🔴 STOPPED"
            print(f"  {name:20} {status}")
        
        print(f"\n{Colors.YELLOW}Para detener: Presiona Ctrl+C{Colors.ENDC}\n")
    
    def monitor_processes(self):
        """Monitorea que los procesos sigan corriendo."""
        while self.running:
            try:
                # Verificar que ningún proceso se ha detenido
                for name, process in self.processes.items():
                    if process.poll() is not None:
                        print(f"\n{Colors.RED}⚠️ {name} se detuvo inesperadamente{Colors.ENDC}")
                        # Reintentar iniciar
                        print(f"{Colors.YELLOW}Reiniciando {name}...{Colors.ENDC}")
                        self._restart_service(name)
                
                time.sleep(5)
            
            except KeyboardInterrupt:
                break
    
    def _restart_service(self, service_name):
        """Reinicia un servicio."""
        try:
            if service_name == "telegram_bot":
                self.start_telegram_bot()
            elif service_name == "scheduler":
                self.start_scheduler()
            elif service_name == "dashboard":
                self.start_dashboard()
        except Exception as e:
            print(f"{Colors.RED}Error reiniciando {service_name}: {e}{Colors.ENDC}")
    
    def start_all(self):
        """Inicia todos los servicios."""
        print_header()
        
        # Verificaciones previas
        check_env_file()
        check_dependencies()
        
        print(f"{Colors.CYAN}Iniciando servicios...{Colors.ENDC}\n")
        
        # Iniciar en orden
        if not self.start_telegram_bot():
            print(f"{Colors.RED}No se pudo iniciar Telegram Bot. Abortando.{Colors.ENDC}")
            sys.exit(1)
        
        print()
        
        if not self.start_scheduler():
            print(f"{Colors.RED}No se pudo iniciar Scheduler. Abortando.{Colors.ENDC}")
            self._stop_all()
            sys.exit(1)
        
        print()
        
        if not self.start_dashboard():
            print(f"{Colors.RED}No se pudo iniciar Dashboard. Abortando.{Colors.ENDC}")
            self._stop_all()
            sys.exit(1)
        
        # Estado final
        print(f"\n{Colors.BOLD}{Colors.GREEN}✓ Todos los servicios iniciados correctamente{Colors.ENDC}")
        self.print_status()
        
        # Monitorear
        try:
            self.monitor_processes()
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Deteniendo servicios...{Colors.ENDC}")
            self._stop_all()
    
    def _stop_all(self):
        """Detiene todos los servicios."""
        self.running = False
        
        for name, process in self.processes.items():
            if process.poll() is None:
                print(f"  Deteniendo {name}...", end=" ")
                try:
                    process.terminate()
                    process.wait(timeout=5)
                    print(f"{Colors.GREEN}OK{Colors.ENDC}")
                except subprocess.TimeoutExpired:
                    print(f"  Forzando {name}...", end=" ")
                    process.kill()
                    print(f"{Colors.GREEN}OK{Colors.ENDC}")
        
        print(f"\n{Colors.GREEN}✓ Todos los servicios detenidos{Colors.ENDC}")


def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description="Investment Swarm Unified Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python run.py                    # Hora default 09:30
  python run.py --scheduler-time 10:00  # Hora custom
        """
    )
    parser.add_argument(
        "--scheduler-time",
        default="09:30",
        help="Hora de análisis diarios (formato HH:MM, default 09:30)"
    )
    
    args = parser.parse_args()
    
    # Validar formato de hora
    try:
        hour, minute = map(int, args.scheduler_time.split(":"))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError("Hora inválida")
    except ValueError:
        print(f"{Colors.RED}Error: Formato de hora inválido (usa HH:MM){Colors.ENDC}")
        sys.exit(1)
    
    # Iniciar launcher
    launcher = UnifiedLauncher(scheduler_time=args.scheduler_time)
    
    try:
        launcher.start_all()
    except Exception as e:
        print(f"{Colors.RED}Error fatal: {e}{Colors.ENDC}")
        launcher._stop_all()
        sys.exit(1)


if __name__ == "__main__":
    main()
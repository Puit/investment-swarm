"""
Script para ejecutar tests fácilmente.

Uso:
    python run_tests.py              # Todos los tests
    python run_tests.py --diagnose   # Solo diagnóstico
    python run_tests.py --suite      # Solo test suite
    python run_tests.py --verbose    # Con output detallado
"""

import sys
import subprocess
from pathlib import Path

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

def run_diagnose(verbose=False):
    """Ejecuta diagnóstico de Telegram."""
    print_header("🔍 Diagnóstico de Telegram Bot")
    
    cmd = [sys.executable, "tests/diagnose_telegram.py"]
    if verbose:
        cmd.append("--verbose")
    
    result = subprocess.run(cmd)
    return result.returncode == 0

def run_suite(verbose=False):
    """Ejecuta test suite."""
    print_header("🧪 Test Suite Completa")
    
    cmd = [sys.executable, "tests/test_suite.py"]
    if verbose:
        cmd.append("--verbose")
    
    result = subprocess.run(cmd)
    return result.returncode == 0

def run_pytest(verbose=False):
    """Ejecuta tests con pytest (si está instalado)."""
    print_header("🧪 Pytest (si está disponible)")
    
    cmd = [sys.executable, "-m", "pytest", "tests/", "-v" if verbose else ""]
    cmd = [c for c in cmd if c]  # Remover strings vacíos
    
    try:
        result = subprocess.run(cmd)
        return result.returncode == 0
    except Exception as e:
        print(f"{Colors.YELLOW}Pytest no disponible: {e}{Colors.ENDC}")
        return None

def main():
    """Función principal."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test Runner para Investment Swarm",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python run_tests.py              # Todos los tests
  python run_tests.py --diagnose   # Solo diagnóstico
  python run_tests.py --suite      # Solo test suite
  python run_tests.py --verbose    # Con output detallado
        """
    )
    parser.add_argument("--diagnose", action="store_true", 
                       help="Ejecutar solo diagnóstico")
    parser.add_argument("--suite", action="store_true",
                       help="Ejecutar solo test suite")
    parser.add_argument("--pytest", action="store_true",
                       help="Ejecutar solo pytest")
    parser.add_argument("--verbose", action="store_true",
                       help="Output detallado")
    
    args = parser.parse_args()
    
    results = {}
    
    # Determinar qué ejecutar
    if args.diagnose:
        results["diagnose"] = run_diagnose(args.verbose)
    elif args.suite:
        results["suite"] = run_suite(args.verbose)
    elif args.pytest:
        results["pytest"] = run_pytest(args.verbose)
    else:
        # Ejecutar todos
        results["diagnose"] = run_diagnose(args.verbose)
        results["suite"] = run_suite(args.verbose)
        # Intentar pytest (opcional)
        pytest_result = run_pytest(args.verbose)
        if pytest_result is not None:
            results["pytest"] = pytest_result
    
    # Resumen
    print_header("📊 Resumen de resultados")
    
    all_passed = True
    for test_type, passed in results.items():
        if passed is None:
            status = f"{Colors.YELLOW}⊘ SKIPPED{Colors.ENDC}"
        elif passed:
            status = f"{Colors.GREEN}✓ PASSED{Colors.ENDC}"
        else:
            status = f"{Colors.RED}✗ FAILED{Colors.ENDC}"
            all_passed = False
        
        print(f"{test_type:15} {status}")
    
    print()
    
    if all_passed and None not in results.values():
        print(f"{Colors.GREEN}{Colors.BOLD}✓ TODOS LOS TESTS PASARON{Colors.ENDC}\n")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ ALGUNOS TESTS FALLARON{Colors.ENDC}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
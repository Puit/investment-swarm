"""Test con la libreria oficial trading212-rest."""
import os
from dotenv import load_dotenv
load_dotenv()

secret = (
    os.getenv("T212_API_SECRET_PAPER_TRADING")
    or os.getenv("T212_API_SECRET")
    or ""
)
print(f"Secret: {len(secret)} chars, '{secret[:6]}...{secret[-4:]}'")
print()

# Demo (cuenta practica)
print("--- Probando modo DEMO (practica) ---")
try:
    from trading212_rest import Trading212
    client = Trading212(api_key=secret, demo=True)
    info = client.account_info()
    print(f"EXITO demo: {info}")
except Exception as e:
    print(f"ERROR demo: {type(e).__name__}: {e}")

print()

# Live (cuenta real)
print("--- Probando modo LIVE (real) ---")
try:
    from trading212_rest import Trading212
    client2 = Trading212(api_key=secret, demo=False)
    info2 = client2.account_info()
    print(f"EXITO live: {info2}")
except Exception as e:
    print(f"ERROR live: {type(e).__name__}: {e}")

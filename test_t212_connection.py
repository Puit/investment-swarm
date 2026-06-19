"""Test T212 - Basic Auth con Base64."""
import os, base64, requests
from dotenv import load_dotenv

load_dotenv()

secret = (
    os.getenv("T212_API_SECRET_PAPER_TRADING")
    or os.getenv("T212_API_SECRET")
    or ""
)
key_id = (
    os.getenv("T212_API_KEY_ID_PAPER_TRADING")
    or os.getenv("T212_API_KEY_ID")
    or ""
)

print(f"Key ID : {len(key_id)} chars, '{key_id[:8]}...'")
print(f"Secret : {len(secret)} chars, '{secret[:6]}...'")
print()

def b64(s): return base64.b64encode(s.encode()).decode()

# Variaciones de Basic Auth que podria usar T212
variants = [
    ("Basic base64(key_id:secret)",  {"Authorization": f"Basic {b64(key_id + ':' + secret)}"}),
    ("Basic base64(:secret)",        {"Authorization": f"Basic {b64(':' + secret)}"}),
    ("Basic base64(secret:)",        {"Authorization": f"Basic {b64(secret + ':')}"}),
    ("Basic base64(secret)",         {"Authorization": f"Basic {b64(secret)}"}),
    ("Bearer key_id:secret",         {"Authorization": f"Bearer {key_id}:{secret}"}),
    ("Raw secret (previo)",          {"Authorization": secret}),
]

for base_url, label in [
    ("https://demo.trading212.com/api/v0", "DEMO"),
    ("https://live.trading212.com/api/v0", "LIVE"),
]:
    url = f"{base_url}/equity/account/info"
    print(f"=== {label} {url} ===")
    for v_label, headers in variants:
        try:
            r = requests.get(url, headers=headers, timeout=8)
            body = r.text.strip()[:200] or "(vacio)"
            mark = "  *** EXITO ***" if r.status_code == 200 else ""
            print(f"  [{r.status_code}] {v_label}{mark}")
            if r.status_code != 401 or body != "(vacio)":
                print(f"         body: {body}")
        except Exception as e:
            print(f"  [ERR] {v_label}: {e}")
    print()

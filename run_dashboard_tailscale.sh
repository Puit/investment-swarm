#!/bin/bash

################################################################################
# LAUNCH DASHBOARD WITH TAILSCALE SUPPORT
#
# Este script:
# 1. Verifica que Tailscale esté instalado y conectado
# 2. Obtiene tu IP de Tailscale
# 3. Lanza el dashboard en esa IP para que sea accesible desde cualquier lugar
# 4. Muestra un link y QR para acceder desde el móvil
#
# Requisitos previos:
#   - Tailscale instalado: curl -fsSL https://tailscale.com/install.sh | sh
#   - Conectado a Tailscale: sudo tailscale up
#
# Uso:
#   bash run_dashboard_tailscale.sh
#
# O para lanzar en background:
#   nohup bash run_dashboard_tailscale.sh > dashboard.log 2>&1 &
################################################################################

set -e

echo "📱 Investment Swarm - Paper Trading Dashboard with Tailscale"
echo "================================================================"
echo ""

# ── Verificar Tailscale instalado ──
if ! command -v tailscale &> /dev/null; then
    echo "❌ Tailscale no está instalado."
    echo ""
    echo "Para instalarlo, ejecuta:"
    echo "  curl -fsSL https://tailscale.com/install.sh | sh"
    echo ""
    echo "Luego conecta:"
    echo "  sudo tailscale up"
    exit 1
fi

echo "✅ Tailscale encontrado"

# ── Verificar que está conectado ──
if ! sudo tailscale status &> /dev/null; then
    echo "❌ Tailscale no está conectado."
    echo ""
    echo "Conéctate con:"
    echo "  sudo tailscale up"
    exit 1
fi

echo "✅ Tailscale conectado"
echo ""

# ── Obtener IP de Tailscale ──
TAILSCALE_IP=$(sudo tailscale ip -4)

if [ -z "$TAILSCALE_IP" ]; then
    echo "❌ No se pudo obtener la IP de Tailscale"
    exit 1
fi

echo "🔗 Tu IP de Tailscale: $TAILSCALE_IP"
echo ""

# ── Verificar que el dashboard y el motor existen ──
if [ ! -f "dashboard.py" ]; then
    echo "❌ dashboard.py no encontrado en el directorio actual"
    echo "   Ejecuta esto desde /home/claude o /mnt/user-data/outputs"
    exit 1
fi

if [ ! -f "paper_trading_engine.py" ]; then
    echo "❌ paper_trading_engine.py no encontrado en el directorio actual"
    echo "   Cópia ambos archivos desde /mnt/user-data/outputs"
    exit 1
fi

echo "✅ Archivos encontrados"
echo ""

# ── Verificar que Streamlit está instalado ──
if ! python3 -c "import streamlit" 2>/dev/null; then
    echo "⚠️  Streamlit no está instalado. Instalando..."
    pip install streamlit --break-system-packages
fi

echo "✅ Streamlit listo"
echo ""

# ── Puerto (usar 8501 por defecto, o dejar que elija Streamlit) ──
PORT=8501

echo "🚀 Lanzando dashboard en http://$TAILSCALE_IP:$PORT"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📱 ACCEDE DESDE TU MÓVIL:"
echo ""
echo "   🔗 URL: http://$TAILSCALE_IP:$PORT"
echo ""
echo "   Copia este link en el navegador de tu móvil (debe estar en Tailscale)"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Presiona Ctrl+C para detener el dashboard"
echo ""
echo "💡 Tip: Si quieres lanzar en background, usa:"
echo "   nohup bash run_dashboard_tailscale.sh > dashboard.log 2>&1 &"
echo ""

# ── Lanzar Streamlit en la IP de Tailscale ──
streamlit run dashboard.py \
    --server.address="$TAILSCALE_IP" \
    --server.port=$PORT \
    --logger.level=info
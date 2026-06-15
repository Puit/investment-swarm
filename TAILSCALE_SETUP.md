# 📱 GUÍA: ACCEDER AL DASHBOARD DESDE EL TELÉFONO CON TAILSCALE

Josep, esta guía te explica cómo tener el dashboard accesible desde tu móvil (o cualquier dispositivo) esté donde esté.

## ¿Qué es Tailscale?

**Tailscale** es una VPN moderna construida sobre WireGuard. Permite conectar dispositivos de forma segura sin exponer puertos públicos. Es ideal para esto:
- Segura (tráfico encriptado)
- Rápida (WireGuard, muy eficiente)
- Fácil (no necesita configurar routers, firewalls, etc.)
- Gratis para uso personal (hasta 3 dispositivos)

---

## PASO 1: Instalar Tailscale en tu PC/Servidor

### En Windows (WSL2):

Si tienes WSL2 en Windows y quieres acceder desde ahí:

```powershell
# Abre una terminal PowerShell como administrador
wsl --install

# Dentro de WSL (Linux):
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Se abrirá un navegador pidiendo que inicies sesión. Completa el login (puedes usar Google, GitHub, etc.)

### En Linux nativo:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

### En macOS (si lo usas):

```bash
brew install tailscale
sudo tailscale up
```

**Qué sucede**: Se te pide que inicies sesión. Abre el link que aparece, completa el login, y automáticamente se conecta a tu red Tailscale.

---

## PASO 2: Verificar que Tailscale está conectado

```bash
sudo tailscale ip -4
```

Deberías ver una IP algo como `100.70.150.200` (el rango 100.64.0.0/10 es reservado para Tailscale).

Anota esta IP — la necesitarás luego.

---

## PASO 3: Lanzar el dashboard con Tailscale

Desde el directorio donde están `dashboard.py` y `paper_trading_engine.py`:

```bash
bash run_dashboard_tailscale.sh
```

Si no tienes el script, créalo manualmente:

```bash
chmod +x run_dashboard_tailscale.sh  # hacerlo ejecutable
bash run_dashboard_tailscale.sh
```

El script:
1. Verifica que Tailscale esté conectado
2. Obtiene tu IP de Tailscale
3. Lanza Streamlit escuchando en esa IP
4. Te muestra el link para acceder desde el móvil

Verás algo como:

```
🚀 Lanzando dashboard en http://100.70.150.200:8501

📱 ACCEDE DESDE TU MÓVIL:

   🔗 URL: http://100.70.150.200:8501

   Copia este link en el navegador de tu móvil
```

---

## PASO 4: Instalar Tailscale en tu teléfono

### iPhone (App Store):

1. Abre App Store
2. Busca **"Tailscale"**
3. Instala la app oficial de Tailscale, Inc.
4. Abre la app
5. Toca **"Sign in with Google"** (o tu proveedor)
6. Usa la MISMA CUENTA que usaste en el PC

### Android (Google Play):

1. Abre Google Play
2. Busca **"Tailscale"**
3. Instala la app oficial
4. Abre la app
5. Toca **"Sign in"** y elige tu proveedor
6. Usa la MISMA CUENTA que en el PC

**Importante**: Debe estar la VPN Tailscale **ACTIVADA** (verás un icono de llave en la barra de estado del teléfono).

---

## PASO 5: Acceder al dashboard desde el móvil

Una vez que:
1. ✅ Tailscale está corriendo en tu PC (el script sigue ejecutándose)
2. ✅ Tailscale está conectado en tu móvil (VPN activada)
3. ✅ Ambos usan la misma cuenta

Abre el navegador del móvil y escribe la URL que el script te mostró:

```
http://100.70.150.200:8501
```

(Reemplaza `100.70.150.200` con TU IP de Tailscale)

¡Listo! Deberías ver el dashboard completo.

---

## 🔄 FUNCIONAMIENTO EN BACKGROUND

Si quieres que el dashboard siga corriendo cuando cierres la terminal:

```bash
# En Linux/WSL:
nohup bash run_dashboard_tailscale.sh > dashboard.log 2>&1 &

# Ver el PID y log:
tail -f dashboard.log

# Detener:
pkill -f "streamlit run dashboard.py"
```

O usa **screen** / **tmux** para una sesión persistente:

```bash
screen -S dashboard
bash run_dashboard_tailscale.sh
# Presiona Ctrl+A, luego D para desconectar (sigue corriendo)

# Reconectar después:
screen -r dashboard
```

---

## ⚙️ CONFIGURACIÓN AVANZADA (opcional)

### Usar otro puerto

Si 8501 no te va bien, edita `run_dashboard_tailscale.sh`:

```bash
PORT=9999  # cambia aquí
```

### Acceso sin Tailscale (solo en red local)

Si quieres acceder solo desde tu WiFi casera (sin VPN):

```bash
streamlit run dashboard.py --server.address=0.0.0.0 --server.port=8501
```

Luego abre `http://<IP_LOCAL_DE_TU_PC>:8501` desde el móvil (misma WiFi).

**Advertencia**: Esto expone el dashboard en tu red local. Si compartes WiFi con otros, es menos seguro.

### Acceso público (NO recomendado, pero posible)

Si quieres un dashboard público en internet (ej: compartir con amigos):

```bash
streamlit run dashboard.py --server.address=0.0.0.0 --server.port=8501
```

Luego expón tu IP pública en el router, pero **protege con contraseña**. Streamlit no tiene auth nativa — necesitarías un proxy (nginx + HTTP basic auth) o usar Heroku/Railway.

---

## 🆘 TROUBLESHOOTING

### "Tailscale no está instalado"

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

### "Tailscale no está conectado"

```bash
sudo tailscale up
```

Sigue el link que aparece y completa el login.

### "No puedo acceder desde el móvil"

Checklist:
- ✅ ¿El script sigue corriendo en el PC? (`tail -f dashboard.log`)
- ✅ ¿Tailscale está activado en el móvil? (busca el icono 🔑 en la barra de estado)
- ✅ ¿Usaste la MISMA CUENTA en PC y móvil?
- ✅ ¿Copiaste bien la IP? (no confundas `100.x.x.x` de Tailscale con `192.168.x.x` del router)
- ✅ ¿El puerto es 8501 o lo cambiaste?

Si siguen problemas:

```bash
# En el PC, verifica tu IP de Tailscale:
sudo tailscale ip -4

# En el móvil, verifica conectividad:
ping 100.70.150.200  # (reemplaza con tu IP)
```

### "Lento / conexión intermitente"

Tailscale optimiza automáticamente la ruta (directo si está en la misma red, relay si no). Si va muy lento:
- Cierra el dashboard y vuelve a abrirlo
- Reinicia Tailscale en ambos dispositivos
- Verifica que no hay bloqueos de firewall

---

## 📊 PRÓXIMOS PASOS

Una vez que el dashboard esté accesible:

1. **Prueba desde el móvil**: añade tickers, escanea, mira posiciones
2. **Mejoras pendientes**:
   - Bot de Telegram (notificaciones de compras/ventas)
   - Gráficos interactivos en el dashboard
   - Alertas por correo / WhatsApp
   
¿Necesitas ayuda con algo de esto?

---

## 💡 TIPS DE SEGURIDAD

- **Tailscale es seguro**: tráfico encriptado, solo tú y tus dispositivos pueden acceder
- **Cuidado con contraseñas**: el dashboard no tiene autenticación nativa (confía en Tailscale)
- **VPN pública**: si usas WiFi pública, Tailscale es especialmente seguro

---

¡Listo! Ahora tienes tu bot de inversión accesible desde cualquier lugar. 🚀
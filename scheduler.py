import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from pytz import timezone
import json

from config import (
    MARKET_TIMEZONE,
    ANALYSIS_START_TIME,
    PRE_MARKET_TIME,
    MARKET_OPEN_TIME,
    POSITION_REVIEW,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Scheduler")


class AnalysisScheduler:
    """
    Orquesta la ejecución de análisis y órdenes a horas específicas
    
    WORKFLOW DÍA 1:
    08:00 → Búsqueda completa y ranking
    
    WORKFLOW DÍA 2:
    08:45 → Reconfirma top 5
    09:31 → Ejecuta compra
    
    DIARIAMENTE:
    16:00 → Revisión de posiciones (¿vender?)
    """

    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone=timezone(MARKET_TIMEZONE))
        self.tz = timezone(MARKET_TIMEZONE)

    def start(self,
        search_callback=None,
        confirm_callback=None,
        execute_callback=None,
        review_callback=None,
    ):
        """
        Inicia el scheduler con callbacks para cada tarea
        
        Args:
            search_callback: función que ejecuta búsqueda (día 1)
            confirm_callback: función que confirma candidatos (día 2, pre-market)
            execute_callback: función que ejecuta compras (día 2, market open)
            review_callback: función que revisa posiciones (diariamente)
        """

        # ── DÍA 1 - BÚSQUEDA COMPLETA ──
        # Lunes a Viernes a las 08:00 (antes de apertura)
        if search_callback:
            self.scheduler.add_job(
                func=search_callback,
                trigger=CronTrigger(hour=8, minute=0, day_of_week="0-4", timezone=self.tz),
                id="daily_search",
                name="Búsqueda completa de candidatos",
                misfire_grace_time=600,
            )
            logger.info("📅 Job programado: Búsqueda diaria 08:00")

        # ── DÍA 2 - CONFIRMACIÓN PRE-MARKET ──
        # Lunes a Viernes a las 08:45 (45 min antes de apertura)
        if confirm_callback:
            self.scheduler.add_job(
                func=confirm_callback,
                trigger=CronTrigger(hour=8, minute=45, day_of_week="0-4", timezone=self.tz),
                id="premarket_confirm",
                name="Confirmación pre-market de candidatos",
                misfire_grace_time=300,
            )
            logger.info("📅 Job programado: Confirmación pre-market 08:45")

        # ── DÍA 2 - EJECUCIÓN DE COMPRAS ──
        # Lunes a Viernes a las 09:31 (1 min después de apertura)
        if execute_callback:
            self.scheduler.add_job(
                func=execute_callback,
                trigger=CronTrigger(hour=9, minute=31, day_of_week="0-4", timezone=self.tz),
                id="market_open_execute",
                name="Ejecución de compras al abrir mercado",
                misfire_grace_time=300,
            )
            logger.info("📅 Job programado: Ejecución de órdenes 09:31")

        # ── DIARIAMENTE - REVISIÓN DE POSICIONES ──
        # Lunes a Viernes a las 16:00 (al cierre del mercado)
        if review_callback and POSITION_REVIEW.get("enabled"):
            self.scheduler.add_job(
                func=review_callback,
                trigger=CronTrigger(hour=16, minute=0, day_of_week="0-4", timezone=self.tz),
                id="daily_position_review",
                name="Revisión de posiciones abiertas",
                misfire_grace_time=300,
            )
            logger.info("📅 Job programado: Revisión de posiciones 16:00")

        self.scheduler.start()
        logger.info("✅ Scheduler iniciado")

    def stop(self):
        """Detiene el scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("🛑 Scheduler detenido")

    def get_next_jobs(self, limit: int = 5) -> list:
        """Retorna próximos jobs a ejecutarse"""
        jobs = []
        for job in self.scheduler.get_jobs()[:limit]:
            next_run = job.next_run_time
            jobs.append({
                "name": job.name,
                "next_run": next_run.isoformat() if next_run else "No programado",
                "id": job.id,
            })
        return jobs

    def get_scheduler_status(self) -> dict:
        """Retorna estado del scheduler"""
        return {
            "running": self.scheduler.running,
            "timezone": str(self.tz),
            "jobs": len(self.scheduler.get_jobs()),
            "next_jobs": self.get_next_jobs(),
        }


# ── FUNCIONES HELPER ──

def is_market_open() -> bool:
    """Verifica si el mercado está abierto"""
    now = datetime.now(timezone(MARKET_TIMEZONE))
    weekday = now.weekday()  # 0=Monday, 4=Friday
    hour = now.hour
    minute = now.minute

    # Fuera de lunes-viernes
    if weekday >= 5:
        return False

    # Fuera de horario (09:30 - 16:00)
    time_minutes = hour * 60 + minute
    open_minutes = 9 * 60 + 30  # 09:30
    close_minutes = 16 * 60  # 16:00

    return open_minutes <= time_minutes < close_minutes


def get_time_until_market_open() -> str:
    """Retorna tiempo hasta apertura del mercado"""
    now = datetime.now(timezone(MARKET_TIMEZONE))
    weekday = now.weekday()

    # Si es fin de semana, apertura es el lunes a las 09:30
    if weekday >= 5:
        days_until_monday = 7 - weekday
        return f"{days_until_monday} días"

    # Si es entre semana
    open_time = now.replace(hour=9, minute=30, second=0, microsecond=0)

    if now < open_time:
        diff = open_time - now
        hours = diff.total_seconds() // 3600
        minutes = (diff.total_seconds() % 3600) // 60
        return f"{int(hours)}h {int(minutes)}m"
    else:
        # Mercado ya cerró hoy, apertura es mañana
        return "Mañana a las 09:30"


def log_scheduler_info():
    """Registra información del scheduler para debugging"""
    tz = timezone(MARKET_TIMEZONE)
    now = datetime.now(tz)
    logger.info(f"⏰ Hora actual (ET): {now.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"🔄 Mercado abierto: {is_market_open()}")
    logger.info(f"⏳ Apertura en: {get_time_until_market_open()}")
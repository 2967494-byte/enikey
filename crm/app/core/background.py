from apscheduler.schedulers.background import BackgroundScheduler
from app.core.database import SessionLocal
from app.core.models import Project, ProjectType
from app.core.executor import CommandExecutor
from app.core.scheduler_engine import SchedulerEngine

scheduler = BackgroundScheduler()

def daily_maintenance_job():
    """Фоновая задача, проверяющая регламенты раз в сутки"""
    db = SessionLocal()
    try:
        # 1. Process project triggers (SSL, mileage, servers)
        projects = db.query(Project).all()
        for p in projects:
            CommandExecutor._process_project_triggers(p, db)
        db.commit()

        # 2. Recalculate schedule
        SchedulerEngine.run(db)
    except Exception as e:
        print(f"[Daily Maintenance Error]: {e}")
    finally:
        db.close()

def start_background_tasks():
    if not scheduler.running:
        scheduler.add_job(daily_maintenance_job, 'cron', hour=3, minute=0, id="daily_maintenance", replace_existing=True)
        scheduler.start()
        print("APScheduler started: daily maintenance job registered.")

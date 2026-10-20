from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
from app.core.seed import seed_initial_data
from app.core.background import start_background_tasks
from app.routers import web, api

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables and seed
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        from sqlalchemy import text
        try:
            conn.execute(text("ALTER TABLE projects ADD COLUMN category_slug VARCHAR(50)"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN is_urgent BOOLEAN DEFAULT 0"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("UPDATE projects SET category_slug = 'auto' WHERE category_slug = 'auto_loan' AND project_type = 'AUTO'"))
            conn.execute(text("UPDATE projects SET category_slug = 'loan' WHERE category_slug = 'auto_loan' AND project_type = 'LOAN'"))
            conn.commit()
        except Exception:
            pass
    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()

    # Start background scheduler
    start_background_tasks()
    yield
    # Shutdown logic if any

app = FastAPI(
    title="Персональная система управления «Второй Мозг» (Personal ERP / CRM)",
    description="Единый шлюз команд (Command Bus), детерминированные алгоритмы и задел под ИИ и iOS.",
    version="1.0.0",
    docs_url=f"{settings.APP_PREFIX}/docs",
    redoc_url=f"{settings.APP_PREFIX}/redoc",
    openapi_url=f"{settings.APP_PREFIX}/openapi.json",
    lifespan=lifespan
)

# Root redirect to prefix
if settings.APP_PREFIX:
    @app.get("/")
    def redirect_to_prefix():
        return RedirectResponse(url=f"{settings.APP_PREFIX}/")

# Include Routers with APP_PREFIX
app.include_router(web.router, prefix=settings.APP_PREFIX)
app.include_router(api.router, prefix=settings.APP_PREFIX)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

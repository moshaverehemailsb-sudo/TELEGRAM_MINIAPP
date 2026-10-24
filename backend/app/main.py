from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .routers import admin, advisor, links, student

settings = get_settings()

if settings.allow_dev_auth and settings.is_production:
    raise RuntimeError("ALLOW_DEV_AUTH must be false when APP_ENV=production.")

# backend/app/main.py -> project root -> frontend/
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(
    title="Konkur Analysis API",
    version="0.1.0",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
)

app.include_router(student.router)
app.include_router(links.router)
app.include_router(advisor.router)
app.include_router(admin.router)


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok"}


# Mounted last so that /api routes are matched first.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
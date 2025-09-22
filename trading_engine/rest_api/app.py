from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from pathlib import Path

from .routes import router

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

def create_app(engine) -> FastAPI:
    """
    Fastapi app, receives engine instance when created
    """
    app = FastAPI(title="Trading Engine UI")
    app.state.engine = engine
    app.state.templates = templates
    app.include_router(router)

    return app

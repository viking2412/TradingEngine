from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from pathlib import Path

from .routes import router

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

def create_app(engine) -> FastAPI:
    """
    Фабрика FastAPI-додатку, отримує engine при створенні.
    """
    app = FastAPI(title="Trading Engine UI")

    # збережемо engine в app.state
    app.state.engine = engine
    app.state.templates = templates

    # підключаємо маршрути
    app.include_router(router)

    return app

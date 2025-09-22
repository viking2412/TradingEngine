from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    engine = request.app.state.engine
    templates = request.app.state.templates

    position = engine.order_manager.position if engine.order_manager.position else {}

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "position": position,
            "running": engine.running,
        }
    )

@router.get("/position")
async def get_position(request: Request):
    engine = request.app.state.engine
    return engine.order_manager.position if engine.order_manager.position else {}

@router.post("/config/reload")
async def reload_config(request: Request):
    engine = request.app.state.engine
    await engine.reload_config()
    return {"status": "reloaded"}

@router.post("/stop")
async def stop_engine(request: Request):
    engine = request.app.state.engine
    engine.running = False
    return {"status": "stopping"}

from fastapi import FastAPI

def create_rest_api(order_manager, position_manager):
    """Return FastAPI app for monitoring engine status"""
    app = FastAPI()

    @app.get("/status")
    async def status():
        return {
            "position": position_manager.position,
            "grid_orders": order_manager.grid_orders,
            "tp_orders": order_manager.tp_orders,
        }

    return app

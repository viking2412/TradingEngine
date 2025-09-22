import argparse
import asyncio

from .utility import logger,load_env, load_config
from .engine import TradingEngine

async def main_async(config_path: str):

    cfg = load_config(config_path)
    api_key, api_secret = load_env(cfg.account.split("/")[0])
    engine = TradingEngine(cfg, api_key, api_secret)

    loop = asyncio.get_event_loop()
    stop = asyncio.Event()
    TradingEngine.setup_graceful_shutdown(loop, stop)

    runner = asyncio.create_task(engine.run())
    try:
        await stop.wait()
    finally:
        logger.info("Shutting down...")
        engine.running = False
        runner.cancel()
        try:
            await runner
        except asyncio.CancelledError:
            pass
        await engine.shutdown()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to trade config JSON")
    args = parser.parse_args()
    asyncio.run(main_async(args.config))

import argparse
import asyncio

from trading_engine.logging import logger
from .config import load_env, load_config
from .engine import TradingEngine

async def main_async(config_path: str):
    logger.info('Starting trading engine...')
    api_key, api_secret = load_env()
    cfg = load_config(config_path)
    logger.info('Config loaded successfully.')
    engine = TradingEngine(cfg, api_key, api_secret)
    await engine.run()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to trade config JSON")
    args = parser.parse_args()
    asyncio.run(main_async(args.config))

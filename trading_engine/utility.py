import asyncio
import logging
import os
import json
from dotenv import load_dotenv
from .models import TradeConfig


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger('engine')

async def safe_sleep(seconds):
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        raise


def load_env(exchange: str):
    """Load API keys from .env"""
    load_dotenv()
    logger.info(f'Loading API keys from {exchange}_API_KEY')
    return os.getenv(f"{exchange}_API_KEY"), os.getenv(f"{exchange}_API_SECRET")

def load_config(path: str) -> TradeConfig:
    """Load trade configuration from JSON file"""
    try:
        with open(path, "r") as f:
            j = json.load(f)
            return TradeConfig.from_dict(j)
    except FileNotFoundError:
        raise FileNotFoundError(f"File {path} not found.")
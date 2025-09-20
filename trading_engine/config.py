import os
import json
from dotenv import load_dotenv
from .models import TradeConfig

def load_env():
    """Load API keys from .env"""
    load_dotenv()
    return os.getenv("API_KEY"), os.getenv("API_SECRET")

def load_config(path: str) -> TradeConfig:
    """Load trade configuration from JSON file"""
    try:
        with open(path, "r") as f:
            j = json.load(f)
            return TradeConfig.from_dict(j)
    except FileNotFoundError:
        raise FileNotFoundError(f"File {path} not found.")
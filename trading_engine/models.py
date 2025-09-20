from dataclasses import dataclass
from typing import List, Dict

@dataclass
class TPOrderConfig:
    price_percent: float
    quantity_percent: float

@dataclass
class LimitGridConfig:
    range_percent: float
    orders_count: int
    engine_deal_duration_minutes: int

@dataclass
class TradeConfig:
    account: str
    symbol: str
    side: str
    market_order_amount: float
    stop_loss_percent: float
    trailing_sl_offset_percent: float
    limit_orders_amount: float
    leverage: float
    move_sl_to_breakeven: bool
    tp_orders: List[TPOrderConfig]
    limit_orders: LimitGridConfig

    @staticmethod
    def from_dict(d: Dict):
        """Convert dict from JSON into TradeConfig instance"""
        tp_orders = [d['tp_orders']]
        limit_orders = d['limit_orders']
        return TradeConfig(
            account=d['account'],
            symbol=d['symbol'],
            side=d['side'],
            market_order_amount=d['market_order_amount'],
            stop_loss_percent=d['stop_loss_percent'],
            trailing_sl_offset_percent=d['trailing_sl_offset_percent'],
            limit_orders_amount=d['limit_orders_amount'],
            leverage=d['leverage'],
            move_sl_to_breakeven=d['move_sl_to_breakeven'],
            tp_orders=tp_orders,
            limit_orders=limit_orders,
        )
from .exchange import ExchangeConnector
from .logging import logger
from .models import TradeConfig
from .monitor import Monitor
from .orders import OrderManager
from .position import PositionManager


class TradingEngine:
    """Main engine tying together exchange, orders, position, monitor."""

    def __init__(self, config: TradeConfig, api_key, api_secret):
        self.config = config
        self.api_key = api_key
        self.api_secret = api_secret
        self.exchange = ExchangeConnector(config, api_key, api_secret).exchange
        self.order_manager = OrderManager(exchange=self.exchange, config=self.config)
        self.position_manager = PositionManager(exchange=self.exchange, config=self.config)
        self.monitor_loop = Monitor(exchange=self.exchange, config=self.config)
        # TODO: init ExchangeConnector, OrderManager, PositionManager, Monitor

    # async def run(self):
    #     """Start engine: connect, place initial orders, launch monitor"""
    #     ExchangeConnector(self.config, self.api_key, self.api_secret)
    #     symbol = self.config.symbol
    #     print(symbol)
    #     pass

    async def run(self):
        await self.connect()

        # Place initial market order
        market_ord = await self.order_manager.place_initial_market()
        # compute average entry
        await safe_sleep(1.0)
        pos = await self.position_manager.compute_average_entry()
        if pos is None:
            # attempt to infer from market order
            if market_ord:
                # simplified: entry price from order info
                price = float(market_ord.get('average') or market_ord.get('price') or 0)
                amount = float(market_ord.get('filled', 0) or market_ord.get('amount', 0))
                if amount > 0 and price > 0:
                    self.position_manager.position = {'size': amount, 'entry_price': price}

        if not self.position_manager.position:
            logger.error('No position found; aborting')
            return

        # Place TP orders based on average
        await self.order_manager.place_tp_orders(self.position_manager.position['entry_price'])

        # Build limit grid to average
        await self.order_manager.build_limit_grid(self.position_manager.position['entry_price'])

        # Start monitor loop concurrently
        monitor_task = asyncio.create_task(self.monitor_loop())

        # If REST available, run uvicorn in background
        if REST_AVAILABLE:
            import uvicorn
            config = uvicorn.Config(self.rest_app, host='0.0.0.0', port=8000, log_level='info')
            server = uvicorn.Server(config)
            rest_task = asyncio.create_task(server.serve())
        else:
            rest_task = None

        # wait for monitor to finish
        try:
            await monitor_task
        finally:
            if rest_task:
                rest_task.cancel()
            await self.shutdown()

    async def shutdown(self):
        try:
            if self.exchange:
                await self.exchange.close()
        except Exception:
            pass

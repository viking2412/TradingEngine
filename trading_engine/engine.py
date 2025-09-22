import asyncio
import signal
import sys

from .exchange import ExchangeConnector
from .utility import logger, safe_sleep
from .models import TradeConfig
from .orders import OrderManager
from .rest_api.app import create_app

try:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    REST_AVAILABLE = True
except Exception:
    REST_AVAILABLE = False

class TradingEngine:
    """Main engine tying together exchange, orders, position, monitor."""

    def __init__(self, config: TradeConfig, api_key, api_secret):
        self.config = config
        self.api_key = api_key
        self.api_secret = api_secret
        self.running = False
        #self.rest_app = FastAPI() if REST_AVAILABLE else None
        self._server = None
        #if self.rest_app:
            #self._setup_rest()
        self.exchange_connector = ExchangeConnector(config, api_key, api_secret)
        self.order_manager = OrderManager(exchange=self.exchange_connector.exchange, config=self.config)

    async def run(self):
        await self.exchange_connector.connect()

        # Place initial market order
        market_ord = await self.order_manager.place_initial_market()
        # compute average entry
        await safe_sleep(2.0)
        pos = await self.order_manager.compute_average_entry()
        logger.info(f'Computed position: {pos}')
        if pos is None:
            logger.info("No position found")
            # attempt to infer from market order
            if market_ord:
                # simplified: entry price from order info
                price = float(market_ord.get('average') or market_ord.get('price') or 0)
                amount = float(market_ord.get('filled', 0) or market_ord.get('amount', 0))
                if amount > 0 and price > 0:
                    self.order_manager.position = {'size': amount, 'entry_price': price}

        if not self.order_manager.position:
            logger.error('No position found; aborting')
            return
        # Place SL orders according to config
        await self.order_manager.update_stop_loss(self.order_manager.position)
        # Place TP orders based on average
        await self.order_manager.place_tp_orders(self.order_manager.position)
        # Build limit grid to average
        await self.order_manager.build_limit_grid(self.order_manager.position['entry_price'])

        # Start monitor loop concurrently
        monitor_task = asyncio.create_task(self.monitor_loop())

        # If REST available, run uvicorn in background
        if REST_AVAILABLE:
            import uvicorn
            rest_app = create_app(self)
            config = uvicorn.Config(rest_app, host='127.0.0.1', port=8000, log_level='info', loop="asyncio")
            self._server = uvicorn.Server(config)
            rest_task = asyncio.create_task(self._server.serve())
        else:
            rest_task = None

        try:
            await monitor_task
        finally:
            if rest_task:
                self._server.should_exit = True
                await rest_task
            await self.shutdown()

    async def _on_trade_exit(self, reason: str = "TP/SL"):
        """Cleanup when a trade is completed (TP or SL hit)."""
        logger.info(f"Trade exit triggered due to {reason}")

        try:

            open_orders = await self.exchange_connector.exchange.fetch_open_orders(self.config.symbol)
            for o in open_orders:
                try:
                    await self.exchange_connector.exchange.cancel_order(o['id'], self.config.symbol)
                    logger.info("Cancelled order %s", o['id'])
                except Exception as e:
                    logger.warning("Failed to cancel order %s: %s", o['id'], e)
        except Exception as e:
            logger.warning(f"Unable to open/close orders: {e}")

        self.order_manager.tp_order_ids.clear()
        self.order_manager.grid_order_ids.clear()

        self.running = False
        logger.info("Trading engine stopped after exit.")

    async def monitor_loop(self, poll_interval: float = 5.0):
        """Main monitor loop: polls orders/positions and reacts when grid orders fill.
        """
        logger.info('Starting monitor loop')
        self.running = True
        try:
            while self.running:
                # refresh open orders
                try:
                    orders = await self.exchange_connector.exchange.fetch_open_orders(self.config.symbol)
                    open_ids = {o['id']: o for o in orders}
                except Exception:
                    open_ids = {}
                # logger.info(f"open_ids: {open_ids}")
                # detect executed grid orders by checking known grid ids against open orders
                executed_grid = []

                for gid in list(self.order_manager.grid_order_ids):
                    if gid not in open_ids:
                        # order no longer open -> likely filled or cancelled. Fetch order to check
                        try:
                            completed = await self.exchange_connector.exchange.fetch_order(gid, self.config.symbol)
                            status = completed.get('status')
                            if status in ('closed', 'filled', 'canceled'):
                                logger.info('Grid order %s status %s', gid, status)
                                if status in ('closed', 'filled'):
                                    executed_grid.append(gid)
                                try:
                                    self.order_manager.grid_order_ids.remove(gid)
                                except ValueError:
                                    pass
                        except Exception:
                            # cannot fetch specific order; assume executed
                            executed_grid.append(gid)
                existing = True
                if executed_grid:
                    # recompute average and replace TP orders
                    logger.info('Detected executed grid orders: %s', executed_grid)
                    pos = await self.order_manager.compute_average_entry()
                    if pos:
                        tps = await self.order_manager.place_tp_orders(pos)
                        existing = False
                        if tps:
                            logger.info('All TP orders placed successfully')
                            existing = True
                # for tid in list(self.order_manager.tp_order_ids):
                #     if tid in open_ids:
                #         existing = True
                if not existing:
                    try:
                        logger.info('TPs are filled; trade complete')
                        await self._on_trade_exit("TP")
                        return
                    except Exception:
                        pass

                # Check position instead of stop order ID
                try:
                    positions = await self.exchange_connector.exchange.fetch_positions([self.config.symbol])
                    pos_active = False
                    for pos in positions:
                        size = float(pos.get("contracts") or 0)
                        if size > 0:
                            pos_active = True
                            # Update SL if position exists
                            try:
                                await self.order_manager.update_stop_loss(pos)
                            except Exception as e:
                                logger.warning(f"Couldn't update SL: {e}")

                    if not pos_active:
                        logger.info("Position closed (SL or TP triggered)")
                        await self._on_trade_exit("SL/TP")
                        return
                except Exception as e:
                    logger.warning(f"Error during position check: {e}")

                await safe_sleep(poll_interval)
        except asyncio.CancelledError:
            logger.info('Monitor loop cancelled')
        finally:
            logger.info('Monitor loop ended')

    async def shutdown(self):
        logger.info("Shutting down TradingEngine...")
        self.running = False
        try:
            if hasattr(self, "exchange_connector") and self.exchange_connector.exchange:
                await self.exchange_connector.exchange.close()
                logger.info("Exchange connection closed")
        except Exception as e:
            logger.warning(f"Error closing exchange: {e}")

    def _setup_rest(self):
        @self.rest_app.get('/status')
        async def status():
            data = {
                'position': self.order_manager.position,
                'grid_orders': self.order_manager.grid_order_ids,
                'tp_orders': self.order_manager.tp_order_ids,
            }
            return JSONResponse(content=data)

    @staticmethod
    def setup_graceful_shutdown(loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event):
        def _sig():
            logger.info("Received stop signal")
            stop_event.set()
        # Linux/MacOS
        try:
            loop.add_signal_handler(signal.SIGINT, _sig)
            loop.add_signal_handler(signal.SIGTERM, _sig)
        except NotImplementedError:
            # Windows
            if sys.platform == "win32":
                def windows_sigint_handler(signum, frame):
                    _sig()
                    loop.stop()
                signal.signal(signal.SIGINT, windows_sigint_handler)
from trading_engine.logging import logger


class Monitor:
    """Polls exchange, detects fills, triggers TP/SL updates."""

    def __init__(self, exchange, order_manager, position_manager, config):
        self.exchange = exchange
        self.orders = order_manager
        self.position = position_manager
        self.config = config
        self.running = False

    async def monitor_loop(self, poll_interval: float = 5.0):
        """Main monitor loop: polls orders/positions and reacts when grid orders fill.
        """
        logger.info('Starting monitor loop')
        self.running = True
        try:
            while self.running:
                # refresh open orders
                try:
                    orders = await self.exchange.fetch_open_orders(self.config.symbol)
                    open_ids = {o['id']: o for o in orders}
                except Exception:
                    open_ids = {}

                # detect executed grid orders by checking known grid ids against open orders
                executed_grid = []
                for gid in list(self.grid_order_ids):
                    if gid not in open_ids:
                        # order no longer open -> likely filled or cancelled. Fetch order to check
                        try:
                            completed = await self.exchange.fetch_order(gid, self.config.symbol)
                            status = completed.get('status')
                            if status in ('closed', 'filled', 'canceled'):
                                logger.info('Grid order %s status %s', gid, status)
                                if status in ('closed', 'filled'):
                                    executed_grid.append(gid)
                                try:
                                    self.grid_order_ids.remove(gid)
                                except ValueError:
                                    pass
                        except Exception:
                            # cannot fetch specific order; assume executed
                            executed_grid.append(gid)

                if executed_grid:
                    # recompute average and replace TP orders
                    logger.info('Detected executed grid orders: %s', executed_grid)
                    pos = await self.compute_average_entry()
                    if pos:
                        await self.place_tp_orders(pos['entry_price'])

                # Also detect if any TP triggered -> log and stop engine
                for tid in list(self.tp_order_ids):
                    if tid not in open_ids:
                        # TP no longer open; check
                        try:
                            ord = await self.exchange.fetch_order(tid, self.config.symbol)
                            if ord.get('status') in ('closed', 'filled'):
                                logger.info('TP %s filled; trade complete', tid)
                                # optionally cancel remaining orders and stop
                                await self._on_trade_exit()
                                return
                        except Exception:
                            pass

                await safe_sleep(poll_interval)
        except asyncio.CancelledError:
            logger.info('Monitor loop cancelled')
        finally:
            logger.info('Monitor loop ended')

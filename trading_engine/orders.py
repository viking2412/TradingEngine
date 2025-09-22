from trading_engine.utility import logger, safe_sleep


class OrderManager:
    """Responsible for placing/canceling market, grid, TP orders."""

    def __init__(self, exchange, config):
        self.exchange = exchange
        self.config = config
        self.tp_orders = []
        self.grid_orders = []
        self.grid_order_ids = []
        self.tp_order_ids = []
        self.position = None
        self.current_sl_order_id = None
        self.trailing_active = False
        self.last_sl_price = None
        self.order_amount = len(self.config.tp_orders)


    async def place_initial_market(self):
        symbol = self.config.symbol  # futures symbol
        side = 'sell' if self.config.side.lower() == 'short' else 'buy'
        amount_quote = float(self.config.market_order_amount)

        ticker = await self.exchange.fetch_ticker(symbol)
        price = ticker['last']
        market = self.exchange.market(symbol)
        contract_size = market.get("contractSize", 1)
        logger.info(f"Contract size: {contract_size}")
        qty = (amount_quote / price) / contract_size

        logger.info(f"Initial market price: {price}, amount {qty:.6f} BTC")

        try:
            await self.exchange.setLeverage(10, symbol)
        except Exception as e:
            logger.warning(f"Could not set leverage: {e}")
        logger.info("Leverage set to 10")
        order = await self.exchange.create_order(
            symbol=symbol,
            type="market",
            side=side,
            amount=qty,
            params={
                "reduceOnly": False,
                "positionSide": "SHORT" if side == "sell" else "LONG",
            }
        )
        logger.info(f"Market order placed: {order}")
        return order

    async def build_limit_grid(self, center_price: float):
        """Create a set of limit orders for averaging within the specified percent range.
        The limit_orders_amount is the total quote amount reserved for the grid.
        """
        cfg = self.config.limit_orders
        total_quote = float(self.config.limit_orders_amount)
        n = int(cfg.orders_count)
        range_pct = cfg.range_percent / 100.0
        symbol = self.config.symbol
        side = 'buy' if self.config.side.lower() == 'long' else 'sell'
        prices = []
        for i in range(1, n + 1):
            fraction = i / (n + 1)
            if self.config.side.lower() == 'long':
                price = center_price * (1 - fraction * range_pct)
            else:
                price = center_price * (1 + fraction * range_pct)
            prices.append(price)

        orders = []
        for price in prices:
            quote_each = total_quote / n
            # convert to base amount
            market = self.exchange.market(symbol)
            contract_size = market.get("contractSize", 1)
            logger.info(f"Contract size: {contract_size}")
            qty = quote_each / price / contract_size
            qty = max(qty, 0.00000001)
            logger.info(f'Creating grid limit order {side} {qty:.8f} @ {price:.2f}')
            try:
                ord = await self.exchange.create_limit_order(symbol, side, qty, price)
                self.grid_order_ids.append(ord['id'])
                orders.append(ord)
                await safe_sleep(0.2)
            except Exception as e:
                logger.exception('Failed to create grid order: %s', e)
        return orders

    async def place_tp_orders(self, pos: dict):
        """Place or replace TP orders based on current average price. Replace existing ones (cancel + create).
        Percentages are relative to avg_price (e.g. 2% means exit at avg_price * (1 + 0.02) for long)
        """

        # Cancel existing TP orders
        symbol = self.config.symbol
        for oid in list(self.tp_order_ids):
            try:

                await self.exchange.cancel_order(oid, symbol)
            except Exception:
                self.order_amount -= 1
                pass
        self.tp_order_ids = []

        side_tp = 'sell' if self.config.side.lower() == 'long' else 'buy'
        base_total = pos['size'] if pos else None
        if base_total is None:
            logger.warning('No position size known; skipping TP placement')
            return []

        created = []
        sorted_orders = sorted(self.config.tp_orders, key=lambda o: o.price_percent)
        print(f"Filled amount: {len(sorted_orders)-self.order_amount}")
        print(sorted_orders[-self.order_amount:])
        for tp in sorted_orders[-self.order_amount:]:

            price = pos['entry_price'] * (1 + (tp.price_percent / 100.0) * (1 if self.config.side.lower() == 'long' else -1))
            market = self.exchange.market(symbol)
            contract_size = market.get("contractSize", 1)
            qty = base_total * (tp.quantity_percent / 100.0) / contract_size # here
            qty = max(qty, 0.00000001)
            logger.info(f'Placing TP {side_tp} {qty:.8f} @ {price:.2f}')
            try:
                lim_order = await self.exchange.create_limit_order(symbol, side_tp, qty, price)
                self.tp_order_ids.append(lim_order['id'])
                created.append(lim_order)
                await safe_sleep(0.2)
            except Exception as e:
                logger.exception('Failed to create TP order: %s', e)
        return created


    async def update_stop_loss(self, position: dict):

        stop_loss_percent = self.config.stop_loss_percent
        trailing_offset = self.config.trailing_sl_offset_percent

        entry_price = float(
            position.get("entry_price") or position.get("entryPrice") or position.get("avgEntryPrice") or 0)
        size = float(position.get("size") or position.get("contracts") or 0)
        side = self.config.side  # 'long' or 'short'

        if entry_price == 0 or size == 0:
            logger.warning(f"Position is no more: {position}")
            # Position is no more - deleting SL if exists
            if self.current_sl_order_id:
                try:
                    await self.exchange.cancel_order(self.current_sl_order_id, self.config.symbol)
                except Exception as e:
                    logger.warning(f"Couldn't remove existing SL: {e}")
            self.current_sl_order_id = None
            self.trailing_active = False
            return

        if side == "long":
            base_sl_price = entry_price * (1 - stop_loss_percent / 100)
        else:  # short
            base_sl_price = entry_price * (1 + stop_loss_percent / 100)

        ticker = await self.exchange.fetch_ticker(self.config.symbol)
        current_price = ticker["last"]
        # sl_price = base_sl_price

        if not self.trailing_active:
            # static SL before activation
            sl_price = base_sl_price
        else:
            # after activation only trailing, no fall backs to static
            if side == "long":
                trailed_price = current_price * (1 - trailing_offset / 100)
                sl_price = max(self.last_sl_price or base_sl_price, trailed_price)
            else:  # short
                trailed_price = current_price * (1 + trailing_offset / 100)
                sl_price = min(self.last_sl_price or base_sl_price, trailed_price)

        # saving last SL, to not move SL back
        self.last_sl_price = sl_price

        if not self.trailing_active:
            # logger.info(f"tp_orders type: {type(self.config.tp_orders[0])}, value: {self.config.tp_orders[0]}")
            first_tp = self.config.tp_orders[0]
            tp1_percent = first_tp.price_percent
            if (side == "long" and current_price >= entry_price * (1 + tp1_percent / 100)) or \
                    (side == "short" and current_price <= entry_price * (1 - tp1_percent / 100)):
                self.trailing_active = True
                logger.info("Trailing stop activated")
        if self.exchange.id == "gate":
            otype = "stop"
            side = 'sell' if side == 'long' else 'buy'
            params = {
                "stop": True,
                "reduceOnly": True,
                "triggerPrice": sl_price
            }
        elif self.exchange.id == "bybit":
            otype = "Stop"
            side = 'Sell' if side == 'long' else 'Buy'
            params = {
                "triggerDirection": "ascending" if side == "long" else "descending",
                "reduceOnly": True,
                "stopLossPrice": sl_price
            }
        else:
            otype = None
            side = None
            params = {}
        try:
            if self.current_sl_order_id:
                logger.info(f"Trying to remove current SL: {self.current_sl_order_id}")
                await self.exchange.cancel_order(self.current_sl_order_id, self.config.symbol, params=params)
        except Exception as e:
            logger.warning(f"Couldn't remove old SL: {e}")

        try:
            sl_order = await self.exchange.create_order(
                symbol=self.config.symbol,
                type=otype,
                side=side,
                amount=size,
                price=sl_price,
                params=params
            )

            self.current_sl_order_id = sl_order["id"]
            logger.info(f"Stop-loss updated: {sl_price}")
        except Exception as e:
            raw = e.args[0] if e.args else ""
            if isinstance(raw, str) and "not modified" in raw:
                logger.info(f"SL was not modified ({sl_price})")
            else:
                logger.error(f"Exchange error: {e}")


    async def compute_average_entry(self):
        """Compute average entry price from fills/position. This is exchange-dependent."""
        symbol = self.config.symbol
        # Try to get position info via fetch_positions or fetch_balance as fallback
        try:
            if hasattr(self.exchange, 'fetch_positions'):
                positions = await self.exchange.fetch_positions([symbol])
                # positions is exchange-specific; pick first with non-zero size
                for p in positions:
                    size = abs(float(p.get('contracts') or p.get('positionAmt') or 0))
                    if size > 0:
                        entry = float(p.get('entryPrice') or p.get('entry_price') or p.get('avgEntryPrice') or 0)
                        self.position = {'size': size, 'entry_price': entry}
                        return self.position
        except Exception:
            logger.debug('fetch_positions not available or failed')

        # fallback: calculate from closed trades / fills - simplified approach
        try:
            trades = await self.exchange.fetch_my_trades(symbol)
            # find most recent fills that sum up to current signed position
            # VERY simplified: compute weighted average of all trades
            total_base = 0.0
            total_quote = 0.0
            for t in trades:
                if t.get('side') is None:
                    continue
                side = t['side']
                amount = float(t['amount'] or 0)
                price = float(t['price'] or 0)
                if amount == 0 or price == 0:
                    continue
                total_base += amount
                total_quote += amount * price
            if total_base > 0:
                avg = total_quote / total_base
                self.position = {'size': total_base, 'entry_price': avg}
                return self.position
        except Exception:
            logger.exception('fetch_my_trades failed')

        logger.info('Could not compute average entry; no position found')
        return None


from trading_engine.logging import logger


class OrderManager:
    """Responsible for placing/canceling market, grid, TP orders."""

    def __init__(self, exchange, config):
        self.exchange = exchange
        self.config = config
        self.tp_orders = []
        self.grid_orders = []

    async def place_initial_market(self):
        """Place market order according to config.market_order_amount (quote currency amount)
        This function is generic but must be adapted to exchange-specific params (market vs futures).
        Returns order info dict.
        """
        symbol = self.config.symbol
        side = 'sell' if self.config.side.lower() == 'short' else 'buy'
        amount_quote = float(self.config.market_order_amount)

        # Need to translate quote amount into quantity for symbol (base amount)
        ticker = await self.exchange.fetch_ticker(symbol)
        price = ticker['last'] or ticker['close']
        if price is None:
            raise RuntimeError('Could not fetch price')
        qty = amount_quote / price

        logger.info(
            f'Placing market {side} order for approx {qty:.8f} {symbol.split("/")[0]} (quote approximately {amount_quote})')

        # If exchange supports create_order with type 'market' and amount in base
        order = await self.exchange.create_order(symbol, 'market', side, qty)
        logger.info('Market order placed: %s', order.get('id'))
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

        # For a short position, grid orders are to add to the position in the direction of entry (sell more)
        if self.config.side.lower() == 'short':
            side = 'sell'
        else:
            side = 'buy'

        prices = []
        # For long: distribute prices below center_price down to center*(1-range_pct)
        # For short: distribute prices above center_price up to center*(1+range_pct)
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
            qty = quote_each / price
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

    async def place_tp_orders(self, avg_price: float):
        """Place or replace TP orders based on current average price. Replace existing ones (cancel + create).
        Percentages are relative to avg_price (e.g. 2% means exit at avg_price * (1 + 0.02) for long)
        """
        # Cancel existing TP orders
        symbol = self.config.symbol
        for oid in list(self.tp_order_ids):
            try:
                await self.exchange.cancel_order(oid, symbol)
            except Exception:
                pass
        self.tp_order_ids = []

        side_tp = 'sell' if self.config.side.lower() == 'long' else 'buy'
        base_total = self.position['size'] if self.position else None
        if base_total is None:
            logger.warning('No position size known; skipping TP placement')
            return []

        created = []
        for tp in self.config.tp_orders:
            price = avg_price * (1 + (tp.price_percent / 100.0) * (1 if self.config.side.lower() == 'long' else -1))
            qty = base_total * (tp.quantity_percent / 100.0)
            qty = max(qty, 0.00000001)
            logger.info(f'Placing TP {side_tp} {qty:.8f} @ {price:.2f}')
            try:
                ord = await self.exchange.create_limit_order(symbol, side_tp, qty, price)
                self.tp_order_ids.append(ord['id'])
                created.append(ord)
                await safe_sleep(0.2)
            except Exception as e:
                logger.exception('Failed to create TP order: %s', e)
        return created
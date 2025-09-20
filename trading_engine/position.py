from trading_engine.logging import logger


class PositionManager:
    """Handles position data, average entry, updates."""

    def __init__(self, exchange, config):
        self.exchange = exchange
        self.config = config
        self.position = None

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

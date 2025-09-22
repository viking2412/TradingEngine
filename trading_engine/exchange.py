import ccxt.async_support as ccxt

from .utility import logger

class ExchangeConnector:
    """Wrapper for Bybit/Gate exchanges (via ccxt or native SDK)."""

    def __init__(self, config, api_key: str, api_secret: str):
        self.config = config
        self.api_key = api_key
        self.api_secret = api_secret
        acct = self.config.account.lower()
        if 'bybit' in acct:
            self.exchange = ccxt.bybit({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True,
                # Bybit via ccxt supports sandbox mode; toggle below
            })
            # enable sandbox/testnet if requested
        elif 'gate' in acct:
            self.exchange = ccxt.gateio({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True,
            })
        if ('testnet' or 'demo') in acct:
            try:
                self.exchange.set_sandbox_mode(True)
                logger.info(f'{self.exchange} sandbox enabled')
            except Exception:
                logger.warning(f'{self.exchange} set_sandbox_mode failed; check ccxt version')
        else:
            raise RuntimeError('Unsupported account/exchange in config.account')

    async def connect(self):
        """Initialize exchange connection & load markets"""
        await self.exchange.load_markets()
        logger.info('Connected to exchange and loaded markets')


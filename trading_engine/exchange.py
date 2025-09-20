import ccxt.async_support as ccxt

from trading_engine.logging import logger


class ExchangeConnector:
    """Wrapper for Bybit/Gate exchanges (via ccxt or native SDK)."""

    def __init__(self, config, api_key: str, api_secret: str):
        self.config = config
        self.api_key = api_key
        self.api_secret = api_secret
        self.exchange = None

    async def connect(self):
        """Initialize exchange connection & load markets"""
        # if self.config.account == "Bybit":
        #     exchange = ccxt.bybit()
        # elif self.config.account == "Gate":
        #     exchange = ccxt.gate()
        # else:
        #     return exception("Wrong Exchange")
        # exchange.apiKey = self.api_key
        # exchange.secretKey = self.api_secret
        # self.exchange = exchange
        # await exchange.load_markets()

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
            # if 'testnet' in acct or 'demo' in acct:
            #     # ccxt gateio may not support set_sandbox_mode; alternative: set urls
            #     try:
            #         self.exchange.set_sandbox_mode(True)
            #         logger.info('GateIO sandbox enabled')
            #     except Exception:
            #         logger.warning(
            #             'GateIO sandbox not available via ccxt; ensure you use gate test API endpoint or native SDK')
        else:
            raise RuntimeError('Unsupported account/exchange in config.account')

        await self.exchange.load_markets()
        logger.info('Connected to exchange and loaded markets')

    async def fetch_price(self, symbol: str) -> float:
        """Fetch last price for symbol"""
        return await self.exchange.ticker(self.config.symbol)

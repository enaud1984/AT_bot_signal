from typing import List

import ccxt


class MiaBitfinex(ccxt.bitfinex):
    def fetch_ohlcv(self, symbol: str, timeframe='1m', since: int = None, limit: int = None, params={}) -> List[list]:
        """
        fetches historical candlestick data with manual pagination support for more than 10,000 records.
        """
        self.load_markets()
        market = self.market(symbol)
        v2id = 't' + market['id']

        # Default limit per singola chiamata (Bitfinex supporta fino a 10.000 per richiesta)
        max_candles_per_request = 10000
        all_candles = []

        # Calcoliamo il numero di batch necessari
        while True:
            # Configurazione della richiesta
            request: dict = {
                'symbol': v2id,
                'timeframe': self.safe_string(self.timeframes, timeframe, timeframe),
                'sort': 1,  # Ordine crescente
                'limit': max_candles_per_request
            }

            # Aggiunge il parametro 'start' per iniziare dalla data specificata
            if since is not None:
                request['start'] = since

            # Effettua la chiamata all'API
            response = self.v2GetCandlesTradeTimeframeSymbolHist(self.extend(request, params))
            candles = self.parse_ohlcvs(response, market, timeframe, since, max_candles_per_request)

            if not candles:
                # Esci se non ci sono più dati
                break

            # Aggiunge i nuovi dati all'elenco completo
            all_candles.extend(candles)

            # Aggiorna il parametro `since` per continuare dalla candela successiva
            since = candles[-1][0] + 1

            # Interrompe il ciclo se si è raggiunto il limite desiderato
            if limit is not None and len(all_candles) >= limit:
                all_candles = all_candles[:limit]
                break

        return all_candles
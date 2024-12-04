import os
import logging
import talib
import numpy as np
import pandas as pd
import ccxt
import matplotlib.pyplot as plt
import time
from param import *


COMPRO_VENDO_FLAG=False
PLOT=False
saldo_iniziale = 5000

hist_timeframe = '6h'
hist_limit = 365*4

timeperiod_SMA50 = 50
timeperiod_SMA200 = 200
fastperiod = 12
slowperiod = 26
signalperiod = 9
timeperiod_RSI = 14

time_sleep = 21600
symbol='BTC/USDT'

# Imposta l'exchange e ottieni i dati OHLCV per un asset (es: BTC/USDT su Kucoin)
exchange_hist = ccxt.kucoin({
    'apiKey': '',
    'secret': '',
    'enableRateLimit': True,
})

exchange_operation = ccxt.bitfinex({
    'apiKey': API_KEY_bitfinex,
    'secret': SECRET_KEY_bitfinex,
    'enableRateLimit': True,
})
if not os.path.exists("log"):
    os.makedirs("log")

logging.basicConfig(
    filename='log/logfile.log',  # Nome del file di log
    level=logging.INFO,      # Livello del log
    format='%(asctime)s - %(levelname)s - %(message)s',  # Formato del log
    datefmt='%Y-%m-%d %H:%M:%S'  # Formato del timestamp
)

# Funzione per acquistare
def acquista(symbol):
    try:
        # Carica i mercati dell'exchange
        exchange_operation.load_markets()

        # Ottieni il saldo corrente in USDT
        balance = exchange_operation.fetch_balance()
        usdt_balance = balance['total']['USDT']

        # Calcola il 30% del saldo in USDT
        amount_to_spend = usdt_balance

        if amount_to_spend <= 0:
            logging.warning("Saldo insufficiente in USDT per effettuare l'acquisto.")
            return

        # Ottieni il prezzo di mercato corrente per BXN/USDT
        ticker = exchange_operation.fetch_ticker(symbol)
        market_price = ticker['last']

        logging.info(f"Saldo USDT: {usdt_balance}, Importo da spendere: {amount_to_spend}, Prezzo di mercato: {market_price}, Importo BXN da acquistare: {amount_to_spend}")

        # Esegui un ordine di acquisto al mercato
        order = exchange_operation.create_market_buy_order(symbol, amount_to_spend)

        logging.info("Ordine di acquisto eseguito con successo:")
        print(order)

    except Exception as e:
        logging.error(f"Errore durante l'esecuzione dell'ordine: {e}")

# Funzione per vendere
def vendi(symbol):
    try:
        symbol_to_sell=symbol.split('/')[0]
        # Carica i mercati dell'exchange
        exchange_operation.load_markets()

        # Ottieni il saldo corrente di BXN
        balance = exchange_operation.fetch_balance()
        balance_to_sell = balance['total'][symbol_to_sell]

        # Se serve aggiungi (balance_to_sell * x) dove x è un numero da 0 ad 1 per vendere solo una parte del saldo
        amount_to_sell = balance_to_sell

        if amount_to_sell <= 0:
            logging.warning("Saldo insufficiente per effettuare la vendita.")
            return

        # Ottieni il prezzo di mercato corrente per BXN/USDT
        ticker = exchange_operation.fetch_ticker(symbol)
        market_price = ticker['last']

        logging.info(f"Saldo {symbol_to_sell}: {balance_to_sell}, Importo da vendere: {amount_to_sell}, Prezzo di mercato: {market_price}")

        # Esegui un ordine di vendita al mercato
        order = exchange_operation.create_market_buy_order(symbol, amount_to_sell)

        logging.info("Ordine di vendita eseguito con successo:")
        print(order)

    except Exception as e:
        logging.error(f"Errore durante l'esecuzione dell'ordine: {str(e)}")

def generate_signals(df):
    signals = []
    position = 'OUT'  # Stato iniziale, senza posizione aperta

    for i in range(1, len(df)):
        # Segnale di acquisto
        if position == 'OUT':
            if (df['SMA_50'].iloc[i] > df['SMA_200'].iloc[i] and df['SMA_50'].iloc[i - 1] <= df['SMA_200'].iloc[i - 1]) or \
                    (df['RSI'].iloc[i] < 30) or \
                    (df['MACD'].iloc[i] > df['MACD_signal'].iloc[i] and df['MACD'].iloc[i - 1] <= df['MACD_signal'].iloc[i - 1]):
                signals.append('BUY')
                position = 'LONG'  # Cambia lo stato in LONG dopo un acquisto
            else:
                signals.append('HOLD')

        # Segnale di vendita
        elif position == 'LONG':
            if (df['SMA_50'].iloc[i] < df['SMA_200'].iloc[i] and df['SMA_50'].iloc[i - 1] >= df['SMA_200'].iloc[i - 1]) or \
                    (df['RSI'].iloc[i] > 70) or \
                    (df['MACD'].iloc[i] < df['MACD_signal'].iloc[i] and df['MACD'].iloc[i - 1] >= df['MACD_signal'].iloc[i - 1]):
                signals.append('SELL')
                position = 'OUT'  # Cambia lo stato in OUT dopo una vendita
            else:
                signals.append('HOLD')

        # Nessun segnale
        else:
            signals.append('HOLD')

    # Assicura che la lunghezza dei segnali sia uguale a quella del DataFrame
    signals = ['HOLD'] + signals
    df['Signal'] = signals
    return df


if __name__ == "__main__":
    logging.info("START BOT")
    while True:
        try:
            bars = exchange_hist.fetch_ohlcv(symbol, timeframe='6h', limit=365*4)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        except Exception as e:
            logging.error("Errore nel recupero dei dati:", e)
            bars = []  # Lasciamo vuoto se c'è un errore di connessione

        try:
            if bars:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

                # Calcola gli indicatori
                df['SMA_50'] = talib.SMA(df['close'], timeperiod=timeperiod_SMA50)
                df['SMA_200'] = talib.SMA(df['close'], timeperiod=timeperiod_SMA200)
                df['MACD'], df['MACD_signal'], _ = talib.MACD(df['close'], fastperiod=fastperiod, slowperiod=slowperiod, signalperiod=signalperiod)
                df['RSI'] = talib.RSI(df['close'], timeperiod=timeperiod_RSI)

                # Funzione per generare segnali di acquisto e vendita alternati con stop loss e take profit
                df = generate_signals(df)

                # Calcolo del risultato solo per le righe con 'SELL'
                df2 = df[df['Signal'] != "HOLD"][['timestamp', 'close', 'Signal']]

                # Calcoliamo il valore percentuale solo per le righe con 'Signal' "SELL"
                df2['last_buy_close'] = df2['close'].where(df2['Signal'] == 'BUY').ffill()

                # Ricalcoliamo il 'result' usando il corretto approccio con .iloc
                df2['result'] = np.nan  # Assicurarsi che la colonna 'result' esista
                df2.loc[(df2['Signal'] == 'SELL') & (~df2['last_buy_close'].isna()), 'result'] = (
                        (df2['close'] - df2['last_buy_close']) / df2['last_buy_close'] * 100
                )

                # Aggiungi il saldo progressivo
                df2['balance'] = np.nan  # Inizializziamo con NaN
                df2.loc[0, 'balance'] = saldo_iniziale  # Impostiamo il saldo iniziale per la prima riga

                # Calcoliamo il saldo progressivo utilizzando .iloc per evitare il KeyError
                for i in range(1, len(df2)):
                    if not pd.isna(df2.iloc[i]['result']):  # Se il risultato non è NaN
                        df2.iloc[i, df2.columns.get_loc('balance')] = df2.iloc[i - 1, df2.columns.get_loc('balance')] * (1 + df2.iloc[i]['result'] / 100)
                    else:
                        # Se il risultato è NaN, mantieni il saldo invariato
                        df2.iloc[i, df2.columns.get_loc('balance')] = df2.iloc[i - 1, df2.columns.get_loc('balance')]

                buy_signals = df[df['Signal'] == 'BUY']
                sell_signals = df[df['Signal'] == 'SELL']
                oggi = pd.Timestamp.today() - pd.Timedelta(hours=1)

                df_filtrato_buy = buy_signals[buy_signals['timestamp'] >= oggi][['timestamp', 'open', 'close', 'Signal']]
                df_filtrato_buy=df_filtrato_buy.sort_values(by='timestamp', ascending=False)
                df_filtrato_sell = sell_signals[sell_signals['timestamp'] >= oggi][['timestamp', 'open', 'close', 'Signal']]
                df_filtrato_sell=df_filtrato_sell.sort_values(by='timestamp', ascending=False)
                print(df_filtrato_buy)
                print(df_filtrato_sell)
                if df_filtrato_buy.empty and df_filtrato_sell.empty:
                    logging.info("Nessuna operazione effettuata")
                print(df2)   # stampa tutta la tabella con i valori BUY and SELL con saldo progressivo
                if COMPRO_VENDO_FLAG:
                    if not df_filtrato_buy.empty:
                        acquista(symbol)

                    if not df_filtrato_sell.empty:
                        vendi(symbol)

                if PLOT:
                    # Visualizzazione grafica
                    plt.figure(figsize=(14, 8))
                    plt.plot(df['timestamp'], df['close'], label='Prezzo di Chiusura', color='blue')
                    plt.plot(df['timestamp'], df['SMA_50'], label='SMA 50', color='orange')
                    plt.plot(df['timestamp'], df['SMA_200'], label='SMA 200', color='green')
                    # Aggiunta dei segnali di acquisto e vendita
                    plt.scatter(df_filtrato_buy['timestamp'], df_filtrato_buy['close'], marker='^', color='green', label='Segnale di Acquisto', alpha=1)
                    plt.scatter(df_filtrato_sell['timestamp'], df_filtrato_sell['close'], marker='v', color='red', label='Segnale di Vendita', alpha=1)
                    plt.title(f'Strategia di Segnale di Acquisto e Vendita su {symbol} con Stop Loss e Take Profit')
                    plt.xlabel('Data')
                    plt.ylabel('Prezzo (USD)')
                    plt.legend(loc='best')
                    plt.grid()
                    plt.show()
                time.sleep(time_sleep)
        except Exception as e:
            logging.error("Errore nella generazione dei risultati:", e)
import logging
import shutil
from datetime import datetime
import pytz

#import talib
import pandas_ta as talib
import numpy as np
import pandas as pd
import ccxt
import matplotlib.pyplot as plt
import time
import os
import sns

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import threading
from param import *
from key import *


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
    filename=f'{LOG_FILE_PATH}/logfile.log',  # Nome del file di log
    level=logging.INFO,      # Livello del log
    format='%(asctime)s - %(levelname)s - %(message)s',  # Formato del log
    datefmt='%Y-%m-%d %H:%M:%S'  # Formato del timestamp
)

app = FastAPI()

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

        logging.info(f"Saldo USDT: {usdt_balance}, Importo da spendere: {amount_to_spend}, "
                     f"Prezzo di mercato: {market_price}, Importo BXN da acquistare: {amount_to_spend}")

        # Esegui un ordine di acquisto al mercato
        order = exchange_operation.create_market_buy_order(symbol, amount_to_spend)

        logging.info("Ordine di acquisto eseguito con successo:")
        print(order)
        sns.sendNotify(f"Saldo USDT: {usdt_balance}, Importo da spendere: {amount_to_spend}, "
                       f"Prezzo di mercato: {market_price}, Importo BXN da acquistare: {amount_to_spend}, => Ordine di acquisto eseguito con successo")

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
        sns.sendNotify(f"Saldo {symbol_to_sell}: {balance_to_sell}, Importo da vendere: {amount_to_sell}, Prezzo di mercato: {market_price}, =>Ordine di vendita eseguito con successo:")

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

@app.get("/")
async def read_root():
    try:
        temp_log_path = f'{LOG_FILE_PATH}/temp_logfile.log'
        shutil.copyfile(f'{LOG_FILE_PATH}/logfile.log', temp_log_path)
        with open(temp_log_path, "r") as file:
            log_content = file.readlines()
            # Crea una stringa HTML che contiene le righe del log
            log_html = "<html><body><h1>Contenuto del log</h1><pre>"
            for line in log_content:
                log_html += line
            log_html += "</pre></body></html>"
            return HTMLResponse(content=log_html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante la lettura del file di log: {str(e)}")


def start_fastapi_server():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    logging.info("START BOT")
    date_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"DateTimestamp: {date_time}")
    if not single_shot:
        threading.Thread(target=start_fastapi_server, daemon=True).start()

    while True:
        df = None
        try:
            since_datetime = datetime.strptime(date_start, "%Y-%m-%d %H:%M:%S")
            # Conversione in timestamp Unix (millisecondi)
            since = int(since_datetime.timestamp() * 1000)
            bars = exchange_hist.fetch_ohlcv(symbol, timeframe=hist_timeframe, since=since, limit=hist_limit)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        except Exception as e:
            logging.error("Errore nel recupero dei dati:", e)
            bars = []  # Lasciamo vuoto se c'è un errore di connessione

        try:
            if bars and df is not None:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                # Converti la colonna timestamp in datetime e assegna il fuso orario UTC
                df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
                # Converti in fuso orario Europe/Rome
                df['timestamp'] = df['timestamp'].dt.tz_convert('Europe/Rome').dt.tz_localize(None)

                # Calcola gli indicatori
                df['SMA_50'] = df.ta.sma(length=timeperiod_SMA50)
                df['SMA_200'] = df.ta.sma(length=timeperiod_SMA200)

                macd = df.ta.macd(fast=fastperiod, slow=slowperiod, signal=signalperiod)
                df['MACD'] = macd['MACD_12_26_9']
                df['MACD_signal'] = macd['MACDs_12_26_9']
                df['RSI'] = df.ta.rsi(length=timeperiod_RSI)

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
                df2['balance'] = np.nan  # Inizializziamo con NaN, così possiamo calcolare il saldo per ogni riga
                df2.iloc[0, df2.columns.get_loc(
                    'balance')] = saldo_iniziale  # Impostiamo il saldo iniziale per la prima riga

                # Calcoliamo il saldo progressivo
                """
                for i in range(1, len(df2)):
                    if not pd.isna(df2['result'].iloc[i]):  # Se il risultato non è NaN
                        df2['balance'].iloc[i] = df2['balance'].iloc[i - 1] * (1 + df2['result'].iloc[i] / 100)
                    else:
                        # Se il risultato è NaN, mantieni il saldo invariato
                        df2['balance'].iloc[i] = df2['balance'].iloc[i - 1]
                """
                buy_signals = df[df['Signal'] == 'BUY']

                sell_signals = df[df['Signal'] == 'SELL']
                oggi = pd.Timestamp.today() - pd.Timedelta(minutes=5)
                print("Oggi:",oggi)
                df_filtrato_buy = buy_signals[buy_signals['timestamp'] >= oggi][['timestamp', 'open', 'close', 'Signal']]
                df_filtrato_buy=df_filtrato_buy.sort_values(by='timestamp', ascending=False)
                df_filtrato_sell = sell_signals[sell_signals['timestamp'] >= oggi][['timestamp', 'open', 'close', 'Signal']]
                df_filtrato_sell=df_filtrato_sell.sort_values(by='timestamp', ascending=False)
                pd.options.display.max_columns=None
                print(df_filtrato_buy)
                print(df_filtrato_sell)
                if df_filtrato_buy.empty and df_filtrato_sell.empty:
                    logging.info("Nessuna operazione effettuata")
                    sns.sendNotify("Nessuna operazione effettuata")
                print(df2)   # stampa tutta la tabella con i valori BUY and SELL con saldo progressivo
                if COMPRO_VENDO_FLAG:
                    if not df_filtrato_buy.empty:
                        print("EFFETTUATA OPERAZIONE DI ACQUISTO")
                        #acquista(symbol)

                    if not df_filtrato_sell.empty:
                        print("EFFETTUATA OPERAZIONE DI VENDITA")
                        #vendi(symbol)

                if PLOT:
                    # Visualizzazione grafica
                    plt.figure(figsize=(14, 8))
                    plt.plot(df['timestamp'], df['close'], label='Prezzo di Chiusura', color='blue')
                    plt.plot(df['timestamp'], df['SMA_50'], label='SMA 50', color='orange')
                    plt.plot(df['timestamp'], df['SMA_200'], label='SMA 200', color='green')

                    # Aggiunta dei segnali di acquisto e vendita
                    buy_signals = df[df['Signal'] == 'BUY']
                    sell_signals = df[df['Signal'] == 'SELL']
                    plt.scatter(buy_signals['timestamp'], buy_signals['close'], marker='^', color='green',
                                label='Segnale di Acquisto', alpha=1)
                    plt.scatter(sell_signals['timestamp'], sell_signals['close'], marker='v', color='red',
                                label='Segnale di Vendita', alpha=1)

                    plt.title(f'Strategia di Segnale di Acquisto e Vendita su {symbol} con Stop Loss e Take Profit')
                    plt.xlabel('Data')
                    plt.ylabel('Prezzo (USD)')
                    plt.legend(loc='best')
                    plt.grid()
                    plt.show()

                if single_shot:
                    break

                time.sleep(time_sleep)
        except Exception as e:
            logging.error("Errore nella generazione dei risultati:", e)
            sns.sendNotify("Errore nella generazione dei risultati:")
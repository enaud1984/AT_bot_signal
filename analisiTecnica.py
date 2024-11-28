import talib
import numpy as np
import pandas as pd
import ccxt
import matplotlib.pyplot as plt
import time
import psutil
import os
from param import *

saldo_iniziale = 5000
soglia_stop = 0.015
soglia_profit = 0.025

hist_timeframe = '6h'
hist_limit = 365*4

timeperiod_SMA50 = 50
timeperiod_SMA200 = 200
fastperiod = 12
slowperiod = 26
signalperiod = 9
timeperiod_RSI = 14

time_sleep = 10

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

while True:
    try:
        bars = exchange_hist.fetch_ohlcv('BTC/USDT', timeframe='6h', limit=365*4)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    except Exception as e:
        print("Errore nel recupero dei dati:", e)
        bars = []  # Lasciamo vuoto se c'è un errore di connessione

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
        oggi = pd.Timestamp.today()
        ieri = oggi - pd.Timedelta(days=30)

        df_filtrato_buy = buy_signals[buy_signals['timestamp'] >= oggi][['timestamp', 'open', 'close', 'Signal']]
        df_filtrato_buy=df_filtrato_buy.sort_values(by='timestamp', ascending=False)
        df_filtrato_sell = sell_signals[sell_signals['timestamp'] >= oggi][['timestamp', 'open', 'close', 'Signal']]
        df_filtrato_sell=df_filtrato_sell.sort_values(by='timestamp', ascending=False)
        print(df_filtrato_buy)
        print(df_filtrato_sell)

        if False:
            # Visualizzazione grafica
            plt.figure(figsize=(14, 8))
            plt.plot(df['timestamp'], df['close'], label='Prezzo di Chiusura', color='blue')
            plt.plot(df['timestamp'], df['SMA_50'], label='SMA 50', color='orange')
            plt.plot(df['timestamp'], df['SMA_200'], label='SMA 200', color='green')
            # Aggiunta dei segnali di acquisto e vendita
            plt.scatter(df_filtrato_buy['timestamp'], df_filtrato_buy['close'], marker='^', color='green', label='Segnale di Acquisto', alpha=1)
            plt.scatter(df_filtrato_sell['timestamp'], df_filtrato_sell['close'], marker='v', color='red', label='Segnale di Vendita', alpha=1)
            plt.title('Strategia di Segnale di Acquisto e Vendita su BTC/USDT con Stop Loss e Take Profit')
            plt.xlabel('Data')
            plt.ylabel('Prezzo (USD)')
            plt.legend(loc='best')
            plt.grid()
            plt.show()
        time.sleep(time_sleep)

import glob
import json
import logging
import shutil
from datetime import datetime, timedelta
import pytz

#import talib
import pandas_ta as talib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import time
import os
import sns

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import threading

from MiaBitfinex import MiaBitfinex
from db_atbot import DB_ATBot
from param import *
from key import *


# Imposta l'exchange e ottieni i dati OHLCV per un asset (es: BTC/USDT su bitfinex)
exchange_hist = MiaBitfinex({
    'apiKey': '',
    'secret': '',
    'enableRateLimit': True,
})

exchange_operation = MiaBitfinex({
    'apiKey': API_KEY_bitfinex,
    'secret': SECRET_KEY_bitfinex,
    'enableRateLimit': True,
})

if not os.path.exists("log"):
    os.makedirs("log")

logging.basicConfig(
    filename=f'{LOG_FILE_PATH}/logfile.log',  # Nome del file di log
    level=logging.INFO,  # Livello del log
    format='%(asctime)s - %(levelname)s - %(message)s',  # Formato del log
    datefmt='%Y-%m-%d %H:%M:%S'  # Formato del timestamp
)

app = FastAPI()


class AT_Bot:

    def __init__(self, config):

        for k, v in config.items():
            setattr(self, k, v)

        if not self.single_shot:
            threading.Thread(target=self.start_fastapi_server, daemon=True).start()

        self.response_dict = {}

        try:
            self.db_atbot = DB_ATBot(self.db_name)
            # Inizializza la tabella saldo
            saldo_totale = exchange_operation.fetch_balance()['total']['USDT']
            self.db_atbot.initialize_saldo(self.symbol_list, saldo_totale)
            if self.ADJUSTMENT_SALDO:
                self.db_atbot.adjust_saldo_to_total(saldo_totale)
            logging.info(f"Tabella saldo inizializzata o aggiornata, saldo_totale:{saldo_totale}")

        except Exception as e:
            logging.error(f"Errore durante l'inizializzazione della tabella saldo: {str(e)}")
            try:
                sns.sendNotify(f"Errore durante l'inizializzazione della tabella saldo: {str(e)}")
            except Exception as notify_error:
                logging.error(f"Errore durante l'invio della notifica")
                raise e

        while True:
            for symbol in self.symbol_list:
                if self.db_atbot:
                    saldo_symbol=self.db_atbot.get_saldo(symbol)
                    self.operation(symbol,saldo_symbol)
            if self.response_dict:
                #print(response_dict)
                sns.sendNotify(self.response_dict)
            if self.single_shot:
                break
            time.sleep(self.time_sleep)

    # Funzione per acquistare
    def acquista(self,symbol):
        try:
            # Carica i mercati dell'exchange
            exchange_operation.load_markets()

            # Ottieni il saldo corrente in USDT
            #balance = exchange_operation.fetch_balance()
            #usdt_balance = balance['total']['USDT']

            saldo_corrente = self.db_atbot.get_saldo(symbol)
            amount_to_spend = saldo_corrente * self.fees

            if amount_to_spend <= 0:
                logging.warning("Saldo insufficiente in USDT per effettuare l'acquisto.")
                return

            # Ottieni il prezzo di mercato corrente per BXN/USDT
            ticker = exchange_operation.fetch_ticker(symbol)
            market_price = ticker['last']
            max_cripto_buy = amount_to_spend / market_price

            logging.info(f"Saldo USDT: {amount_to_spend}, Importo da spendere: {amount_to_spend}, "
                         f"Prezzo di mercato: {market_price}, Importo {symbol} da acquistare: {max_cripto_buy}")

            order = exchange_operation.create_market_buy_order(symbol, max_cripto_buy)

            logging.info("Ordine di acquisto eseguito con successo:")
            print(order)

            # Aggiorna il saldo nel database
            nuovo_saldo = saldo_corrente - amount_to_spend
            self.db_atbot.set_saldo(symbol, nuovo_saldo)

            self.response_dict[symbol] = f'''Saldo USDT: {saldo_corrente}, Importo da spendere: {amount_to_spend}, 
                                    Prezzo di mercato: {market_price}, Importo {symbol} da acquistare: {max_cripto_buy}, 
                                    => Ordine di acquisto eseguito con successo
                                    Nuovo saldo: {nuovo_saldo}
                                    '''
            print("Nuovo saldo",nuovo_saldo)
        except Exception as e:
            logging.error(f"Errore durante l'esecuzione dell'ordine: {e}")
            self.response_dict[symbol] = f"Errore durante l'esecuzione dell'ordine: {e}"

    # Funzione per vendere
    def vendi(self,symbol):
        try:
            symbol_to_sell = symbol.split('/')[0]
            # Carica i mercati dell'exchange
            exchange_operation.load_markets()

            # Ottieni il saldo corrente della cripto
            balance = exchange_operation.fetch_balance()
            balance_to_sell = balance['total'][symbol_to_sell]

            # Se serve aggiungi (balance_to_sell * x) dove x è un numero da 0 ad 1 per vendere solo una parte del saldo
            amount_to_sell = balance_to_sell  # Vendere tutti le cripto disponibili

            if amount_to_sell <= 0:
                logging.warning("Saldo insufficiente per effettuare la vendita.")
                return

            # Ottieni il prezzo di mercato corrente per cripto/USDT
            ticker = exchange_operation.fetch_ticker(symbol)
            market_price = ticker['last']

            # Esegui un ordine di vendita al mercato
            order = exchange_operation.create_market_sell_order(symbol, amount_to_sell)

            logging.info("Ordine di vendita eseguito con successo:")
            print(order)

            # Aggiorna il saldo nel database
            saldo_corrente = self.db_atbot.get_saldo(symbol)
            nuovo_saldo = saldo_corrente + ((amount_to_sell * market_price) * self.fees)
            self.db_atbot.set_saldo(symbol, nuovo_saldo)

            self.response_dict[symbol] = f"""Saldo {symbol_to_sell}: {balance_to_sell}, 
                                        Importo da vendere: {amount_to_sell}, 
                                        Prezzo di mercato: {market_price}, =>Ordine di vendita eseguito con successo:
                                        Nuovo saldo: {nuovo_saldo}
                                     """
            print("Nuovo saldo",nuovo_saldo)
        except Exception as e:
            logging.error(f"Errore durante l'esecuzione dell'ordine: {str(e)}")
            self.response_dict[symbol] = f"Errore durante l'esecuzione dell'ordine: {e}"

    def generate_signals(self,df):
        signals = []
        position = 'OUT'  # Stato iniziale, senza posizione aperta

        for i in range(1, len(df)):
            if pd.isna(df['SMA_50'].iloc[i]) or pd.isna(df['SMA_200'].iloc[i]) or pd.isna(df['RSI'].iloc[i]):
                signals.append('HOLD')
                continue

            # Segnale di acquisto
            if position == 'OUT':
                if (df['SMA_50'].iloc[i] > df['SMA_200'].iloc[i] and df['SMA_50'].iloc[i - 1] <= df['SMA_200'].iloc[
                    i - 1]) or \
                        (df['RSI'].iloc[i] < 30) or \
                        (df['MACD'].iloc[i] > df['MACD_signal'].iloc[i] and df['MACD'].iloc[i - 1] <=
                         df['MACD_signal'].iloc[i - 1]):
                    signals.append('BUY')
                    position = 'LONG'  # Cambia lo stato in LONG dopo un acquisto
                else:
                    signals.append('HOLD')

            # Segnale di vendita
            elif position == 'LONG':
                if (df['SMA_50'].iloc[i] < df['SMA_200'].iloc[i] and df['SMA_50'].iloc[i - 1] >= df['SMA_200'].iloc[
                    i - 1]) or \
                        (df['RSI'].iloc[i] > 70) or \
                        (df['MACD'].iloc[i] < df['MACD_signal'].iloc[i] and df['MACD'].iloc[i - 1] >=
                         df['MACD_signal'].iloc[i - 1]):
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


    def convertToLocalTime(self,df):
        # Converti la colonna timestamp in datetime e assegna il fuso orario UTC
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        # Converti in fuso orario Europe/Rome
        df['timestamp'] = df['timestamp'].dt.tz_convert('Europe/Rome').dt.tz_localize(None)
        return df

    @staticmethod
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

    def start_fastapi_server(self):
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)

    def save_history(self,df,cripto):
        now = datetime.now().strftime('%Y%m%d_%H%M')
        df.to_csv(f'csv/history_{cripto}_{now}.csv', index=False)

    def get_Df(self,symbol,since,oggi,nome_tabella):
        try:
            df = None
            if not self.db_atbot.tabella_esiste(nome_tabella):
                bars = exchange_hist.fetch_ohlcv(symbol, timeframe=self.hist_timeframe, limit=None, since=since)#, limit=self.hist_limit)
                df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df = df.sort_values(by='timestamp', ascending=True)
                df = df[df['timestamp'].dt.minute == 10]
            else:
                rows = self.db_atbot.get_tabella(nome_tabella)
                if rows:
                    df = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df = df.sort_values(by='timestamp', ascending=True)

                #configurazioni per ottenere i dati degli ultimi 5 minuti con ROC
                hist_timeframe= '1m'
                hist_limit = 1
                oggi_10 = oggi + timedelta(minutes=10)
                since_oggi_10 = int(oggi_10.timestamp() * 1000)
                bars_last = exchange_hist.fetch_ohlcv(symbol, timeframe=hist_timeframe, since=since_oggi_10, limit=hist_limit)
                df_last = pd.DataFrame(bars_last, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df_last['timestamp'] = pd.to_datetime(df_last['timestamp'], unit='ms')

            # Aggiunta della nuova riga al DataFrame DF
            if df is not None:
                df = pd.concat([df, df_last], ignore_index=True)

            return df, df_last
        except Exception as e:
            logging.error(f"Errore durante la creazione del DataFrame, (get_Df()): {str(e)}")
            print(e)
            return None


    def operation(self,symbol,saldo_symbol):
        df = None
        try:
            oggi = pd.Timestamp.utcnow().tz_localize(None).replace(minute=0, second=0, microsecond=0)

            since_datetime = datetime.strptime(self.date_start, "%Y-%m-%d %H:%M:%S")
            # Conversione in timestamp Unix (millisecondi)
            df_last=None
            df=None
            since = int(since_datetime.timestamp() * 1000)
            nome_tabella=self.tabella_storico_consolidato.format(symbol.replace('/','_'))
            df,df_last = self.get_Df(symbol,since,oggi,nome_tabella)
            self.db_atbot.salva_df(df,nome_tabella)
            if self.SAVE_CSV_HIST:
                self.save_history(df,symbol.split('/')[0])
        except Exception as e:
            print(e)
            logging.error(f"Errore nel recupero dei dati:{e}")

        try:
            if df is not None and df_last is not None:
                #df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                # Calcola gli indicatori
                if len(df) >= 50:
                    df['SMA_50'] = df.ta.sma(length=self.timeperiod_SMA50)
                else:
                    logging.error("Df non sufficientemente grande per SMA_50")
                    raise Exception("Df non sufficientemente grande per SMA_50")

                if len(df) >= 200:
                    df['SMA_200'] = df.ta.sma(length=self.timeperiod_SMA200)
                else:
                    logging.error("Df non sufficientemente grande per SMA_200")
                    raise Exception("Df non sufficientemente grande per SMA_200")

                macd = df.ta.macd(fast=self.fastperiod, slow=self.slowperiod, signal=self.signalperiod)
                df['MACD'] = macd['MACD_12_26_9']
                df['MACD_signal'] = macd['MACDs_12_26_9']
                df['RSI'] = df.ta.rsi(length=self.timeperiod_RSI)

                # Funzione per generare segnali di acquisto e vendita alternati con stop loss e take profit
                df = self.generate_signals(df)
                df3 = df[['timestamp', 'close', 'Signal']]
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
                """
                df2['balance'] = np.nan  # Inizializziamo con NaN, così possiamo calcolare il saldo per ogni riga
                df2.iloc[0, df2.columns.get_loc(
                    'balance')] = saldo_iniziale  # Impostiamo il saldo iniziale per la prima riga
    
                # Calcoliamo il saldo progressivo
                for i in range(1, len(df2)):
                    if not pd.isna(df2['result'].iloc[i]):  # Se il risultato non è NaN
                        df2['balance'].iloc[i] = df2['balance'].iloc[i - 1] * (1 + df2['result'].iloc[i] / 100)
                    else:
                        # Se il risultato è NaN, mantieni il saldo invariato
                        df2['balance'].iloc[i] = df2['balance'].iloc[i - 1]
                """
                buy_signals = df[df['Signal'] == 'BUY']
                sell_signals = df[df['Signal'] == 'SELL']

                """
                new_row = {
                    'timestamp': pd.Timestamp("2024-12-15 20:00"),
                    'open': 1,
                    'close': 1,
                    'Signal': 'BUY'
                }
                buy_signals = pd.concat([buy_signals, pd.DataFrame([new_row])], ignore_index=True)
                """

                #oggi = pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(minutes=15)

                print("Symbol:", symbol)
                print("Oggi:", oggi)
                print("Saldo:",saldo_symbol)
                df_filtrato_buy = buy_signals[buy_signals['timestamp'] == oggi][['timestamp', 'open', 'close', 'Signal']]
                df_filtrato_buy = df_filtrato_buy.sort_values(by='timestamp', ascending=False)
                df_filtrato_sell = sell_signals[sell_signals['timestamp'] == oggi][['timestamp', 'open', 'close', 'Signal']]
                df_filtrato_sell = df_filtrato_sell.sort_values(by='timestamp', ascending=False)
                pd.options.display.max_columns = None
                print(df_filtrato_buy)
                print(df_filtrato_sell)
                if df_filtrato_buy.empty and df_filtrato_sell.empty:
                    logging.info(f"Nessuna operazione effettuata per cripto {symbol}")
                    self.response_dict[symbol] = f"Nessuna operazione effettuata per cripto {symbol}"
                    #sns.sendNotify(f"Nessuna operazione effettuataper cripto {symbol}")
                print(df3)
                print(df2)  # stampa tutta la tabella con i valori BUY and SELL con saldo progressivo


                if self.COMPRO_VENDO_FLAG:
                    if not df_filtrato_buy.empty:
                        self.acquista(symbol)

                    if not df_filtrato_sell.empty:
                        self.vendi(symbol)

                if self.PLOT:
                    self.plot(df,symbol)

        except Exception as e:
            logging.error(f"Errore nella generazione dei risultati: {str(e)}")
            try:
                sns.sendNotify(f"Errore nella generazione dei risultati:{str(e)}")
            except Exception as notify_error:
                logging.error(f"Errore durante l'invio della notifica")

    def plot(self,df,symbol):
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


if __name__ == "__main__":
    logging.info("START BOT")
    date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"DateTimestamp: {date_time}")

    t = AT_Bot(config)


config={"single_shot" : True,
        "COMPRO_VENDO_FLAG":False,
        "SAVE_CSV_HIST":False,
        "PLOT":False,
        "ADJUSTMENT_SALDO":False,
        "saldo_iniziale":5000,
        "date_start":"2024-11-01 01:00:00", #in locale mettere un ora avanti rispetto ad utc desiderato
        "hist_timeframe":'1m',
        "hist_limit":1500,
        "timeperiod_SMA50":50,
        "timeperiod_SMA200":200,
        "fastperiod":12,
        "slowperiod":26,
        "signalperiod":9,
        "timeperiod_RSI":14,
        "time_sleep":21600,
        "symbol_list":['BTC/USDT', 'ETH/USDT'],
        "fees":0.95,
        "db_name":"db_atbot.db",
        "tabella_storico_consolidato":"storico_consolidato_{}",
        "peso_close": 0.0005
        }

LOG_FILE_PATH="log"

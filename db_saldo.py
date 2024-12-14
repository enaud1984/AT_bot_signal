import sqlite3


class SaldoDB:
    def __init__(self, db_name):
        self.db_name=db_name
        # Connessione al database
        with sqlite3.connect(db_name) as conn:
            cursor =conn.cursor()
            cursor.execute("""
                    CREATE TABLE IF NOT EXISTS saldo (
                        symbol TEXT PRIMARY KEY,
                        amount REAL
                    )
                    """)

    def initialize_saldo(self, symbol_list, saldo_totale):
        for symbol in symbol_list:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT amount FROM saldo WHERE symbol = ?", (symbol,))
                result = cursor.fetchone()
                if result is None:  # Se il simbolo non è nella tabella, lo inizializza
                    saldo_iniziale = saldo_totale / len(symbol_list)
                    cursor.execute("INSERT INTO saldo (symbol, amount) VALUES (?, ?)", (symbol, saldo_iniziale))

    def get_saldo(self, symbol):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT amount FROM saldo WHERE symbol = ?", (symbol,))
            result = cursor.fetchone()
        return result[0] if result else 0

    def set_saldo(self, symbol, nuovo_saldo):
        with sqlite3.connect(self.db_name) as conn:
            cursor =conn.cursor()
             cursor.execute("UPDATE saldo SET amount = ? WHERE symbol = ?", (nuovo_saldo, symbol))

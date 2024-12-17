import sqlite3


class DB_ATBot:
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

            conn.commit()

    def initialize_saldo(self, symbol_list, saldo_totale):
        for symbol in symbol_list:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT amount FROM saldo WHERE symbol = ?", (symbol,))
                result = cursor.fetchone()
                if result is None:  # Se il simbolo non è nella tabella, lo inizializza
                    saldo_iniziale = saldo_totale / len(symbol_list)
                    cursor.execute("INSERT INTO saldo (symbol, amount) VALUES (?, ?)", (symbol, saldo_iniziale))
                    conn.commit()

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
             conn.commit()

    def get_total_saldo(self):
        """Ritorna la somma totale dei saldi nel database."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(amount) FROM saldo")
            result = cursor.fetchone()
        return result[0] if result[0] else 0

    def adjust_saldo_to_total(self, total_usdt):
        """Distribuisce la differenza tra il totale calcolato e il totale sull'exchange."""
        current_total = self.get_total_saldo()
        if current_total>0:
            difference = total_usdt - current_total
            if difference > 0:  # Distribuisci solo se ci sono fondi aggiuntivi
                with sqlite3.connect(self.db_name) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT symbol, amount FROM saldo")
                    rows = cursor.fetchall()

                    if rows:
                        symbols = len(rows)
                        incremento = difference / symbols

                        for symbol, amount in rows:
                            new_amount = amount + incremento
                            cursor.execute("UPDATE saldo SET amount = ? WHERE symbol = ?", (new_amount, symbol))
                            conn.commit()

    def tabella_esiste(self, nome_tabella):
        """Controlla se la tabella esiste nel database."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (nome_tabella,))
            result = bool(cursor.fetchone())
        return result

    def get_tabella(self, nome_tabella):
        """Ritorna il contenuto della tabella."""
        if self.tabella_esiste(nome_tabella):
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT * FROM {nome_tabella}")
                rows = cursor.fetchall()
            return rows
        else:
            return None

    def salva_df(self, df, nome_tabella):
        conn=None
        try:
            conn=sqlite3.connect(self.db_name)
            """Salva un DataFrame nella tabella."""
            if self.tabella_esiste(nome_tabella):
                ultima_riga=df.iloc[[-1]]
                ultima_riga = ultima_riga.copy()
                import pandas as pd
                ultima_riga['timestamp'] = pd.to_datetime(ultima_riga['timestamp'], errors='coerce')
                ultima_riga['timestamp'] = ultima_riga['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                ultima_riga.to_sql(nome_tabella, con=conn, if_exists='append', index=False)
                print(f"Aggiunta riga {ultima_riga} a {nome_tabella}")
            else:
                df.to_sql(nome_tabella, con=conn, index=False)
                print(f"Tabella creata:{nome_tabella}")
        except Exception as e:
            print(f"Error insert/create row/table",e)
            raise e
        finally:
            if conn:
                conn.close()

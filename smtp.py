import smtplib
from email.mime.text import MIMEText

# Configura i dettagli dell'email
SMTP_SERVER = 'smtp.gmail.com'  # Server SMTP, es. Gmail
SMTP_PORT = 587                 # Porta SMTP per connessioni TLS
EMAIL = 'xxxx@gmail.com'   # La tua email
PASSWORD = 'tuapassword'        # La tua password (o una app password)

# Crea il messaggio
destinatario = 'destinatario@example.com'
oggetto = 'Oggetto del messaggio'

# Invio dell'email
def sendEmail(message):
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Avvia connessione TLS
            server.login(EMAIL, PASSWORD)  # Accedi con le tue credenziali
            msg = MIMEText(message)
            msg['From'] = EMAIL
            msg['To'] = destinatario
            msg['Subject'] = oggetto
            server.sendmail(EMAIL, destinatario, msg.as_string())  # Invia l'email
            print("Email inviata con successo!")
    except Exception as e:
        print(f"Errore durante l'invio dell'email: {e}")
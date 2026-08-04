import smtplib
from email.mime.text import MIMEText

msg = MIMEText("Teste de envio de e-mail via Outlook SMTP.", "plain", "utf-8")
msg["Subject"] = "Teste Outlook SMTP"
msg["From"] = "Contabilidade Melo <fred.discouto@hotmail.com>"
msg["To"] = "fredmourao@gmail.com"

try:
    with smtplib.SMTP("smtp-mail.outlook.com", 587, timeout=15) as server:
        server.starttls()
        print("CONECTADO AO OUTLOOK SMTP COM SUCESSO!")
except Exception as e:
    print(f"ERROR: {e}")

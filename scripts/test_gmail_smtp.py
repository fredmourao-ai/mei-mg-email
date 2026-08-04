import smtplib
from email.mime.text import MIMEText

msg = MIMEText("Teste de envio de e-mail via Gmail SMTP para MEI MG.", "plain", "utf-8")
msg["Subject"] = "Teste Gmail SMTP"
msg["From"] = "Contabilidade Melo <shopvivaliz@gmail.com>"
msg["To"] = "fredmourao@gmail.com"

try:
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login("shopvivaliz@gmail.com", "zdju qjkd lpug vpdr")
        server.send_message(msg)
    print("SUCCESS: E-mail enviado com sucesso via Gmail SMTP!")
except Exception as e:
    print(f"ERROR: {e}")

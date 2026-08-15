"""
SMTP email delivery.

"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_report_email(subject, html_body, recipient=None, sender=None, password=None,
                       smtp_host=None, smtp_port=None):
    recipient = recipient or os.environ["EMAIL_RECIPIENT"]
    sender = sender or os.environ["SMTP_USERNAME"]
    password = password or os.environ["SMTP_PASSWORD"]
    smtp_host = smtp_host or os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(smtp_port or os.environ.get("SMTP_PORT", 587))

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, [recipient], message.as_string())

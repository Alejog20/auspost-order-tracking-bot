"""
SMTP email delivery.

"""

import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# Referenced by templates/report_email.html as src="cid:report-logo".
LOGO_CONTENT_ID = "report-logo"
XLSX_SUBTYPE = "vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_SUBTYPE_ALIASES = {"jpg": "jpeg"}


def send_report_email(subject, html_body, recipient=None, sender=None, password=None,
                       smtp_host=None, smtp_port=None, logo_path=None,
                       attachment_bytes=None, attachment_filename=None):
    recipient = recipient or os.environ["EMAIL_RECIPIENT"]
    sender = sender or os.environ["SMTP_USERNAME"]
    password = password or os.environ["SMTP_PASSWORD"]
    smtp_host = smtp_host or os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(smtp_port or os.environ.get("SMTP_PORT", 587))

    # "mixed" at the top so a real downloadable attachment (e.g. the xlsx
    # export) sits alongside the email body, not nested inside the "related"
    # part meant for inline resources like the cid: logo.
    message = MIMEMultipart("mixed")
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient

    body = MIMEMultipart("related")
    body.attach(MIMEText(html_body, "html"))

    if logo_path:
        suffix = Path(logo_path).suffix.lstrip(".").lower()
        subtype = _SUBTYPE_ALIASES.get(suffix, suffix)
        with open(logo_path, "rb") as f:
            # _subtype is required here: MIMEImage falls back to the
            # stdlib `imghdr` module when it's omitted, which was removed
            # in Python 3.13.
            logo = MIMEImage(f.read(), _subtype=subtype)
        logo.add_header("Content-ID", f"<{LOGO_CONTENT_ID}>")
        logo.add_header("Content-Disposition", "inline", filename=Path(logo_path).name)
        body.attach(logo)

    message.attach(body)

    if attachment_bytes and attachment_filename:
        attachment = MIMEApplication(attachment_bytes, _subtype=XLSX_SUBTYPE)
        attachment.add_header("Content-Disposition", "attachment", filename=attachment_filename)
        message.attach(attachment)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, [recipient], message.as_string())

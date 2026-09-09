import os
import smtplib
import mimetypes
from html import escape
from email.message import EmailMessage
from datetime import datetime
from pathlib import Path
from src.services.allure_service import AllureService

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv()

class EmailService:
    def __init__(self):
        self.region = os.getenv("AWS_REGION")
        self.smtp_server = os.getenv("SMTP_SERVER")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.smtp_from = os.getenv("SMTP_FROM")
        self.smtp_recipents = os.getenv("SMTP_RECIPIENTS", "").split(",")

        if not self.smtp_server:
            raise ValueError("SMTP_SERVER environment variable is not set.")

        if not self.smtp_username:
            raise ValueError("SMTP_USERNAME environment variable is not set.")

        if not self.smtp_password:
            raise ValueError("SMTP_PASSWORD environment variable is not set.")

        if not self.smtp_from:
            raise ValueError("SMTP_FROM environment variable is not set.")

        if not self.smtp_recipents:
            raise ValueError("SMTP_RECIPIENTS environment variable is not set.")
        
    def send_email_allure(
        self, 
        subject: str, 
        body: str, 
        attachment_path: str | None = None
    ) -> bool:

        msg = EmailMessage()
        msg["To"] = self.smtp_recipents
        msg["From"] = self.smtp_from
        msg["Subject"] = os.getenv(
            "AWS_MAIL_SUBJECT",
            subject or f"teste de envio de e-mail usando smtp da AWS - {datetime.now()}",
        )
        msg.set_content(
            os.getenv(
                "AWS_MAIL_BODY",
                body or f"teste de envio de e-mail usando smtp da AWS - {datetime.now()}",
            )
        )

        if attachment_path:
            attachment = Path(attachment_path)
            if not attachment.is_absolute():
                attachment = PROJECT_ROOT / attachment

            if not attachment.is_file():
                raise FileNotFoundError(f"Attachment file not found: {attachment}")

            content_type, _ = mimetypes.guess_type(attachment.name)
            maintype, subtype = (content_type or "application/octet-stream").split(
                "/", 1
            )
            with open(attachment, "rb") as file:
                msg.add_attachment(
                    file.read(),
                    maintype=maintype,
                    subtype=subtype,
                    filename=attachment.name,
                )

        smtp_endpoint = os.getenv("SMTP_SERVER", self.smtp_server)
        smtp_port = int(os.getenv("SMTP_PORT", str(self.smtp_port)))

        try:
            with smtplib.SMTP(smtp_endpoint, smtp_port, timeout=360) as client:
                client.starttls()
                client.login(self.smtp_username, self.smtp_password)
                refused_recipients = client.send_message(msg)

            if refused_recipients:
                raise RuntimeError(
                    f"SMTP recusou destinatários: {refused_recipients}"
                )

            print("E-mail aceito pelo servidor SMTP; entrega pendente.")
            return True
        except (OSError, smtplib.SMTPException) as error:
            raise RuntimeError(f"Failed to send email: {error}") from error

    def send_email(
        self, 
        subject: str, 
        body: str, 
        html_body: str | None = None,
    ) -> bool:

        msg = EmailMessage()
        allure_service = AllureService()
        html_table = allure_service.generate_html_table()

        msg["To"] = self.smtp_recipents
        msg["From"] = self.smtp_from
        msg["Subject"] = subject

        msg.set_content(body)
        report_html = html_body or (
            "<pre style='white-space: pre-wrap; font-family: monospace;'>"
            f"{escape(body)}</pre>"
        )
        msg.add_alternative(
            report_html + html_table,
            subtype="html"
        )

        smtp_endpoint = os.getenv("SMTP_SERVER", self.smtp_server)
        smtp_port = int(os.getenv("SMTP_PORT", str(self.smtp_port)))

        try:
            with smtplib.SMTP(smtp_endpoint, smtp_port, timeout=360) as client:
                client.starttls()
                client.login(self.smtp_username, self.smtp_password)
                refused_recipients = client.send_message(msg)

            if refused_recipients:
                raise RuntimeError(
                    f"SMTP recusou destinatários: {refused_recipients}"
                )

            print("E-mail aceito pelo servidor SMTP; entrega pendente.")
            return True
        except (OSError, smtplib.SMTPException) as error:
            raise RuntimeError(f"Failed to send email: {error}") from error
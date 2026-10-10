import smtplib
import ssl
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Checks the Gmail SMTP login with both ports (587 and 465) and shows where it fails."

    def add_arguments(self, parser):
        parser.add_argument("--to", help="Email address that receives a test mail", default=None)

    def try_port(self, port, use_ssl):
        self.stdout.write(f"\nTrying {settings.EMAIL_HOST}:{port} ({'SSL' if use_ssl else 'STARTTLS'})")
        context = ssl.create_default_context()
        try:
            if use_ssl:
                server = smtplib.SMTP_SSL(settings.EMAIL_HOST, port, timeout=20, context=context)
            else:
                server = smtplib.SMTP(settings.EMAIL_HOST, port, timeout=20)
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
            server.set_debuglevel(1)
            server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            self.stdout.write(self.style.SUCCESS(f"Login OK on port {port}"))
            return server
        except smtplib.SMTPAuthenticationError as error:
            self.stdout.write(self.style.ERROR(f"Wrong email or app password: {error}"))
        except Exception as error:
            self.stdout.write(self.style.ERROR(f"{type(error).__name__}: {error}"))
        return None

    def handle(self, *args, **options):
        self.stdout.write(f"User: {settings.EMAIL_HOST_USER}")
        self.stdout.write(f"Password length: {len(settings.EMAIL_HOST_PASSWORD or '')} (Gmail app password must be 16)")
        server = self.try_port(587, False) or self.try_port(465, True)
        if server is None:
            self.stdout.write(self.style.ERROR("\nBoth ports failed. See the fix list in the answer."))
            return
        if options["to"]:
            message = f"From: {settings.EMAIL_HOST_USER}\r\nTo: {options['to']}\r\nSubject: EDU-PREDICT test\r\n\r\nSMTP works."
            server.sendmail(settings.EMAIL_HOST_USER, [options["to"]], message)
            self.stdout.write(self.style.SUCCESS(f"Test mail sent to {options['to']}"))
        server.quit()
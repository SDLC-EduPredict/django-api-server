import logging
import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone
from twilio.rest import Client
from accounts.models import OTP, User

logger = logging.getLogger(__name__)

OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 10
MAX_ATTEMPTS = 5
RESEND_SECONDS = 60


def remove_country_code(phone: str) -> str:
    phone = phone.strip()
    if phone.startswith(settings.SMS_COUNTRY_CODE):
        phone = phone[len(settings.SMS_COUNTRY_CODE):]
    return phone


def find_user(identifier: str) -> User | None:
    identifier = remove_country_code(identifier)
    return User.objects.filter(Q(email__iexact=identifier) | Q(phone=identifier), is_active=True).first()


def seconds_to_wait(user: User) -> int:
    last_otp = OTP.objects.filter(user=user).first()
    if last_otp is None:
        return 0
    seconds_passed = int((timezone.now() - last_otp.created_at).total_seconds())
    return max(RESEND_SECONDS - seconds_passed, 0)


def create_otp(user: User, channel: str) -> str:
    otp = "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))
    OTP.objects.filter(user=user).delete()
    OTP.objects.create(
        user=user,
        channel=channel,
        otp_hash=make_password(otp),
        expires_at=timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES))
    return otp


def send_sms(phone: str, message: str) -> None:
    if not settings.TWILIO_ACCOUNT_SID:
        if settings.DEBUG:
            logger.warning("Twilio is not set up. SMS to %s%s: %s", settings.SMS_COUNTRY_CODE, phone, message)
            return
        raise ImproperlyConfigured("Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER in .env")

    to_number = settings.SMS_COUNTRY_CODE + phone
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    sms = client.messages.create(to=to_number, from_=settings.TWILIO_PHONE_NUMBER, body=message)
    logger.info("Twilio accepted the SMS to %s: sid=%s status=%s", to_number, sms.sid, sms.status)


def send_otp(user: User, channel: str, otp: str) -> None:
    message = f"{otp} is your EDU-PREDICT OTP. It is valid for {OTP_EXPIRY_MINUTES} minutes. Do not share it with anyone."

    if channel == OTP.Channel.SMS:
        send_sms(user.phone, message)
    else:
        send_mail("EDU-PREDICT OTP", message, settings.DEFAULT_FROM_EMAIL, [user.email])


def verify_otp(user: User, otp: str) -> str | None:
    saved_otp = OTP.objects.filter(user=user).first()

    if saved_otp is None or saved_otp.expires_at < timezone.now() or saved_otp.attempts >= MAX_ATTEMPTS:
        return "OTP expired or not requested. Please request a new OTP."

    if not check_password(otp, saved_otp.otp_hash):
        saved_otp.attempts += 1
        saved_otp.save()
        return "Invalid OTP."
    return None
from datetime import datetime, timedelta, timezone as dt_timezone
import re
from io import StringIO
from unittest.mock import patch

import jwt
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core.management import call_command
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.forms import UserAdminCreationForm
from accounts.models import OTP, FacultyProfile, RefreshToken
from accounts.serializers import UserSerializer
from accounts.tokens import create_access_token

User = get_user_model()
PASSWORD = "Str0ng-Pass-123!"


# ----------------------------------------------------------------------------- models
class UserModelTests(TestCase):
    def test_create_user_defaults_to_student_and_lowercases_email(self) -> None:
        user = User.objects.create_user("Rahul@Example.com", "pass12345!", first_name="Rahul")
        self.assertEqual(user.email, "rahul@example.com")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertTrue(user.check_password("pass12345!"))
        self.assertFalse(user.is_staff)

    def test_create_superuser_gets_super_admin_role(self) -> None:
        user = User.objects.create_superuser("root@example.com", "pass12345!", first_name="Root")
        self.assertEqual(user.role, User.Role.SUPER_ADMIN)
        self.assertTrue(user.is_staff and user.is_superuser)

    def test_email_is_required(self) -> None:
        with self.assertRaises(ValueError):
            User.objects.create_user("", "pass12345!")

    def test_blank_phone_numbers_do_not_clash(self) -> None:
        User.objects.create_user("a@example.com", "pass12345!", first_name="A")
        User.objects.create_user("b@example.com", "pass12345!", first_name="B")
        self.assertEqual(User.objects.filter(phone__isnull=True).count(), 2)

    def test_faculty_profile_string(self) -> None:
        user = User.objects.create_user("f@example.com", "pass12345!", first_name="Fay", role=User.Role.FACULTY)
        profile = FacultyProfile.objects.create(user=user, employee_code="FAC-001")
        self.assertIn("FAC-001", str(profile))


# ----------------------------------------------------------------------------- backend
class BackendTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user("rahul@example.com", PASSWORD, first_name="Rahul", phone="9876543210")

    def test_login_with_email_phone_and_uppercase_email(self) -> None:
        for username in ("rahul@example.com", "9876543210", "RAHUL@Example.com"):
            self.assertEqual(authenticate(username=username, password=PASSWORD), self.user)

    def test_wrong_password_or_unknown_user(self) -> None:
        self.assertIsNone(authenticate(username="rahul@example.com", password="wrong"))
        self.assertIsNone(authenticate(username="nobody@example.com", password=PASSWORD))

    def test_inactive_user_cannot_login(self) -> None:
        self.user.is_active = False
        self.user.save()
        self.assertIsNone(authenticate(username="rahul@example.com", password=PASSWORD))


# ----------------------------------------------------------------------------- API
class AuthApiTests(TestCase):
    def setUp(self) -> None:
        call_command("seed_permissions", stdout=StringIO())
        self.client = APIClient()
        self.register_data = {
            "email": "rahul@example.com", "first_name": "Rahul", "last_name": "Sen", "phone": "9876543210",
            "password": PASSWORD, "confirm_password": PASSWORD,
        }

    def login(self, username="rahul@example.com", password=PASSWORD):
        return self.client.post("/api/auth/login/", {"username": username, "password": password}, format="json")

    def auth(self, token) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # ---- register
    def test_register_creates_a_student_even_if_role_is_sent(self) -> None:
        response = self.client.post("/api/auth/register/", {**self.register_data, "role": "SUPER_ADMIN"}, format="json")
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="rahul@example.com")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertFalse(user.is_staff)
        self.assertNotIn("password", response.json()["user"])

    def test_register_validation_errors(self) -> None:
        bad = {**self.register_data, "confirm_password": "different", "email": "not-an-email"}
        response = self.client.post("/api/auth/register/", bad, format="json")
        self.assertEqual(response.status_code, 400)
        errors = response.json()["errors"]
        self.assertIn("email", errors)
        self.assertIn("confirm_password", errors)

    def test_register_rejects_weak_password_and_duplicate_email(self) -> None:
        weak = {**self.register_data, "password": "12345678", "confirm_password": "12345678"}
        self.assertIn("password", self.client.post("/api/auth/register/", weak, format="json").json()["errors"])
        self.client.post("/api/auth/register/", self.register_data, format="json")
        duplicate = self.client.post("/api/auth/register/", {**self.register_data, "phone": "9000000000"}, format="json")
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("email", duplicate.json()["errors"])

    # ---- login
    def test_login_returns_both_tokens_and_permissions(self) -> None:
        self.client.post("/api/auth/register/", self.register_data, format="json")
        for username in ("rahul@example.com", "9876543210"):
            response = self.login(username)
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertTrue(body["access_token"] and body["refresh_token"])
            self.assertEqual(body["user"]["role"], "STUDENT")
            self.assertIn("ENROL_IN_COURSE", body["user"]["permissions"])
            self.assertNotIn("MANAGE_USERS", body["user"]["permissions"])

    def test_login_failures(self) -> None:
        self.client.post("/api/auth/register/", self.register_data, format="json")
        self.assertEqual(self.login(password="wrong").status_code, 401)
        self.assertEqual(self.client.post("/api/auth/login/", {}, format="json").status_code, 400)

    # ---- tokens
    def test_access_token_content_and_secret_keys_are_different(self) -> None:
        user = User.objects.create_user("t@example.com", PASSWORD, first_name="T")
        token = create_access_token(user)
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        self.assertEqual((payload["user_id"], payload["type"], payload["role"]), (str(user.id), "access", "STUDENT"))
        with self.assertRaises(jwt.InvalidSignatureError):
            jwt.decode(token, settings.JWT_REFRESH_SECRET_KEY, algorithms=["HS256"])

    def test_me_needs_a_valid_access_token(self) -> None:
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        self.auth("garbage")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_expired_access_token(self) -> None:
        user = User.objects.create_user("e@example.com", PASSWORD, first_name="E")
        past = datetime.now(dt_timezone.utc) - timedelta(minutes=30)
        token = jwt.encode(
            {"user_id": str(user.id), "role": "STUDENT", "type": "access", "jti": "x", "iat": past, "exp": past + timedelta(minutes=1)},
            settings.JWT_SECRET_KEY, algorithm="HS256",
        )
        self.auth(token)
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 401)
        self.assertIn("expired", response.json()["message"])

    def test_refresh_token_cannot_be_used_as_access_token(self) -> None:
        self.client.post("/api/auth/register/", self.register_data, format="json")
        tokens = self.login().json()
        self.auth(tokens["refresh_token"])
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_access_token_cannot_be_used_as_refresh_token(self) -> None:
        self.client.post("/api/auth/register/", self.register_data, format="json")
        tokens = self.login().json()
        response = self.client.post("/api/auth/refresh/", {"refresh_token": tokens["access_token"]}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_me_returns_profile(self) -> None:
        self.client.post("/api/auth/register/", self.register_data, format="json")
        self.auth(self.login().json()["access_token"])
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["email"], "rahul@example.com")

    # ---- refresh / logout
    def test_refresh_rotates_the_refresh_token(self) -> None:
        self.client.post("/api/auth/register/", self.register_data, format="json")
        first = self.login().json()
        response = self.client.post("/api/auth/refresh/", {"refresh_token": first["refresh_token"]}, format="json")
        self.assertEqual(response.status_code, 200)
        second = response.json()
        self.assertNotEqual(second["refresh_token"], first["refresh_token"])
        self.auth(second["access_token"])
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)
        self.client.credentials()
        reused = self.client.post("/api/auth/refresh/", {"refresh_token": first["refresh_token"]}, format="json")
        self.assertEqual(reused.status_code, 401)

    def test_logout_revokes_the_refresh_token(self) -> None:
        self.client.post("/api/auth/register/", self.register_data, format="json")
        tokens = self.login().json()
        self.auth(tokens["access_token"])
        self.assertEqual(self.client.post("/api/auth/logout/", {"refresh_token": tokens["refresh_token"]}, format="json").status_code, 200)
        self.client.credentials()
        response = self.client.post("/api/auth/refresh/", {"refresh_token": tokens["refresh_token"]}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(RefreshToken.objects.filter(revoked=False).count(), 0)

    def test_logout_requires_refresh_token(self) -> None:
        self.client.post("/api/auth/register/", self.register_data, format="json")
        self.auth(self.login().json()["access_token"])
        self.assertEqual(self.client.post("/api/auth/logout/", {}, format="json").status_code, 400)

    # ---- profile / password
    def test_patch_profile_changes_only_sent_fields(self) -> None:
        self.client.post("/api/auth/register/", self.register_data, format="json")
        self.auth(self.login().json()["access_token"])
        response = self.client.patch("/api/auth/profile/", {"first_name": "Rahul Kumar"}, format="json")
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email="rahul@example.com")
        self.assertEqual((user.first_name, user.last_name, user.phone), ("Rahul Kumar", "Sen", "9876543210"))

    def test_patch_profile_cannot_change_role_or_email(self) -> None:
        self.client.post("/api/auth/register/", self.register_data, format="json")
        self.auth(self.login().json()["access_token"])
        self.client.patch("/api/auth/profile/", {"role": "SUPER_ADMIN", "email": "x@example.com"}, format="json")
        user = User.objects.get(phone="9876543210")
        self.assertEqual((user.role, user.email), ("STUDENT", "rahul@example.com"))

    def test_change_password_revokes_refresh_tokens(self) -> None:
        self.client.post("/api/auth/register/", self.register_data, format="json")
        tokens = self.login().json()
        self.auth(tokens["access_token"])
        new = "An0ther-Pass-456!"
        response = self.client.post(
            "/api/auth/change-password/", {"old_password": PASSWORD, "password": new, "confirm_password": new}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.client.credentials()
        self.assertEqual(self.client.post("/api/auth/refresh/", {"refresh_token": tokens["refresh_token"]}, format="json").status_code, 401)
        self.assertEqual(self.login(password=PASSWORD).status_code, 401)
        self.assertEqual(self.login(password=new).status_code, 200)

    def test_change_password_wrong_old_password(self) -> None:
        self.client.post("/api/auth/register/", self.register_data, format="json")
        self.auth(self.login().json()["access_token"])
        response = self.client.post(
            "/api/auth/change-password/", {"old_password": "nope", "password": PASSWORD, "confirm_password": PASSWORD}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("old_password", response.json()["errors"])


class AdminUserApiTests(TestCase):
    def setUp(self) -> None:
        call_command("seed_permissions", stdout=StringIO())
        self.client = APIClient()
        self.super_admin = User.objects.create_superuser("admin@gmail.com", PASSWORD, first_name="Admin")
        self.admin = User.objects.create_user("manager@example.com", PASSWORD, first_name="Manager", role=User.Role.ADMIN)
        self.student = User.objects.create_user("stud@example.com", PASSWORD, first_name="Stu")

    def act_as(self, user) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {create_access_token(user)}")

    def test_only_super_admin_can_manage_users(self) -> None:
        self.act_as(self.student)
        self.assertEqual(self.client.get("/api/admin/users/").status_code, 403)
        self.act_as(self.admin)
        response = self.client.get("/api/admin/users/")
        self.assertEqual(response.status_code, 403)
        self.act_as(self.super_admin)
        self.assertEqual(self.client.get("/api/admin/users/").status_code, 200)

    def test_user_list_filters_and_pagination(self) -> None:
        self.act_as(self.super_admin)
        body = self.client.get("/api/admin/users/?role=STUDENT").json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["email"], "stud@example.com")
        self.assertEqual(self.client.get("/api/admin/users/?search=manager").json()["count"], 1)
        self.assertEqual(len(self.client.get("/api/admin/users/?page_size=2").json()["results"]), 2)

    def test_create_users_of_any_role(self) -> None:
        self.act_as(self.super_admin)
        data = {"email": "Fay@Example.com", "first_name": "Fay", "role": "FACULTY", "password": PASSWORD}
        response = self.client.post("/api/admin/users/", data, format="json")
        self.assertEqual(response.status_code, 201)
        faculty = User.objects.get(email="fay@example.com")
        self.assertEqual(faculty.role, "FACULTY")
        self.assertTrue(faculty.is_active)
        self.assertFalse(faculty.is_staff)
        sa = self.client.post("/api/admin/users/", {**data, "email": "boss@example.com", "role": "SUPER_ADMIN"}, format="json")
        self.assertEqual(sa.status_code, 201)
        self.assertTrue(User.objects.get(email="boss@example.com").is_staff)

    def test_create_user_rejects_bad_role(self) -> None:
        self.act_as(self.super_admin)
        data = {"email": "x@example.com", "first_name": "X", "role": "HACKER", "password": PASSWORD}
        response = self.client.post("/api/admin/users/", data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.json()["errors"])

    def test_change_role_and_deactivate(self) -> None:
        self.act_as(self.super_admin)
        url = f"/api/admin/users/{self.student.id}/"
        self.assertEqual(self.client.patch(url, {"role": "FACULTY"}, format="json").status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual((self.student.role, self.student.first_name), ("FACULTY", "Stu"))
        self.assertEqual(self.client.delete(url).status_code, 200)
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)
        # deactivated users cannot use an old access token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {create_access_token(self.student)}")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_super_admin_cannot_change_own_account(self) -> None:
        self.act_as(self.super_admin)
        self.assertEqual(self.client.delete(f"/api/admin/users/{self.super_admin.id}/").status_code, 400)
        self.assertEqual(self.client.patch(f"/api/admin/users/{self.super_admin.id}/", {"role": "STUDENT"}, format="json").status_code, 400)

    def test_unknown_user_is_404(self) -> None:
        self.act_as(self.super_admin)
        self.assertEqual(self.client.get("/api/admin/users/00000000-0000-0000-0000-000000000000/").status_code, 404)


class ValidationRuleTests(TestCase):
    def setUp(self) -> None:
        call_command("seed_permissions", stdout=StringIO())
        self.client = APIClient()
        self.data = {
            "email": "dion@gmail.com", "first_name": "Dion", "last_name": "Smith", "phone": "1234567890",
            "password": PASSWORD, "confirm_password": PASSWORD,
        }

    def register(self, **changes):
        data = {**self.data, **changes}
        if "password" in changes and "confirm_password" not in changes:
            data["confirm_password"] = changes["password"]
        return self.client.post("/api/auth/register/", data, format="json")

    def test_the_exact_request_from_postman_is_accepted_without_a_token(self) -> None:
        self.assertEqual(self.register().status_code, 201)         # no Authorization header: registration is public

    def test_password_rules(self) -> None:
        bad_passwords = {
            "qwe": ["at least 6", "uppercase", "special"],
            "abcdef": ["uppercase", "special"],
            "ABCDEF!1": ["lowercase"],
            "Abcdef1": ["special"],
            "Ab@1x": ["at least 6"],
            "Abc def": ["special"],            # a space is not a special character
        }
        for password, expected_parts in bad_passwords.items():
            with self.subTest(password=password):
                response = self.register(password=password)
                self.assertEqual(response.status_code, 400)
                messages = " ".join(response.json()["errors"]["password"])
                for part in expected_parts:
                    self.assertIn(part, messages)

    def test_good_passwords(self) -> None:
        for index, password in enumerate(["Abc@12", "aA#bcd", "Zz!zzz9", "Hello_World"]):
            with self.subTest(password=password):
                response = self.register(password=password, email=f"user{index}@gmail.com", phone=f"98000000{index:02d}")
                self.assertEqual(response.status_code, 201, response.json())

    def test_phone_rules(self) -> None:
        for phone in ["123456789", "12345678901", "98765abcde", "+919876543210", "98765 43210", "98765-43210", "98765.43210", "(987)6543210"]:
            with self.subTest(phone=phone):
                response = self.register(phone=phone)
                self.assertEqual(response.status_code, 400)
                self.assertIn("phone", response.json()["errors"])

    def test_phone_is_optional_but_unique(self) -> None:
        self.assertEqual(self.register(phone="").status_code, 201)
        self.assertEqual(self.register(phone="", email="second@gmail.com").status_code, 201)     # two users without a phone are fine
        self.assertEqual(self.register(email="third@gmail.com").status_code, 201)                # phone 1234567890
        duplicate = self.register(email="fourth@gmail.com")
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("phone", duplicate.json()["errors"])

    def test_name_rules(self) -> None:
        for first_name in ["R2D2", "Rahul!", "Ra$hul", "  ", "123"]:
            with self.subTest(first_name=first_name):
                self.assertIn("first_name", self.register(first_name=first_name).json()["errors"])
        for index, first_name in enumerate(["Mary-Ann", "O'Brien", "J. K", "Rahul Kumar", "Ananya"]):
            with self.subTest(first_name=first_name):
                response = self.register(first_name=first_name, email=f"n{index}@gmail.com", phone=f"97000000{index:02d}")
                self.assertEqual(response.status_code, 201, response.json())

    def test_email_rules(self) -> None:
        for email in ["not-an-email", "a@b", "@gmail.com", "dion@", "di on@gmail.com", ""]:
            with self.subTest(email=email):
                self.assertIn("email", self.register(email=email).json()["errors"])

    def test_email_is_saved_in_lower_case_and_duplicates_ignore_case(self) -> None:
        self.assertEqual(self.register(email="Dion@GMAIL.com").status_code, 201)
        self.assertTrue(User.objects.filter(email="dion@gmail.com").exists())
        duplicate = self.register(email="DION@gmail.com", phone="9999999999")
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("email", duplicate.json()["errors"])

    def test_same_rules_in_the_django_admin_site_form(self) -> None:
        base = {"email": "Dion@gmail.com", "first_name": "Dion", "last_name": "", "phone": "1234567890", "role": "STUDENT"}
        weak = UserAdminCreationForm({**base, "password1": "qwe", "password2": "qwe"})
        self.assertFalse(weak.is_valid())
        self.assertIn("password2", weak.errors)
        bad_phone = UserAdminCreationForm({**base, "phone": "98765abcde", "password1": PASSWORD, "password2": PASSWORD})
        self.assertIn("phone", bad_phone.errors)
        User.objects.create_user("dion@gmail.com", PASSWORD, first_name="Dion")
        duplicate = UserAdminCreationForm({**base, "password1": PASSWORD, "password2": PASSWORD})
        self.assertIn("email", duplicate.errors)         # Dion@gmail.com is the same as dion@gmail.com

    def test_same_rules_in_the_admin_panel_api_and_change_password(self) -> None:
        super_admin = User.objects.create_superuser("admin@gmail.com", PASSWORD, first_name="Admin")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {create_access_token(super_admin)}")
        response = self.client.post("/api/admin/users/", {"email": "fay@gmail.com", "first_name": "Fay", "phone": "12345", "role": "FACULTY", "password": "qwe"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("phone", response.json()["errors"])
        self.assertIn("password", response.json()["errors"])
        response = self.client.post("/api/auth/change-password/", {"old_password": PASSWORD, "password": "qwe", "confirm_password": "qwe"}, format="json")
        self.assertIn("password", response.json()["errors"])

    def test_user_serializer_never_sends_the_password(self) -> None:
        user = User.objects.create_user("s@gmail.com", PASSWORD, first_name="S")
        data = UserSerializer(user).data
        self.assertNotIn("password", data)
        self.assertNotIn("is_superuser", data)
        self.assertEqual(data["email"], "s@gmail.com")


TWILIO = {"TWILIO_ACCOUNT_SID": "ACtest", "TWILIO_AUTH_TOKEN": "token", "TWILIO_PHONE_NUMBER": "+15005550006"}


class ForgotPasswordTests(TestCase):
    def setUp(self) -> None:
        call_command("seed_permissions", stdout=StringIO())
        self.client = APIClient()
        self.user = User.objects.create_user("rahul@gmail.com", PASSWORD, first_name="Rahul", phone="9876543210")
        no_wait = patch("accounts.otp.RESEND_SECONDS", 0)
        no_wait.start()
        self.addCleanup(no_wait.stop)

    def forgot(self, username="rahul@gmail.com"):
        return self.client.post("/api/auth/forgot-password/", {"username": username}, format="json")

    def verify_phone(self, otp, phone="+919876543210"):
        return self.client.post("/api/auth/verify-phone-otp/", {"phone": phone, "otp": otp}, format="json")

    def verify_email(self, otp, email="rahul@gmail.com"):
        return self.client.post("/api/auth/verify-email-otp/", {"email": email, "otp": otp}, format="json")

    def reset(self, otp, password="New-Pass@456", username="rahul@gmail.com", confirm=None):
        data = {"username": username, "otp": otp, "password": password, "confirm_password": confirm or password}
        return self.client.post("/api/auth/reset-password/", data, format="json")

    def email_otp(self) -> str:
        return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)

    def wrong_otp(self, real_otp: str) -> str:
        return "000000" if real_otp != "000000" else "111111"

    def test_otp_is_sent_by_email_with_send_mail(self) -> None:
        self.assertEqual(self.forgot().status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["rahul@gmail.com"])
        saved = OTP.objects.get(user=self.user)
        self.assertEqual(saved.channel, "EMAIL")
        self.assertNotEqual(saved.otp_hash, self.email_otp())

    @override_settings(**TWILIO)
    def test_otp_is_sent_by_sms_with_twilio(self) -> None:
        with patch("accounts.otp.Client") as client_class:
            response = self.forgot("9876543210")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        client_class.assert_called_once_with("ACtest", "token")
        sent = client_class.return_value.messages.create.call_args.kwargs
        self.assertEqual((sent["to"], sent["from_"]), ("+919876543210", "+15005550006"))
        self.assertEqual(len(re.search(r"\b(\d{6})\b", sent["body"]).group(1)), 6)
        self.assertEqual(OTP.objects.get().channel, "SMS")

    @override_settings(**TWILIO)
    def test_phone_with_country_code_is_accepted(self) -> None:
        with patch("accounts.otp.Client") as client_class:
            self.assertEqual(self.forgot("+919876543210").status_code, 200)
        self.assertEqual(client_class.return_value.messages.create.call_count, 1)

    @override_settings(DEBUG=True)
    def test_without_twilio_keys_the_sms_is_only_logged_while_developing(self) -> None:
        with self.assertLogs("accounts.otp", level="WARNING") as logs:
            self.assertEqual(self.forgot("9876543210").status_code, 200)
        self.assertIn("+919876543210", logs.output[0])

    def test_without_twilio_keys_sms_fails_outside_development(self) -> None:
        response = self.forgot("9876543210")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(OTP.objects.count(), 0)

    def test_email_failure_returns_503_and_removes_the_otp(self) -> None:
        with patch("accounts.otp.send_mail", side_effect=OSError("smtp down")):
            response = self.forgot()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(OTP.objects.count(), 0)

    def test_unknown_and_deactivated_users_get_the_same_answer_and_nothing_is_sent(self) -> None:
        self.user.is_active = False
        self.user.save()
        deactivated = self.forgot()
        unknown = self.forgot("nobody@gmail.com")
        self.assertEqual(deactivated.status_code, 200)
        self.assertEqual(deactivated.json(), unknown.json())
        self.assertEqual((len(mail.outbox), OTP.objects.count()), (0, 0))

    def test_resend_is_limited(self) -> None:
        with patch("accounts.otp.RESEND_SECONDS", 60):
            self.assertEqual(self.forgot().status_code, 200)
            second = self.forgot()
        self.assertEqual(second.status_code, 429)
        self.assertIn("wait", second.json()["message"])
        self.assertEqual(len(mail.outbox), 1)

    def test_forgot_password_needs_a_username(self) -> None:
        self.assertEqual(self.client.post("/api/auth/forgot-password/", {}, format="json").status_code, 400)

    def test_verify_email_otp(self) -> None:
        self.forgot()
        otp = self.email_otp()
        self.assertEqual(self.verify_email(self.wrong_otp(otp)).status_code, 400)
        self.assertEqual(self.verify_email(otp).status_code, 200)
        self.assertEqual(self.verify_email(otp, email="nobody@gmail.com").status_code, 400)

    @override_settings(**TWILIO)
    def test_verify_phone_otp_with_and_without_country_code(self) -> None:
        with patch("accounts.otp.Client") as client_class:
            self.forgot("9876543210")
        body = client_class.return_value.messages.create.call_args.kwargs["body"]
        otp = re.search(r"\b(\d{6})\b", body).group(1)
        self.assertEqual(self.verify_phone(self.wrong_otp(otp)).status_code, 400)
        self.assertEqual(self.verify_phone(otp, "+919876543210").status_code, 200)
        self.assertEqual(self.verify_phone(otp, "9876543210").status_code, 200)

    def test_verify_phone_otp_validation(self) -> None:
        self.assertIn("phone", self.verify_phone("123456", phone="98765abcde").json()["errors"])
        self.assertIn("phone", self.verify_phone("123456", phone="12345").json()["errors"])
        self.assertIn("otp", self.verify_phone("12ab56").json()["errors"])
        self.assertIn("otp", self.verify_phone("12345").json()["errors"])
        self.assertEqual(self.client.post("/api/auth/verify-phone-otp/", {}, format="json").status_code, 400)

    def test_otp_stops_working_after_five_wrong_attempts(self) -> None:
        self.forgot()
        otp = self.email_otp()
        for _ in range(5):
            self.assertEqual(self.verify_email(self.wrong_otp(otp)).status_code, 400)
        self.assertEqual(self.verify_email(otp).status_code, 400)
        self.assertEqual(self.forgot().status_code, 200)
        self.assertEqual(self.verify_email(self.email_otp()).status_code, 200)

    def test_new_otp_replaces_the_old_one(self) -> None:
        self.forgot()
        self.forgot()
        self.assertEqual(OTP.objects.filter(user=self.user).count(), 1)

    def test_expired_otp(self) -> None:
        self.forgot()
        otp = self.email_otp()
        OTP.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        response = self.verify_email(otp)
        self.assertEqual(response.status_code, 400)
        self.assertIn("expired", response.json()["message"])

    def test_reset_password_with_otp(self) -> None:
        tokens = self.client.post("/api/auth/login/", {"username": "rahul@gmail.com", "password": PASSWORD}, format="json").json()
        self.forgot()
        otp = self.email_otp()
        self.assertEqual(self.reset(otp).status_code, 200)
        self.assertEqual(OTP.objects.count(), 0)
        old_login = self.client.post("/api/auth/login/", {"username": "rahul@gmail.com", "password": PASSWORD}, format="json")
        new_login = self.client.post("/api/auth/login/", {"username": "rahul@gmail.com", "password": "New-Pass@456"}, format="json")
        self.assertEqual((old_login.status_code, new_login.status_code), (401, 200))
        refresh = self.client.post("/api/auth/refresh/", {"refresh_token": tokens["refresh_token"]}, format="json")
        self.assertEqual(refresh.status_code, 401)
        self.assertEqual(self.reset(otp, password="Third-Pass@789").status_code, 400)

    def test_reset_with_phone_number_as_username(self) -> None:
        self.forgot()
        self.assertEqual(self.reset(self.email_otp(), username="+919876543210").status_code, 200)

    def test_wrong_otp_does_not_reset_the_password(self) -> None:
        self.forgot()
        response = self.reset(self.wrong_otp(self.email_otp()))
        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.get(pk=self.user.pk).check_password(PASSWORD))

    def test_weak_password_does_not_use_up_the_otp(self) -> None:
        self.forgot()
        otp = self.email_otp()
        response = self.reset(otp, password="qwe")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json()["errors"])
        self.assertEqual(self.reset(otp).status_code, 200)

    def test_reset_validation_and_unknown_user(self) -> None:
        self.assertEqual(self.reset("12345").status_code, 400)
        self.assertEqual(self.reset("123456", confirm="Different@1").status_code, 400)
        unknown = self.reset("123456", username="nobody@gmail.com")
        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(unknown.json()["message"], "Invalid OTP.")


class ChangePasswordTests(TestCase):
    def setUp(self) -> None:
        call_command("seed_permissions", stdout=StringIO())
        self.client = APIClient()
        self.user = User.objects.create_user("rahul@gmail.com", PASSWORD, first_name="Rahul")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {create_access_token(self.user)}")

    def change(self, **changes):
        data = {"old_password": PASSWORD, "password": "New-Pass@456", "confirm_password": "New-Pass@456", **changes}
        return self.client.post("/api/auth/change-password/", data, format="json")

    def test_password_is_changed(self) -> None:
        self.assertEqual(self.change().status_code, 200)
        self.assertTrue(User.objects.get(pk=self.user.pk).check_password("New-Pass@456"))

    def test_requires_login(self) -> None:
        self.client.credentials()
        self.assertEqual(self.change().status_code, 401)

    def test_wrong_old_password(self) -> None:
        response = self.change(old_password="Wrong@123")
        self.assertEqual(response.status_code, 400)
        self.assertIn("old_password", response.json()["errors"])

    def test_new_password_follows_the_password_rules(self) -> None:
        for password in ["qwe", "abcdefg1", "ABCDEFG1!", "Abcdefg1"]:
            with self.subTest(password=password):
                response = self.change(password=password, confirm_password=password)
                self.assertEqual(response.status_code, 400)
                self.assertIn("password", response.json()["errors"])

    def test_confirm_password_must_match(self) -> None:
        self.assertIn("confirm_password", self.change(confirm_password="Different@1").json()["errors"])
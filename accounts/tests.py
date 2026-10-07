from datetime import datetime, timedelta, timezone
from io import StringIO

import jwt
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import FacultyProfile, RefreshToken
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
        past = datetime.now(timezone.utc) - timedelta(minutes=30)
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
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from accounts.tokens import create_access_token
from permissions.constants import ADD_COURSE, PERMISSION_DESCRIPTIONS, ROLE_PERMISSIONS
from permissions.models import Permission, RolePermission
from permissions.utils import get_permission_names

PASSWORD = "Str0ng-Pass-123!"


class SeedTests(TestCase):
    def test_seed_creates_everything_and_is_repeatable(self) -> None:
        call_command("seed_permissions", stdout=StringIO())
        count = RolePermission.objects.count()
        self.assertEqual(Permission.objects.count(), len(PERMISSION_DESCRIPTIONS))
        call_command("seed_permissions", stdout=StringIO())
        self.assertEqual(RolePermission.objects.count(), count)

    def test_every_role_permission_is_a_known_permission(self) -> None:
        for names in ROLE_PERMISSIONS.values():
            for name in names:
                self.assertIn(name, PERMISSION_DESCRIPTIONS)

    def test_report_rules(self) -> None:
        call_command("seed_permissions", stdout=StringIO())
        self.assertNotIn("MANAGE_USERS", get_permission_names("ADMIN"))
        self.assertIn("MANAGE_USERS", get_permission_names("SUPER_ADMIN"))
        self.assertIn("VIEW_OWN_PREDICTION", get_permission_names("STUDENT"))
        self.assertNotIn("VIEW_PREDICTIONS", get_permission_names("STUDENT"))
        self.assertIn("ENTER_MARKS", get_permission_names("FACULTY"))
        self.assertNotIn(ADD_COURSE, get_permission_names("FACULTY"))


class PermissionApiTests(TestCase):
    def setUp(self) -> None:
        call_command("seed_permissions", stdout=StringIO())
        self.client = APIClient()
        self.super_admin = User.objects.create_superuser("admin@gmail.com", PASSWORD, first_name="Admin")
        self.admin = User.objects.create_user("manager@example.com", PASSWORD, first_name="M", role=User.Role.ADMIN)

    def act_as(self, user) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {create_access_token(user)}")

    def test_only_super_admin_sees_permissions(self) -> None:
        self.act_as(self.admin)
        self.assertEqual(self.client.get("/api/admin/permissions/").status_code, 403)
        self.act_as(self.super_admin)
        body = self.client.get("/api/admin/permissions/").json()
        self.assertEqual(len(body["permissions"]), len(PERMISSION_DESCRIPTIONS))
        self.assertEqual(set(body["roles"]), {"STUDENT", "FACULTY", "ADMIN", "SUPER_ADMIN"})

    def test_replace_role_permissions_changes_what_the_role_can_do(self) -> None:
        self.act_as(self.super_admin)
        url = "/api/admin/roles/FACULTY/permissions/"
        response = self.client.put(url, {"permissions": ["VIEW_STUDENTS", "ADD_COURSE"]}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_permission_names("FACULTY"), ["ADD_COURSE", "VIEW_STUDENTS"])
        self.assertEqual(self.client.get(url).json()["permissions"], ["ADD_COURSE", "VIEW_STUDENTS"])

        faculty = User.objects.create_user("fay@example.com", PASSWORD, first_name="Fay", role=User.Role.FACULTY)
        self.act_as(faculty)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 403)    # VIEW_OWN_PROFILE was removed

    def test_unknown_permission_name_is_rejected(self) -> None:
        self.act_as(self.super_admin)
        response = self.client.put("/api/admin/roles/FACULTY/permissions/", {"permissions": ["FLY_PLANE"]}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_unknown_role_and_super_admin_role(self) -> None:
        self.act_as(self.super_admin)
        self.assertEqual(self.client.get("/api/admin/roles/HACKER/permissions/").status_code, 404)
        response = self.client.put("/api/admin/roles/SUPER_ADMIN/permissions/", {"permissions": []}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_super_admin_keeps_access_even_without_role_permission_rows(self) -> None:
        RolePermission.objects.all().delete()
        self.act_as(self.super_admin)
        self.assertEqual(self.client.get("/api/admin/users/").status_code, 200)

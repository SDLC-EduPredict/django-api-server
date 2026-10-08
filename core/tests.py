from django.test import TestCase
from django.urls import reverse
from core.constants import MODULES


class PageTests(TestCase):
    def test_home_page_renders(self) -> None:
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "EDU-PREDICT")

    def test_every_module_page_renders_and_is_linked_from_base(self) -> None:
        home = self.client.get(reverse("core:home"))
        for module in MODULES:
            url = reverse(f"{module['key']}:index")
            self.assertContains(home, f'href="{url}"')
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, module["label"])
            self.assertContains(response, 'href="/"')

    def test_bootstrap_and_script_are_loaded(self) -> None:
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "bootstrap@5.3.3")
        self.assertContains(response, "js/script.js")
        self.assertNotContains(response, "<script>")

    def test_health_endpoint(self) -> None:
        response = self.client.get(reverse("core:health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["database"], "up")

    def test_health_endpoint_rejects_post(self) -> None:
        response = self.client.post(reverse("core:health"))
        self.assertEqual(response.status_code, 405)

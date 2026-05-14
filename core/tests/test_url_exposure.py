import importlib

import energystats.urls as project_urls
from django.test import SimpleTestCase, override_settings
from django.urls import Resolver404, clear_url_caches, resolve


class UrlExposureTests(SimpleTestCase):
    def tearDown(self):
        clear_url_caches()
        super().tearDown()

    def _reload_project_urls(self):
        importlib.reload(project_urls)
        clear_url_caches()

    @override_settings(ENABLE_ADMIN=False)
    def test_admin_route_not_exposed_when_admin_disabled(self):
        self._reload_project_urls()
        match = resolve("/")
        self.assertEqual(match.url_name, "index")

        with self.assertRaises(Resolver404):
            resolve("/admin/")

    @override_settings(ENABLE_ADMIN=True)
    def test_admin_route_exposed_when_admin_enabled(self):
        self._reload_project_urls()
        match = resolve("/admin/")
        self.assertEqual(match.app_name, "admin")

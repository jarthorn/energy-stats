from django.test import SimpleTestCase


class RobotsTxtTests(SimpleTestCase):
    def test_robots_txt_is_served_with_expected_directives(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")

        body = response.content.decode("utf-8")
        self.assertIn("User-agent: *", body)
        self.assertIn("Disallow: /", body)
        self.assertIn("Allow: /$", body)
        self.assertIn("Allow: /about/", body)
        self.assertIn("Allow: /countries/", body)
        self.assertIn("Allow: /fuels/", body)
        self.assertIn("Allow: /tracker/", body)
        self.assertIn("Allow: /records/", body)

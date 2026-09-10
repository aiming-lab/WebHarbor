from __future__ import annotations

import sys
import unittest
from pathlib import Path


VERIFY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VERIFY_DIR))

from verify_lib import (  # noqa: E402
    final_url_is_path,
    is_ikea_site_url,
    navigated_to_path,
    trajectory_input_contains,
    trajectory_last_email,
    trajectory_task_matches,
)


class VerifyLibTrajectoryTests(unittest.TestCase):
    def test_loopback_origins_and_configured_ports_are_allowed(self) -> None:
        for url in (
            "http://localhost:40016/product/IK-10001",
            "http://127.0.0.1:8791/product/IK-10001?from=search",
            "http://[::1]:40016/product/IK-10001",
        ):
            with self.subTest(url=url):
                self.assertTrue(is_ikea_site_url(url))
                self.assertTrue(
                    navigated_to_path(
                        {"steps": [{"url": url}]}, "/product/IK-10001"
                    )
                )

    def test_external_bare_and_non_http_urls_are_rejected(self) -> None:
        for url in (
            "https://example.com/product/IK-10001",
            "/product/IK-10001",
            "file:///product/IK-10001",
            "javascript://localhost/product/IK-10001",
        ):
            with self.subTest(url=url):
                self.assertFalse(is_ikea_site_url(url))
                self.assertFalse(
                    navigated_to_path(
                        {"steps": [{"url": url}]}, "/product/IK-10001"
                    )
                )

    def test_final_url_requires_an_on_site_origin(self) -> None:
        self.assertTrue(
            final_url_is_path(
                {"final_url": "http://localhost:40016/checkout/review?step=4"},
                "/checkout/review",
            )
        )
        self.assertFalse(
            final_url_is_path(
                {"final_url": "https://example.com/checkout/review"},
                "/checkout/review",
            )
        )

    def test_account_email_must_come_from_an_input_action(self) -> None:
        email = "alice.j@test.com"
        self.assertTrue(
            trajectory_input_contains(
                {
                    "steps": [
                        {
                            "action": "input",
                            "params": {"text": "Alice.J@Test.com"},
                        }
                    ]
                },
                email,
            )
        )
        self.assertFalse(
            trajectory_input_contains(
                {"steps": [{"action": "done", "params": {"text": email}}]},
                email,
            )
        )
        self.assertEqual(
            trajectory_last_email(
                {
                    "steps": [
                        {"action": "input", "params": {"text": email}},
                        {"action": "input", "params": {"text": "bob.c@test.com"}},
                    ]
                }
            ),
            "bob.c@test.com",
        )

    def test_task_id_must_match_exactly(self) -> None:
        self.assertTrue(trajectory_task_matches({"task_id": "IKEA--8"}, "IKEA--8"))
        self.assertFalse(trajectory_task_matches({"task_id": "IKEA--7"}, "IKEA--8"))
        self.assertFalse(trajectory_task_matches({}, "IKEA--8"))


if __name__ == "__main__":
    unittest.main()
